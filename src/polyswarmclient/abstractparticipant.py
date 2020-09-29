import aioredis
import aiohttp
import asyncio
import json
import logging

from polyswarmartifact import ArtifactType, DecodeError
from polyswarmartifact.schema import FileArtifact, URLArtifact

from polyswarmclient import Client
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.exceptions import FatalError
from polyswarmclient.server.events import Bounty, ScanResultRequest

logger = logging.getLogger(__name__)


class AbstractParticipant(object):
    def __init__(self, client, scanner=None):
        self.client = client
        self.scanner = scanner
        self.client.on_run.register(self.__handle_run)
        self.client.on_stop.register(self.__handle_stop)
        self.client.on_new_bounty.register(self.__handle_new_bounty)

    @classmethod
    def connect(cls, host, port, api_key=None, scanner=None, **kwargs):
        """Connect the Microengine to a Client.

        Args:
            host (str): Host for the webhook
            port (str): Port to listen for webhooks
            api_key (str): Your PolySwarm API key.
            scanner (Scanner): `Scanner` instance to use.

        Returns:
            AbstractMicroengine: Microengine instantiated with a Client.
        """
        client = Client(api_key, host, port)
        return cls(client, scanner)

    def run(self):
        """
        Run the `Client` on the Microengine's chains.
        """
        self.client.run()

    async def __handle_run(self, chain):
        """Perform setup required once on correct loop

        Args:
            chain (str): Chain we are operating on.
        """
        self.bounties_pending_locks = asyncio.Lock()
        if self.scanner is not None and not await self.scanner.setup():
            raise FatalError('Scanner setup failed', 1)

    async def __handle_stop(self):
        if self.scanner is not None:
            await self.scanner.teardown()

    async def __handle_new_bounty(self, bounty: Bounty):
        """Scan and assert on a posted bounty

        Args:
            bounty (Bounty) Bounty received from the server

        Returns:
            Response JSON parsed from polyswarmd containing placed assertions
        """
        try:
            result = await self.fetch_and_scan(bounty)
        except (DecodeError, aiohttp.ClientError, aioredis.errors.RedisError):
            result = ScanResult()

        logger.info('Responding to %s bounty %s', bounty.artifact_type, bounty.guid)

        request = ScanResultRequest(verdict=result.verdict_string, confidence=result.confidence, metadata=json.loads(result.metadata))
        await self.client.make_request(bounty.response_url, json=request.to_json())

    async def fetch_and_scan(self, bounty: Bounty) -> ScanResult:
        """Fetch and scan all artifacts concurrently

        Args:
            bounty (Bounty) Bounty received from the server

        Returns:
            ScanResult
        """
        result = ScanResult()
        artifact_type = ArtifactType.from_string(bounty.artifact_type)
        if artifact_type == ArtifactType.FILE:
            content = await self.client.get_artifact(bounty.artifact_url)
            metadata = FileArtifact(filename=bounty.sha256, filesize=len(content), mimetype=bounty.mimetype,
                                    sha256=bounty.sha256)
        elif artifact_type == ArtifactType.URL:
            content = bounty.artifact_url
            metadata = URLArtifact(uri=bounty.artifact_url)
        else:
            content = await self.client.get_artifact(bounty.artifact_url)
            metadata = {}

        if content is not None:
            result = await self.scan(bounty.guid,
                                     artifact_type,
                                     artifact_type.decode_content(content),
                                     metadata,
                                     '')

        return result

    async def scan(self, guid, artifact_type, content, metadata, chain):
        """Override this to implement custom scanning logic

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to be scan
            metadata (dict): Metadata about the artifact being scanned
            chain (str): Chain we are operating on
        Returns:
            ScanResult: Result of this scan
        """
        if self.scanner:
            return await self.scanner.scan(guid, artifact_type, content, metadata, chain)

        raise NotImplementedError(
            'You must 1) override this scan method OR 2) provide a scanner to your Microengine constructor')

