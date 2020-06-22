import logging
import os
import platform
import yara

from polyswarmartifact import ArtifactType
from polyswarmartifact.schema.verdict import Verdict
from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult, ScanMode

logger = logging.getLogger(__name__)  # Initialize logger
RULES_DIR = os.getenv('RULES_DIR', 'docker/yara-rules')


class Scanner(AbstractScanner):

    def __init__(self):
        super(Scanner, self).__init__(ScanMode.SYNC)
        self.rules = yara.compile(os.path.join(RULES_DIR, 'malware/MALW_Eicar'))

    def scan_sync(self, guid, artifact_type, content, metadata, chain):
        """Scan an artifact with Yara.

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to be scan
            metadata (dict) Dict of metadata for the artifact
            chain (str): Chain we are operating on

        Returns:
            ScanResult: Result of this scan
        """
        matches = self.rules.match(data=content)
        metadata = Verdict().set_scanner(operating_system=self.system,
                                         architecture=self.machine,
                                         vendor_version=yara.__version__)
        if matches:
            # author responsible for distilling multiple metadata values into a value for ScanResult
            metadata.set_malware_family(matches[0].rule)
            return ScanResult(bit=True, verdict=True, metadata=metadata.json())

        metadata.set_malware_family('')
        return ScanResult(bit=True, verdict=False, metadata=metadata.json())


class Microengine(AbstractMicroengine):
    """Microengine which matches samples against yara rules"""

    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None, **kwargs):
        """Initialize a Yara microengine

        Args:
            client (`Client`): Client to use
            testing (int): How many test bounties to respond toq
            chains (set[str]): Chain(s) to operate on
            artifact_types (list(ArtifactType)): List of artifact types you support
        """
        if artifact_types is None:
            artifact_types = [ArtifactType.FILE]
        scanner = Scanner()
        super().__init__(client, testing, scanner, chains, artifact_types, **kwargs)
