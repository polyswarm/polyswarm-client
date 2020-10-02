import asyncio
import aioredis
import pytest

import psutil

from polyswarmclient import Client
from polyswarmclient.utils import asyncio_stop, asyncio_join


@pytest.fixture()
def redis_uri():
    return 'redis://redis:6379'


@pytest.fixture()
@pytest.mark.asyncio
async def redis_client(event_loop):
    redis = await aioredis.create_redis_pool('redis://redis:6379')
    with await redis as redis_client:
        yield redis_client

    redis.close()
    await redis.wait_closed()


def not_listening_on_port(port):
    return port not in [conn.laddr.port for conn in psutil.net_connections()]


@pytest.fixture()
@pytest.mark.asyncio
def test_client(event_loop):
    client = Client(api_key='0'*32, host='127.0.0.1')
    asyncio.set_event_loop(event_loop)
    event_loop.create_task(client.run_task())
    yield client
    asyncio_stop()
    asyncio_join()
