import asyncio
import logging

from polyswarmclient import Client
from polyswarmclient.bloom import BloomFilter
from polyswarmclient.events import VoteOnBounty, SettleBounty

logger = logging.getLogger(__name__)  # Initialize logger
MAX_STAKE_RETRIES = 10


class AbstractArbiter(object):
    def __init__(self, client, testing=0, scanner=None, chains=None):
        self.client = client
        self.chains = chains
        self.scanner = scanner
        self.client.on_run.register(self.handle_run)
        self.client.on_new_bounty.register(self.handle_new_bounty)
        self.client.on_vote_on_bounty_due.register(self.handle_vote_on_bounty)
        self.client.on_settle_bounty_due.register(self.handle_settle_bounty)

        self.testing = testing
        self.bounties_seen = 0
        self.votes_posted = 0
        self.settles_posted = 0

    @classmethod
    def connect(cls, polyswarmd_addr, keyfile, password, api_key=None, testing=0, insecure_transport=False, scanner=None, chains=None):
        """Connect the Arbiter to a Client.

        Args:
            polyswarmd_addr (str): URL of polyswarmd you are referring to.
            keyfile (str): Keyfile filename.
            password (str): Password associated with Keyfile.
            api_key (str): Your PolySwarm API key.
            testing (int): Number of testing bounties to use.
            insecure_transport (bool): Allow insecure transport such as HTTP?
            chains (set(str)):  Set of chains you are acting on.

        Returns:
            AbstractArbiter: Arbiter instantiated with a Client.
        """
        client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
        return cls(client, testing, scanner, chains)

    async def scan(self, guid, content, chain):
        """Override this to implement custom scanning logic

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            content (bytes): Content of the artifact to be scan
            chain (str): Chain we are operating on
        Returns:
            (bool, bool, str): Tuple of bit, vote, metadata

        Note:
            | The meaning of the return types are as follows:
            |   - **bit** (*bool*): Whether to include this artifact in the assertion or not
            |   - **vote** (*bool*): Whether this artifact is malicious or not
            |   - **metadata** (*str*): Optional metadata about this artifact
        """
        if self.scanner:
            return await self.scanner.scan(guid, content, chain)

        raise NotImplementedError("You must subclass this class and override this method.")

    def run(self):
        """
        Run the Client on the Arbiter's chains.
        """
        self.client.run(self.chains)

    async def handle_run(self, chain):
        """
        If the Client's current balance is less than the minimum stake
        then deposit the difference between the two to the given chain.

        Args:
            chain (str): Chain we are operating on.
        """
        min_stake = self.client.staking.parameters[chain]['minimum_stake']
        staking_balance = await self.client.staking.get_total_balance(chain)
        tries = 0
        if staking_balance < min_stake:
            while True:
                nct_balance = await self.client.balances.get_nct_balance(chain)
                if self.testing > 0 and nct_balance < min_stake - staking_balance and tries >= MAX_STAKE_RETRIES:
                    logger.error('Failed %d attempts to deposit due to low balance. Exiting', tries)
                    self.client.exit_code = 1
                    self.client.stop()
                elif nct_balance < min_stake - staking_balance:
                    logger.warning('Insufficient balance to deposit stake on %s. Have %s need %s', chain, nct_balance, min_stake - staking_balance)
                    tries += 1
                    await asyncio.sleep(tries * tries)
                    continue

                deposits = await self.client.staking.post_deposit(min_stake - staking_balance, chain)
                logger.info('Depositing stake: %s', deposits)
                break

    async def handle_new_bounty(self, guid, author, amount, uri, expiration, chain):
        """Scan and assert on a posted bounty

        Args:
            guid (str): The bounty to assert on
            author (str): The bounty author
            amount (str): Amount of the bounty in base NCT units (10 ^ -18)
            uri (str): IPFS hash of the root artifact
            expiration (str): Block number of the bounty's expiration
            chain (str): Is this on the home or side chain?
        Returns:
            Response JSON parsed from polyswarmd containing placed assertions
        """
        self.bounties_seen += 1
        if self.testing > 0:
            if self.bounties_seen > self.testing:
                logger.info('Received new bounty, but finished with testing mode')
                return []
            logger.info('Testing mode, %s bounties remaining', self.testing - self.bounties_seen)

        votes = []
        async for content in self.client.get_artifacts(uri):
            bit, vote, metadata = await self.scan(guid, content, chain)
            votes.append(vote)

        bounty = await self.client.bounties.get_bounty(guid, chain)
        if bounty is None:
            logging.error('Unable to get retrieve new bounty')
            return []

        bloom_parts = await self.client.bounties.get_bloom(guid, chain)
        bounty_bloom = 0
        for b in bloom_parts:
            bounty_bloom = bounty_bloom << 256 | int(b)

        calculated_bloom = await self.client.bounties.calculate_bloom(uri)
        valid_bloom = bounty and bounty_bloom == calculated_bloom

        expiration = int(expiration)
        assertion_reveal_window = self.client.bounties.parameters[chain]['assertion_reveal_window']
        arbiter_vote_window = self.client.bounties.parameters[chain]['arbiter_vote_window']

        vb = VoteOnBounty(guid, votes, valid_bloom)
        self.client.schedule(expiration + assertion_reveal_window, vb, chain)

        sb = SettleBounty(guid)
        self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)

        return []

    async def handle_vote_on_bounty(self, bounty_guid, votes, valid_bloom, chain):
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
        return await self.client.bounties.post_vote(bounty_guid, votes, valid_bloom, chain)

    async def handle_settle_bounty(self, bounty_guid, chain):
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
        if self.testing > 0 and self.settles_posted >= self.testing:
            logger.info("All testing bounties complete, exiting")
            self.client.stop()
        return ret