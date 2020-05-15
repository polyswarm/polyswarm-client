import asyncio
import logging


logger = logging.getLogger(__name__)

RATE_LIMIT_SLEEP = 2


class RequestRateLimit:
    def __init__(self, event, lock):
        self.is_limited = False
        self.rate_limit_event = event
        self.lock = lock

    @classmethod
    async def build(cls):
        event = asyncio.Event()
        lock = asyncio.Lock()
        event.set()
        return cls(event, lock)

    async def check(self):
        await self.rate_limit_event.wait()

    async def trigger(self):
        """
        Rate limit new outgoing requests, and debounces to prevent simultaneous triggers
        """
        async with self.lock:
            if self.is_limited:
                return
            self.is_limited = True

        await self.limit()

        async with self.lock:
            self.is_limited = False

    async def limit(self):
        logger.debug('Rate limiting for %s seconds', RATE_LIMIT_SLEEP)
        self.rate_limit_event.clear()
        await asyncio.sleep(RATE_LIMIT_SLEEP)
        self.rate_limit_event.set()
