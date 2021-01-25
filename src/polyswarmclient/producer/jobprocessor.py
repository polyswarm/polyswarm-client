import aioredis
import asyncio
import json
import logging
import math
import time

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

    def times(self):
        return [int(math.floor(time.time())) - job.ts for job in self.jobs]

    def time_ratios(self):
        return [(int(math.floor(time.time())) - job.ts) / job.duration for job in self.jobs]

    async def fetch_results(self, redis: Redis, confidence_modifier):
        """
        Fetch and store as many results as are in the queue

        :param redis: open redis client
        :param confidence_modifier: Confidence modifier object
        """
        logger.debug('Getting results for %s', self.key)
        try:
            # Check expired before doing any redis connections
            if not self.__is_expired():
                async for result in self.__redis_results(redis):
                    response = JobResponse(**json.loads(result.decode('utf-8')))
                    logger.debug('Found job response', extra={'extra': response.asdict()})
                    self.__store_job_response(response, confidence_modifier)
                    if self.is_done():
                        logger.debug('Job is finished')
                        break

                logger.debug('Read all available redis results')

        except aioredis.errors.ReplyError:
            logger.exception('Redis out of memory')
            raise
        except aioredis.errors.ConnectionForcedCloseError:
            logger.exception('Redis connection closed')
            raise
        except aioredis.RedisError:
            logger.exception('Redis experienced unknown error')
            raise
        except OSError:
            logger.exception('Redis connection down')
            raise
        except (AttributeError, ValueError, KeyError):
            logger.exception('Received invalid response from worker')
            raise

        # finish if expired or has all results
        if self.is_done():
            logger.debug('Job is finished, letting it move to polyswarmd')
            self.__finish()

    async def __redis_results(self, redis: Redis):
        """
        Generator of redis results for the key
        :param redis: open redis client
        :return a generator of json strings that represent a JobResponse
        """
        while True:
            result = await redis.lpop(self.key)
            if not result:
                logger.debug('No more events for %s', self.key)
                break

            logger.debug('Got %s for %s', result, self.key)

            yield result

    def __store_job_response(self, response: JobResponse, confidence_modifier: Optional[ConfidenceModifier]):
        """
        Converts a JobResponse to ScanResult with modified confidence.
        Stores at the correct index in internal results

        :param response: JobResponse to conver
        :param confidence_modifier: an optional ConfidenceModifier to potentially change the confidence
        :return:
        """
        confidence = response.confidence
        if confidence_modifier:
            confidence = confidence_modifier.modify(self.jobs[response.index].metadata, response.confidence)

        self.results[response.index] = ScanResult(bit=response.bit,
                                                  verdict=response.verdict,
                                                  confidence=confidence,
                                                  metadata=response.metadata)

    def is_done(self):
        """
        Checks all things to see if it is done
        :return: true if expired, or has all results
        """
        return self.__is_expired() or self.__has_all_results()

    def __is_expired(self):
        """
        Returns true if any of the jobs are expired
        """
        if self.jobs:
            now = time.time()
            return any((job.is_expired(now) for job in self.jobs))

        return False

    def __has_all_results(self):
        """
        Returns true if all the jobs have a result
        """
        # I'm not sure how results could have more, but if it does, we got all the results we wanted
        return len(self.jobs) <= len(self.results.items())

    def __finish(self):
        """
        Set the results in the future and mark done
        """
        scan_results = [self.results.get(i, ScanResult()) for i, _ in enumerate(self.jobs)]
        self.future.set_result(scan_results)


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

    def __init__(self, redis: Redis, queue: str, confidence_modifier: Optional[ConfidenceModifier], period: float = .25,
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
            if guid in self.pending_jobs:
                logger.warning('Received duplicate job')

            self.pending_jobs[guid] = pending

    async def __process(self):
        while True:
            # noinspection PyBroadException
            try:
                await self.fetch_results()
                # Don't consumer all the resources for this loop
                await asyncio.sleep(self.period)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception('Exception processing pending jobs')

    async def fetch_results(self):
        """
        Iterates across all jobs and triggers them to self update
        """
        async with self.job_lock:
            jobs = self.pending_jobs.items()

        # This allows interior mutability of the jobs, while not holding the lock.
        results = await asyncio.gather(*[pending_job.fetch_results(self.redis, self.confidence_modifier)
                                         for guid, pending_job in jobs], return_exceptions=True)

        reset = False
        for result in results:
            if isinstance(result, aioredis.RedisError) or isinstance(result, OSError):
                reset = True
                logger.exception("Exception fetching results", exc_info=result)

        if reset and self.reset_callback:
            await self.reset_callback()

        finished_jobs = []
        for guid, job in jobs:
            # Finish anything with True result
            if job.is_done():
                finished_jobs.append((guid, job))

        if finished_jobs:
            await self.__track_finished(finished_jobs)

    async def __track_finished(self, finished_jobs: List[Tuple[str, PendingJob]]):
        """
        Updates the counter of results, and removes the finished jobs from the pending_jobs dict

        :param finished_jobs: List of PendingJobs that are finished
        """
        if not finished_jobs:
            return

        # Update Results counter for scaling
        results_count = sum([len(finished_job.results) for _, finished_job in finished_jobs])
        asyncio.get_event_loop().create_task(self.__update_job_results_counter(results_count))

        # Update Time for scaling
        result_times = [result_time for _, job in finished_jobs for result_time in job.times()]
        result_time_ratio = [result_time for _, job in finished_jobs for result_time in job.time_ratios()]
        asyncio.get_event_loop().create_task(self.__update_job_result_times(result_times, result_time_ratio))

        # Tell Pending job to send results back, and delete
        for guid, finished_job in finished_jobs:
            # Delete pending job
            logger.debug('Removing %s', guid)
            async with self.job_lock:
                if guid in self.pending_jobs:
                    del self.pending_jobs[guid]

    async def __update_job_result_times(self, result_times, result_time_ratio):
        total_time_key = f'{self.queue}_job_completion_time_accum'
        total_time_count_key = f'{self.queue}_job_completion_times_count'
        time_ratio_key = f'{self.queue}_job_completion_time_ratios_accum'
        time_ratio_count_key = f'{self.queue}_job_completion_time_ratios_count'

        transaction = self.redis.multi_exec()

        transaction.incrby(total_time_key, sum(result_times))
        transaction.incrby(total_time_count_key, len(result_times))

        transaction.incrbyfloat(time_ratio_key, sum(result_time_ratio))
        transaction.incrby(time_ratio_count_key, len(result_time_ratio))

        await transaction.execute()

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
