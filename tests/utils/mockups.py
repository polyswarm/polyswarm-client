import os
import base64
import tempfile
import logging
from hashlib import sha256
import asyncio
import time

from polyswarmclient.abstractambassador import AbstractAmbassador
from polyswarmartifact import ArtifactType

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult
from polyswarmclient.filters.bountyfilter import BountyFilter
from polyswarmclient.filters.confidencefilter import ConfidenceModifier
from polyswarmclient.abstractarbiter import AbstractArbiter

from tests.utils.fixtures import TESTKEY, TESTKEY_PASSWORD

POLYSWARMD_FAST_ADDRESS = 'polyswarmd-fast:8000/v1'

CHAINS = ['side']

EICAR = base64.b64decode(
    b'WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=')

BOUNTY_TEST_DURATION_BLOCKS = int(os.getenv('BOUNTY_TEST_DURATION_BLOCKS', 5))

EICAR_HASH = sha256(EICAR).hexdigest()

logger = logging.getLogger(__name__)


class MockAmbassador(AbstractAmbassador):

    def __init__(self, client, testing=0, chains=None, watchdog=0, submission_rate=30):
        super().__init__(client, testing, chains, watchdog, submission_rate)
        self.start_time = None
        self.timeout = 5

    async def generate_bounties(self, chain):
        """
        Submit EICAR test string
        """
        amount = await self.client.bounties.parameters[chain].get('bounty_amount_minimum')

        ipfs_uri = await self.client.post_artifacts([('eicar', EICAR)])

        await self.push_bounty(ArtifactType.FILE, amount, ipfs_uri, BOUNTY_TEST_DURATION_BLOCKS, chain)

    def run(self):
        self.start_time = time.time()
        super(MockAmbassador, self).run()

    async def _handle_empty_queue(self):
        """
        Stop all loop's task if backend waits on an empty queue too long.
        """
        if (time.time() - self.start_time) > self.timeout:
            logger.debug('Queue empty and timeout of %d seconds reached, canceling all tasks', self.timeout)
            await self.__cancel_all_tasks()
        else:
            logger.debug('Queue empty, waiting for timeout in %d seconds', self.timeout)

    @staticmethod
    async def __cancel_all_tasks():
        for task in asyncio.Task.all_tasks():
            task.cancel()


class MockScanner(AbstractScanner):

    def __init__(self):
        super(MockScanner, self).__init__()

    async def scan(self, guid, artifact_type, content, metadata, chain):
        test_hash = sha256(content).hexdigest()
        if test_hash == EICAR_HASH:
            return ScanResult(bit=True, verdict=True)

        return ScanResult(bit=True, verdict=False)

    async def setup(self):
        """
        Fail setup on purpose to stop backend.
        """
        return False


class MockMicroengine(AbstractMicroengine):

    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None,
                 bid_strategy=None, bounty_filter=BountyFilter(None, None),
                 confidence_modifier=ConfidenceModifier(None, None)):

        logger.info("Loading Mock scanner...")
        if artifact_types is None:
            artifact_types = [ArtifactType.FILE, ArtifactType.URL]
        if scanner is None:
            scanner = MockScanner()

        super().__init__(client, testing, scanner, chains, artifact_types)

    async def bid(self, guid, mask, verdicts, confidences, metadatas, chain):
        return await self.client.bounties.parameters[chain].get('assertion_bid_minimum')


class MockArbiter(AbstractArbiter):

    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None):

        logger.info("Loading Mock scanner...")
        if artifact_types is None:
            artifact_types = [ArtifactType.FILE, ArtifactType.URL]
        if scanner is None:
            scanner = MockScanner()

        super().__init__(client, testing, scanner, chains, artifact_types)


with tempfile.NamedTemporaryFile(delete=True) as key_file:
    key_file.write(TESTKEY)
    key_file.flush()

    mock_ambassador = MockAmbassador.connect(POLYSWARMD_FAST_ADDRESS,
                                             key_file.name,
                                             TESTKEY_PASSWORD,
                                             insecure_transport=True,
                                             chains=CHAINS)

    mock_microengine = MockMicroengine.connect(POLYSWARMD_FAST_ADDRESS,
                                               key_file.name,
                                               TESTKEY_PASSWORD,
                                               insecure_transport=True,
                                               chains=CHAINS)

    mock_arbiter = MockArbiter.connect(POLYSWARMD_FAST_ADDRESS,
                                       key_file.name,
                                       TESTKEY_PASSWORD,
                                       insecure_transport=True,
                                       chains=CHAINS)
