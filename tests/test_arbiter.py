import asyncio
import pytest
from polyswarmclient.abstractarbiter import AbstractArbiter
from polyswarmclient.abstractscanner import AbstractScanner

from tests.utils.fixtures import mock_client


class Arbiter(AbstractArbiter):
    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None, **kwargs):
        super().__init__(client, testing, scanner, chains, artifact_types, **kwargs)


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_stop_calls_scanner_teardown(mock_client):
    teardown = asyncio.Event()

    class Scanner(AbstractScanner):

        async def teardown(self):
            teardown.set()

    Arbiter(mock_client, scanner=Scanner())
    await mock_client.on_stop.run()
    await teardown.wait()
