import asyncio

import aioredis
import datetime
import logging

from polyswarmclient.ratelimit.abstractratelimit import AbstractRateLimit

logger = logging.getLogger(__name__)

TWENTY_FIVE_HOURS = 60 * 60 * 25


class RedisDailyRateLimit(AbstractRateLimit):
    """ Third Party limitation where redis is used to track a daily scan limit.
        Keys are based on the current date, and will expire the next day.

        This implemntation is used in the worker since it is known to use Redis.
    """
    def __init__(self, redis_uri, queue, limit):
        self.redis_uri = redis_uri
        self.redis = None
        self.queue = queue
        self.limit = limit if limit is None else int(limit)

    @property
    def daily_key(self):
        date = datetime.date.today().strftime('%Y-%m-%d')
        return f'{self.queue}:{date}'

    async def setup(self):
        self.redis = await aioredis.create_redis_pool(self.redis_uri)

    async def use(self, *args, **kwargs):
        """
        Keep track of use by incrementing a counter for the current date

        Args:
            *args: None
            **kwargs: None
        """
        loop = asyncio.get_event_loop()
        if self.limit is None:
            return True

        key = self.daily_key
        try:
            value = await self.redis.incr(key)
            if value == 1:
                # Give an hour extra before expiring, in case someone wants to take a look manually
                loop.create_task(self.expire_key(key, TWENTY_FIVE_HOURS))

            if value > self.limit:
                logger.warning("Reached daily limit of %s with %s total attempts", self.limit, value)
                return False

        # We don't want to be DOS ourselves if redis goes down
        except OSError:
            logger.exception('Redis connection down')
        except aioredis.errors.ReplyError:
            logger.exception('Redis out of memory')
        except aioredis.errors.ConnectionForcedCloseError:
            logger.exception('Redis connection closed')

        return True

    async def expire_key(self, key, timeout):
        await self.redis.expire(key, timeout)
