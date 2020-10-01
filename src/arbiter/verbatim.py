import asyncio

import base64
import sqlite3
import hashlib
import logging
import os

from polyswarmartifact import ArtifactType

from polyswarmclient.abstractarbiter import AbstractArbiter
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.corpus import DownloadToFileSystemCorpus

logger = logging.getLogger(__name__)  # Initialize logger
ARTIFACT_DIRECTORY = os.getenv('ARTIFACT_DIRECTORY', 'docker/artifacts')
EICAR = base64.b64decode(
    b'WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=')


class Arbiter(AbstractArbiter):
    """Arbiter which matches hashes to a database of known samples"""

    def __init__(self, client, **kwargs):
        """Initialize a verbatim arbiter"""
        super().__init__(client, None, **kwargs)

        db_pth = os.path.join(ARTIFACT_DIRECTORY, 'truth.db')

        if os.getenv('MALICIOUS_BOOTSTRAP_URL'):
            d = DownloadToFileSystemCorpus(base_dir=ARTIFACT_DIRECTORY)
            d.download_truth()
            self.conn = sqlite3.connect(d.truth_db_pth)
        else:
            self.conn = sqlite3.connect(db_pth)

    async def scan(self, guid, artifact_type, content, metadata, chain):
        """Match hash of an artifact with our database

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to be scan
            metadata (dict): Metadata blob for this artifact
            chain (str): Chain sample is being sent from
        Returns:
            ScanResult: Result of this scan
        """
        loop = asyncio.get_event_loop()
        sha256 = await loop.run_in_executor(None, self.hash_content, content)

        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM files WHERE name=?', (sha256,))
        row = cursor.fetchone()

        bit = row is not None
        vote = row is not None and row[1] == 1
        vote = vote or EICAR in content

        return ScanResult(bit, vote)

    @staticmethod
    def hash_content(content):
        return hashlib.sha256(content).hexdigest()
