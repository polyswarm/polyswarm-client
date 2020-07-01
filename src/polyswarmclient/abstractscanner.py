import asyncio
import enum
import logging
import platform
import warnings
from concurrent.futures import Executor
from typing import Optional

from polyswarmartifact.schema.verdict import Verdict
from polyswarmclient.exceptions import ScannerSetupFailedError

logger = logging.getLogger(__name__)  # Initialize logger


class ScanResult(object):
    """Results from scanning one artifact"""

    def __init__(self, bit=False, verdict=False, confidence=1.0, metadata=Verdict().set_malware_family('').json()):
        """Report the results from scanning one artifact

        Args:
            bit (bool): Are we asserting on this artifact
            verdict (bool): Is this artifact malicious (True) or benign (False)
            confidence (float): How confident are we in our verdict ranging from 0.0 to 1.0
            metadata (json str): Optional metadata from the scan
        """
        self.bit = bit
        self.verdict = verdict
        self.confidence = confidence
        self.metadata = metadata

    def __repr__(self):
        return '<ScanResult bit={}, verdict={}, confidence={}, metadata={}>'.format(self.bit, self.verdict,
                                                                                    self.confidence, self.metadata)


class ScanMode(enum.Enum):
    """
    Denote whether the Scanner is using asynchronous or synchronous scan
    """
    SYNC = 0
    ASYNC = 1


class AbstractScanner:
    """
    Base `Scanner` class. To be overwritten with other scanning logic.

    This class offers two scan options, which can be specified by passing a ScanMode enum value as `mode`.
    It uses asynchronous scan by default.

    The function `scan_async` is a coroutine function where everything called from this function must be async compatible,
    That means it uses only non-blocking IO, and runs nothing cpu-bound, like hash functions.

    The function `scan_sync` is a synchronous function where anything goes.
    It is called in a ThreadPoolExecutor so it is compatible with the worker that uses asyncio.

    Overwriting `scan` directly is deprecated.
    """
    def __init__(self, mode: ScanMode = ScanMode.ASYNC):
        """
        :param mode: ScanMode determines sync or async execution
        """
        self.mode = mode
        self.system = platform.system()
        self.machine = platform.machine()

        if self.__class__.scan != AbstractScanner.scan:
            warnings.warn("Implementing `scan()` is deprecated. Use `scan_async` for asynchronous scan implementations",
                          DeprecationWarning)

    async def setup(self):
        """Override this method to implement custom setup logic.

        This is run immediately after the Scanner class is instantiated and before any calls to the scan() method.
        This can be called multiple times, due to exception handling restarting the worker/microengine/arbiter

        Returns:
            status (bool): Did setup complete successfully?
        """
        return True

    async def teardown(self):
        """
        Override this method to do any cleanup when the scanner is being shut down.

        This can be called multiple times, due to exception handling restarting the worker/microengine/arbiter
        There is an expectation that calling `setup()` again will put the AbstractScanner implementation back into working order
        """
        pass

    async def scan(self, guid, artifact_type, content, metadata, chain):

        if self.mode == ScanMode.ASYNC:
            return await self.scan_async(guid, artifact_type, content, metadata, chain)
        elif self.mode == ScanMode.SYNC:
            return await self.__execute_scan_sync(guid, artifact_type, content, metadata, chain)
        else:
            raise ValueError('Invalid scan mode')

    async def scan_async(self, guid, artifact_type, content, metadata, chain):
        """Override this to implement custom asynchronous scanning logic

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to scan
            metadata (dict): Metadata dict from the ambassador
            chain (str): What chain are we operating on
        Returns:
            ScanResult: Result of this scan
        """
        raise NotImplementedError("Must implement scan_async when using ScanMode.ASYNC")

    async def __execute_scan_sync(self, guid, artifact_type, content, metadata, chain):
        loop = asyncio.get_event_loop()
        executor = self.get_executor()
        if executor:
            with executor as pool:
                return await loop.run_in_executor(pool, self.scan_sync, guid, artifact_type, content, metadata, chain)
        else:
            return await loop.run_in_executor(None, self.scan_sync, guid, artifact_type, content, metadata, chain)

    def get_executor(self) -> Optional[Executor]:
        return None

    def scan_sync(self, guid, artifact_type, content, metadata, chain):
        """Override this to implement custom synchronous scanning logic

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to scan
            metadata (dict): Metadata dict from the ambassador
            chain (str): What chain are we operating on
        Returns:
            ScanResult: Result of this scan
        """
        raise NotImplementedError("Must implement scan_sync when using ScanMode.SYNC")

    async def __aenter__(self):
        if not await self.setup():
            raise ScannerSetupFailedError
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.teardown()
