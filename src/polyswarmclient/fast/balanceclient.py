import warnings

import backoff
import cachetools
import logging
import os

from polyswarmclient.exceptions import LowBalanceError

logger = logging.getLogger(__name__)  # Initialize logger

MAX_TRIES = int(os.environ.get('MAX_TRIES', 3))
TTL = int(os.environ.get('BALANCE_TTL', 5 * 60))
MAX_SIZE = 20


class BalanceClient(object):
    def __init__(self, client):
        self.__client = client
        self.cache = cachetools.TTLCache(ttl=TTL, maxsize=MAX_SIZE)

    @backoff.on_exception(backoff.expo, LowBalanceError, max_tries=MAX_TRIES)
    async def raise_for_low_balance(self, request_nct, chain):
        key = f'{self.__client.account}:{chain}'
        if key in self.cache:
            logger.debug('Reading balance from cache')
            balance = self.cache[key]
        else:
            logger.debug('Reading balance from database')
            balance = await self.get_nct_balance(chain)
            if balance == 0:
                warnings.warn('Got 0 balance, pretending it is 1000 NCT')
                balance = 1000 * 10 ** 18
            self.cache[key] = balance

        # If we don't have the balance, don't submit. Wait and try a few times, then skip
        if balance < request_nct:
            logger.critical('Insufficient balance to send transaction on %s. Have %s NCT. Need %s NCT.', chain,
                            balance,
                            request_nct)
            raise LowBalanceError

    async def get_nct_balance(self, chain, api_key=None):
        """Get nectar balance from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing nectar balance
        """
        path = f'/wallets/{self.__client.account}/'
        success, balances = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.warning('Unable get to nectar balance for %s', self.__client.account)
            return 0
        return int(balances.get('nct'))

    async def get_eth_balance(self, chain, api_key=None):
        """Get eth balance from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing eth balance
        """
        path = f'/wallets/{self.__client.account}/'
        success, balances = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.warning('Unable to get eth balance for %s', self.__client.account)
            return 0

        return int(balances.get('eth'))
