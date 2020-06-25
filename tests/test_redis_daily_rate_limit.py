import platform
import pytest
from polyswarmclient.ratelimit.redis import RedisDailyRateLimit


@pytest.fixture()
def redis_uri():
    return 'redis://redis:6379'


@pytest.fixture()
@pytest.mark.asyncio
async def daily_limit(event_loop, redis_uri):
    daily_limit = RedisDailyRateLimit(redis_uri, '', 0)
    yield daily_limit
    daily_limit.redis.close()
    await daily_limit.redis.wait_closed()


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system().lower() == 'windows', reason='ClamAV does not run on windows')
async def test_peek_works_without_key(daily_limit):
    daily_limit.queue = 'test_peek_works_without_key'
    daily_limit.limit = 1
    await daily_limit.setup()

    assert await daily_limit.use(peek=True)
    assert await daily_limit.redis.get(daily_limit.daily_key) is None


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system().lower() == 'windows', reason='ClamAV does not run on windows')
async def test_peek_works_without_incrementing(daily_limit):
    daily_limit.queue = 'test_peek_works_without_incrementing'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(2):
        await daily_limit.use()

    assert await daily_limit.use(peek=True)
    assert int(await daily_limit.redis.get(daily_limit.daily_key)) == 2


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system().lower() == 'windows', reason='ClamAV does not run on windows')
async def test_peek_false_after_reaching_limit(daily_limit):
    daily_limit.queue = 'test_peek_false_after_reaching_limit'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(10):
        await daily_limit.use()

    assert not await daily_limit.use(peek=True)


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system().lower() == 'windows', reason='ClamAV does not run on windows')
async def test_use_increments(daily_limit):
    daily_limit.queue = 'test_use_increments'
    daily_limit.limit = 10
    await daily_limit.setup()

    assert await daily_limit.use()
    assert int(await daily_limit.redis.get(daily_limit.daily_key)) == 1


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system().lower() == 'windows', reason='ClamAV does not run on windows')
async def test_increment_up_to_limit(daily_limit):
    daily_limit.queue = 'test_increment_up_to_limit'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(10):
        assert await daily_limit.use()


@pytest.mark.asyncio
@pytest.mark.skipif(platform.system().lower() == 'windows', reason='ClamAV does not run on windows')
async def test_use_returns_false_after_limit(daily_limit):
    daily_limit.queue = 'test_use_returns_false_after_limit'
    daily_limit.limit = 10
    await daily_limit.setup()

    for _ in range(10):
        assert await daily_limit.use()

    assert not await daily_limit.use()
