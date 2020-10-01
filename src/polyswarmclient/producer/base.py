import aioredis
import asyncio
import json
import logging
import time

from asyncio import Future

from polyswarmartifact import ArtifactType
from polyswarmartifact.schema import FileArtifact, URLArtifact
from polyswarmclient.producer.job import JobRequest
from polyswarmclient.producer.jobprocessor import JobProcessor
from polyswarmclient.ratelimit.redis import RedisDailyRateLimit

logger = logging.getLogger(__name__)

WAIT_TIME = 20
KEY_TIMEOUT = 10
JOB_RESULTS_FORMAT = '{}_{}_{}_results'


class Producer:
    def __init__(self, client, redis_uri, queue, time_to_post, bounty_filter=None, rate_limit=None, **kwargs):
        self.client = client
        self.redis_uri = redis_uri
        self.queue = queue
        self.time_to_post = time_to_post
        self.bounty_filter = bounty_filter
        self.redis = None
        self.rate_limit = rate_limit
        self.rate_limiter = None
        self.job_processor = None

    async def start(self):
        self.redis = await aioredis.create_redis_pool(self.redis_uri)
        await self._setup_rate_limit(self.redis)
        await self._setup_job_processor(self.redis)

    async def _setup_rate_limit(self, redis):
        if self.rate_limit is not None:
            self.rate_limiter = RedisDailyRateLimit(redis, self.queue, self.rate_limit)

    async def _setup_job_processor(self, redis):
        self.job_processor = JobProcessor(redis=redis, queue=self.queue, redis_error_callback=self.__reset_redis)
        asyncio.get_event_loop().create_task(self.job_processor.run())

    async def __reset_redis(self):
        self.redis.close()
        await self.redis.wait_closed()
        self.redis = await aioredis.create_redis_pool(self.redis_uri)

        # Update job processor
        await self.job_processor.set_redis(self.redis)

        # Update rate_limiter
        if self.rate_limiter:
            self.rate_limiter.set_redis(self.redis)

    async def scan(self, bounty):
        """Creates a set of jobs to scan all the artifacts at the given URI that are passed via Redis to workers

            Args:
                bounty (Bounty): The bounty to scan

            Returns:
                ScanResult: ScanResult object
        """
        artifact_type = ArtifactType.from_string(bounty.artifact_type)
        if artifact_type == ArtifactType.FILE:
            metadata = FileArtifact(filename=bounty.sha256, mimetype=bounty.mimetype,
                                    sha256=bounty.sha256).dict()
        else:
            metadata = URLArtifact(uri=bounty.artifact_url).dict()

        # Ensure we don't wait past the scan duration for one large artifact
        timeout = bounty.duration - self.time_to_post
        logger.info(f'Timeout set to {timeout}')
        loop = asyncio.get_event_loop()

        # Need to break up the artifact url into 2 parts to download this.
        try:
            if self.rate_limiter is None or await self.rate_limiter.use():
                job = JobRequest(polyswarmd_uri='',
                                 guid=bounty.guid,
                                 index=0,
                                 uri=bounty.artifact_url,
                                 artifact_type=artifact_type.value,
                                 duration=timeout,
                                 metadata=metadata,
                                 chain='',
                                 ts=int(time.time()))

                # Update number of jobs sent
                loop.create_task(self._increment_job_counter())

                # Send jobs as json string to backend
                loop.create_task(self._send_jobs(json.dumps(job.asdict())))

                # Send jobs to job processor
                future = Future()
                key = JOB_RESULTS_FORMAT.format(self.queue, bounty.guid, '')
                await self.job_processor.register_job(bounty.guid, key, job, future)

                # Age off old result keys
                loop.create_task(self._expire_key(key, bounty.duration + KEY_TIMEOUT))

                # Wait for results from job processor
                return await future
        except OSError:
            logger.exception('Redis connection down')
            await self.__reset_redis()
        except aioredis.errors.ReplyError:
            logger.exception('Redis out of memory')
            await self.__reset_redis()
        except aioredis.errors.ConnectionForcedCloseError:
            logger.exception('Redis connection closed')
            await self.__reset_redis()

        return []

    async def _increment_job_counter(self):
        job_counter = f'{self.queue}_scan_job_counter'
        await self.redis.incr(job_counter)

    async def _send_jobs(self, job):
        await self.redis.rpush(self.queue, job)

    async def _expire_key(self, key, timeout):
        await self.redis.expire(key, timeout)
