import asyncio
import logging
import json

from polyswarmartifact import ArtifactType
from polyswarmartifact.schema.verdict import Verdict

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult
from microengine.clamav import Scanner as ClamavScanner
from microengine.yara import Scanner as YaraScanner

logger = logging.getLogger(__name__)
BACKENDS = [ClamavScanner, YaraScanner]


class Scanner(AbstractScanner):
    def __init__(self):
        super(Scanner, self).__init__()
        self.backends = [cls() for cls in BACKENDS]

    async def scan(self, guid, artifact_type, content, metadata, chain):
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
        results = await asyncio.gather(
            *[backend.scan(guid, artifact_type, content, metadata, chain) for backend in self.backends]
        )

        # Unpack the results
        bits = [r.bit for r in results]
        verdicts = [r.verdict for r in results]
        confidences = [r.confidence for r in results]
        metadatas = [r.metadata for r in results]

        asserted_confidences = [c for b, c in zip(bits, confidences) if b]
        avg_confidence = sum(asserted_confidences) / len(asserted_confidences)

        # author responsible for distilling multiple metadata values into a value for ScanResult
        metadata = metadatas[0]
        try:
            metadatas = [json.loads(metadata) for metadata in metadatas
                         if metadata and Verdict.validate(json.loads(metadata))]
            if metadatas:
                metadata = Verdict().set_malware_family(metadatas[0].get('malware_family', '')).json()
        except json.JSONDecodeError:
            logger.exception(f'Error decoding sub metadata')

        return ScanResult(bit=any(bits), verdict=any(verdicts), confidence=avg_confidence, metadata=metadata)


class Microengine(AbstractMicroengine):
    """Microengine which aggregates multiple sub-microengines"""

    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None, **kwargs):
        """Initialize a multi-backend microengine

        Args:
            client (polyswarmclient.Client): Client to use
            testing (int): How many test bounties to respond to
            chains (set[str]): Chain(s) to operate on
            artifact_types (list(ArtifactType)): List of artifact types you support
        """
        if artifact_types is None:
            artifact_types = [ArtifactType.FILE]
        scanner = Scanner()
        super().__init__(client, testing, scanner, chains, artifact_types, **kwargs)
