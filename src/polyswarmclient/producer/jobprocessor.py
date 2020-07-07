import aioredis
import asyncio
import json
import logging

from aioredis import Redis
from asyncio import Future, Task
from typing import Dict, List, Optional, Tuple, Coroutine, Callable

from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.filters.confidencefilter import ConfidenceModifier
from polyswarmclient.producer.job import JobRequest, JobResponse

logger = logging.getLogger(__name__)


class PendingJob:
    """
    A wrapper around a list of Jobs that are processing in the backend
    """
    key: str
    jobs: List[JobRequest]
    results: Dict[int, ScanResult]
    future: Future

    def __init__(self, key: str, jobs: List[JobRequest], future: Future):
        self.key = key
        self.jobs = jobs
        self.future = future
        self.results = {}

    def is_expired(self):
        """
        Returns true if any of the jobs are expired
        """
        if self.jobs:
            return any((job.is_expired() for job in self.jobs))

        return False

    def has_all_results(self):
        """
        Returns true if all the jobs have a result
        """
        return len(self.jobs) == len(self.results.items())

    def finish(self):
        """
        Set the results in the future and mark done
        """
        scan_results = [self.results.get(i, ScanResult()) for i in range(len(self.results))]
        self.future.set_result(scan_results)

    async def fetch_results(self, redis, confidence_modifier):
        """
        Fetch and store as many results as are in the queue
        Break when there are no more results

        :param redis:
        :param confidence_modifier:
        """
        # No need for a lock here, since it is only called inside the JobProcessor lock
        logger.debug('Getting results for %s', self.key)
        while True:
            try:
                result = await redis.lpop(self.key)
                if not result:
                    logger.debug('No more events for %s', self.key)
                    return

                response = JobResponse(**json.loads(result.decode('utf-8')))
                logger.debug('Found job response', extra={'extra': response.asdict()})

                confidence = response.confidence
                if confidence_modifier:
                    confidence = confidence_modifier.modify(self.jobs[response.index].metadata, response.confidence)

                self.results[response.index] = ScanResult(bit=response.bit,
                                                          verdict=response.verdict,
                                                          confidence=confidence,
                                                          metadata=response.metadata)
            except aioredis.errors.ReplyError:
                logger.exception('Redis out of memory')
                raise
            except aioredis.errors.ConnectionForcedCloseError:
                logger.exception('Redis connection closed')
                raise
            except OSError:
                logger.exception('Redis connection down')
                raise
            except (AttributeError, ValueError, KeyError):
                logger.exception('Received invalid response from worker')
                break


class JobProcessor:
    """
    Keeps track pending jobs, and polls the PendingJob results every period of time (.5 seconds)
    """
    redis_uri: str
    confidence_modifier: Optional[ConfidenceModifier]
    queue: str
    period: float
    pending_jobs: Dict[str, PendingJob]
    job_lock: Optional[asyncio.Lock]
    redis: Optional[Redis]
    task = Optional[Task]
    reset_callback = Optional[Callable[[], Coroutine]]

    def __init__(self, redis: Redis, queue: str, confidence_modifier: Optional[ConfidenceModifier], period: float = .5,
                 redis_error_callback: Optional[Callable[[], Coroutine]] = None):
        self.redis = redis
        self.queue = queue
        self.confidence_modifier = confidence_modifier
        self.period = period
        self.reset_callback = redis_error_callback
        self.pending_jobs = {}
        self.job_lock = None
        self.task = None

    async def run(self):
        """
        Start the JobProcessor in a new task that will process any pending jobs forever

        """
        if self.redis is None:
            raise ValueError('Must set redis client prior to run')

        loop = asyncio.get_event_loop()
        self.job_lock = asyncio.Lock()
        self.task = loop.create_task(self.__process())

    def stop(self):
        """
        Stop processing jobs
        """
        self.task.cancel()

    async def set_redis(self, redis):
        """
        Update the redis connection,
        """
        async with self.job_lock:
            self.redis = redis

    async def register_jobs(self, guid: str, key: str, jobs: List[JobRequest], future: Future):
        """
        Register a new pending job to be monitored, and polled

        :param guid: bounty guid
        :param key: redis key to poll
        :param jobs: list of jobs in progress
        :param future: future to return results
        """
        logger.debug('Registering %s jobs under %s', len(jobs), guid)
        pending = PendingJob(key=key, jobs=jobs, future=future)
        async with self.job_lock:
            self.pending_jobs[guid] = pending

    async def __process(self):
        while True:
            # Set result for all expired jobs
            await self.__handle_expired()

            await self.fetch_results()

            # Set result for all jobs that have a full set of results
            await self.__handle_jobs_with_all_results()

            # Don't consumer all the resources for this loop
            await asyncio.sleep(self.period)

    async def __handle_expired(self):
        """
        Finishes any pending job that has expired
        """
        async with self.job_lock:
            finished_jobs = [(guid, job) for guid, job in self.pending_jobs.items() if job.is_expired()]

        for guid, job in finished_jobs:
            logger.warning('Timeout handling bounty %s, responding as is.', guid,
                           extra={'extra': job.results})

        async with self.job_lock:
            self.__track_and_finish(finished_jobs)

    async def fetch_results(self):
        async with self.job_lock:
            jobs = self.pending_jobs.items()

        results = await asyncio.gather(*[pending_job.fetch_results(self.redis, self.confidence_modifier)
                                         for guid, pending_job in jobs], return_exceptions=True)

        reset = False
        for result in results:
            if isinstance(result, aioredis.errors.RedisError) or isinstance(result, OSError):
                reset = True
                logger.exception("Exception fetching results", exc_info=result)

        if reset and self.reset_callback:
            await self.reset_callback()

    async def __handle_jobs_with_all_results(self):
        """
        Finishes any pending job that has all the results it needs
        """
        async with self.job_lock:
            finished_jobs = [(guid, job) for guid, job in self.pending_jobs.items() if job.has_all_results()]

        for guid, job in finished_jobs:
            logger.debug("Job %s got all results", guid)

        async with self.job_lock:
            self.__track_and_finish(finished_jobs)

    def __track_and_finish(self, finished_jobs: List[Tuple[str, PendingJob]]):
        """
        Updates the counter of results, tells the pending_job to finish, and removes it from the list of pending jobs

        :param finished_jobs: List of PendingJobs that are finished
        """
        # Update Results counter for scaling
        loop = asyncio.get_event_loop()
        loop.create_task(self.__update_job_results_counter(sum([len(pending_job.results) for _, pending_job in finished_jobs])))

        # Tell Pending job to send results back, and delete
        for guid, pending_job in finished_jobs:
            pending_job.finish()
            # Delete pending job
            logger.debug('Removing %s', guid)
            del self.pending_jobs[guid]

    async def __update_job_results_counter(self, count):
        """
        Update redis about the total number of results processed
        :param count: number to increment
        """
        if count > 0:
            logger.debug('Incrementing results counter by %s', count)
            result_counter = f'{self.queue}_scan_result_counter'
            await self.redis.incrby(result_counter, count)

    async def __aenter__(self):
        await self.run()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop()
