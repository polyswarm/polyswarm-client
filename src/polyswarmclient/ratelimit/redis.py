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

        This implementation is used in the producer and worker since they use Redis already.
    """
    def __init__(self, redis, queue, limit):
        self.redis = redis
        self.queue = queue
        self.limit = limit if limit is None else int(limit)

    def set_redis(self, redis):
        self.redis = redis

    @property
    def daily_key(self):
        date = datetime.date.today().strftime('%Y-%m-%d')
        return f'{self.queue}:{date}'

    async def use(self, *args, peek=False, **kwargs):
        """
        Keep track of use by incrementing a counter for the current date

        Args:
            *args: None
            peek (Bool): Check rate limit without incrementing
            **kwargs: None
        """
        loop = asyncio.get_event_loop()
        if self.limit is None:
            return True

        key = self.daily_key
        try:

            if peek:
                value = await self.redis.get(key) or 0
                value = int(value) + 1
            else:
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
            raise
        except aioredis.errors.ReplyError:
            logger.exception('Redis out of memory')
            raise
        except aioredis.errors.ConnectionForcedCloseError:
            logger.exception('Redis connection closed')
            raise

        return True

    async def expire_key(self, key, timeout):
        await self.redis.expire(key, timeout)
