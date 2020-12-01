import aioredis
import aiohttp
import asyncio
import logging
import os

from polyswarmartifact import ArtifactType, DecodeError
from polyswarmartifact.schema import FileArtifact, URLArtifact

from polyswarmclient import Client
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.exceptions import FatalError, InvalidBidError
from polyswarmclient.server.events import Bounty, BountyResult

logger = logging.getLogger(__name__)

NCT_WEI_CONVERSION = 10 ** 18
BID_PHASE = os.environ.get('BID_PHASE', 'assert')
MIN_ALLOWED_BID = os.environ.get('MIN_ALLOWED_BID', 1 / 12 * NCT_WEI_CONVERSION)
MAX_ALLOWED_BID = os.environ.get('MAX_ALLOWED_BID', NCT_WEI_CONVERSION)


class AbstractParticipant(object):
    def __init__(self, client, scanner=None, bid_strategy=None):
        self.client = client
        self.scanner = scanner
        self.bid_strategy = bid_strategy
        self.client.on_run.register(self.__handle_run)
        self.client.on_stop.register(self.__handle_stop)
        self.client.on_new_bounty.register(self.__handle_new_bounty)

    @classmethod
    def connect(cls, host, port, api_key=None, scanner=None, bid_strategy=None, **kwargs):
        """Connect the Microengine to a Client.

        Args:
            host (str): Host for the webhook
            port (str): Port to listen for webhooks
            api_key (str): Your PolySwarm API key.
            scanner (Scanner): `Scanner` object to use.
            bid_strategy (BidStrategy): `BidStrategy` object to use

        Returns:
            AbstractMicroengine: Microengine instantiated with a Client.
        """
        client = Client(api_key, host, port)
        return cls(client, scanner=scanner, bid_strategy=bid_strategy)

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
            scan_result = await self.fetch_and_scan(bounty)
        except (DecodeError, aiohttp.ClientError, aioredis.errors.RedisError):
            scan_result = ScanResult()

        if bounty.phase.lower() == BID_PHASE:
            bid = self.bid(bounty.guid, [scan_result.bit], [scan_result.verdict], [scan_result.confidence],
                           [scan_result.metadata], chain='side')
        else:
            bid = 0

        bounty_result = BountyResult(scan_result.bit, scan_result.verdict, bid, scan_result.metadata)
        logger.info('Responding to %s bounty %s: %s', bounty.artifact_type, bounty.guid, bounty_result)

        await self.client.make_request(method='POST', url=bounty.response_url, json=bounty_result.to_json())

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
            async with aiohttp.ClientSession(raise_for_status=True) as session:
                async with session.get(bounty.artifact_url) as response:
                    content = await response.content.read()

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

    async def bid(self, guid, mask, verdicts, confidences, metadatas, chain):
        """Override this to implement custom bid calculation logic

        Args:
            guid (str): GUID of the bounty under analysis
            mask (list[bool]): mask for the from scanning the bounty files
            verdicts (list[bool]): scan verdicts from scanning the bounty files
            confidences (list[float]): Measure of confidence of verdict per artifact ranging from 0.0 to 1.0
            metadatas (list[str]): metadata blurbs from scanning the bounty files
            chain (str): Chain we are operating on

        Returns:
            list[int]: Amount of NCT to bid in base NCT units (10 ^ -18)
        """
        if self.bid_strategy is not None:
            bid = await self.bid_strategy.bid(guid,
                                              mask,
                                              verdicts,
                                              confidences,
                                              metadatas,
                                              MIN_ALLOWED_BID,
                                              MAX_ALLOWED_BID,
                                              chain)
            if [b for b in bid if b < MIN_ALLOWED_BID or b > MAX_ALLOWED_BID]:
                raise InvalidBidError()

            return bid

        raise NotImplementedError(
            'You must 1) override this bid method OR 2) provide a bid_strategy to your Microengine constructor')
