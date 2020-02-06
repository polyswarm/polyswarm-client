import logging

import backoff

from polyswarmclient.ethereum.balanceclient import MAX_TRIES
from polyswarmclient.exceptions import LowBalanceError

logger = logging.getLogger(__name__)  # Initialize logger


class BalanceClient(object):
    def __init__(self, client):
        self.__client = client

    @backoff.on_exception(backoff.expo, LowBalanceError, max_tries=MAX_TRIES)
    async def raise_for_low_balance(self, request_nct, chain):
        balance = await self.get_nct_balance(chain)
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
        path = f'/wallet/{self.__client.account.address}/'
        success, balances = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.warning('Unable to nectar balance for %s', self.__client.account.address)
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
        path = f'/wallet/{self.__client.account.address}/'
        success, balances = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.warning('Unable to eth balance for %s', self.__client.account.address)
            return 0

        return int(balances.get('eth'))
