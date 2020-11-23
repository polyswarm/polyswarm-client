from asyncio import Future

import aiohttp
import asyncio
import logging

from typing import Optional

from polyswarmclient import utils, events
from polyswarmclient.exceptions import RateLimitedError
from polyswarmclient.backoff_wrapper import BackoffWrapper
from polyswarmclient.request_rate_limit import RequestRateLimit
from polyswarmclient.server import Server
from polyswarmclient.server.events import Bounty

logger = logging.getLogger(__name__)

MAX_ARTIFACTS = 1
RATE_LIMIT_SLEEP = 2.0
MAX_BACKOFF = 32
LONG_SLEEP = 24 * 60 * 60


class Client(object):
    api_key: str
    webhook_secret: str
    tx_error_fatal: bool
    host: str
    port: str
    rate_limit: Optional[RequestRateLimit]
    server = Optional[Server]

    """Client to connected to a Ethereum wallet as well as a polyswarmd instance.

    Args:
        api_key (str): Your PolySwarm API key.
        tx_error_fatal (bool): Transaction errors are fatal and exit the program
        host (str): Hostname for the webhook server
        port (str): Port to listen to the webhook server
    """

    def __init__(self, api_key=None, webhook_secret=None, host="0.0.0.0", port="8080", **kwargs):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.rate_limit = None
        self.host = host
        self.port = port
        self.server = None

        # Events from polyswarmd
        self.on_new_bounty = events.OnNewBountyCallback()
        self.on_run = events.OnRunCallback()
        self.on_stop = events.OnStopCallback()

        utils.configure_event_loop()

    def run(self):
        """Run the main event loop
        """

        # noinspection PyBroadException
        try:
            asyncio.get_event_loop().run_until_complete(self.run_task())
        except asyncio.CancelledError:
            logger.info('Clean exit requested')
            utils.asyncio_join()
        except Exception:
            logger.exception('Unhandled exception at top level')
            utils.asyncio_stop()
            utils.asyncio_join()

    async def run_task(self):
        """
        Starts a server to receive webhooks from PolySwarm
        """
        loop = asyncio.get_event_loop()
        self.rate_limit = await RequestRateLimit.build()
        await self.on_run.run(chain='')

        def callback(bounty: Bounty):
            loop.create_task(self.on_new_bounty.run(bounty))

        self.server = Server(self.webhook_secret, self.host, self.port, bounty_callback=callback)
        logger.info('Starting server')
        try:
            await self.server.run()
            # Don't exit unless cancelled
            future = Future()
            await future
        except asyncio.CancelledError:
            await self.on_stop.run()
            raise

    @utils.return_on_exception((aiohttp.ServerDisconnectedError, asyncio.TimeoutError, aiohttp.ClientOSError,
                                aiohttp.ContentTypeError, RateLimitedError), default=(False, {}))
    async def make_request(self, method, url, json=None, params=None):
        """Make a request to polyswarmd, expecting a json response
        Args:
            method (str): HTTP method to use
            url (str): Endpoint to make request to
            json (obj): JSON payload to send with request
            api_key (str): Override default API key
            params (dict): Optional params for the request
        Returns:
            (bool, obj): Tuple of boolean representing success, and response JSON parsed from polyswarmd
        """
        logger.debug('making request to url: %s', url)

        params = params or {}

        # Allow overriding API key per request
        headers = {'Authorization': self.api_key} if self.api_key else {}

        response = {}
        try:
            await self.rate_limit.check()
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, params=params, headers=headers, json=json) as raw:
                    self._check_status_for_rate_limit(raw.status)
                    raw.raise_for_status()

                    try:
                        response = await raw.json()
                    except aiohttp.ContentTypeError:
                        response = await raw.read() if raw else 'None'
                        raise

                    queries = '&'.join([a + '=' + str(b) for (a, b) in params.items()])
                    logger.debug('%s %s?%s', method, url, queries, extra={'extra': response})

                    return response
        except aiohttp.ContentTypeError:
            logger.exception('Received non-json response: %s, url: %s', response, url)
            raise
        except (aiohttp.ClientOSError, aiohttp.ServerDisconnectedError):
            logger.exception('Connection  refused')
            raise
        except asyncio.TimeoutError:
            logger.error('Connection timed out')
            raise
        except RateLimitedError:
            # Handle "Too many requests" rate limit by not hammering server, and pausing all requests for a bit
            logger.warning('Hit rate limits, stopping all requests for a moment')
            asyncio.get_event_loop().create_task(self.rate_limit.trigger())
            raise

    @staticmethod
    def _check_status_for_rate_limit(status):
        if status == 429:
            raise RateLimitedError
