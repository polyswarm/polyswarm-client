import asyncio
import logging

from abc import ABCMeta, abstractmethod
from web3.auto import w3

from polyswarmclient.exceptions import FatalError

logger = logging.getLogger(__name__)

LOG_MSG_ENGINE_TOO_SLOW = ('PLEASE REVIEW YOUR SCANNING LOGIC. '
                           'Bounty inactive errors indicate that the microengine received the bounty, '
                           'but was unable to respond to the bounty within the time window. '
                           'Such errors are considered fatal during testing so you can easily identify them. '
                           'If your engine is unable to respond within the time window on the live PolySwarm '
                           'network, you risk losing the bid amount of the bounty at hand. We strongly '
                           'encourage you to review your artifact scan process to identify areas where engine '
                           'speed can be improved.')


class NonceManager:
    """Manages the nonce for some Ethereum chain"""

    def __init__(self, client, chain):
        self.base_nonce = 0
        self.client = client
        self.chain = chain
        self.needs_update = True
        self.overset = False
        self.nonce_lock = None
        self.update_lock = None
        self.pending = []

    async def setup(self):
        self.nonce_lock = asyncio.Lock()
        self.update_lock = asyncio.Lock()

    async def acquire(self):
        """Acquires the nonce lock and updates base_nonce if needs_update is set"""
        await self.nonce_lock.acquire()

    async def reserve(self, amount=1):
        """Grab the next amount nonces.

        Args:
            amount (int): amount of sequential nonces to be claimed
        Returns
            (list[int]): a list of nonces to use
        """
        # Clear any waiting that should be used at this point
        async with self:
            async with self.update_lock:
                needs_update = self.needs_update
                overset = self.overset

            if needs_update:
                nonces = await self.sync_nonce(amount, overset)
                # Since we acquire twice, we may overwrite changes, but we don't care since the nonce just synced
                async with self.update_lock:
                    self.needs_update = False
                    self.overset = False
            else:
                nonces = [r for r in range(self.base_nonce, self.base_nonce + amount)]
                self.base_nonce = nonces[-1] + 1
            return nonces

    async def sync_nonce(self, amount, overset):
        """ Sync the nonce with the Ethereum chain
        Reads the pending transactions from the tx pool, and gets the nonce ignoring all transactions
        Using those values it determines the nonce to use, or if the transactions are in a timeout state, returns None

        Args:
            amount: Number of transactions to make
            overset: Is the nonce overset

        Returns
            (None|list[int]): List of int values for nonces, or None if the transaction would timeout

        """
        low_nonce = await self.get_nonce(True)
        nonce = max(self.base_nonce, low_nonce) if not overset else low_nonce
        pending = sorted(await self.get_pending_nonces(self.chain))
        self.pending = pending
        # -1 because nonces are zero indexed, so nonce + amount -1 is max nonce
        if not pending or nonce + amount - 1 < pending[0]:
            nonces = [r for r in range(nonce, nonce + amount)]
            # If we filled the front gap to the pending transactions, jump forward to the next gap, or the end
            if pending and nonces[-1] + 1 == pending[0]:
                gaps = NonceManager.find_gaps(pending)
                self.base_nonce = gaps[0] if gaps else pending[-1] + 1
            else:
                self.base_nonce = nonces[-1] + 1
            return nonces
        # If the base_nonce butts against pending, jump forward to the end
        elif nonce == pending[0] and not NonceManager.find_gaps(pending):
            nonce = pending[-1] + 1
            nonces = [r for r in range(nonce, nonce + amount)]
            self.base_nonce = nonces[-1] + 1
            return nonces
        else:
            # If there is gap before the first pending, but it isn't big enough, return None
            # If there is a gap in pending, we have to fill up to it, so return and wait for the gap to be at the front
            return None

    @staticmethod
    def find_gaps(nonces):
        """Finds any gaps between base nonce and the last nonce in the given nonces list.

        Args:
            nonces (list[int]): list of nonces being checked

        Returns
            (list[int]): Any missing nonces between base_nonce and the last given nonce

        """
        # Only check through the end of the waitlist if results exceed it
        return [r for r in range(nonces[0], nonces[-1]) if r not in nonces]

    async def get_base_nonce(self, chain, ignore_pending=False, api_key=None):
        """Get account's nonce from polyswarmd

        Args:
            chain (str): Which chain to operate on
            ignore_pending (bool): Whether to include pending transactions in nonce or not
            api_key (str): Override default API key
        """
        params = {'ignore_pending': ' '} if ignore_pending else None
        success, base_nonce = await self.client.make_request('GET', '/nonce', chain, api_key=api_key, params=params)
        if success:
            return base_nonce
        else:
            logger.error('Failed to fetch base nonce')
            return None

    async def get_pending_nonces(self, chain, api_key=None):
        """Get account's pending nonces from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        success, nonces = await self.client.make_request('GET', '/pending', chain, api_key=api_key)
        if success:
            return [int(nonce) for nonce in nonces]
        else:
            logger.error('Failed to fetch base nonce')
            return []

    async def get_nonce(self, ignore_pending):
        """Get nonce from polswarmd

        Args:
            ignore_pending: Do we want the transaction count with a count of pending transactions

        Returns
                (int): Nonce

        """
        while True:
            nonce = await self.get_base_nonce(self.chain, ignore_pending)
            if nonce is not None:
                break

            await asyncio.sleep(1)

        return nonce

    async def mark_update_nonce(self):
        """
        Call this when the nonce is out of sync.
        This sets the update flag to true.
        The next reserve after being set will trigger an update
        """
        async with self.update_lock:
            if not self.needs_update:
                self.needs_update = True
                self.overset = False

    async def mark_overset_nonce(self, nonces):
        """
        Call this when the nonce is too high
        This sets the update flag to true.
        The next reserve after being set will trigger an update
        """
        async with self.update_lock:
            # if we know this nonce is too high, ignore it
            if not any(nonce for nonce in nonces if nonce in self.pending) and not self.needs_update:
                self.needs_update = True
                self.overset = True

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self.nonce_lock.release()


# FIXME This needs to change to building transaction itself from the addresses before we can go live
class EthereumTransaction(metaclass=ABCMeta):
    """Used to verify and post groups of transactions that make up a specific action.

    For instance, when approving some funds to move, and calling a contract function that will consumer them.
    """

    def __init__(self, client, verifiers):
        """Initialize a transaction

        Args:
            client (Client): Client object used to post transactions
            verifiers (list): Ordered verifiers for each transaction
        """
        self.client = client
        self.verifiers = verifiers

    async def send(self, chain, tries=2, api_key=None):
        """Make a transaction generating request to polyswarmd, then sign and post the transactions

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
            tries (int): Number of times to retry before giving up
        Returns:
            (bool, obj): Tuple of boolean representing success, and response JSON parsed from polyswarmd
        """
        if api_key is None:
            api_key = self.client.api_key

        # Ensure we try at least once
        tries = max(tries, 1)

        # Step 1: Prepare the transaction, this is only done once
        success, results = await self.client.make_request('POST',
                                                          self.get_path(),
                                                          chain,
                                                          json=self.get_body(),
                                                          send_nonce=True,
                                                          api_key=api_key,
                                                          tries=tries)

        results = {} if results is None else results

        if not success or 'transactions' not in results:
            logger.error('Expected transactions, received', extra={'extra': results})
            return False, results

        transactions = results.get('transactions', [])
        if not self.verify(transactions):
            logger.critical('Transactions did not match expectations for the given request.',
                            extra={'extra': transactions})
            if self.client.tx_error_fatal:
                logger.critical(LOG_MSG_ENGINE_TOO_SLOW)
                raise FatalError('Transaction error in testing mode', 1)
            return False, {}

        # Keep around any extra data from the first request, such as nonce for assertion
        if 'transactions' in results:
            del results['transactions']

        orig_tries = tries
        post_errors = []
        get_errors = []
        while tries > 0:
            # Step 2: Update nonces, sign then post transactions
            txhashes, nonces, post_errors = await self.__sign_and_post_transactions(transactions, orig_tries, chain,
                                                                                    api_key)
            if not txhashes:
                return False, {'errors': post_errors}

            # Step 3: At least one transaction was submitted successfully, get and verify the events it generated
            success, results, get_errors = await self.__get_transactions(txhashes, nonces, orig_tries, chain, api_key)
            return success, results

        return False, {'errors': post_errors + get_errors}

    async def __sign_and_post_transactions(self, transactions, tries, chain, api_key):
        """Signs and posts a set of transactions to Ethereum via polyswarmd

        Args:
            transactions (List[Transaction]): The transactions to sign and post
            tries (int): Number of times to retry before giving upyy
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing transaction status
        """
        nonce_manager = self.client.nonce_managers[chain]
        nonces = []
        txhashes = []
        errors = []
        while tries > 0:
            tries -= 1

            while True:
                nonces = await nonce_manager.reserve(amount=len(transactions))
                if nonces is not None:
                    break

                await asyncio.sleep(1)

            for i, transaction in enumerate(transactions):
                transaction['nonce'] = nonces[i]

            signed_txs = self.__sign_transactions(transactions)
            raw_signed_txs = [bytes(tx['rawTransaction']).hex() for tx in signed_txs
                              if tx.get('rawTransaction', None) is not None]

            success, results = await self.client.make_request('POST', '/transactions', chain,
                                                              json={'transactions': raw_signed_txs}, api_key=api_key,
                                                              tries=1)

            if not success:
                # Known transaction errors seem to be a geth issue, don't spam log about it
                all_known_tx_errors = results is not None and \
                                      all(['known transaction' in r.get('message', '') for r in results if
                                           r.get('is_error')])

                if self.client.tx_error_fatal:
                    logger.critical('Received fatal transaction error during post.', extra={'extra': results})
                    logger.critical(LOG_MSG_ENGINE_TOO_SLOW)
                    raise FatalError('Transaction error in testing mode', 1)
                elif not all_known_tx_errors:
                    logger.error('Received transaction error during post',
                                 extra={'extra': {'results': results, 'transactions': transactions}})

            results = [] if results is None else results

            if len(results) != len(signed_txs):
                logger.warning('Transaction result length mismatch')

            txhashes = []
            errors = []
            for tx, result in zip(signed_txs, results):
                if tx.get('hash', None) is None:
                    logger.warning(f'Signed transaction missing txhash: {tx}')
                    continue

                txhash = bytes(tx['hash']).hex()
                message = result.get('message', '')
                is_error = result.get('is_error', False)

                # Known transaction errors seem to be a geth issue, don't retransmit in this case
                if is_error and 'known transaction' not in message.lower():
                    errors.append(message)
                else:
                    txhashes.append(txhash)

            if txhashes:
                if errors:
                    logger.warning('Transaction errors detected but some succeeded, fetching events',
                                   extra={'extra': errors})

                return txhashes, nonces, errors

            # Indicates nonce is too low, we can handle this now, resync nonces and retry
            if any(['invalid transaction error' in e.lower() for e in errors]):
                logger.error('Nonce desync detected during post, resyncing and trying again')
                await nonce_manager.mark_update_nonce()

        return txhashes, nonces, errors

    def __sign_transactions(self, transactions):
        """Sign a set of transactions

        Args:
            transactions (List[Transaction]): The transactions to sign
        Returns:
            List[Transaction]: The signed transactions
        """
        return [w3.eth.account.signTransaction(tx, self.client.priv_key) for tx in transactions]

    async def __get_transactions(self, txhashes, nonces, tries, chain, api_key):
        """Get generated events or errors from receipts for a set of txhashes

        Args:
            txhashes (List[str]): The txhashes of the receipts to process
            tries (int): Number of times to retry before giving upyy
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            (bool, dict, List[str]): Success, Resync nonce, Response JSON parsed from polyswarmd containing
                emitted events, errors
        """
        nonce_manager = self.client.nonce_managers[chain]

        success = False
        timeout = False
        results = {}
        errors = []
        while tries > 0:
            tries -= 1

            success, results = await self.client.make_request('GET', '/transactions', chain,
                                                              json={'transactions': txhashes}, api_key=api_key, tries=1)
            results = {} if results is None else results
            success = self.has_required_event(results)
            if not success:
                if self.client.tx_error_fatal:
                    logger.critical('Received fatal transaction error during get.', extra={'extra': results})
                    raise FatalError('Transaction error in testing mode', 1)
                else:
                    logger.error('Received transaction error during get', extra={'extra': results})

            errors = results.get('errors', [])

            # Indicates nonce may be too high
            # First, tries to sleep and see if the transaction did succeed (settles can timeout)
            # If still timing out, resync nonce
            if any([e for e in errors if 'timeout during wait for receipt' in e.lower()]):
                # We got the items we wanted, but I want it to get all items
                if success:
                    if not timeout:
                        timeout = True
                        continue
                    # Oh well, it worked so just keep going
                elif not timeout:
                    logger.error('Nonce desync detected during get, resyncing and trying again')
                    await nonce_manager.mark_overset_nonce(nonces)
                    # Just give one extra try since settles sometimes timeout
                    tries += 1
                    timeout = True
                    continue
                else:
                    logger.error('Transaction continues to timeout, sleeping then trying again')
                    await asyncio.sleep(1)
                    continue

            # Check to see if we failed to retrieve some receipts, retry the fetch if so
            if not success and any(['receipt' in e.lower() for e in errors]):
                logger.warning('Error fetching some receipts, retrying')
                continue

            if any(['transaction failed' in e.lower() for e in errors]):
                logger.error('Transaction failed due to bad parameters, not retrying', extra={'extra': errors})
                break

            # I think we need a break here. We have been just retrying every transaction, even on success
            break

        if timeout:
            logger.warning('Transaction completed after timeout', extra={'extra': results})

        return success, results, errors

    @abstractmethod
    def has_required_event(self, transaction_events):
        """Checks for existence of events in transaction logs, ensuring successful completion

        Returns:
            True if the required event was in the list, false otherwise
        """
        raise NotImplementedError('has_required_event not implemented')

    @abstractmethod
    def get_path(self):
        """Get the path of the route to build this transaction

        Returns:
            str: Polyswarmd path to get the transaction data
        """
        raise NotImplementedError('get path is not implemented')

    @abstractmethod
    def get_body(self):
        """
        Build the payload to send to polyswarmd
        Returns:
            Dict payload
        """
        raise NotImplementedError('get body is not implemented')

    def verify(self, transactions):
        """Check the given transactions against known expectations

        Args:
            transactions (list) - A list of transactions from polyswarmd
        Returns:
            (bool): True if transactions match expectations. False otherwise
        """
        if len(transactions) != len(self.verifiers):
            return False

        return all([v.verify(tx) for v, tx in zip(self.verifiers, transactions)])
