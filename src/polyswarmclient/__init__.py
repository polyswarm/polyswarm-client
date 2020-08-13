import aiohttp
import asyncio
import backoff
import functools
import json
import logging
import math
import os
import time
import websockets

from web3.auto import w3

from polyswarmclient import events
from polyswarmclient import utils
from polyswarmclient.bidstrategy import BidStrategyBase
from polyswarmclient.ethereum.transaction import NonceManager
from polyswarmclient.exceptions import RateLimitedError
from polyswarmclient.liveness.local import LocalLivenessRecorder
from polyswarmclient.backoff_wrapper import BackoffWrapper
from polyswarmclient.request_rate_limit import RequestRateLimit

logger = logging.getLogger(__name__)

MAX_ARTIFACTS = 256
RATE_LIMIT_SLEEP = 2.0
MAX_BACKOFF = 32


class Client(object):
    """Client to connected to a Ethereum wallet as well as a polyswarmd instance.

    Args:
        polyswarmd_addr (str): URI of polyswarmd you are referring to.
        keyfile (str): Keyfile filename.
        password (str): Password associated with keyfile.
        api_key (str): Your PolySwarm API key.
        tx_error_fatal (bool): Transaction errors are fatal and exit the program
        insecure_transport (bool): Allow insecure transport such as HTTP?
    """

    def __init__(self, polyswarmd_addr, keyfile, password, api_key=None, tx_error_fatal=False):
        self.polyswarmd_uri = polyswarmd_addr
        logger.debug('self.polyswarmd_uri: %s', self.polyswarmd_uri)

        self.api_key = api_key

        self.tx_error_fatal = tx_error_fatal
        self.params = {}

        with open(keyfile, 'r') as f:
            self.priv_key = w3.eth.account.decrypt(f.read(), password)

        self.account = w3.eth.account.from_key(self.priv_key).address
        logger.info('Using account: %s', self.account)

        self.rate_limit = None

        # Do not init nonce manager here. Need to wait until we can guarantee that our event loop is set.
        self.nonce_managers = {}
        self.__schedules = {}

        self.tries = 0

        self.bounties = None
        self.staking = None
        self.offers = None
        self.relay = None
        self.balances = None

        # Setup a liveliness instance
        self.liveness_recorder = LocalLivenessRecorder()

        # Events from client
        self.on_run = events.OnRunCallback()
        self.on_stop = events.OnStopCallback()

        # Events from polyswarmd
        self.on_new_block = events.OnNewBlockCallback()
        self.on_new_bounty = events.OnNewBountyCallback()
        self.on_new_assertion = events.OnNewAssertionCallback()
        self.on_reveal_assertion = events.OnRevealAssertionCallback()
        self.on_new_vote = events.OnNewVoteCallback()
        self.on_quorum_reached = events.OnQuorumReachedCallback()
        self.on_settled_bounty = events.OnSettledBountyCallback()
        self.on_initialized_channel = events.OnInitializedChannelCallback()
        self.on_deprecated = events.OnDeprecatedCallback()

        # Events scheduled on block deadlines
        self.on_reveal_assertion_due = events.OnRevealAssertionDueCallback()
        self.on_vote_on_bounty_due = events.OnVoteOnBountyDueCallback()
        self.on_settle_bounty_due = events.OnSettleBountyDueCallback()
        self.on_withdraw_stake_due = events.OnWithdrawStakeDueCallback()
        utils.configure_event_loop()

    def run(self, chains=None):
        """Run the main event loop

        Args:
            chains (set(str)): Set of chains to operate on. Defaults to {'home', 'side'}
        """
        if chains is None:
            chains = {'home', 'side'}

        # noinspection PyBroadException
        try:
            asyncio.get_event_loop().run_until_complete(self.run_task(chains=chains))
        except asyncio.CancelledError:
            logger.info('Clean exit requested')
            utils.asyncio_join()
        except Exception:
            logger.exception('Unhandled exception at top level')
            utils.asyncio_stop()
            utils.asyncio_join()

    async def run_task(self, chains=None, listen_for_events=True):
        """
        How the event loop handles running a task.

        Args:
            chains (set(str)): Set of chains to operate on. Defaults to {'home', 'side'}
            listen_for_events (bool): Whether or not to listen to the websocket for events
        """
        self.params = {'account': self.account}
        if chains is None:
            chains = {'home', 'side'}

        self.__schedules = {chain: events.Schedule() for chain in chains}
        # We can now create our locks, because we are assured that the event loop is set
        self.nonce_managers = {chain: NonceManager(self, chain) for chain in chains}
        for nonce_manager in self.nonce_managers.values():
            await nonce_manager.setup()

        self.rate_limit = await RequestRateLimit.build()

        try:
            await self.liveness_recorder.start()
            await self.create_sub_clients(chains)
            for chain in chains:
                await self.bounties.fetch_parameters(chain)
                await self.staking.fetch_parameters(chain)
                await self.on_run.run(chain)

            # At this point we're initialized, reset our failure counter and listen for events
            self.tries = 0
            if listen_for_events:
                await asyncio.wait([self.listen_for_events(chain) for chain in chains])
        finally:
            await self.on_stop.run()
            self.clear_sub_clients()

    def clear_sub_clients(self):
        self.balances = None
        self.bounties = None
        self.offers = None
        self.relay = None
        self.staking = None

    @backoff.on_exception(backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=3)
    async def create_sub_clients(self, chains):
        # Test polyswarmd, then either load ethereum or fast
        try:
            # Wallets only exists in polyswarmd-fast
            headers = {}
            if self.api_key:
                headers.update({'Authorization': self.api_key})

            async with aiohttp.ClientSession() as session:
                async with session.options(f'{self.polyswarmd_uri}/wallets/', headers=headers) as response:
                    if response.status == 404:
                        logger.debug('Using ethereum sub-clients')
                        self.create_ethereum_sub_clients(chains)
                        return
                    response.raise_for_status()
                logger.debug('Using fast sub-clients')
                self.create_fast_sub_clients(chains)
        except aiohttp.ClientConnectionError:
            logger.exception('Unable to connect to polyswarmd')
            raise
        except asyncio.TimeoutError:
            logger.exception('Timeout connecting to polyswarmd')
            raise

    def create_ethereum_sub_clients(self, chains):
        from polyswarmclient.ethereum import BalanceClient,  BountiesClient, StakingClient, OffersClient, RelayClient
        self.bounties = BountiesClient(self)
        self.staking = StakingClient(self)
        self.offers = OffersClient(self)
        self.relay = RelayClient(self)
        self.balances = BalanceClient(self)

    def create_fast_sub_clients(self, chains):
        from polyswarmclient.fast import BalanceClient,  BountiesClient, StakingClient, OffersClient, RelayClient
        self.bounties = BountiesClient(self)
        self.staking = StakingClient(self)
        self.offers = OffersClient(self)
        self.relay = RelayClient(self)
        self.balances = BalanceClient(self)

        async def periodic():
            # FIXME PSC continues to hit a down polyswarmd, because the trigger is time, not blocks from websocket
            while True:
                number = int(math.floor(time.time()))
                for chain in chains:
                    asyncio.get_event_loop().create_task(self.__handle_scheduled_events(number, chain=chain))
                    asyncio.get_event_loop().create_task(self.on_new_block.run(number=number, chain=chain))

                asyncio.get_event_loop().create_task(self.liveness_recorder.advance_time(number))
                await asyncio.sleep(1)

        asyncio.get_event_loop().create_task(periodic())

    @utils.return_on_exception((aiohttp.ServerDisconnectedError, asyncio.TimeoutError, aiohttp.ClientOSError,
                                aiohttp.ContentTypeError, RateLimitedError), default=(False, {}))
    async def make_request(self, method, path, chain, json=None, send_nonce=False, api_key=None, params=None):
        """Make a request to polyswarmd, expecting a json response

        Args:
            method (str): HTTP method to use
            path (str): Path portion of URI to send request to
            chain (str): Which chain to operate on
            json (obj): JSON payload to send with request
            send_nonce (bool): Whether to include a base_nonce query string parameter in this request
            api_key (str): Override default API key
            params (dict): Optional params for the request
        Returns:
            (bool, obj): Tuple of boolean representing success, and response JSON parsed from polyswarmd
        """
        if chain != 'home' and chain != 'side':
            raise ValueError(f'Chain parameter must be `home` or `side`, got {chain}')

        uri = f'{self.polyswarmd_uri}{path}'
        logger.debug('making request to url: %s', uri)

        params = params or {}
        params.update(dict(self.params))
        params['chain'] = chain

        if send_nonce:
            # Set to 0 because I will replace it later
            params['base_nonce'] = 0

        # Allow overriding API key per request
        api_key = api_key or self.api_key
        headers = {}
        if api_key:
            headers = {'Authorization': api_key}

        response = {}
        try:
            await self.rate_limit.check()
            async with aiohttp.ClientSession() as session:
                async with session.request(method, uri, params=params, headers=headers, json=json) as raw:
                    self._check_status_for_rate_limit(raw.status)

                    try:
                        response = await raw.json()
                    except aiohttp.ContentTypeError:
                        response = await raw.read() if raw else 'None'
                        raise

                    queries = '&'.join([a + '=' + str(b) for (a, b) in params.items()])
                    logger.debug('%s %s?%s', method, path, queries, extra={'extra': response})

                    if not utils.check_response(response):
                        logger.warning('Request %s %s?%s failed', method, path, queries)
                        return False, response.get('errors')

                    return True, response.get('result')
        except aiohttp.ContentTypeError:
            logger.exception('Received non-json response from polyswarmd: %s, url: %s', response, uri)
            raise
        except (aiohttp.ClientOSError, aiohttp.ServerDisconnectedError):
            logger.exception('Connection to polyswarmd refused')
            raise
        except asyncio.TimeoutError:
            logger.error('Connection to polyswarmd timed out')
            raise
        except RateLimitedError:
            # Handle "Too many requests" rate limit by not hammering server, and pausing all requests for a bit
            logger.warning('Hit polyswarmd rate limits, stopping all requests for a moment')
            asyncio.get_event_loop().create_task(self.rate_limit.trigger())
            raise

    async def list_artifacts(self, ipfs_uri, api_key=None):
        """Return a list of artifacts from a given ipfs_uri.

        Args:
            ipfs_uri (str): IPFS URI to get artifiacts from.
            api_key (str): Override default API key

        Returns:
            List[(str, str)]: A list of tuples. First tuple element is the artifact name, second tuple element
            is the artifact hash.
        """
        if not utils.is_valid_uri(ipfs_uri):
            logger.warning('Invalid IPFS URI: %s', ipfs_uri)
            return []

        path = f'/artifacts/{ipfs_uri}/'

        # Chain parameter doesn't matter for artifacts, just set to side
        success, result = await self.make_request('GET', path, 'side', api_key=api_key)
        if not success:
            logger.error('Expected artifact listing, received', extra={'extra': result})
            return []

        result = {} if result is None else result
        return [(a.get('name', ''), a.get('hash', '')) for a in result]

    async def get_artifact_count(self, ipfs_uri, api_key=None):
        """Gets the number of artifacts at the ipfs uri

        Args:
            ipfs_uri (str): IPFS URI for the artifact set
            api_key (str): Override default API key
        Returns:
            Number of artifacts at the uri
        """
        artifacts = await self.list_artifacts(ipfs_uri, api_key=api_key)
        return len(artifacts) if artifacts is not None and artifacts else 0

    @utils.return_on_exception((aiohttp.ServerDisconnectedError, asyncio.TimeoutError, aiohttp.ContentTypeError,
                                RateLimitedError, aiohttp.ClientOSError), default=None)
    async def get_artifact(self, ipfs_uri, index, api_key=None):
        """Retrieve an artifact from IPFS via polyswarmd

        Args:
            ipfs_uri (str): IPFS hash of the artifact to retrieve
            index (int): Index of the sub artifact to retrieve
            api_key (str): Override default API key
        Returns:
            (bytes): Content of the artifact
        """
        if not utils.is_valid_uri(ipfs_uri):
            raise ValueError('Invalid IPFS URI')

        uri = f'{self.polyswarmd_uri}/artifacts/{ipfs_uri}/{index}/'
        logger.debug('getting artifact from uri: %s', uri)

        params = dict(self.params)

        # Allow overriding API key per request
        api_key = api_key or self.api_key
        headers = {}
        if api_key:
            headers = {'Authorization': api_key}

        try:
            await self.rate_limit.check()
            async with aiohttp.ClientSession() as session:
                async with session.get(uri, params=params, headers=headers) as raw_response:
                    # Handle "Too many requests" rate limit by not hammering server, and instead sleeping a bit
                    self._check_status_for_rate_limit(raw_response.status)

                    if raw_response.status / 100 == 2:
                        return await raw_response.read()
        except (aiohttp.ClientOSError, aiohttp.ServerDisconnectedError):
            logger.exception('Connection to polyswarmd refused')
            raise
        except asyncio.TimeoutError:
            logger.error('Connection to polyswarmd timed out')
            raise
        except RateLimitedError:
            # Handle "Too many requests" rate limit by not hammering server, and pausing all requests for a bit
            logger.warning('Hit polyswarmd rate limits, stopping all requests for a moment')
            asyncio.get_event_loop().create_task(self.rate_limit.trigger())
            raise

    @staticmethod
    def to_wei(amount, unit='ether'):
        return w3.toWei(amount, unit)

    @staticmethod
    def from_wei(amount, unit='ether'):
        return w3.fromWei(amount, unit)

    @utils.return_on_exception((aiohttp.ServerDisconnectedError, asyncio.TimeoutError, RateLimitedError,
                                aiohttp.ClientOSError), default=None)
    async def post_artifacts(self, files, api_key=None):
        """Post artifacts to polyswarmd, flexible files parameter to support different use-cases

        Args:
            files (list[(filename, contents)]): The artifacts to upload, accepts one of:
                (filename, bytes): File name and contents to upload
                (filename, file_obj): (Optional) file name and file object to upload
                (filename, None): File name to open and upload
            api_key (str): Override default API key
        Returns:
            (str): IPFS URI of the uploaded artifact
        """

        uri = f'{self.polyswarmd_uri}/artifacts/'
        logger.debug('posting artifact to uri: %s', uri)

        params = dict(self.params)

        # Allow overriding API key per request
        if api_key is None:
            api_key = self.api_key
        headers = {'Authorization': api_key} if api_key is not None else None

        # MultipartWriter can only be used once, recreate if on retry
        with aiohttp.MultipartWriter('form-data') as mpwriter:
            response = {}
            to_close = []
            try:
                for filename, f in files:
                    # If contents is None, open filename for reading and remember to close it
                    if f is None:
                        f = open(filename, 'rb')
                        to_close.append(f)

                    # If filename is None and our file object has a name attribute, use it
                    if filename is None and hasattr(f, 'name'):
                        filename = f.name

                    if filename:
                        filename = os.path.basename(filename)
                    else:
                        filename = 'file'

                    payload = aiohttp.payload.get_payload(f, content_type='application/octet-stream')
                    payload.set_content_disposition('form-data', name='file', filename=filename)
                    mpwriter.append_payload(payload)
                    await self.rate_limit.check()
                    # Make the request
                    async with aiohttp.ClientSession() as session:
                        async with session.post(uri, params=params, headers=headers,
                                                data=mpwriter) as raw_response:

                            self._check_status_for_rate_limit(raw_response.status)
                            try:
                                response = await raw_response.json()
                            except (ValueError, aiohttp.ContentTypeError):
                                response = await raw_response.read() if raw_response else 'None'
                                logger.error('Received non-json response from polyswarmd: %s, uri: %s', response, uri)
                                response = {}
            except (aiohttp.ClientOSError, aiohttp.ServerDisconnectedError):
                logger.exception('Connection to polyswarmd refused, files: %s', files)
                raise
            except asyncio.TimeoutError:
                logger.error('Connection to polyswarmd timed out, files: %s', files)
                raise
            except RateLimitedError:
                # Handle "Too many requests" rate limit by not hammering server, and pausing all requests for a bit
                logger.warning('Hit polyswarmd rate limits, stopping all requests for a moment')
                asyncio.get_event_loop().create_task(self.rate_limit.trigger())
                raise
            finally:
                for f in to_close:
                    f.close()

            logger.debug('POST/artifacts', extra={'extra': response})

            if not utils.check_response(response):
                logger.info('Posting artifacts to polyswarmd failed, giving up')
                return None

            return response.get('result')

    @staticmethod
    def _check_status_for_rate_limit(status):
        if status == 429:
            raise RateLimitedError

    def schedule(self, expiration, event, chain):
        """Schedule an event to execute on a particular block

        Args:
            expiration (int): Which block to execute on
            event (Event): Event to trigger on expiration block
            chain (str): Which chain to operate on
        """
        if chain != 'home' and chain != 'side':
            raise ValueError(f'Chain parameter must be `home` or `side`, got {chain}')
        self.__schedules[chain].put(expiration, event)

    async def __handle_scheduled_events(self, number, chain):
        """Perform scheduled events when a new block is reported

        Args:
            number (int): The current block number reported from polyswarmd
            chain (str): Which chain to operate on
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('Chain parameter must be `home` or `side`, got {chain}')
        while self.__schedules[chain].peek() and self.__schedules[chain].peek()[0] < number:
            exp, task = self.__schedules[chain].get()
            if isinstance(task, events.RevealAssertion):
                asyncio.get_event_loop().create_task(
                    self.on_reveal_assertion_due.run(bounty_guid=task.guid, index=task.index, nonce=task.nonce,
                                                     verdicts=task.verdicts, metadata=task.metadata, chain=chain))
            elif isinstance(task, events.SettleBounty):
                asyncio.get_event_loop().create_task(
                    self.on_settle_bounty_due.run(bounty_guid=task.guid, chain=chain))
            elif isinstance(task, events.VoteOnBounty):
                asyncio.get_event_loop().create_task(
                    self.on_vote_on_bounty_due.run(bounty_guid=task.guid, votes=task.votes,
                                                   valid_bloom=task.valid_bloom, chain=chain))
            elif isinstance(task, events.WithdrawStake):
                asyncio.get_event_loop().create_task(
                    self.on_withdraw_stake_due.run(amount=task.amount, chain=chain))

    async def listen_for_events(self, chain):
        """Listen for events via websocket connection to polyswarmd
        Args:
            chain (str): Which chain to operate on
        """
        if chain != 'home' and chain != 'side':
            raise ValueError(f'Chain parameter must be `home` or `side`, got {chain}')
        if not self.polyswarmd_uri.startswith('http'):
            raise ValueError(f'polyswarmd_uri protocol is not http or https, got {self.polyswarmd_uri}')

        # http:// -> ws://, https:// -> wss://
        wsuri = f'{self.polyswarmd_uri.replace("http", "ws", 1)}/events/?chain={chain}'
        last_block = 0

        async for message in self.websocket_events(wsuri, chain):
            next_block = await self.route_websocket_message(message, last_block, chain)
            if next_block:
                last_block = next_block

        # If the websocket closes naturally, exit this function
        logger.info('%s chain closed the websocket', chain)

    async def websocket_events(self, websocket_uri, chain):
        exponential_backoff = BackoffWrapper(backoff.expo, max_value=MAX_BACKOFF)
        while True:
            try:
                async with websockets.connect(websocket_uri) as websocket:
                    # reset backoff because we got a connection
                    exponential_backoff.reset()
                    logger.error('Websocket connection to polyswarmd established')
                    # Fetch parameters again here because we may have missed update events
                    await self.bounties.fetch_parameters(chain)
                    await self.staking.fetch_parameters(chain)
                    while not websocket.closed:
                        message = await websocket.recv()
                        if message is not None:
                            logger.debug('Received message on websocket', extra={'extra': message})
                            yield message
            except (websockets.exceptions.ConnectionClosed, asyncio.streams.IncompleteReadError):
                logger.error('Websocket connection to polyswarmd closed, retrying')
                await exponential_backoff.sleep()
            except (OSError, websockets.exceptions.InvalidHandshake):
                logger.error('Websocket connection to polyswarmd refused, retrying')
                await exponential_backoff.sleep()
            except asyncio.TimeoutError:
                logger.error('Websocket connection to polyswarmd timed out, retrying')
                await exponential_backoff.sleep()

    async def route_websocket_message(self, message, last_block, chain):
        try:
            message = json.loads(message)
            event = message.get('event')
            data = message.get('data')
            block_number = message.get('block_number')
            txhash = message.get('txhash')
        except json.JSONDecodeError:
            logger.error('Invalid event message from polyswarmd: %s', message)
            return

        if event != 'block':
            logger.info('Received %s on chain %s', event, chain, extra={'extra': data})

        if event == 'connected':
            logger.info('Connected to event socket at: %s', data.get('start_time'))
        elif event == 'block':
            number = data.get('number', 0)

            if number <= last_block:
                return

            if number % 100 == 0:
                logger.debug('Block %s on chain %s', number, chain)

            asyncio.get_event_loop().create_task(self.on_new_block.run(number=number, chain=chain))
            # These are staying here because we need the homechain block events as well
            asyncio.get_event_loop().create_task(self.__handle_scheduled_events(number, chain=chain))
            asyncio.get_event_loop().create_task(self.liveness_recorder.advance_time(number))
            return number
        elif event == 'fee_update':
            d = {'bounty_fee': data.get('bounty_fee'), 'assertion_fee': data.get('assertion_fee')}
            await self.bounties.parameters[chain].update({k: v for k, v in d.items() if v is not None})
        elif event == 'window_update':
            d = {'assertion_reveal_window': data.get('assertion_reveal_window'),
                 'arbiter_vote_window': data.get('arbiter_vote_window')}
            await self.bounties.parameters[chain].update({k: v for k, v in d.items() if v is not None})
        elif event == 'bounty':
            asyncio.get_event_loop().create_task(
                self.on_new_bounty.run(**data, block_number=block_number, txhash=txhash, chain=chain))
        elif event == 'assertion':
            asyncio.get_event_loop().create_task(
                self.on_new_assertion.run(**data, block_number=block_number, txhash=txhash,
                                          chain=chain))
        elif event == 'reveal':
            asyncio.get_event_loop().create_task(
                self.on_reveal_assertion.run(**data, block_number=block_number, txhash=txhash,
                                             chain=chain))
        elif event == 'vote':
            asyncio.get_event_loop().create_task(
                self.on_new_vote.run(**data, block_number=block_number, txhash=txhash, chain=chain))
        elif event == 'quorum':
            asyncio.get_event_loop().create_task(
                self.on_quorum_reached.run(**data, block_number=block_number, txhash=txhash,
                                           chain=chain))
        elif event == 'settled_bounty':
            asyncio.get_event_loop().create_task(
                self.on_settled_bounty.run(**data, block_number=block_number, txhash=txhash,
                                           chain=chain))
        elif event == 'deprecated':
            asyncio.get_event_loop().create_task(
                self.on_deprecated.run(**data, block_number=block_number, txhash=txhash,
                                       chain=chain))
        elif event == 'initialized_channel':
            asyncio.get_event_loop().create_task(
                self.on_initialized_channel.run(**data, block_number=block_number, txhash=txhash))
        else:
            logger.error('Invalid event type from polyswarmd: %s', message)
