import asyncio
import pytest

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner

from tests.utils.fixtures import test_client


class Microengine(AbstractMicroengine):
    def __init__(self, client, scanner=None, **kwargs):
        super().__init__(client, scanner, **kwargs)


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_stop_calls_scanner_teardown(test_client):
    teardown = asyncio.Event()

    class Scanner(AbstractScanner):

        async def teardown(self):
            teardown.set()

    Microengine(test_client,  scanner=Scanner())
    await test_client.on_stop.run()
    await teardown.wait()
