import logging
from abc import ABCMeta, abstractmethod
from typing import Any, Dict

from polyswarmtransaction import SignedTransaction, Transaction
from polyswarmclient import Client
from polyswarmclient.exceptions import TransactionError

logger = logging.getLogger(__name__)


class PolySwarmTransactionRequest(metaclass=ABCMeta):
    """Used to verify and post groups of transactions that make up a specific action.

    For instance, when approving some funds to move, and calling a contract function that will consumer them.
    """

    def __init__(self, client: Client, transaction: Transaction):
        """Initialize a transaction

        Args:
            client (Client): Client object used to post transactions
            transaction (Transaction): Transaction object used for sending the transaction
        """
        self.client = client
        self.transaction = transaction

    async def send(self, api_key: str = None) -> Dict[str, Any]:
        """Make a transaction generating request to polyswarmd, then sign and post the transactions

        Args:
            api_key (str): Override default API key
        Returns:
            Dict[str, Any]: Tuple of boolean representing success, and response JSON parsed from polyswarmd
        """
        if api_key is None:
            api_key = self.client.api_key

        signed = self.sign_transaction()
        return await self.post_transaction(signed, api_key)

    def sign_transaction(self) -> SignedTransaction:
        """Signs a transaction

        Returns:
            SignedTransaction
        """
        return self.transaction.sign(self.client.priv_key)

    async def post_transaction(self, signed: SignedTransaction, api_key: str) -> Dict[str, Any]:
        success, results = await self.client.make_request('POST', self.path, json=signed.payload, api_key=api_key,
                                                          chain='side')
        # TODO: Remove this temporary solution once there is time to use raise_for_status in make_request
        if not success:
            logger.error('Error posting transaction: %s', results)
            raise TransactionError('Failed to post transaction')
        return results

    @property
    @abstractmethod
    def path(self):
        """Get the path of the route to build this transaction

        Returns:
            str: Polyswarmd path to get the transaction data
        """
        raise NotImplementedError('get path is not implemented')
