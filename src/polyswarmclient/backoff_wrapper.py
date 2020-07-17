import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class BackoffWrapper:
    """
    Uses a generator to create backoff times

    This is for use in functions that don't return. In our use case, listen_for_events is not supposed to return,
    but exists as a long running Task. Using the decorator, the backoff time grows forever, because the function is only
    called one time. So each error causes a longer and longer timeout.

    This adds an ability to reset the backoff, so your long running function can reduce the timeout after success
    """
    def __init__(self, func, **kwargs):
        self.func = func
        self.kwargs = kwargs
        self.backoff_generator = self.func(**kwargs)

    def reset(self):
        self.backoff_generator = self.func(**self.kwargs)

    async def sleep(self):
        next_sleep = next(self.backoff_generator)
        logger.debug('Backoff async triggered. Sleeping for %s', next_sleep)
        await asyncio.sleep(next_sleep)
