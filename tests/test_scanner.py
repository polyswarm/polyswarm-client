import asyncio
from concurrent.futures import Executor
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Optional
import time
import pytest
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult, ScanMode


class DefaultScanner(AbstractScanner):

    def __init__(self, mode=ScanMode.ASYNC, sleep=0):
        super().__init__(mode)
        self.sleep = sleep

    def scan_sync(self, guid, artifact_type, content, metadata, chain):
        time.sleep(self.sleep)
        return ScanResult(verdict=True)

    async def scan_async(self, guid, artifact_type, content, metadata, chain):
        time.sleep(self.sleep)
        return ScanResult(verdict=False)


class ThreadPoolScanner(DefaultScanner):

    def get_executor(self) -> Optional[Executor]:
        return ThreadPoolExecutor(max_workers=1)


class ProcessPoolScanner(DefaultScanner):

    def get_executor(self) -> Optional[Executor]:
        return ProcessPoolExecutor(max_workers=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("scanner_class", [ProcessPoolScanner, ThreadPoolScanner, DefaultScanner])
async def test_scan_routes_based_on_scan_mode(scanner_class):
    scanner = scanner_class(mode=ScanMode.SYNC)
    result = await scanner.scan(None, None, None, None, None)

    assert result.verdict

    scanner = scanner_class(mode=ScanMode.ASYNC)
    result = await scanner.scan(None, None, None, None, None)
    assert not result.verdict


@pytest.mark.asyncio
@pytest.mark.timeout(3)
@pytest.mark.parametrize("scanner_class", [ThreadPoolScanner, DefaultScanner])
async def test_sync_scan_completes(scanner_class):
    scanner = scanner_class(mode=ScanMode.SYNC, sleep=2)
    results = await asyncio.gather(*[scanner.scan(None, None, None, None, None)] * 2)

    for result in results:
        assert result.verdict


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_sync_scan_completes_process():
    scanner = ProcessPoolScanner(mode=ScanMode.SYNC)
    results = await asyncio.gather(*[scanner.scan(None, None, None, None, None)] * 2)

    for result in results:
        assert result.verdict


@pytest.mark.asyncio
@pytest.mark.timeout(3)
@pytest.mark.parametrize("scanner_class", [ProcessPoolScanner, ThreadPoolScanner, DefaultScanner])
async def test_async_scan_completes(scanner_class):
    scanner = scanner_class(mode=ScanMode.ASYNC)
    results = await asyncio.gather(*[scanner.scan(None, None, None, None, None)] * 2)

    for result in results:
        assert not result.verdict


def test_overwrite_scan_still_works(mocker):
    class Scanner(AbstractScanner):
        async def scan(self, guid, artifact_type, content, metadata, chain):
            return ScanResult(bit=True)

    # Make sure deprecation warning is triggered
    mocked_warn = mocker.patch('warnings.warn')

    scanner = Scanner()
    result = asyncio.get_event_loop().run_until_complete(scanner.scan(None, None, None, None, None))
    assert result.bit
    mocked_warn.assert_called()


@pytest.mark.asyncio
@pytest.mark.timeout(3)
async def test_scanner_context_manager():
    setup = asyncio.Event()
    teardown = asyncio.Event()

    class Scanner(AbstractScanner):
        async def setup(self):
            setup.set()
            return True

        async def teardown(self):
            teardown.set()

    async with Scanner():
        await setup.wait()

    await teardown.wait()
