import logging

from polyswarmclient.parameters import Parameters
from polyswarmclient.ethereum.verifiers import StakingDepositVerifier, StakingWithdrawVerifier, \
    NctApproveVerifier
from polyswarmclient.ethereum.transaction import EthereumTransaction

logger = logging.getLogger(__name__)


class StakeDepositTransaction(EthereumTransaction):
    def __init__(self, client, amount):
        self.amount = amount
        approve = NctApproveVerifier(amount)
        deposit = StakingDepositVerifier(amount)
        super().__init__(client, [approve, deposit])

    def get_path(self):
        return '/staking/deposit'

    def get_body(self):
        return {
            'amount': str(self.amount),
        }

    def has_required_event(self, transaction_events):
        deposits = transaction_events.get('deposits', [])
        for deposit in deposits:
            if deposit.get('value', '') == self.amount:
                return True

        return False


class StakeWithdrawTransaction(EthereumTransaction):
    def __init__(self, client, amount):
        self.amount = amount
        withdraw = StakingWithdrawVerifier(amount)
        super().__init__(client, [withdraw])

    def get_path(self):
        return '/staking/withdraw'

    def get_body(self):
        return {
            'amount': str(self.amount),
        }

    def has_required_event(self, transaction_events):
        withdrawals = transaction_events.get('withdrawals', [])
        for withdrawal in withdrawals:
            if withdrawal.get('value', '') == self.amount:
                return True

        return False


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
        success, result = await self.__client.make_request('GET', '/staking/parameters', chain, api_key=api_key)
        if not success:
            raise Exception('Error retrieving staking parameters')

        self.parameters[chain] = Parameters(result)

    async def get_total_balance(self, chain, api_key=None):
        """Get total staking balance from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing staking balance
        """
        path = '/balances/{0}/staking/total'.format(self.__client.account)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        return int(result)

    async def get_withdrawable_balance(self, chain, api_key=None):
        """Get withdrawable staking balance from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing staking balance
        """
        path = '/balances/{0}/staking/withdrawable'.format(self.__client.account)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        return int(result)

    async def post_deposit(self, amount, chain, api_key=None):
        """Post a deposit to the staking contract

        Args:
            amount (int): The amount to stake
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        transaction = StakeDepositTransaction(self.__client, amount)
        success, results = await transaction.send(chain, api_key=api_key)
        if not success or 'deposits' not in results:
            logger.error('Expected deposit, received', extra={'extra': results})

        return results.get('deposits', [])

    async def post_withdraw(self, amount, chain, api_key=None):
        """Post a withdrawal to the staking contract

        Args:
            amount (int): The amount to withdraw
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        transaction = StakeWithdrawTransaction(self.__client, amount)
        success, results = await transaction.send(chain, api_key=api_key)
        if not success or 'withdrawals' not in results:
            logger.error('Expected withdrawal, received', extra={'extra': results})

        return results.get('withdrawals', [])
