import asyncio
import logging

from polyswarmartifact import ArtifactType, DecodeError

from polyswarmclient import Client
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.events import VoteOnBounty, SettleBounty, WithdrawStake
from polyswarmclient.exceptions import LowBalanceError, FatalError
from polyswarmclient.utils import asyncio_stop

logger = logging.getLogger(__name__)  # Initialize logger


class AbstractArbiter(object):
    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None):
        self.client = client
        self.chains = chains
        self.scanner = scanner

        if artifact_types is None:
            self.valid_artifact_types = [ArtifactType.FILE]
        else:
            self.valid_artifact_types = artifact_types

        self.client.on_run.register(self.__handle_run)
        self.client.on_stop.register(self.__handle_stop)
        self.client.on_new_bounty.register(self.__handle_new_bounty)
        self.client.on_deprecated.register(self.__handle_deprecated)
        self.client.on_vote_on_bounty_due.register(self.__handle_vote_on_bounty_due)
        self.client.on_settle_bounty_due.register(self.__handle_settle_bounty)
        self.client.on_withdraw_stake_due.register(self.__handle_withdraw_stake_due)

        self.testing = testing
        self.bounties_seen = 0
        self.votes_posted = 0
        self.settles_posted = 0

    @classmethod
    def connect(cls, polyswarmd_addr, keyfile, password, api_key=None, testing=0, scanner=None, chains=None,
                artifact_types=None):
        """Connect the Arbiter to a Client.

        Args:
            polyswarmd_addr (str): URL of polyswarmd you are referring to.
            keyfile (str): Keyfile filename.
            password (str): Password associated with Keyfile.
            api_key (str): Your PolySwarm API key.
            testing (int): Number of testing bounties to use.
            scanner (AbstractScanner): Scanner for scanning artifacts
            chains (set(str)):  Set of chains you are acting on.
            artifact_types (list(ArtifactType)): List of artifact types you support

        Returns:
            AbstractArbiter: Arbiter instantiated with a Client.
        """
        client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0)
        return cls(client, testing, scanner, chains, artifact_types)

    async def scan(self, guid, artifact_type, content, metadata, chain):
        """Override this to implement custom scanning logic

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to be scan
            metadata (dict) Dict of metadata for the artifact
            chain (str): Chain we are operating on
        Returns:
            ScanResult: Result of this scan
        """
        if self.scanner:
            return await self.scanner.scan(guid, artifact_type, content, metadata, chain)

        raise NotImplementedError('You must subclass this class and override this method.')

    async def fetch_and_scan_all(self, guid, artifact_type, uri, duration, metadata, chain):
        """Fetch and scan all artifacts concurrently

        Args:
            guid (str): GUID of the associated bounty
            artifact_type (ArtifactType): Artifact type for the associated bounty
            uri (str):  Base artifact URI
            duration (int): Max number of blocks to take
            metadata (list[dict]) List of metadata json blobs for artifacts
            chain (str): Chain we are operating on

        Returns:
            (list(ScanResult)): Tuple of mask bits, verdicts, and metadatas
        """

        async def fetch_and_scan(index):
            content = await self.client.get_artifact(uri, index)
            if content is not None:
                # Ignoring metadata for now
                try:
                    return await self.scan(guid, artifact_type, artifact_type.decode_content(content), None, chain)
                except DecodeError:
                    return ScanResult()

            return ScanResult()

        artifacts = await self.client.list_artifacts(uri)
        return await asyncio.gather(*[fetch_and_scan(i) for i in range(len(artifacts))])

    def run(self):
        """
        Run the Client on the Arbiter's chains.
        """
        self.client.run(self.chains)

    async def __handle_run(self, chain):
        """
        If the Client's current balance is less than the minimum stake
        then deposit the difference between the two to the given chain.

        Args:
            chain (str): Chain we are operating on.
        """

        await self.client.balances.get_nct_balance(chain)
        min_stake = await self.client.staking.parameters[chain].get('minimum_stake')
        staking_balance = await self.client.staking.get_total_balance(chain)
        if staking_balance < min_stake:
            try:
                await self.deposit_stake(min_stake - staking_balance, chain)
            except LowBalanceError as e:
                raise FatalError(f'Failed to stake {min_stake - staking_balance} nct due to low balance', 1) from e

        if self.scanner is not None and not await self.scanner.setup():
            raise FatalError('Scanner setup failed', 1)

    async def __handle_stop(self):
        if self.scanner is not None:
            await self.scanner.teardown()

    async def deposit_stake(self, nct, chain):
        await self.client.balances.raise_for_low_balance(nct, chain)
        deposits = await self.client.staking.post_deposit(nct, chain)
        logger.info('Depositing stake: %s', deposits)

    async def __handle_deprecated(self, rollover, block_number, txhash, chain):
        """Schedule Withdraw stake for when the last settles are due

        Args:
            rollover (bool): Is arbiter staking being rolled over?
            block_number (int): Block number the bounty was posted on
            txhash (str): Transaction hash which caused the event
            chain (str): Is this on the home or side chain?
        Returns: Empty list
        """
        # Settle all bounties on contract
        asyncio.get_event_loop().create_task(self.client.bounties.settle_all_bounties(chain))
        # Withdraw stake, if needed
        if not rollover:
            logger.critical('BountyRegistry contract is now deprecated, withdrawing stake.')
            parameters = self.client.bounties.parameters[chain]
            assertion_reveal_window = await parameters.get('assertion_reveal_window')
            arbiter_vote_window = await parameters.get('arbiter_vote_window')
            max_duration = await parameters.get('max_duration')
            withdraw_start = block_number + max_duration + assertion_reveal_window + arbiter_vote_window
            staking_balance = await self.client.staking.get_total_balance(chain)
            ws = WithdrawStake(staking_balance)
            self.client.schedule(withdraw_start, ws, chain)
        else:
            logger.critical('BountyRegistry contract is now deprecated, but stake will rollover to the new contract')

        return []

    async def __handle_new_bounty(self, guid, artifact_type, author, amount, uri, expiration, metadata, block_number, txhash, chain):
        """Scan and assert on a posted bounty

        Args:
            guid (str): The bounty to assert on
            artifact_type (ArtifactType): The type of artifacts in this bounty
            author (str): The bounty author
            amount (str): Amount of the bounty in base NCT units (10 ^ -18)
            uri (str): IPFS hash of the root artifact
            expiration (str): Block number of the bounty's expiration
            metadata (dict): Dictionary of metadata or None
            block_number (int): Block number the bounty was posted on
            txhash (str): Transaction hash which caused the event
            chain (str): Is this on the home or side chain?
        Returns:
            Response JSON parsed from polyswarmd containing placed assertions
        """
        # Skip bounties for types we don't support
        if artifact_type not in self.valid_artifact_types:
            return []

        self.bounties_seen += 1
        if self.testing > 0:
            if self.bounties_seen > self.testing:
                logger.info('Received new bounty, but finished with testing mode')
                return []
            logger.info('Testing mode, %s bounties remaining', self.testing - self.bounties_seen)

        expiration = int(expiration)
        assertion_reveal_window = await self.client.bounties.parameters[chain].get('assertion_reveal_window')
        arbiter_vote_window = await self.client.bounties.parameters[chain].get('arbiter_vote_window')

        vote_start = expiration + assertion_reveal_window
        settle_start = expiration + assertion_reveal_window + arbiter_vote_window
        duration = settle_start - block_number

        await self.client.liveness_recorder.add_waiting_task(guid, block_number)
        results = await self.fetch_and_scan_all(guid, artifact_type, uri, duration, metadata, chain)
        votes = [result.verdict for result in results]

        if any((not result.bit for result in results)):
            return []

        bloom_parts = await self.client.bounties.get_bloom(guid, chain)
        bounty_bloom = 0
        for b in bloom_parts:
            bounty_bloom = bounty_bloom << 256 | int(b)

        calculated_bloom = await self.client.bounties.calculate_bloom(uri)
        valid_bloom = bounty_bloom == calculated_bloom

        vb = VoteOnBounty(guid, votes, valid_bloom)
        self.client.schedule(vote_start, vb, chain)

        sb = SettleBounty(guid)
        self.client.schedule(settle_start, sb, chain)

        return []

    async def __handle_vote_on_bounty_due(self, bounty_guid, votes, valid_bloom, chain):
        """
        Submit votes on a given bounty GUID to a given chain.

        Args:
            bounty_guid (str): The bounty which we are voting on.
            votes (List[bool]): Vote (malicious/benign) for each of the artifacts in the bounty.
            valid_bloom (bool):  Is the bloom filter reported by the bounty poster valid?
            chain (str): Which chain to operate on.
        Returns:
            Response JSON parsed from polyswarmd containing emitted events.
        """
        self.votes_posted += 1
        if self.testing > 0:
            if self.votes_posted > self.testing:
                logger.warning('Scheduled vote, but finished with testing mode')
                return []
            logger.info('Testing mode, %s votes remaining', self.testing - self.votes_posted)
        response = await self.client.bounties.post_vote(bounty_guid, votes, valid_bloom, chain)
        await self.client.liveness_recorder.remove_waiting_task(bounty_guid)
        return response

    async def __handle_settle_bounty(self, bounty_guid, chain):
        """
        Settle the given bounty on the given chain.

        Args:
            bounty_guid (str): The bounty which we are settling.
            chain (str): Which chain to operate on.
        Returns:
            Response JSON parsed from polyswarmd containing emitted events.
        """
        self.settles_posted += 1
        if self.testing > 0:
            if self.settles_posted > self.testing:
                logger.warning('Scheduled settle, but finished with testing mode')
                return []
            logger.info('Testing mode, %s settles remaining', self.testing - self.settles_posted)

        ret = await self.client.bounties.settle_bounty(bounty_guid, chain)
        if 0 < self.testing <= self.settles_posted:
            logger.info('All testing bounties complete, exiting')
            asyncio_stop()
        return ret

    async def __handle_withdraw_stake_due(self, amount, chain):
        """
        Withdraw given amount from the stake on the given chain

        Args:
            amount (int): Amount to withdraw
            chain (str): Which chain to operate on.

        Returns:
            Response JSON parsed from polyswarmd containing emitted events.
        """
        logger.info('No more in-progress bounties. Withdrawing %s', amount)
        return await self.client.staking.post_withdraw(amount, chain)
