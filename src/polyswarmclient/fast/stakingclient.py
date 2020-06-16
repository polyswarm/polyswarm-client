import logging

from polyswarmclient.parameters import Parameters

logger = logging.getLogger(__name__)


class StakingClient(object):
    def __init__(self, client):
        self.__client = client
        self.parameters = {}

    async def fetch_parameters(self, chain, api_key=None):
        """Get staking parameters from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing staking parameters
        """
        result = {
            'minimum_stake': 0,
            'maximum_stake': 0,
            'vote_ratio_numerator': 9,
            'vote_ratio_denominator': 10
        }

        self.parameters[chain] = Parameters(result)

    async def get_total_balance(self, chain, api_key=None):
        """Get total staking balance from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing staking balance
        """
        return 0

    async def get_withdrawable_balance(self, chain, api_key=None):
        """Get withdrawable staking balance from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing staking balance
        """
        return 0

    async def post_deposit(self, amount, chain, api_key=None):
        """Post a deposit to the staking contract

        Args:
            amount (int): The amount to stake
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        pass

    async def post_withdraw(self, amount, chain, api_key=None):
        """Post a withdrawal to the staking contract

        Args:
            amount (int): The amount to withdraw
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        pass
