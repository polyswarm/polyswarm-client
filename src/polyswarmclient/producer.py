import aioredis
import asyncio
import dataclasses
import json
import logging
import time

from typing import Optional, Any, Dict

from polyswarmartifact import ArtifactType
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.filters.filter import MetadataFilter

logger = logging.getLogger(__name__)

WAIT_TIME = 20
KEY_TIMEOUT = WAIT_TIME + 10


@dataclasses.dataclass
class JobRequest:
    polyswarmd_uri: str
    guid: str
    index: int
    uri: str
    artifact_type: int
    duration: int
    metadata: Optional[Dict[str, Any]]
    chain: str
    ts: int

    @property
    def key(self):
        return f'{self.guid}:{self.index}'

    def get_artifact_type(self) -> ArtifactType:
        return ArtifactType(self.artifact_type)

    def asdict(self):
        return dataclasses.asdict(self)


@dataclasses.dataclass
class JobResponse:
    index: int
    bit: bool
    verdict: bool
    confidence: float
    metadata: str

    def asdict(self):
        return dataclasses.asdict(self)


class Producer:
    def __init__(self, client, redis_uri, queue, time_to_post, bounty_filter=None, confidence_modifier=None,
                 rate_limit=None):
        self.client = client
        self.redis_uri = redis_uri
        self.queue = queue
        self.time_to_post = time_to_post
        self.bounty_filter = bounty_filter
        self.confidence_modifier = confidence_modifier
        self.redis = None
        self.rate_limit = rate_limit

    async def start(self):
        if self.rate_limit is not None:
            await self.rate_limit.setup()
        self.redis = await aioredis.create_redis_pool(self.redis_uri)

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

        async def wait_for_result(result_key):
            try:
                while True:
                    result = await self.redis.lpop(result_key)
                    if result:
                        break

                    await asyncio.sleep(1)

                response = JobResponse(**json.loads(result.decode('utf-8')))
                confidence = response.confidence if not self.confidence_modifier \
                    else self.confidence_modifier.modify(metadata[response.index], response.confidence)

                return response.index, ScanResult(bit=response.bit, verdict=response.verdict, confidence=confidence,
                                                  metadata=response.metadata)
            except aioredis.errors.ReplyError:
                logger.exception('Redis out of memory')
            except aioredis.errors.ConnectionForcedCloseError:
                logger.exception('Redis connection closed')
            except OSError:
                logger.exception('Redis connection down')
            except (AttributeError, ValueError, KeyError):
                logger.exception('Received invalid response from worker')
                return None

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
                jobs.append(json.dumps(job.asdict()))

        if jobs:
            try:
                # Update number of jobs sent
                loop.create_task(self.update_job_counter(len(jobs)))
                loop.create_task(self.send_jobs(jobs))

                key = '{}_{}_{}_results'.format(self.queue, guid, chain)
                results = await asyncio.gather(*[asyncio.wait_for(wait_for_result(key), timeout=timeout) for _ in jobs],
                                               return_exceptions=True)
                # In the event of filter or rate limit, the index (r[0]) will not have a value in the dict
                results = {r[0]: r[1] for r in results if r is not None and not isinstance(r, Exception)}
                if len(results.keys()) < num_artifacts:
                    logger.error('Exception handling guid %s', guid)

                # Update number of results from jobs
                loop.create_task(self.update_job_results_counter(len(results.keys())))
                # Age off old result keys
                loop.create_task(self.expire_key(key, KEY_TIMEOUT))

                # Any missing responses will be replaced inline with an empty scan result
                return [results.get(i, ScanResult()) for i in range(num_artifacts)]
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

    async def update_job_results_counter(self, count):
        result_counter = f'{self.queue}_scan_result_counter'
        await self.redis.incrby(result_counter, count)

    async def expire_key(self, key, timeout):
        await self.redis.expire(key, timeout)
