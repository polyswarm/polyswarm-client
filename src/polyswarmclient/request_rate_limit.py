import asyncio
import aiorwlock
import logging


logger = logging.getLogger(__name__)

RATE_LIMIT_SLEEP = 2


class RequestRateLimit:
    rwlock: aiorwlock.RWLock
    lock: asyncio.Lock
    is_limited: bool

    def __init__(self, rwlock, lock):
        self.rwlock = rwlock
        self.lock = lock
        self.is_limited = False

    @classmethod
    async def build(cls):
        rwlock = aiorwlock.RWLock()
        lock = asyncio.Lock()
        return cls(rwlock, lock)

    async def check(self):
        return self.rwlock.reader

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
        async with self.rwlock.writer:
            await asyncio.sleep(RATE_LIMIT_SLEEP)
