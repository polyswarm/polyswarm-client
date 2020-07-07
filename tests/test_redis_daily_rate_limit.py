import pytest
from polyswarmclient.ratelimit.redis import RedisDailyRateLimit
from tests.utils.fixtures import not_listening_on_port, redis_client


@pytest.fixture()
@pytest.mark.asyncio
async def daily_limit(event_loop, redis_client):
    daily_limit = RedisDailyRateLimit(redis_client, '', 0)
    yield daily_limit
    daily_limit.redis.close()
    await daily_limit.redis.wait_closed()


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_peek_works_without_key(daily_limit):
    daily_limit.queue = 'test_peek_works_without_key'
    daily_limit.limit = 1
    await daily_limit.setup()

    assert await daily_limit.use(peek=True)
    assert await daily_limit.redis.get(daily_limit.daily_key) is None


@pytest.mark.asyncio
@pytest.mark.skipif(not_listening_on_port(6379), reason='Redis is not running')
async def test_peek_works_without_incrementing(daily_limit):
    daily_limit.queue = 'test_peek_works_without_incrementing'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(2):
        await daily_limit.use()

    assert await daily_limit.use(peek=True)
    assert int(await daily_limit.redis.get(daily_limit.daily_key)) == 2


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
    assert int(await daily_limit.redis.get(daily_limit.daily_key)) == 1


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
