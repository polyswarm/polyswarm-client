import aiohttp
import aiojobs.aiohttp
import asyncio
import json
import hmac
import logging

from aiohttp.web_exceptions import HTTPForbidden, HTTPBadRequest
from aiohttp import web
from asyncio import Event

from aiohttp.web_runner import TCPSite
from polyswarmclient.server.events import Bounty
from typing import Optional, Callable


logger = logging.getLogger(__name__)


class Server:
    webhook_secret: str
    host: str
    port: str
    site: Optional[TCPSite]
    runner: Optional[web.AppRunner]
    event: Optional[Event]
    bounty_callback: Callable

    def __init__(self, webhook_secret, host, port, bounty_callback):
        self.webhook_secret = webhook_secret
        self.host = host
        self.port = port
        self.bounty_callback = bounty_callback
        self.event = None
        self.site = None

    async def run(self):
        app = web.Application(middlewares=[self.verify_sender])
        routes = self.generate_routes()
        app.add_routes(routes)

        # start aiojobs to handle closed connections
        aiojobs.aiohttp.setup(app)
        # Start up the endpoint
        self.runner = aiohttp.web.AppRunner(app)
        await self.runner.setup()

        self.site = aiohttp.web.TCPSite(self.runner, self.host, int(self.port))

        logger.info('Starting server at %s:%s', self.host, self.port)
        await self.site.start()

    async def stop(self):
        await self.site.stop()
        await self.runner.cleanup()

    @web.middleware
    async def verify_sender(self, request, handler):
        signature = request.headers.get('X-POLYSWARM-SIGNATURE')

        if not signature:
            raise HTTPBadRequest()

        body = await request.read()
        loop = asyncio.get_event_loop()
        computed_signature = await loop.run_in_executor(None, self.generate_hmac, self.webhook_secret.encode('utf-8'), body)
        logger.debug('Comparing computed %s vs given %s', computed_signature, signature)
        if not await loop.run_in_executor(None, hmac.compare_digest, computed_signature, signature):
            raise HTTPForbidden()

        return await handler(request)

    @staticmethod
    def generate_hmac(key, body):
        return hmac.new(key, body, digestmod='sha256').hexdigest()

    def generate_routes(self):
        routes = web.RouteTableDef()

        @routes.post('/')
        async def request_handler(request):
            headers = {'Content-Type': 'application/json'}
            event_name = request.headers.get('X-POLYSWARM-EVENT')
            if event_name == 'bounty':
                try:
                    bounty_json = await request.json()
                    logger.info('Received new bounty: %s', bounty_json)
                    bounty = Bounty(**bounty_json)
                    self.bounty_callback(bounty)
                except (TypeError, KeyError, ValueError):
                    logger.exception("Invalid bounty request")
                    message = {'bounty': 'Invalid bounty body'}
                    return web.Response(body=json.dumps(message), headers=headers, status=400)
            elif event_name == 'ping':
                pass
            else:
                message = {'X-POLYSWARM-EVENT': 'Unsupported event name'}
                return web.Response(body=json.dumps(message), headers=headers, status=400)

            message = 'OK'
            return web.Response(body=json.dumps(message), headers=headers, status=200)

        return routes

