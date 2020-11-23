import datetime

import asyncio
import aioredis
import logging

from abc import ABC, abstractmethod

from polyswarmclient.ratelimit.abstractratelimit import AbstractRateLimit

logger = logging.getLogger(__name__)

SECONDS = 1
MINUTELY_SECONDS = 60
HOURLY_SECONDS = MINUTELY_SECONDS * 60
DAILY_SECONDS = HOURLY_SECONDS * 24


class RedisKeyManager(ABC):
    @abstractmethod
    def get_key(self, prefix):
        raise NotImplementedError()

    @abstractmethod
    def get_expiration(self):
        raise NotImplementedError()


class DateKeyManager(RedisKeyManager):
    def __init__(self, expiration, format_str):
        self.expiration = expiration
        self.format_str = format_str

    def get_key(self, prefix):
        date = datetime.datetime.today().strftime(self.format_str)
        return f'{prefix}_{date}'

    def get_expiration(self):
        return self.expiration


class DailyKeyManager(DateKeyManager):
    def __init__(self):
        super().__init__(expiration=DAILY_SECONDS, format_str='%Y-%m-%d')


class HourlyKeyManager(DateKeyManager):
    def __init__(self):
        super().__init__(expiration=HOURLY_SECONDS, format_str='%Y-%m-%dT%H')


class MinutelyKeyManager(DateKeyManager):
    def __init__(self):
        super().__init__(expiration=MINUTELY_SECONDS, format_str='%Y-%m-%dT%H:%M')


class SecondlyKeyManager(DateKeyManager):
    def __init__(self):
        super().__init__(expiration=SECONDS, format_str='%Y-%m-%dT%H:%M:%S')


class RedisRateLimit(AbstractRateLimit):
    """ Third Party limitation where redis is used to track a daily scan limit.
        Keys are based on the current date, and will expire the next day.

        This implementation is used in the producer and worker since they use Redis already.
    """
    def __init__(self, redis, queue, limit, key_manager=None):
        self.redis = redis
        self.queue = queue
        self.limit = limit if limit is None else int(limit)
        self.key_manager = key_manager or DailyKeyManager()

    def set_redis(self, redis):
        self.redis = redis

    @property
    def key(self):
        return self.key_manager.get_key(self.queue)

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

        key = self.key
        try:

            if peek:
                value = await self.redis.get(key) or 0
                value = int(value) + 1
            else:
                value = await self.redis.incr(key)
                if value == 1:
                    loop.create_task(self.expire_key(key, self.key_manager.get_expiration()))

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


class RedisDailyRateLimit(RedisRateLimit):
    pass
