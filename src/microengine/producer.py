import logging
import os

from polyswarmartifact import ArtifactType

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.producer import Producer

logger = logging.getLogger(__name__)

REDIS_ADDR = os.getenv('REDIS_ADDR', 'localhost:6379')
QUEUE = os.getenv('QUEUE')
RATE_LIMIT = os.getenv('RATE_LIMIT', None)

TIME_TO_POST_ASSERTION = 6
KEY_TIMEOUT = 20


class Microengine(AbstractMicroengine):
    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None, bid_strategy=None, **kwargs):
        if artifact_types is None:
            artifact_types = [ArtifactType.FILE]
        super().__init__(client, testing, None, chains, artifact_types, bid_strategy=bid_strategy, **kwargs)

        if QUEUE is None:
            raise ValueError('No queue configured, set the QUEUE environment variable')
        if QUEUE.endswith('_results'):
            raise ValueError('Queue name cannot end with `_results`')

        self.client.on_run.register(self.__handle_run)
        self.redis = None

    async def __handle_run(self, chain):
        if REDIS_ADDR.startswith('redis://'):
            redis_uri = REDIS_ADDR
        else:
            redis_uri = 'redis://' + REDIS_ADDR

        self.producer = Producer(self.client, redis_uri, QUEUE, TIME_TO_POST_ASSERTION,
                                 bounty_filter=self.bounty_filter, confidence_modifier=self.confidence_modifier,
                                 rate_limit=RATE_LIMIT)
        await self.producer.start()

    async def fetch_and_scan_all(self, guid, artifact_type, uri, duration, metadata, chain):
        """Overrides the default fetch logic to embed the URI and index rather than downloading on producer side

        Args:
            guid (str): GUID of the associated bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            uri (str):  Base artifact URI
            duration (int): Blocks until vote round ends
            metadata (list[dict]) List of metadata json blobs for artifacts
            chain (str): Chain we are operating on

        Returns:
            list(ScanResult): List of ScanResult objects
        """
        return await self.producer.scan(guid, artifact_type, uri, duration, metadata, chain)
