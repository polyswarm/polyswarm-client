import base64
import logging

from polyswarmartifact import ArtifactType
from polyswarmartifact.schema.verdict import Verdict

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult, ScanMode

logger = logging.getLogger(__name__)
EICAR = base64.b64decode(
    b'WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=')


class Scanner(AbstractScanner):

    def __init__(self):
        super(Scanner, self).__init__(ScanMode.SYNC)

    def scan_sync(self, guid, artifact_type, content, metadata, chain):
        """Scan an artifact

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to be scan
            metadata (dict) Dict of metadata for the artifact
            chain (str): Chain we are operating on
        Returns:
            ScanResult: Result of this scan
        """
        metadata = Verdict().set_scanner(operating_system=self.system,
                                         architecture=self.machine)
        if isinstance(content, str):
            content = content.encode()
        if EICAR in content:
            metadata.set_malware_family('Eicar Test File')
            return ScanResult(bit=True, verdict=True, metadata=metadata.json())

        metadata.set_malware_family('')
        return ScanResult(bit=True, verdict=False, metadata=metadata.json())


class Microengine(AbstractMicroengine):
    """
    Microengine which tests for the EICAR test file.

    Args:
        client (`Client`): Client to use
        testing (int): How many test bounties to respond to
        chains (set[str]): Chain(s) to operate on
    """
    def __init__(self, client, scanner=None, **kwargs):
        """Initialize an eicar microengine"""
        scanner = Scanner()
        super().__init__(client, scanner)
