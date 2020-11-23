import aioredis
import aiohttp
import asyncio
import json
import logging
import math
import platform
import signal
import time
import urllib3.util

from aiohttp import ClientSession
from polyswarmclient.ratelimit.abstractratelimit import AbstractRateLimit
from typing import AsyncGenerator, Optional

from polyswarmartifact import DecodeError
from polyswarmclient.liveness.local import LocalLivenessRecorder
from polyswarmclient.exceptions import ApiKeyException, FatalError, ScannerSetupFailedError
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.producer import JobResponse, JobRequest
from polyswarmclient.ratelimit.redis import RedisRateLimit, DailyKeyManager, HourlyKeyManager, \
    MinutelyKeyManager, SecondlyKeyManager
from polyswarmclient.utils import asyncio_join, asyncio_stop, configure_event_loop
from worker.exceptions import ExpiredException

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 5.0


class RateLimitAggregate(AbstractRateLimit):
    daily: Optional[RedisRateLimit]
    hourly: Optional[RedisRateLimit]
    minutely: Optional[RedisRateLimit]
    secondly: Optional[RedisRateLimit]

    def __init__(self, redis, queue, daily_rate_limit, hourly_rate_limit, minutely_rate_limit, secondly_rate_limit):
        self.daily = None
        self.hourly = None
        self.minutely = None
        self.secondly = None

        if daily_rate_limit is not None:
            self.daily = RedisRateLimit(redis, queue, daily_rate_limit, key_manager=DailyKeyManager())

        if hourly_rate_limit is not None:
            self.hourly = RedisRateLimit(redis, queue, hourly_rate_limit, key_manager=HourlyKeyManager())

        if minutely_rate_limit is not None:
            self.minutely = RedisRateLimit(redis, queue, minutely_rate_limit, key_manager=MinutelyKeyManager())

        if secondly_rate_limit is not None:
            self.secondly = RedisRateLimit(redis, queue, secondly_rate_limit, key_manager=SecondlyKeyManager())

    async def use(self, *args, peek=False, **kwargs):
        # Start with fastest rate limit, so we don't consumer slower limits when a faster limit is exhausted
        # But, it will use higher rate limits along with lower rate limits
        for rate_limit in [self.secondly, self.minutely, self.hourly, self.daily]:
            if rate_limit is not None:
                if not await rate_limit.use(*args, peek=peek, **kwargs):
                    return False
        else:
            return True


class OptionalSemaphore(asyncio.Semaphore):
    given_value: int

    def __init__(self, value=1, loop=None):
        self.given_value = value
        try:
            super().__init__(value=value, loop=loop)
        except ValueError:
            # We have handling for values < 1, so we can ignore this value error
            pass

    async def acquire(self):
        if self.given_value > 0:
            await super().acquire()

        return True

    def release(self) -> None:
        if self.given_value > 0:
            super().release()


class Worker:
    def __init__(self, redis_addr, queue, task_count=0, download_limit=0, scan_limit=0, api_key=None, testing=0,
                 scanner=None, scan_time_requirement=0, daily_rate_limit=None, hourly_rate_limit=None,
                 minutely_rate_limit=None, secondly_rate_limit=None, allow_key_over_http=False):
        self.redis_uri = 'redis://' + redis_addr
        self.redis = None
        self.queue = queue
        self.api_key = api_key
        self.testing = testing
        self.scanner = scanner
        self.scan_time_requirement = scan_time_requirement
        self.daily_rate_limit = daily_rate_limit
        self.hourly_rate_limit = hourly_rate_limit
        self.minutely_rate_limit = minutely_rate_limit
        self.secondly_rate_limit = secondly_rate_limit
        self.max_task_count = task_count
        self.current_task_count = 0
        self.task_count_lock = None
        self.download_limit = download_limit
        self.scan_limit = scan_limit
        self.rate_limit_aggregate = None
        self.download_semaphore = None
        self.scan_semaphore = None
        self.tries = 0
        self.finished = False
        self.allow_key_over_http = allow_key_over_http
        # Setup a liveness instance
        self.liveness_recorder = LocalLivenessRecorder()

    def run(self):
        configure_event_loop()
        loop = asyncio.get_event_loop()
        try:
            self.start(loop)
            # This stops any leftover tasks after out main task finishes
            asyncio_stop()
        except asyncio.CancelledError:
            logger.info('Clean exit requested, exiting')
            asyncio_join()
        except Exception:
            logger.exception('Unhandled exception at top level')
            asyncio_stop()
            asyncio_join()

    def start(self, loop: asyncio.AbstractEventLoop):
        loop.run_until_complete(self.setup(loop))
        loop.run_until_complete(self.run_task())

    async def setup(self, loop: asyncio.AbstractEventLoop):
        self.setup_synchronization(loop)
        self.setup_graceful_shutdown(loop)
        await self.setup_liveness(loop)
        await self.setup_redis(loop)

    def setup_synchronization(self, loop: asyncio.AbstractEventLoop):
        self.scan_semaphore = OptionalSemaphore(value=self.scan_limit, loop=loop)
        self.download_semaphore = OptionalSemaphore(value=self.download_limit, loop=loop)
        self.task_count_lock = asyncio.Condition()

    def setup_graceful_shutdown(self, loop: asyncio.AbstractEventLoop):
        # K8 uses SIGTERM on linux and SIGINT and windows
        exit_signal = signal.SIGINT if platform.system() == 'Windows' else signal.SIGTERM
        try:
            loop.add_signal_handler(exit_signal, self.handle_signal)
        except NotImplementedError:
            # Disable graceful exit, but run anyway
            logger.warning('%s does not support graceful shutdown', platform.system())

    def handle_signal(self):
        logger.critical('Received exit signal. Gracefully shutting down.')
        self.finished = True

    async def setup_liveness(self, loop: asyncio.AbstractEventLoop):
        async def advance_liveness_time(liveness):
            while True:
                await liveness.advance_time(round(time.time()))
                await asyncio.sleep(1)

        await self.liveness_recorder.start()
        loop.create_task(advance_liveness_time(self.liveness_recorder))

    async def setup_redis(self, loop: asyncio.AbstractEventLoop):
        self.redis = await aioredis.create_redis_pool(self.redis_uri, loop=loop)
        queue = f'{self.queue}_backend'
        self.rate_limit_aggregate = RateLimitAggregate(self.redis, queue, self.daily_rate_limit, self.hourly_rate_limit, self.minutely_rate_limit, self.secondly_rate_limit)

    async def run_task(self):
        loop = asyncio.get_event_loop()
        conn = aiohttp.TCPConnector(limit=100)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with self.scanner:
                async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
                    async for job in self.get_jobs():
                        loop.create_task(self.process_job(job, session))

        except ScannerSetupFailedError:
            logger.critical('Scanner instance reported unsuccessful setup. Exiting.')
            raise FatalError('Scanner setup failed', 1)

    async def get_jobs(self) -> AsyncGenerator[JobRequest, None]:
        while not self.finished:
            try:
                with await self.redis as redis:
                    async with self.task_count_lock:
                        # Wait for task to complete, if at maximum
                        if 0 < self.max_task_count <= self.current_task_count:
                            await self.task_count_lock.wait()

                        job = await redis.blpop(self.queue, timeout=1)
                        if not job:
                            continue

                        _, job = job
                        job = json.loads(job.decode('utf-8'))
                        logger.info('Received job', extra={'extra': job})
                        self.current_task_count += 1
                    yield JobRequest(**job)
            except OSError:
                logger.exception('Redis connection down')
            except aioredis.errors.ReplyError:
                logger.exception('Redis out of memory')
            except (TypeError, KeyError):
                logger.exception('Invalid job received, ignoring')

    async def process_job(self, job: JobRequest, session: ClientSession):
        remaining_time = 0
        loop = asyncio.get_event_loop()
        try:
            async with self.liveness_recorder.waiting_task(job.key, round(time.time())):
                remaining_time = self.get_remaining_time(job)

                # Don't waste bandwidth and resources downloading files if we hit the rate limit
                if await self.rate_limit_aggregate.use(peek=True):
                    content = await asyncio.wait_for(self.download(job, session), timeout=remaining_time)
                    remaining_time = self.get_remaining_time(job)

                    # Double check there are still scans remaining, and also increment the account just before scanning
                    if await self.rate_limit_aggregate.use():
                        scan_result = await asyncio.wait_for(self.scan(job, content), timeout=remaining_time)
                        response = JobResponse(job.index, scan_result.bit, scan_result.verdict, scan_result.confidence,
                                               scan_result.metadata)
                        loop.create_task(self.respond(job, response))
                    else:
                        self.rate_limit_respond(job)
                else:
                    self.rate_limit_respond(job)

                self.tries = 0
        except OSError:
            logger.exception('Redis connection down')
        except aioredis.errors.ReplyError:
            logger.exception('Redis out of memory')
        except ExpiredException:
            logger.exception('Received expired job', extra={'extra': job.asdict()})
        except aiohttp.ClientResponseError:
            logger.exception('Error fetching artifact', extra={'extra': job.asdict()})
        except DecodeError:
            logger.exception('Error Decoding artifact', extra={'extra': job.asdict()})
        except ApiKeyException:
            logger.exception('Refusing to send API key over insecure transport')
        except asyncio.TimeoutError:
            logger.exception('Timeout processing artifact after %s seconds', remaining_time,
                             extra={'extra': job.asdict()})
        except asyncio.CancelledError:
            logger.exception('Worker shutdown while processing job', extra={'extra': job.asdict()})
        finally:
            async with self.task_count_lock:
                self.current_task_count -= 1
                self.task_count_lock.notify()

    def get_remaining_time(self, job: JobRequest) -> int:
        remaining_time = int(job.ts + job.duration - math.floor(time.time()))
        if remaining_time - self.scan_time_requirement < 0:
            raise ExpiredException()
        return remaining_time

    async def download(self, job: JobRequest, session: ClientSession) -> bytes:
        if not self.is_key_secure(job):
            raise ApiKeyException()

        headers = {'Authorization': self.api_key} if self.api_key is not None else None
        uri = f'{job.polyswarmd_uri}/artifacts/{job.uri}/{job.index}/'
        async with self.download_semaphore:
            response = await session.get(uri, headers=headers)
            response.raise_for_status()
            return await response.read()

    async def scan(self, job: JobRequest, content: bytes) -> ScanResult:
        artifact_type = job.get_artifact_type()
        async with self.scan_semaphore:
            return await self.scanner.scan(job.guid, artifact_type, artifact_type.decode_content(content), job.metadata,
                                           job.chain)

    def rate_limit_respond(self, job: JobRequest):
        loop = asyncio.get_event_loop()
        blank = ScanResult()
        response = JobResponse(job.index, blank.bit, blank.verdict, blank.confidence, blank.metadata)
        loop.create_task(self.respond(job, response))

    async def respond(self, job: JobRequest, response: JobResponse):
        logger.info('Scan results for job %s', job.key, extra={'extra': response.asdict()})
        key = f'{self.queue}_{job.guid}_{job.chain}_results'
        with await self.redis as redis:
            await redis.rpush(key, json.dumps(response.asdict()))

    def is_key_secure(self, job: JobRequest):
        parsed = urllib3.util.parse_url(job.polyswarmd_uri)
        return self.allow_key_over_http or not self.api_key or parsed.scheme == 'https'
