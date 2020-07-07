import aioredis
import asyncio
import base64
import pytest
import tempfile
import sys
import base58
import json
import os
import psutil
import random
from web3 import Web3
from aioresponses import aioresponses
from asynctest.mock import patch

from polyswarmclient import Client


# THE FOLLOWING KEY IS FOR TESTING PURPOSES ONLY
from polyswarmclient.utils import asyncio_stop, asyncio_join

TESTKEY = base64.b64decode(
    'eyJhZGRyZXNzIjoiZWNhZDBhZmNhYjgyZjhlNGExY2YwZTk1MjUyNjUzNzFiNTg2ZWZiZCIsImNy'
    'eXB0byI6eyJjaXBoZXIiOiJhZXMtMTI4LWN0ciIsImNpcGhlcnRleHQiOiJmZTczMWViYzllMDFh'
    'ZWE0ZGI5NGEzYjM4YzkwYjYwOGExNjQ4N2ZkYzgzMDcyYzI5NWU3YTYxMWQ0MmIwNzdmIiwiY2lw'
    'aGVycGFyYW1zIjp7Iml2IjoiZmYzODNhYWY3MDY5NzgxYjJiMDM4M2NkZGE2Nzk2MTQifSwia2Rm'
    'Ijoic2NyeXB0Iiwia2RmcGFyYW1zIjp7ImRrbGVuIjozMiwibiI6MjYyMTQ0LCJwIjoxLCJyIjo4'
    'LCJzYWx0IjoiMjc1OGU1ODNlOTViNmMwMDQwMDJlMDcwNjBjNjJiZWY2NmJiYjVjMzE2ZWU3MGE3'
    'MDBmMzM5NDc1NTRiZjVlYyJ9LCJtYWMiOiIxYzI2ZGI5YWIxYzQxYTJjM2FjNTZlZDg2OTQ0M2I3'
    'MDMzYjBlZDVlNmQ4MDVmNmExM2UwYWZjMGU5MGU1MjMzIn0sImlkIjoiMDhiMjUzODctYTZhYi00'
    'NGUwLThmMTAtOGU5MzI4OTM3NjZmIiwidmVyc2lvbiI6M30=')

TESTKEY_PASSWORD = 'password'


def success(result):
    return json.dumps({'status': 'OK', 'result': result})


def failure(errors):
    return json.dumps({'status': 'FAIL', 'errors': errors})


def event(event, data, block_number=0, txhash='0x0'):
    return json.dumps({'event': event, 'data': data, 'block_number': block_number, 'txhash': txhash})


def random_address():
    return Web3().toChecksumAddress(os.urandom(20).hex())


def random_bitset():
    x = random.getrandbits(256)
    return [(1 << i) & x != 0 for i in range(256)]


def random_ipfs_uri():
    return base58.b58encode(b'\x12' + os.urandom(32)).decode('utf-8')


class WebsocketMockManager(object):
    def __init__(self):
        self.connect_patch = patch('websockets.connect', new_callable=lambda: self)
        self.open_sockets = {}

    # TODO: Support other args
    def __call__(self, uri):
        if uri in self.open_sockets:
            return self.open_sockets.get(uri)

        ret = WebsocketMock()
        self.open_sockets[uri] = ret
        return ret

    def start(self):
        self.connect_patch.start()

    def stop(self):
        self.connect_patch.stop()

        for _, s in self.open_sockets.items():
            s.close()

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class WebsocketMock(object):
    def __init__(self):
        self.closed = False
        self.queue = asyncio.Queue()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def close(self):
        self.closed = True

    async def recv(self):
        return await self.queue.get()

    async def send(self, data):
        await self.queue.put(data)


class MockClient(Client):
    def __init__(self):
        # write will complain about permissions if `NamedTemporaryFile' is
        # delete=True under windows.
        do_delete = sys.platform != 'win32'
        with tempfile.NamedTemporaryFile(delete=do_delete) as tf:
            tf.write(TESTKEY)
            tf.flush()

            super().__init__('localhost', tf.name, TESTKEY_PASSWORD, insecure_transport=True)

        self.http_mock = aioresponses()

        self.__ws_mock_manager = WebsocketMockManager()

        self.home_ws_mock = None
        self.side_ws_mock = None

        self.home_init_done = asyncio.Event()
        self.side_init_done = asyncio.Event()

        self.on_run.register(self.__handle_run)

    async def __handle_run(self, chain):
        if chain == 'home':
            self.home_init_done.set()
        elif chain == 'side':
            self.side_init_done.set()
        else:
            raise ValueError('Invalid chain running')

    async def wait_for_running(self):
        await asyncio.wait([self.home_init_done.wait(),  self.side_init_done.wait()])

    def start(self):
        self.http_mock.start()
        self.__ws_mock_manager.start()

        # This is needed to get us through initialization
        self.http_mock.options('http://localhost/wallets/', status=404)
        self.http_mock.get(self.url_with_parameters('/nonce', chain='home'), body=success(0))
        self.http_mock.get(self.url_with_parameters('/nonce', chain='side'), body=success(0))

        bounty_parameters = {
            "arbiter_lookback_range": 100,
            "arbiter_vote_window": 100,
            "assertion_bid_minimum": 62500000000000000,
            "assertion_bid_maximum": 1000000000000000000,
            "assertion_fee": 62500000000000000,
            "assertion_reveal_window": 25,
            "bounty_amount_minimum": 62500000000000000,
            "bounty_fee": 62500000000000000,
            "max_duration": 100
        }

        for _ in range(2):
            self.http_mock.get(self.url_with_parameters('/bounties/parameters', chain='home'),
                               body=success(bounty_parameters))
            self.http_mock.get(self.url_with_parameters('/bounties/parameters', chain='side'),
                               body=success(bounty_parameters))

        staking_parameters = {
            "maximum_stake": 100000000000000000000000000,
            "minimum_stake": 10000000000000000000000000,
            "vote_ratio_denominator": 10,
            "vote_ratio_numerator": 9
        }

        for _ in range(2):
            self.http_mock.get(self.url_with_parameters('/staking/parameters', chain='home'),
                               body=success(staking_parameters))
            self.http_mock.get(self.url_with_parameters('/staking/parameters', chain='side'),
                               body=success(staking_parameters))

        asyncio.get_event_loop().create_task(self.run_task({'side', 'home'}))
        asyncio.get_event_loop().run_until_complete(self.wait_for_running())

        self.home_ws_mock = self.__ws_mock_manager.open_sockets['ws://localhost/events/?chain=home']
        self.side_ws_mock = self.__ws_mock_manager.open_sockets['ws://localhost/events/?chain=side']

    def stop(self):
        self.http_mock.stop()
        self.__ws_mock_manager.stop()

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def url_with_parameters(self, path, params=None, chain=None):
        # This is for tests, so don't bother grabbing the lock, we know what tasks are running
        if params is None:
            params = {}

        params.update({'account': self.account})

        if chain is not None:
            params['chain'] = chain

        qs = '&'.join('{0}={1}'.format(k, v) for k, v in sorted(params.items()))
        return 'http://localhost{0}?{1}'.format(path, qs)


@pytest.fixture()
def mock_client(event_loop):
    asyncio.set_event_loop(event_loop)
    client = MockClient()
    client.start()
    yield client
    client.stop()
    asyncio_stop()
    asyncio_join()


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

