import asyncio
import logging

logger = logging.getLogger(__name__)


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

    async def reserve(self, amount=1):
        """Grab the next amount nonces.

        Args:
            amount (int): amount of sequential nonces to be claimed
        Returns
            (list[int]): a list of nonces to use
        """
        # Clear any waiting that should be used at this point
        async with self.nonce_lock:
            if self.needs_update:
                async with self.update_lock:
                    needs_update = self.needs_update

                if needs_update:
                    nonces = await self.sync_nonce(amount, self.overset)
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
