import asyncio
import logging

from polyswarmclient.utils import asyncio_stop, configure_event_loop
import polyswarmclient.fast.bountiesclient

logger = logging.getLogger(__name__)

# Extra blocks for the relay to process. Includes multiple relay transactions.
# 3 is minimum. 5 Gives a little extra room for slow transactions
RELAY_LEEWAY = 5


def convert(client, denomination, amount):
    """
    Convert the amount from it's original precision to 18 decimals
    """
    if denomination == 'nct':
        return client.to_wei(amount, 'ether')
    elif denomination == 'nct-gwei':
        return client.to_wei(amount, 'gwei')
    elif denomination == 'nct-wei':
        return amount
    else:
        raise ValueError()


def convert_from(client, denomination, amount):
    """
    Convert the amount from 18 decimals to the dedsired precision
    """
    if denomination == 'nct':
        return client.from_wei(amount, 'ether')
    elif denomination == 'nct-gwei':
        return client.from_wei(amount, 'gwei')
    elif denomination == 'nct-wei':
        return amount
    else:
        raise ValueError()


class BalanceManager(object):
    """
    Balance manager is used for single transfer events in either direction.
    Create a client, choose a chain and amount then run it.
    """

    def __init__(self, client, denomination, transfer_all, amount, testing=0, chains=None):
        self.client = client
        self.chains = chains
        self.denomination = denomination
        self.transfer_all = transfer_all
        self.amount = amount
        self.testing = testing
        self.client.on_run.register(self.handle_run)
        self.exit_code = 0

    def run(self):
        """
        Starts the client on whichever chain this uses.
        """
        self.client.run(chains=self.chains)

    def run_oneshot(self):
        """
        Runs run_task once
        """
        configure_event_loop()
        asyncio.get_event_loop().run_until_complete(self.client.run_task(chains=self.chains, listen_for_events=False))

    async def handle_run(self, chain):
        """
        Just starts the transfer up async.
        """
        # Do nothing when talking to polyswarmd-fast
        if isinstance(self.client.bounties, polyswarmclient.fast.bountiesclient.BountiesClient):
            self.exit_code = 0
            return

        if self.testing > 0:
            for i in range(0, self.testing):
                logger.info('Transferred %s times of %s', i, self.testing)
                await self.handle_transfer(chain)
        else:
            await self.handle_transfer(chain)

    async def handle_transfer(self, chain):
        """
        On client start, this tries to deposit or withdraw nectar from the sidechain.
        The direction, depends on the chain the client is running on.
        If it is on homechain, it deposits. Otherwise, withdraws.

        It also checks the balances to make sure the source chain wallet can cover the transfer.
        """
        balance = await self.client.balances.get_nct_balance(chain)

        if self.transfer_all:
            base_amount = int(balance)
        else:
            try:
                base_amount = int(convert(self.client, self.denomination, self.amount))
            except ValueError:
                logger.critical('Error trying to convert %s to 18 decimals from %s', self.amount, self.denomination)
                return

        if balance >= base_amount:
            if chain == 'home':
                # deposit
                logger.info('Depositing %s', base_amount)
                await self.client.relay.post_deposit(base_amount)
            elif chain == 'side':
                # withdraw
                logger.info('Withdrawing %s', base_amount)
                await self.client.relay.post_withdraw(base_amount)
        else:
            if chain == 'home':
                # Converting from amount_wei because it gives a better string output than self.amount
                logger.critical(
                    'Insufficient funds for deposit. Have %s nct-wei. Need %s nct-wei.', balance, base_amount)
            elif chain == 'side':
                logger.critical(
                    'Insufficient funds for withdrawal. Have %s nct-wei. Need %s nct-wei.', balance, base_amount)

            self.exit_code = 1


class Deposit(BalanceManager):
    """
    Deposit only version of Balance Manager
    """

    def __init__(self, client, denomination, transfer_all, amount, testing=0):
        super().__init__(client, denomination, transfer_all, amount, testing=testing, chains={'home'})


class Withdraw(BalanceManager):
    """
    Withdraw only version of Balance Manager
    """

    def __init__(self, client, denomination, transfer_all, amount, testing=0):
        super().__init__(client, denomination, transfer_all, amount, testing=testing, chains={'side'})


class DepositStake(BalanceManager):
    """
    Deposit only version of Balance Manager
    """

    def __init__(self, client, denomination, transfer_all, amount, testing=0, chain='side'):
        super().__init__(client, denomination, transfer_all, amount, testing=testing, chains={chain})

    async def handle_transfer(self, chain):
        """
        On client start, this tries to deposit or withdraw nectar from the sidechain.
        The direction, depends on the chain the client is running on.
        If it is on homechain, it deposits. Otherwise, withdraws.

        It also checks the balances to make sure the source chain wallet can cover the transfer.
        """
        balance = await self.client.balances.get_nct_balance(chain)
        min_stake = int(await self.client.staking.parameters[chain].get('minimum_stake'))
        max_stake = int(await self.client.staking.parameters[chain].get('maximum_stake'))
        staking_balance = int(await self.client.staking.get_total_balance(chain))

        if self.transfer_all:
            base_amount = int(balance)
        else:
            try:
                base_amount = int(convert(self.client, self.denomination, self.amount))
            except ValueError:
                logger.critical('Error trying to convert %s to 18 decimals from %s', self.amount, self.denomination)
                return
        if balance < base_amount:
            logger.critical(
                'Insufficient funds for staking deposit. Have %s nct-wei. Need %s nct-wei.',
                balance,
                base_amount)
            self.exit_code = 1
        if not (min_stake <= base_amount + staking_balance <= max_stake):
            logger.critical(
                '%s plus the staking balance of %s is not between %s and %s',
                base_amount,
                staking_balance,
                min_stake,
                max_stake)
        else:
            await self.client.staking.post_deposit(base_amount, chain)


class WithdrawStake(BalanceManager):
    """
    Withdraw only version of Balance Manager
    """

    def __init__(self, client, denomination, transfer_all, amount, testing=0, chain='side'):
        super().__init__(client, denomination, transfer_all, amount, testing=testing, chains={chain})

    async def handle_transfer(self, chain):
        """
        On client start, this tries to deposit or withdraw nectar from the sidechain.
        The direction, depends on the chain the client is running on.
        If it is on homechain, it deposits. Otherwise, withdraws.

        It also checks the balances to make sure the source chain wallet can cover the transfer.
        """
        balance = await self.client.staking.get_withdrawable_balance(chain)

        if self.transfer_all:
            base_amount = int(balance)
        else:
            try:
                base_amount = int(convert(self.client, self.denomination, self.amount))
            except ValueError:
                logger.critical('Error trying to convert %s to 18 decimals from %s', self.amount, self.denomination)
                return

        if balance >= base_amount:
            await self.client.staking.post_withdraw(base_amount, chain)
        else:
            logger.critical(
                'Insufficient funds for staking withdrawal. Requested %s nct-wei, but only %s nct-wei is available.',
                base_amount,
                balance)

            self.exit_code = 1


class Maintainer(object):
    """
    This class maintains a balance on the sidechain.
    It requires a base setup of a minimum balance.
    Optionally, it can take a maximum balance, so that earnings can automatically be transferred back to the homechain.
    """

    def __init__(self, client, denomination, confirmations, minimum, refill_amount, maximum, withdraw_target, testing=0):
        self.client = client
        self.client.on_run.register(self._set_locks)
        self.client.on_new_block.register(self.watch_balance)
        self.deposit_lock = None
        self.block_lock = None
        self.last_relay = None
        self.latest_block = 0
        self.last_balance = 0
        self.initial_balance = 0
        self.denomination = denomination
        self.confirmations = confirmations
        self.minimum = int(convert(client, denomination, minimum))
        self.refill_amount = int(convert(client, denomination, refill_amount))
        self.maximum = None if maximum < 0 else int(convert(client, denomination, maximum))
        self.withdraw_target = None if withdraw_target < 0 else int(convert(client, denomination, withdraw_target))
        self.testing = testing
        self.transfers = 0

    async def _set_locks(self, chain):
        """
        Once the client starts the async loop, we can set the locks.
        :param chain: Chain value is ignored here.
        """
        self.deposit_lock = asyncio.Lock()
        self.block_lock = asyncio.Lock()

    def run(self):
        """
        Starts the client.
        Have to run with both chains, or lots of nonce errors
        """
        self.client.run(chains={'home', 'side'})

    async def try_withdrawal(self, side_balance):
        """
        Computes the amount to withdraw based on the current balance, and the target balance.
        Then, it tries to withdraw the required NCT.
        """
        withdrawal_amount = side_balance - self.withdraw_target
        if side_balance > withdrawal_amount:
            logger.info(
                'Sidechain balance of %s nct-wei exceeds maximum %s nct-wei.  Withdrawing %s nct-wei',
                side_balance,
                self.maximum,
                withdrawal_amount)
            await self.client.relay.post_withdraw(withdrawal_amount)
            self.transfers += 1
            if self.testing > 0:
                logger.info('Transferred %s times of %s', self.transfers, self.testing)
            # Don't need to wait on withdrawals. The funds are instantly locked up on the sidechain
        else:
            logger.critical(
                'Insufficient funds for withdrawal. Have %s nct-wei. Need %s nct-wei.', side_balance, withdrawal_amount)

    async def try_deposit(self, side_balance):
        """
        Deposits the refill amount to the sidechain, as long as there is a sufficient balance on the homechain.
        """
        home_balance = await self.client.balances.get_nct_balance(chain='home')
        side_balance = await self.client.balances.get_nct_balance(chain='side')
        if home_balance >= self.refill_amount:
            logger.info(
                'Sidechain balance of %s nct-wei is under minimum %s nct-wei. Depositing %s nct-wei',
                side_balance,
                self.minimum,
                self.refill_amount)
            # Tell it to wait for the transaction to complete
            if await self.client.relay.post_deposit(self.refill_amount):
                # Account for blocks that moved while creating the transaction, and the transactions made by the relay
                async with self.block_lock:
                    self.last_relay = self.latest_block + RELAY_LEEWAY
                    self.last_balance = side_balance
                    self.initial_balance = side_balance
            self.transfers += 1
            if self.testing > 0:
                logger.info('Transferred %s times of %s', self.transfers, self.testing)
        else:
            logger.critical(
                'Insufficient funds for deposit. Have %s nct-wei. Need %s nct-wei',
                home_balance,
                self.refill_amount)

    async def watch_balance(self, block, chain):
        """
        Stores the latest block and then kicks off some balance checks.
        If the balance is outside the given range, it deposits, or withdraws as needed.
        """
        # Do nothing when talking to polyswarmd-fast
        if isinstance(self.client.bounties, polyswarmclient.fast.bountiesclient.BountiesClient):
            return

        if chain == 'side':
            return

        # Keep block up to date, so we can use that value when figuring out what block the transaction may have gone in
        if chain == 'home':
            async with self.block_lock:
                if block > self.latest_block:
                    self.latest_block = block
                else:
                    return

        async with self.deposit_lock:
            side_balance = await self.client.balances.get_nct_balance(chain='side')
            if 0 < self.testing <= self.transfers:
                logger.info('Finished text runs')
                asyncio_stop()

            if self.last_relay is not None and (self.last_relay + self.confirmations) >= block:
                more_blocks = self.last_relay + self.confirmations - block
                logger.info('Waiting for %d more blocks', more_blocks)
                return
            elif self.last_relay is not None:
                logger.info('Checking NCT balance')
                # We can handle up to half refill_amount changes in either direction for any given block.
                # Greater than that, and the client will have to restart.
                if self.last_balance + (self.refill_amount / 2) >= side_balance:
                    # Update balance, so each check against refill amount is from the latest changes
                    self.last_balance = side_balance
                    logger.error(
                        'Transfer does not appear to have completed. '
                        'Initial Balance: %s nct-wei. Current Balance: %s nct-wei.',
                        self.initial_balance,
                        side_balance)
                    return
                else:
                    logger.info('Balance increased to %s nct-wei', side_balance)
                    self.last_relay = None
                    self.last_balance = 0
                    self.initial_balance = 0

            if self.maximum is not None and self.withdraw_target is not None and side_balance > self.maximum:
                await self.try_withdrawal(side_balance)
            elif side_balance < self.minimum:
                await self.try_deposit(side_balance)


class ViewBalance(object):
    """
    ViewBalance retrieves the NCT balance from a chain
    Create a client, choose a chain and amount then run it.
    """

    def __init__(self, client, denomination, chain):
        self.client = client
        self.client.on_run.register(self.handle_run)
        self.denomination = denomination
        self.chain = chain
        self.exit_code = 0

    def run(self):
        """
        Starts the client on whichever chain this uses.
        """
        self.client.run(chains=[self.chain])

    def run_oneshot(self):
        """
        Runs run_task once
        """
        configure_event_loop()
        asyncio.get_event_loop().run_until_complete(self.client.run_task(chains=[self.chain], listen_for_events=False))

    async def handle_run(self, chain):
        """
        Just fetches the balance
        """
        balance = await self.client.balances.get_nct_balance(chain)
        logger.critical('Balance is %s (%s) on %s ', int(convert_from(self.client, self.denomination, balance)),
                        self.denomination, chain)


class ViewStake(ViewBalance):
    async def handle_run(self, chain):
        """
        Just fetches the staking balances
        """
        available_balance = convert_from(self.client,
                                         self.denomination,
                                         await self.client.staking.get_withdrawable_balance(chain))
        total_balance = convert_from(self.client,
                                     self.denomination,
                                     await self.client.staking.get_total_balance(chain))
        logger.critical('Can withdraw %s (%s) of a total staked %s (%s) on %s', available_balance, self.denomination, total_balance, self.denomination, chain)
