from io import BytesIO

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
    api_key: str
    host: str
    port: str
    site: Optional[TCPSite]
    event: Optional[Event]
    bounty_callback: Callable

    def __init__(self, api_key, host, port, bounty_callback):
        self.api_key = api_key
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
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()

        self.site = aiohttp.web.TCPSite(runner, self.host, int(self.port))

        await self.site.start()
        logger.info('Starting server at %s:%s', self.host, self.port)
        self.event = asyncio.Event()
        await self.event.wait()
        logger.info('Shutting down server')
        await runner.cleanup()

    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.event:
            self.event.set()

    @web.middleware
    async def verify_sender(self, request, handler):
        signature = request.headers.get('X-POLYSWARM-SIGNATURE')

        if not signature:
            raise HTTPBadRequest()

        body = await request.read()
        digest = hmac.new(self.api_key.encode('utf-8'), body, digestmod='sha256').hexdigest()
        logger.debug('Comparing computed %s vs given %s', digest, signature)
        if not hmac.compare_digest(digest, signature):
            raise HTTPForbidden()

        return await handler(request)

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

