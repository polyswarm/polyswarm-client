import aiohttp
import aiojobs.aiohttp
import asyncio
import hmac
import logging

from aiohttp.web_exceptions import HTTPForbidden, HTTPBadRequest
from aiohttp import web
from asyncio import Event

from aiohttp.web_runner import TCPSite
from typing import Optional
from io import BytesIO


logger = logging.getLogger(__name__)


class Server:
    routes: web.RouteTableDef
    api_key: str
    host: str
    port: str
    site: Optional[TCPSite]
    event: Optional[Event]

    def __init__(self, routes, api_key, host, port):
        self.routes = routes
        self.api_key = api_key
        self.host = host
        self.port = port
        self.event = None
        self.site = None

    async def run(self):
        app = web.Application(middlewares=[self.verify_sender])
        app.add_routes(self.routes)

        # start aiojobs to handle closed connections
        aiojobs.aiohttp.setup(app)
        # Start up the endpoint
        runner = aiohttp.web.AppRunner(app)
        await runner.setup()

        self.site = aiohttp.web.TCPSite(runner, self.host, int(self.port))

        await self.site.start()
        self.event = asyncio.Event()
        await self.event.wait()
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

        body = await request.content.read()
        digest = hmac.new(self.api_key.encode('utf-8'), body).hexdigest()
        logger.debug('Comparing computed %s vs given %s', digest, signature)
        if not hmac.compare_digest(digest, signature):
            raise HTTPForbidden()

        request.content = BytesIO(body)

        return await handler(request)
