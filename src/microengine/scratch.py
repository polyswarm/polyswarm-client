import logging

from polyswarmartifact import ArtifactType

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult, ScanMode

logger = logging.getLogger(__name__)  # Initialize logger


class Scanner(AbstractScanner):

    def __init__(self):
        super(Scanner, self).__init__()

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
        return ScanResult()

    async def scan_async(self, guid, artifact_type, content, metadata, chain):
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
        return ScanResult()


class Microengine(AbstractMicroengine):
    """
    Scratch microengine is the same as the default behavior.

    Args:
        client (`Client`): Client to use
        testing (int): How many test bounties to respond to
        chains (set[str]): Chain(s) to operate on
    """
    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None, **kwargs):
        """Initialize Scanner"""
        if artifact_types is None:
            artifact_types = [ArtifactType.FILE]
        scanner = Scanner()
        super().__init__(client, testing, scanner, chains, artifact_types, **kwargs)
