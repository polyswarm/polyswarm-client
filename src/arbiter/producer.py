import logging
import os

from polyswarmartifact import ArtifactType

from polyswarmclient.abstractarbiter import AbstractArbiter
from polyswarmclient.producer import Producer


logger = logging.getLogger(__name__)

REDIS_ADDR = os.getenv('REDIS_ADDR', 'localhost:6379')
QUEUE = os.getenv('QUEUE')
RATE_LIMIT = os.getenv('RATE_LIMIT', None)

TIME_TO_POST_VOTE = 6


class Arbiter(AbstractArbiter):
    def __init__(self, client, scanner, **kwargs):
        super().__init__(client, scanner, **kwargs)

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

        self.producer = Producer(self.client, redis_uri, QUEUE, TIME_TO_POST_VOTE, rate_limit=RATE_LIMIT)
        await self.producer.start()

    async def fetch_and_scan(self, bounty):
        """Overrides the default fetch logic to embed the URI and index rather than downloading on producer side

        Args:
            bounty (Bounty): The bounty to scan

        Returns:
            ScanResult: ScanResult object
        """
        return await self.producer.scan(bounty)
