from asyncio import Future

import aioredis
import asyncio

import json
import logging
import time

from polyswarmartifact import ArtifactType
from polyswarmclient.filters.filter import MetadataFilter
from polyswarmclient.producer.job import JobRequest
from polyswarmclient.producer.jobprocessor import JobProcessor

logger = logging.getLogger(__name__)

WAIT_TIME = 20
KEY_TIMEOUT = WAIT_TIME + 10
JOB_RESULTS_FORMAT = '{}_{}_{}_results'


class Producer:
    def __init__(self, client, redis_uri, queue, time_to_post, bounty_filter=None, confidence_modifier=None,
                 rate_limit=None):
        self.client = client
        self.redis_uri = redis_uri
        self.queue = queue
        self.time_to_post = time_to_post
        self.bounty_filter = bounty_filter
        self.redis = None
        self.rate_limit = rate_limit
        self.job_processor = JobProcessor(redis_uri, queue, confidence_modifier)

    async def start(self):
        if self.rate_limit is not None:
            await self.rate_limit.setup()
        self.redis = await aioredis.create_redis_pool(self.redis_uri)

        # Start job processor
        await self.job_processor.setup()
        asyncio.get_event_loop().create_task(self.job_processor.run())

    async def scan(self, guid, artifact_type, uri, duration, metadata, chain):
        """Creates a set of jobs to scan all the artifacts at the given URI that are passed via Redis to workers

            Args:
                guid (str): GUID of the associated bounty
                artifact_type (ArtifactType): Artifact type for the bounty being scanned
                uri (str):  Base artifact URI
                duration (int): number of blocks until scan is due
                metadata (list[dict]) List of metadata json blobs for artifacts
                chain (str): Chain we are operating on

            Returns:
                list(ScanResult): List of ScanResult objects
            """
        # Ensure we don't wait past the scan duration for one large artifact
        timeout = duration - self.time_to_post
        logger.info(f'Timeout set to {timeout}')
        loop = asyncio.get_event_loop()

        num_artifacts = len(await self.client.list_artifacts(uri))
        # Fill out metadata to match same number of artifacts
        metadata = MetadataFilter.pad_metadata(metadata, num_artifacts)

        jobs = []
        for i in range(num_artifacts):
            if (self.bounty_filter is None or self.bounty_filter.is_allowed(metadata[i])) \
             and (self.rate_limit is None or await self.rate_limit.use()):
                job = JobRequest(polyswarmd_uri=self.client.polyswarmd_uri,
                                 guid=guid,
                                 index=i,
                                 uri=uri,
                                 artifact_type=artifact_type.value,
                                 duration=timeout,
                                 metadata=metadata[i],
                                 chain=chain,
                                 ts=int(time.time()))
                jobs.append(job)

        if jobs:
            try:
                # Update number of jobs sent
                loop.create_task(self.update_job_counter(len(jobs)))

                # Send jobs as json string to backend
                loop.create_task(self.send_jobs([json.dumps(job.asdict()) for job in jobs]))

                # Send jobs to job processor
                future = Future()
                key = JOB_RESULTS_FORMAT.format(self.queue, guid, chain)
                await self.job_processor.register_jobs(guid, key, jobs, future)

                # Age off old result keys
                loop.create_task(self.expire_key(key, KEY_TIMEOUT))

                # Wait for results from job processor
                return await future
            except OSError:
                logger.exception('Redis connection down')
            except aioredis.errors.ReplyError:
                logger.exception('Redis out of memory')
            except aioredis.errors.ConnectionForcedCloseError:
                logger.exception('Redis connection closed')

        return []

    async def update_job_counter(self, count):
        job_counter = f'{self.queue}_scan_job_counter'
        await self.redis.incrby(job_counter, count)

    async def send_jobs(self, jobs):
        await self.redis.rpush(self.queue, *jobs)

    async def expire_key(self, key, timeout):
        await self.redis.expire(key, timeout)
