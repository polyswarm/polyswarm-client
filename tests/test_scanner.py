import asyncio
import time
import pytest
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult, ScanMode


@pytest.mark.asyncio
async def test_scan_routes_based_on_scan_mode():

    class Scanner(AbstractScanner):
        def __init__(self, mode):
            super().__init__(mode)

        def scan_sync(self, guid, artifact_type, content, metadata, chain):
            return ScanResult(verdict=True)

        async def scan_async(self, guid, artifact_type, content, metadata, chain):
            return ScanResult(verdict=False)

    scanner = Scanner(mode=ScanMode.SYNC)
    result = await scanner.scan(None, None, None, None, None)

    assert result.verdict

    scanner = Scanner(mode=ScanMode.ASYNC)
    result = await scanner.scan(None, None, None, None, None)
    assert not result.verdict


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_sync_scan_completes():

    class Scanner(AbstractScanner):
        def __init__(self):
            super().__init__(ScanMode.SYNC)

        def scan_sync(self, guid, artifact_type, content, metadata, chain):
            time.sleep(2)
            return ScanResult(verdict=True)

    scanner = Scanner()
    results = await asyncio.gather(*[scanner.scan(None, None, None, None, None)] * 2)

    for result in results:
        assert result.verdict


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_async_scan_completes():

    class Scanner(AbstractScanner):
        def __init__(self):
            super().__init__(ScanMode.ASYNC)

        async def scan_async(self, guid, artifact_type, content, metadata, chain):
            await asyncio.sleep(2)
            return ScanResult(verdict=True)

    scanner = Scanner()
    results = await asyncio.gather(*[scanner.scan(None, None, None, None, None)] * 2)

    for result in results:
        assert result.verdict


@pytest.mark.asyncio
async def test_overwrite_scan_still_works(mocker):
    class Scanner(AbstractScanner):
        async def scan(self, guid, artifact_type, content, metadata, chain):
            return ScanResult(bit=True)

    # Make sure deprecation warning is triggered
    mocked_warn = mocker.patch('warnings.warn')

    scanner = Scanner()
    result = await scanner.scan(None, None, None, None, None)
    assert result.bit
    mocked_warn.assert_called_once()


