import asyncio
import asynctest
import json
import logging
import time
import pytest

from asyncio import Future

from polyswarmclient.producer import JobProcessor, JobRequest, JobResponse
from polyswarmartifact import ArtifactType
from tests.utils.fixtures import not_listening_on_port, redis_client

logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
@pytest.mark.asyncio
async def job_processor(event_loop, redis_client) -> JobProcessor:
    asyncio.set_event_loop(event_loop)
    async with JobProcessor(redis_client, 'QUEUE', None) as processor:
        yield processor


@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
@pytest.mark.timeout(3)
@pytest.mark.asyncio
async def test_result_values_in_redis(redis_client, job_processor):
    job = JobRequest('polyswarmd-addr', 'guid', 0, 'uri', ArtifactType.FILE.value, 10, None, 'side', int(time.time()))
    future = Future()
    await job_processor.register_jobs('guid', 'test_result_values_in_redis', [job], future)

    # Add response before waiting on the future
    job_response = JobResponse(index=0, bit=True, verdict=False, confidence=.5, metadata='')

    await asyncio.sleep(1)
    await redis_client.rpush('test_result_values_in_redis', json.dumps(job_response.asdict()))
    await future

    # wait for the loop to finish in job_processor
    await asyncio.sleep(1)

    assert float(await redis_client.get('QUEUE_job_completion_time_accum')) > 0
    assert int(await redis_client.get('QUEUE_job_completion_times_count')) == 1
    assert 0 < float(await redis_client.get('QUEUE_job_completion_time_ratios_accum')) < 1
    assert int(await redis_client.get('QUEUE_job_completion_time_ratios_count')) == 1
    assert int(await redis_client.get('QUEUE_scan_result_counter')) == 1


@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
@pytest.mark.timeout(3)
@pytest.mark.asyncio
async def test_results_after_complete(redis_client, job_processor):
    job = JobRequest('polyswarmd-addr', 'guid', 0, 'uri', ArtifactType.FILE.value, 10, None, 'side', int(time.time()))
    future = Future()
    await job_processor.register_jobs('guid', 'test_results_after_complete', [job], future)

    # Add response before waiting on the future
    job_response = JobResponse(index=0, bit=True, verdict=False, confidence=.5, metadata='')

    await redis_client.rpush('test_results_after_complete', json.dumps(job_response.asdict()))
    scan_results = await future

    assert scan_results
    assert scan_results[0].bit
    assert not scan_results[0].verdict
    assert scan_results[0].confidence == .5


@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_results_multiple_results(redis_client, job_processor):
    # Add responses before pushing job
    for i in range(2):
        job_response = JobResponse(index=i, bit=True, verdict=False, confidence=.5, metadata='')
        await redis_client.rpush('test_results_multiple_results', json.dumps(job_response.asdict()))

    future = Future()
    jobs = [JobRequest('polyswarmd-addr', 'guid', i, 'uri', ArtifactType.FILE.value, 1, None, 'side', int(time.time()))
            for i in range(2)]
    await job_processor.register_jobs('guid', 'test_results_multiple_results', jobs, future)

    scan_results = await future

    assert len(scan_results) == 2
    assert scan_results[0].bit


@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_results_after_timeout(redis_client, job_processor):
    # Add response before registering
    job_response = JobResponse(index=0, bit=True, verdict=False, confidence=.5, metadata='')
    await redis_client.rpush('test_results_after_timeout', json.dumps(job_response.asdict()))

    jobs = [JobRequest('polyswarmd-addr', 'guid', i, 'uri', ArtifactType.FILE.value, 1, None, 'side', int(time.time()))
            for i in range(1)]

    future = Future()
    await job_processor.register_jobs('guid', 'test_results_after_timeout', jobs, future)

    scan_results = await future

    assert len(scan_results) == 1
    assert scan_results[0].bit


@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_redis_error_recovery(job_processor):
    reset_redis = asynctest.CoroutineMock()
    job_processor.reset_callback = reset_redis
    job = JobRequest('polyswarmd-addr', 'guid', 0, 'uri', ArtifactType.FILE.value, 1, None, 'side', int(time.time()))

    future = Future()
    job_processor.stop()
    job_processor.redis.close()
    await job_processor.redis.wait_closed()
    await job_processor.register_jobs('guid', 'test_redis_error_recovery', [job], future)
    await job_processor.fetch_results()

    reset_redis.assert_called()


@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
@pytest.mark.timeout(15)
@pytest.mark.asyncio
async def test_results_thousands_pending_jobs(redis_client, job_processor):
    count = 10_000
    futures = []

    def create_job(i):
        return JobRequest('polyswarmd-addr', f'guid:{i}', 0, 'uri', ArtifactType.FILE.value, 19, None, 'side', int(time.time()))

    def create_future():
        future = Future()
        futures.append(future)
        return future

    await asyncio.gather(*[job_processor.register_jobs(f'guid:{i}', f'test_results_thousands_pending_jobs:{i}', [create_job(i)], create_future()) for i in range(count)])

    job_response = JobResponse(index=0, bit=True, verdict=False, confidence=.5, metadata='')
    await asyncio.gather(*[redis_client.rpush(f'test_results_thousands_pending_jobs:{i}', json.dumps(job_response.asdict())) for i in range(count)])

    aggregated_scan_results = await asyncio.gather(*futures)

    assert len(aggregated_scan_results) == count

    assert all([scan_results[0].bit for scan_results in aggregated_scan_results])
