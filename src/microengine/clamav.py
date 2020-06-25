import clamd
import logging
import os
from io import BytesIO

from polyswarmartifact import ArtifactType
from polyswarmartifact.schema.verdict import Verdict
from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult, ScanMode

logger = logging.getLogger(__name__)

CLAMD_HOST = os.getenv('CLAMD_HOST', 'localhost')
CLAMD_PORT = int(os.getenv('CLAMD_PORT', '3310'))
CLAMD_TIMEOUT = 30.0


class Scanner(AbstractScanner):
    def __init__(self):
        super(Scanner, self).__init__(ScanMode.ASYNC)
        self.clamd = clamd.ClamdAsyncNetworkSocket(CLAMD_HOST, CLAMD_PORT, CLAMD_TIMEOUT)

    async def scan_async(self, guid, artifact_type, content, metadata, chain):
        """Scan an artifact with ClamAV

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to be scan
            metadata (dict) Dict of metadata for the artifact
            chain (str): Chain we are operating on
        Returns:
            ScanResult: Result of this scan
        """
        result = await self.clamd.instream(BytesIO(content))
        stream_result = result.get('stream', [])

        vendor = await self.clamd.version()
        metadata = Verdict().set_scanner(operating_system=self.system,
                                         architecture=self.machine,
                                         vendor_version=vendor.strip('\n'))
        if len(stream_result) >= 2 and stream_result[0] == 'FOUND':
            metadata.set_malware_family(stream_result[1].strip('\n'))
            return ScanResult(bit=True, verdict=True, confidence=1.0, metadata=metadata.json())

        metadata.set_malware_family('')
        return ScanResult(bit=True, verdict=False, metadata=metadata.json())


class Microengine(AbstractMicroengine):
    """
    Microengine which scans samples through clamd.

    Args:
        client (`Client`): Client to use
        testing (int): How many test bounties to respond to
        chains (set[str]): Chain(s) to operate on
    """

    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None, **kwargs):
        """Initialize a ClamAV microengine"""
        if artifact_types is None:
            artifact_types = [ArtifactType.FILE]
        scanner = Scanner()
        super().__init__(client, testing, scanner, chains, artifact_types, **kwargs)
