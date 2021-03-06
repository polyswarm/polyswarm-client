import logging

from polyswarmtransaction import Transaction
from polyswarmtransaction.nectar import WithdrawalTransaction

from polyswarmclient.ethereum.verifiers import NctTransferVerifier
from polyswarmclient.ethereum.transaction import EthereumTransaction
from polyswarmclient.fast.transaction import PolySwarmTransactionRequest

logger = logging.getLogger(__name__)  # Initialize logger


class RelayDepositTransaction(EthereumTransaction):
    def __init__(self, client, amount):
        self.amount = amount
        transfer = NctTransferVerifier(amount)
        super().__init__(client, [transfer])

    def get_path(self):
        return f'/wallets/{self.client.account}/deposit/'

    def get_body(self):
        return {
            'amount': str(self.amount),
        }

    def has_required_event(self, transaction_events):
        transfers = transaction_events.get('transfers', [])
        for transfer in transfers:
            value = int(transfer.get('value', 0))
            if value == self.amount:
                return True

        return False


class RelayWithdrawTransactionRequest(PolySwarmTransactionRequest):
    def __init__(self, client, amount):
        super().__init__(client, WithdrawalTransaction(amount))

    @property
    def path(self):
        return f'/wallets/{self.client.account}/withdrawal/'


class RelayClient(object):
    def __init__(self, client):
        self.__client = client

    async def post_deposit(self, amount, api_key=None):
        """Post a deposit

        Args:
            amount (int): The amount to deposit to the sidechain
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        transaction = RelayDepositTransaction(self.__client, amount)
        success, results = await transaction.send('home', api_key=api_key)
        if not success or 'transfers' not in results:
            logger.error('Expected deposit to relay', extra={'extra': results})
        return results.get('transfers', [])

    async def post_withdraw(self, amount, api_key=None):
        """Post a withdrawal

        Args:
            amount (int): The amount to withdraw from the sidechain
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        transaction = RelayWithdrawTransactionRequest(self.__client, str(amount))
        success, results = await transaction.send(api_key=api_key)
        if not success or 'transfers' not in results:
            logger.error('Expected withdrawal from relay', extra={'extra': results})
            return {}
        return results.get('transfers', [])
