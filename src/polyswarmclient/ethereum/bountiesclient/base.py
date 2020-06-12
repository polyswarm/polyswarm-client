import asyncio
import json
import logging
import warnings

import aiohttp
from polyswarmartifact import ArtifactType

from polyswarmclient.ethereum import bloom
from polyswarmclient.ethereum.bountiesclient.transaction import SettleBountyTransaction, PostVoteTransaction, \
    RevealAssertionTransaction, PostAssertionTransaction, PostBountyTransaction
from polyswarmclient.parameters import Parameters
from polyswarmclient.utils import bool_list_to_int, calculate_commitment

logger = logging.getLogger(__name__)


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
        success, result = await self.__client.make_request('GET', '/bounties/parameters', chain, api_key=api_key)
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
        artifacts = await self.__client.list_artifacts(ipfs_uri, api_key=api_key)
        bf = bloom.BloomFilter()
        for _, h in artifacts:
            bf.add(h.encode('utf-8'))

        return int(bf)

    async def get_bloom(self, bounty_guid, chain, api_key=None):
        """
        Get bloom from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        path = '/bounties/{0}/bloom'.format(bounty_guid)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected bloom, received', extra={'extra': result})
            return None
        return result.get('bloom')

    async def get_bounty(self, guid, chain, api_key=None):
        """Get a bounty from polyswarmd.

        Args:
            guid (str): GUID of the bounty to retrieve
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing bounty details
        """
        path = '/bounties/{0}'.format(guid)
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
        path = '/bounties'
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

    async def post_bounty(self, artifact_type, amount, artifact_uri, duration, chain, api_key=None, metadata=None):
        """Post a bounty to polyswarmd.

        Args:
            artifact_type (ArtifactType): The artifact type in this bounty
            amount (int): The amount to put up as a bounty
            artifact_uri (str): URI of artifacts
            duration (int): Number of blocks to accept new assertions
            chain (str): Which chain to operate on
            api_key (str): Override default API key
            metadata (Optional[str]): Optional metadata
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        bounty_fee = await self.parameters[chain].get('bounty_fee')
        bloom = await self.calculate_bloom(artifact_uri)
        num_artifacts = await self.__client.get_artifact_count(artifact_uri)
        transaction = PostBountyTransaction(self.__client, ArtifactType.to_string(artifact_type), amount, bounty_fee,
                                            artifact_uri, num_artifacts, duration, bloom, metadata)
        success, result = await transaction.send(chain, api_key=api_key)

        if not success or 'bounties' not in result:
            logger.error('Expected bounty, received', extra={'extra': result})

        return result.get('bounties', [])

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
        path = '/bounties/{0}/assertions/{1}'.format(bounty_guid, index)
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
        path = '/bounties/{0}/assertions'.format(bounty_guid)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected assertion, received', extra={'extra': result})
            return None

        return result

    async def post_assertion(self, bounty_guid, bid, mask, verdicts, chain, api_key=None, metadata=None):
        """Post an assertion to polyswarmd.

        Args:
            bounty_guid (str): The bounty to assert on
            bid (int): The amount to bid
            mask (List[bool]): Which artifacts in the bounty to assert on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        fee = await self.parameters[chain].get('assertion_fee')
        nonce, commitment = calculate_commitment(self.__client.account, bool_list_to_int(verdicts))

        transaction = PostAssertionTransaction(self.__client, bounty_guid, bid, fee, mask, commitment)
        success, result = await transaction.send(chain, api_key=api_key)
        if not success or 'assertions' not in result:
            logger.error('Expected assertions, received', extra={'extra': result})

        return nonce, result.get('assertions', [])

    async def post_reveal(self, bounty_guid, index, nonce, verdicts, metadata, chain, api_key=None):
        """Post an assertion reveal to polyswarmd.

        Args:
            bounty_guid (str): The bounty which we have asserted on
            index (int): The index of the assertion to reveal
            nonce (str): Secret nonce used to reveal assertion
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            metadata (str): Metadata about the scan
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        try:
            metadata = await self.post_metadata(metadata, chain, api_key)
        except (json.JSONDecodeError, aiohttp.client.ClientResponseError):
            warnings.warn('Posting non-json, or non-confirming json is deprecated', DeprecationWarning)
            pass

        transaction = RevealAssertionTransaction(self.__client, bounty_guid, index, nonce, verdicts, metadata)

        success, result = await transaction.send(chain, api_key=api_key)
        if not success or 'reveals' not in result:
            logger.error('Expected reveal, received', extra={'extra': result})

        return result.get('reveals', [])

    async def post_metadata(self, metadata, chain, api_key=None):
        """Posts metadata to IPFS

        Args:
            metadata (str): metadata json that conforms to Schema in polyswarm-artifact
            chain (str): Which chain to operate on
            api_key (str): Override default API key

        Returns: ipfs_hash or None

        """
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        success, ipfs_hash = await self.__client.make_request('POST', '/bounties/metadata', chain,
                                                              json=metadata,
                                                              api_key=api_key)
        return ipfs_hash if success else None

    async def get_vote(self, bounty_guid, index, chain, api_key=None):
        """
        Get a vote from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            index (int): Index of the vote
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        path = '/bounties/{0}/votes/{1}'.format(bounty_guid, index)
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
        path = '/bounties/{0}/votes'.format(bounty_guid)
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
        transaction = PostVoteTransaction(self.__client, bounty_guid, votes, valid_bloom)
        success, result = await transaction.send(chain, api_key=api_key)
        if not success or 'votes' not in result:
            logger.error('Expected vote, received', extra={'extra': result})

        return result.get('votes', [])

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
        if not await self.did_participate(bounty_guid, chain, api_key):
            logger.debug('Will not settle %s because %s did not participate', bounty_guid, self.__client.account)
            return []

        transaction = SettleBountyTransaction(self.__client, bounty_guid)
        success, result = await transaction.send(chain, api_key=api_key)
        if not success or 'transfers' not in result:
            logger.warning('No transfer event, received', extra={'extra': result})

        return result.get('transfers', [])

    async def settle_all_bounties(self, chain, api_key=None):
        """Settles all bounties on a contract via polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        transfers = 0
        # Fetch bounties from polyd, 75 at a time.
        async for page in self.get_all_bounty_guids(count=75, chain=chain):
            # Settle out each page
            logger.debug('Settling %s', page)
            found = await asyncio.gather(*[self.settle_bounty(guid, chain, api_key) for guid in page])
            for transfer_list in found:
                transfers += sum([int(transfer) for transfer in transfer_list])

        logger.info('Recovered %s NCT by settling all bounties', transfers)
