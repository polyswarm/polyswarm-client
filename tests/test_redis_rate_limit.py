import asyncio

import pytest
from polyswarmclient.ratelimit.redis import RedisRateLimit, SecondlyKeyManager, RedisDailyRateLimit
from worker.base import RateLimitAggregate

from tests.utils.fixtures import not_listening_on_port, redis_client


@pytest.fixture()
@pytest.mark.asyncio
async def daily_limit(event_loop, redis_client):
    daily_limit = RedisRateLimit(redis_client, '', 0)
    yield daily_limit
    daily_limit.redis.close()
    await daily_limit.redis.wait_closed()


@pytest.fixture()
@pytest.mark.asyncio
async def secondly_limit(event_loop, redis_client):
    secondly_limit = RedisRateLimit(redis_client, '', 0, SecondlyKeyManager())
    yield secondly_limit
    secondly_limit.redis.close()
    await secondly_limit.redis.wait_closed()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_peek_works_without_key(daily_limit):
    daily_limit.queue = 'test_peek_works_without_key'
    daily_limit.limit = 1
    await daily_limit.setup()

    assert await daily_limit.use(peek=True)
    assert await daily_limit.redis.get(daily_limit.key) is None


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_peek_works_without_incrementing(daily_limit):
    daily_limit.queue = 'test_peek_works_without_incrementing'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(2):
        await daily_limit.use()

    assert await daily_limit.use(peek=True)
    assert int(await daily_limit.redis.get(daily_limit.key)) == 2


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_peek_false_after_reaching_limit(daily_limit):
    daily_limit.queue = 'test_peek_false_after_reaching_limit'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(10):
        await daily_limit.use()

    assert not await daily_limit.use(peek=True)


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_use_increments(daily_limit):
    daily_limit.queue = 'test_use_increments'
    daily_limit.limit = 10
    await daily_limit.setup()

    assert await daily_limit.use()
    assert int(await daily_limit.redis.get(daily_limit.key)) == 1


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_increment_up_to_limit(daily_limit):
    daily_limit.queue = 'test_increment_up_to_limit'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(10):
        assert await daily_limit.use()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_use_returns_false_after_limit(daily_limit):
    daily_limit.queue = 'test_use_returns_false_after_limit'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(10):
        assert await daily_limit.use()

    assert not await daily_limit.use()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def limit_flips_after_1_second(secondly_limit):
    secondly_limit.queue = 'limit_flips_after_1_second'
    secondly_limit.limit = 1
    await secondly_limit.setup()

    assert await secondly_limit.use()
    assert not await secondly_limit.use()

    await asyncio.sleep(1)

    assert await secondly_limit.use()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_redis_daily_class(event_loop, redis_client):
    daily_limit = RedisDailyRateLimit(redis_client, 'test_redis_daily_class', 10)
    await daily_limit.setup()

    assert await daily_limit.use()
    assert int(await daily_limit.redis.get(daily_limit.key)) == 1
    daily_limit.redis.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_rate_limit_aggregate_counts_all(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_rate_limit_aggregate_counts_all', 1, 1, 1, 1)
    assert await rate_limit.secondly.use(peek=True)
    assert await rate_limit.minutely.use(peek=True)
    assert await rate_limit.hourly.use(peek=True)
    assert await rate_limit.daily.use(peek=True)

    await rate_limit.use()

    assert not await rate_limit.secondly.use(peek=True)
    assert not await rate_limit.minutely.use(peek=True)
    assert not await rate_limit.hourly.use(peek=True)
    assert not await rate_limit.daily.use(peek=True)


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_rate_limit_aggregate_second_exhaust_does_not_effect_minute(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_rate_limit_aggregate_second_exhaust_does_not_effect_minute', 1, 1, 1, 0)

    assert not await rate_limit.use()

    assert not await rate_limit.secondly.use(peek=True)
    assert await rate_limit.minutely.use(peek=True)
    assert await rate_limit.hourly.use(peek=True)
    assert await rate_limit.daily.use(peek=True)
    redis_client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_rate_limit_second_exhaust_fails(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_rate_limit_second_exhaust_fails', 1, 1, 1, 0)

    assert not await rate_limit.use()
    redis_client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_rate_limit_minute_exhaust_fails(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_rate_limit_minute_exhaust_fails', 1, 1, 0, 1)

    assert not await rate_limit.use()
    redis_client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_rate_limit_hour_exhaust_fails(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_rate_limit_hour_exhaust_fails', 1, 0, 1, 1)

    assert not await rate_limit.use()
    redis_client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_rate_limit_daily_exhaust_fails(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_rate_limit_daily_exhaust_fails', 0, 1, 1, 1)

    assert not await rate_limit.use()
    redis_client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_rate_limit_with_some_none(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_rate_limit_with_some_none', 1, None, None, 1)

    assert await rate_limit.use()
    assert not await rate_limit.daily.use(peek=True)
    assert not await rate_limit.secondly.use(peek=True)

    redis_client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_rate_limit_with_all_none(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_rate_limit_with_all_none', None, None, None, None)

    assert await rate_limit.use(peek=True)
    assert await rate_limit.use()

    redis_client.close()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_peek_does_not_use(event_loop, redis_client):
    rate_limit = RateLimitAggregate(redis_client, 'test_peek_does_not_use', 1, None, None, 1)

    assert await rate_limit.use(peek=True)
    assert await rate_limit.use()

    redis_client.close()
