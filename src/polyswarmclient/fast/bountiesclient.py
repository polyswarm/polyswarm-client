import json
import logging
import uuid
from collections import Iterable

from polyswarmartifact import ArtifactType
from polyswarmclient.fast.transaction import PolySwarmTransactionRequest
from polyswarmclient.parameters import Parameters
from polyswarmtransaction.bounty import BountyTransaction, AssertionTransaction, VoteTransaction
from polyswarmclient.exceptions import InvalidMetadataError

logger = logging.getLogger(__name__)

DEFAULT_METADATA = '{"malware_family": ""}'


class PostBountyTransactionRequest(PolySwarmTransactionRequest):
    @property
    def path(self):
        return '/bounties/'

    def __init__(self, client, guid, reward, artifact_uri, artifact_type, duration, metadata):
        inner = BountyTransaction(guid, reward, artifact_uri, artifact_type, duration, metadata)
        super().__init__(client, inner)


class PostAssertionTransactionRequest(PolySwarmTransactionRequest):
    @property
    def path(self):
        return f'/bounties/{self.bounty_guid}/assertions/'

    def __init__(self, client, bounty_guid, bid, verdict, metadata):
        self.bounty_guid = bounty_guid
        inner = AssertionTransaction(bounty_guid, verdict, bid, metadata)
        super().__init__(client, inner)


class PostVoteTransactionRequest(PolySwarmTransactionRequest):
    @property
    def path(self):
        return f'/bounties/{self.bounty_guid}/votes/'

    def __init__(self, client, bounty_guid, vote):
        self.bounty_guid = bounty_guid
        inner = VoteTransaction(bounty_guid, vote)
        super().__init__(client, inner)


class BountiesClient(object):
    def __init__(self, client):
        self.__client = client
        self.parameters = {}

    async def fetch_parameters(self, chain, api_key=None):
        """Get bounty parameters from polyswarmd.

        Args:
            chain (str): Which chain to operate on.
            api_key (str): Override default API key
        Note:
            This function doesn't return anything. It instead stores the bounty parameters
            as parsed JSON in self.parameters[chain].
        """
        success, result = await self.__client.make_request('GET', '/bounties/parameters/', chain, api_key=api_key)
        if not success:
            raise Exception('Error retrieving bounty parameters')
        self.parameters[chain] = Parameters(result)

    async def calculate_bloom(self, ipfs_uri, api_key=None):
        """Calculate bloom filter for a set of artifacts.

        Args:
            ipfs_uri (str): IPFS URI for the artifact set
            api_key (str): Override default API key
        Returns:
            Bloom filter value for the artifact set
        """
        return []

    async def get_bloom(self, bounty_guid, chain, api_key=None):
        """
        Get bloom from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        return []

    async def get_bounty(self, guid, chain, api_key=None):
        """Get a bounty from polyswarmd.

        Args:
            guid (str): GUID of the bounty to retrieve
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing bounty details
        """
        path = f'/bounties/{guid}/'
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected bounty, received', extra={'extra': result})
            return None
        return result

    async def get_bounty_guids(self, page, count, chain, api_key=None):
        """Get the list of bounties at the given page

        Args:
            page (int): Page to read
            count (int): Size of the pages
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing list of bounty guids
         """
        path = '/bounties/'
        params = {'page': page, 'count': count}
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key, params=params)
        if not success:
            logger.error('Expected list, received', extra={'extra': result})
            return None

        return result

    async def get_all_bounty_guids(self, count, chain, api_key=None):
        """Generator that gets all the bounty guids a page at a time

        Args:
            count (int): Size of the pages
            chain (str): Which chain to operate on
            api_key (str): Override default API key

        Returns:
            Generator of lists of bounty guids
        """
        page = 0
        guids = await self.get_bounty_guids(page, count, chain, api_key)
        while guids:
            yield guids
            page += 1
            guids = await self.get_bounty_guids(page, count, chain, api_key)

    async def post_bounty(self, artifact_type, amount, artifact_uri, duration, chain, api_key=None, metadata=''):
        """Post a bounty to polyswarmd.

        Args:
            amount (int): The amount to put up as a bounty
            artifact_uri (str): URI of artifacts
            artifact_type (ArtifactType): The artifact type in this bounty
            duration (int): Number of blocks to accept new assertions
            metadata (str): Optional IPFS hash for metadata
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
        guid = uuid.uuid4()
        transaction = PostBountyTransactionRequest(self.__client, str(guid), amount, artifact_uri, artifact_type.value,
                                                   duration, metadata)
        result = await transaction.send(api_key=api_key)
        return [result]

    async def get_assertion(self, bounty_guid, index, chain, api_key=None):
        """Get an assertion from polyswarmd.

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the assertion from
            index (int): Index of the assertion
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing assertion details
        """
        path = f'/bounties/{bounty_guid}/assertions/{index}/'
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected assertion, received', extra={'extra': result})
            return None

        return result

    async def get_assertions(self, bounty_guid, chain, api_key=None):
        """Get an assertion from polyswarmd.

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the assertion from
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing assertion details
        """
        path = f'/bounties/{bounty_guid}/assertions/'
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected assertions, received', extra={'extra': result})
            return None

        return result

    async def post_assertion(self, bounty_guid, bid, mask, verdicts, chain, api_key=None, metadata=DEFAULT_METADATA):
        """Post an assertion to polyswarmd.

        Args:
            bounty_guid (str): The bounty to assert on
            bid (List[int]): The amount to bid
            mask (List[bool]): Which artifacts in the bounty to assert on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            chain (str): Which chain to operate on
            api_key (str): Override default API key
            metadata (str): Metadata for this assertion
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        try:
            metadata = json.loads(metadata)
        except (ValueError, json.JSONDecodeError) as e:
            raise InvalidMetadataError from e

        if isinstance(metadata, str) or not isinstance(metadata, Iterable):
            metadata = [metadata]

        for verdict_mask, verdict_bid, verdict, verdict_metadata in zip(mask, bid, verdicts, metadata):
            if not verdict_mask:
                continue

            transaction = PostAssertionTransactionRequest(self.__client, bounty_guid, verdict_bid, verdict,
                                                          verdict_metadata)
            return 0, [await transaction.send(api_key=api_key)]

    async def post_reveal(self, bounty_guid, index, nonce, verdicts, metadata, chain, api_key=None):
        """Post an assertion reveal to polyswarmd.

        Args:
            bounty_guid (str): The bounty which we have asserted on
            index (int): The index of the assertion to reveal
            nonce (str): Secret nonce used to reveal assertion
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            metadata (List[Dict[str, Any]]): Optional metadata
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        pass

    async def post_metadata(self, metadata, chain, api_key=None):
        """
        Returns the metadata unchanged
        """
        return metadata

    async def get_vote(self, bounty_guid, index, chain, api_key=None):
        """
        Get a vote from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            index (int): Index of the vote
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        path = f'/bounties/{bounty_guid}/votes/{index}/'
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected vote, received', extra={'extra': result})
            return None

        return result

    async def get_votes(self, bounty_guid, chain, api_key=None):
        """
        Get a vote from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        path = f'/bounties/{bounty_guid}/votes/'
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected vote, received', extra={'extra': result})
            return None

        return result

    async def post_vote(self, bounty_guid, votes, valid_bloom, chain, api_key=None):
        """Post a vote to polyswarmd.

        Args:
            bounty_guid (str): The bounty which we are voting on
            votes (List[bool]): Vote (malicious/benign) for each of the artifacts in the bounty
            valid_bloom (bool): Is the bloom filter reported by the bounty poster valid
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if votes:
            vote = votes[0]
            transaction = PostVoteTransactionRequest(self.__client, bounty_guid, vote)
            return await transaction.send(api_key=api_key)

    async def did_participate(self, bounty_guid, chain, api_key=None):
        """Check to see if this client participated in a bounty

        Args:
            bounty_guid (str): The bounty being checked
            chain (str): Which chain to operate on
            api_key (str): Override default API key

        Returns:
            True if this account participated

        """
        account = self.__client.account
        bounty = await self.get_bounty(bounty_guid, chain, api_key)
        if not bounty:
            return False

        if bounty.get('author', None) == account:
            return True

        for assertion in await self.get_assertions(bounty_guid, chain, api_key):
            if assertion.get('author', None) == account:
                return True

        for vote in await self.get_votes(bounty_guid, chain, api_key):
            if vote.get('voter', None) == account:
                return True

        return False

    async def settle_bounty(self, bounty_guid, chain, api_key=None):
        """Settle a bounty via polyswarmd

        Args:
            bounty_guid (str): The bounty which we are settling
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        pass

    async def settle_all_bounties(self, chain, api_key=None):
        """Settles all bounties on a contract via polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        pass
