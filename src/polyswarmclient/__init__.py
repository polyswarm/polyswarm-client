import aiohttp
import asyncio
import backoff
import json
import logging
import os
import time
import websockets

from web3.auto import w3

from polyswarmclient import events
from polyswarmclient import utils
from polyswarmclient.bidstrategy import BidStrategyBase
from polyswarmclient.ethereum.transaction import NonceManager
from polyswarmclient.liveness.local import LocalLivenessRecorder


logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 5
MAX_ARTIFACTS = 256
RATE_LIMIT_SLEEP = 2.0


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

    def __init__(self, polyswarmd_addr, keyfile, password, api_key=None, tx_error_fatal=False,
                 insecure_transport=False):
        if api_key and insecure_transport:
            raise ValueError('Refusing to send API key over insecure transport')

        protocol = 'http://' if insecure_transport else 'https://'
        self.polyswarmd_uri = protocol + polyswarmd_addr
        logger.debug('self.polyswarmd_uri: %s', self.polyswarmd_uri)

        self.api_key = api_key

        self.tx_error_fatal = tx_error_fatal
        self.params = {}

        with open(keyfile, 'r') as f:
            self.priv_key = w3.eth.account.decrypt(f.read(), password)

        self.account = w3.eth.account.from_key(self.priv_key).address
        logger.info('Using account: %s', self.account)

        self.__session = None

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

    @backoff.on_exception(backoff.expo, Exception)
    def run(self, chains=None):
        """Run the main event loop

        Args:
            chains (set(str)): Set of chains to operate on. Defaults to {'home', 'side'}
        """
        if chains is None:
            chains = {'home', 'side'}

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
        """
        self.params = {'account': self.account}
        if chains is None:
            chains = {'home', 'side'}

        if self.api_key and not self.polyswarmd_uri.startswith('https://'):
            raise Exception('Refusing to send API key over insecure transport')

        self.__schedules = {chain: events.Schedule() for chain in chains}
        # We can now create our locks, because we are assured that the event loop is set
        self.nonce_managers = {chain: NonceManager(self, chain) for chain in chains}
        for nonce_manager in self.nonce_managers.values():
            await nonce_manager.setup()

        try:
            await self.liveness_recorder.start()
            # No limits on connections
            conn = aiohttp.TCPConnector(limit=0, limit_per_host=0)
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            async with aiohttp.ClientSession(connector=conn, timeout=timeout) as self.__session:
                await self.create_sub_clients()
                for chain in chains:
                    await self.bounties.fetch_parameters(chain)
                    await self.staking.fetch_parameters(chain)
                    await self.on_run.run(chain)

                # At this point we're initialized, reset our failure counter and listen for events
                self.tries = 0
                if listen_for_events:
                    await asyncio.wait([self.listen_for_events(chain) for chain in chains])
        finally:
            self.__session = None
            self.clear_sub_clients()

    def clear_sub_clients(self):
        self.balances = None
        self.bounties = None
        self.offers = None
        self.relay = None
        self.staking = None

    @backoff.on_exception(backoff.expo, (aiohttp.ClientError, asyncio.TimeoutError), max_tries=3)
    async def create_sub_clients(self):
        # Test polyswarmd, then either load ethereum or fast
        try:
            # Wallets only exists in polyswarmd-fast
            headers = {}
            if self.api_key:
                headers.update({'Authorization': self.api_key})
            async with self.__session.options(f'{self.polyswarmd_uri}/wallets/', headers=headers) as response:
                if response.status == 404:
                    logger.debug('Using ethereum sub-clients')
                    self.create_ethereum_sub_clients()
                    return
                response.raise_for_status()
            logger.debug('Using fast sub-clients')
            self.create_fast_sub_clients()
        except aiohttp.ClientConnectionError:
            logger.exception('Unable to connect to polyswarmd')
            raise
        except asyncio.TimeoutError:
            logger.exception('Timeout connecting to polyswarmd')
            raise

    def create_ethereum_sub_clients(self):
        from polyswarmclient.ethereum import BalanceClient,  BountiesClient, StakingClient, OffersClient, RelayClient
        self.bounties = BountiesClient(self)
        self.staking = StakingClient(self)
        self.offers = OffersClient(self)
        self.relay = RelayClient(self)
        self.balances = BalanceClient(self)

    def create_fast_sub_clients(self):
        from polyswarmclient.fast import BalanceClient,  BountiesClient, StakingClient, OffersClient, RelayClient
        self.bounties = BountiesClient(self)
        self.staking = StakingClient(self)
        self.offers = OffersClient(self)
        self.relay = RelayClient(self)
        self.balances = BalanceClient(self)

        async def periodic():
            # FIXME PSC continues to hit a down polyswarmd, because the trigger is time, not blocks from websocket
            while True:
                number = int(time.time())
                asyncio.get_event_loop().create_task(self.__handle_scheduled_events(number, chain='side'))
                asyncio.get_event_loop().create_task(self.liveness_recorder.advance_time(number))
                asyncio.get_event_loop().create_task(self.on_new_block.run(number=number, chain='side'))
                await asyncio.sleep(1)

        asyncio.get_event_loop().create_task(periodic())

    async def make_request(self, method, path, chain, json=None, send_nonce=False, api_key=None, tries=2, params=None):
        """Make a request to polyswarmd, expecting a json response

        Args:
            method (str): HTTP method to use
            path (str): Path portion of URI to send request to
            chain (str): Which chain to operate on
            json (obj): JSON payload to send with request
            send_nonce (bool): Whether to include a base_nonce query string parameter in this request
            api_key (str): Override default API key
            tries (int): Number of times to retry before giving up
            params (dict): Optional params for the request
        Returns:
            (bool, obj): Tuple of boolean representing success, and response JSON parsed from polyswarmd
        """
        if chain != 'home' and chain != 'side':
            raise ValueError(f'Chain parameter must be `home` or `side`, got {chain}')
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        # Ensure we try at least once
        tries = max(tries, 1)

        uri = f'{self.polyswarmd_uri}{path}'
        logger.debug('making request to url: %s', uri)

        if params is None:
            params = dict()

        params.update(dict(self.params))
        params['chain'] = chain

        if send_nonce:
            # Set to 0 because I will replace it later
            params['base_nonce'] = 0

        # Allow overriding API key per request
        if api_key is None:
            api_key = self.api_key
        headers = {}

        if api_key:
            headers = {'Authorization': api_key}

        qs = '&'.join([a + '=' + str(b) for (a, b) in params.items()])
        response = {}
        while tries > 0:
            tries -= 1

            response = {}
            try:
                async with self.__session.request(method, uri, params=params, headers=headers, json=json)\
                        as raw_response:
                    try:
                        # Handle "Too many requests" rate limit by not hammering server, and instead sleeping a bit
                        if raw_response.status == 429:
                            logger.warning('Hit polyswarmd rate limits, sleeping then trying again')
                            await asyncio.sleep(RATE_LIMIT_SLEEP)
                            tries += 1
                            continue

                        response = await raw_response.json()
                    except (ValueError, aiohttp.ContentTypeError):
                        response = await raw_response.read() if raw_response else 'None'
                        logger.error('Received non-json response from polyswarmd: %s, url: %s', response, uri)
                        response = {}
                        continue
            except (OSError, aiohttp.ServerDisconnectedError):
                logger.error('Connection to polyswarmd refused, retrying')
            except asyncio.TimeoutError:
                logger.error('Connection to polyswarmd timed out, retrying')

            logger.debug('%s %s?%s', method, path, qs, extra={'extra': response})

            if not utils.check_response(response):
                if tries > 0:
                    logger.info('Request %s %s?%s failed, retrying...', method, path, qs)
                    continue
                else:
                    logger.warning('Request %s %s?%s failed, giving up', method, path, qs)
                    return False, response.get('errors')

            return True, response.get('result')

        return False, response.get('errors')

    async def list_artifacts(self, ipfs_uri, api_key=None, tries=2):
        """Return a list of artificats from a given ipfs_uri.

        Args:
            ipfs_uri (str): IPFS URI to get artifiacts from.
            api_key (str): Override default API key

        Returns:
            List[(str, str)]: A list of tuples. First tuple element is the artifact name, second tuple element
            is the artifact hash.
        """
        if not utils.is_valid_ipfs_uri(ipfs_uri):
            logger.warning('Invalid IPFS URI: %s', ipfs_uri)
            return []

        path = f'/artifacts/{ipfs_uri}/'

        # Chain parameter doesn't matter for artifacts, just set to side
        success, result = await self.make_request('GET', path, 'side', api_key=api_key, tries=tries)
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

    async def get_artifact(self, ipfs_uri, index, api_key=None, tries=2):
        """Retrieve an artifact from IPFS via polyswarmd

        Args:
            ipfs_uri (str): IPFS hash of the artifact to retrieve
            index (int): Index of the sub artifact to retrieve
            api_key (str): Override default API key
        Returns:
            (bytes): Content of the artifact
        """
        if not utils.is_valid_ipfs_uri(ipfs_uri):
            raise ValueError('Invalid IPFS URI')

        uri = f'{self.polyswarmd_uri}/artifacts/{ipfs_uri}/{index}/'
        logger.debug('getting artifact from uri: %s', uri)

        params = dict(self.params)

        # Allow overriding API key per request
        if api_key is None:
            api_key = self.api_key
        headers = {'Authorization': api_key} if api_key is not None else None

        while tries > 0:
            tries -= 1

            try:
                async with self.__session.get(uri, params=params, headers=headers) as raw_response:
                    # Handle "Too many requests" rate limit by not hammering server, and instead sleeping a bit
                    if raw_response.status == 429:
                        logger.warning('Hit polyswarmd rate limits, sleeping then trying again')
                        await asyncio.sleep(RATE_LIMIT_SLEEP)
                        tries += 1
                        continue

                    if raw_response.status == 200:
                        return await raw_response.read()
            except (OSError, aiohttp.ServerDisconnectedError):
                logger.error('Connection to polyswarmd refused')
            except asyncio.TimeoutError:
                logger.error('Connection to polyswarmd timed out')

        return None

    @staticmethod
    def to_wei(amount, unit='ether'):
        return w3.toWei(amount, unit)

    @staticmethod
    def from_wei(amount, unit='ether'):
        return w3.fromWei(amount, unit)

    # Async iterator helper class
    class __GetArtifacts(object):
        def __init__(self, client, ipfs_uri, api_key=None):
            self.i = 0
            self.client = client
            self.ipfs_uri = ipfs_uri
            self.api_key = api_key

        async def __aiter__(self):
            return self

        async def __anext__(self):
            if not utils.is_valid_ipfs_uri(self.ipfs_uri):
                raise StopAsyncIteration

            i = self.i
            self.i += 1

            if i < MAX_ARTIFACTS:
                content = await self.client.get_artifact(self.ipfs_uri, i, api_key=self.api_key)
                if content:
                    return content

            raise StopAsyncIteration

    def get_artifacts(self, ipfs_uri, api_key=None):
        """Get an iterator to return artifacts.

        Args:
            ipfs_uri (str): URI where artificats are located
            api_key (str): Override default API key

        Returns:
            `__GetArtifacts` iterator
        """
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        return Client.__GetArtifacts(self, ipfs_uri, api_key=api_key)

    async def post_artifacts(self, files, api_key=None, tries=2):
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

        while tries > 0:
            tries -= 1

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

                    # Make the request
                    async with self.__session.post(uri, params=params, headers=headers,
                                                   data=mpwriter) as raw_response:
                        try:
                            # Handle "Too many requests" rate limit by not hammering server, and instead sleeping a bit
                            if raw_response.status == 429:
                                logger.warning('Hit polyswarmd rate limits, sleeping then trying again')
                                await asyncio.sleep(RATE_LIMIT_SLEEP)
                                tries += 1
                                continue

                            response = await raw_response.json()
                        except (ValueError, aiohttp.ContentTypeError):
                            response = await raw_response.read() if raw_response else 'None'
                            logger.error('Received non-json response from polyswarmd: %s, uri: %s', response, uri)
                            response = {}
                            continue
                except (OSError, aiohttp.ServerDisconnectedError):
                    logger.error('Connection to polyswarmd refused, files: %s', files)
                except asyncio.TimeoutError:
                    logger.error('Connection to polyswarmd timed out, files: %s', files)
                finally:
                    for f in to_close:
                        f.close()

                logger.debug('POST/artifacts', extra={'extra': response})

                if not utils.check_response(response):
                    if tries > 0:
                        logger.info('Posting artifacts to polyswarmd failed, retrying')
                        continue
                    else:
                        logger.info('Posting artifacts to polyswarmd failed, giving up')
                        return None

                return response.get('result')

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

    @backoff.on_exception(backoff.expo, (websockets.exceptions.ConnectionClosed, OSError, asyncio.TimeoutError,
                                         websockets.exceptions.InvalidHandshake))
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
        try:
            async with websockets.connect(wsuri) as ws:
                # Fetch parameters again here so we don't miss update events
                await self.bounties.fetch_parameters(chain)
                await self.staking.fetch_parameters(chain)

                logger.error('Websocket connection to polyswarmd established')

                while not ws.closed:
                    resp = None
                    try:
                        resp = await ws.recv()
                        resp = json.loads(resp)
                        event = resp.get('event')
                        data = resp.get('data')
                        block_number = resp.get('block_number')
                        txhash = resp.get('txhash')
                    except json.JSONDecodeError:
                        logger.error('Invalid event response from polyswarmd: %s', resp)
                        continue

                    if event != 'block':
                        logger.info('Received %s on chain %s', event, chain, extra={'extra': data})

                    if event == 'connected':
                        logger.info('Connected to event socket at: %s', data.get('start_time'))
                    elif event == 'block':
                        number = data.get('number', 0)

                        if number <= last_block:
                            continue

                        if number % 100 == 0:
                            logger.debug('Block %s on chain %s', number, chain)

                        asyncio.get_event_loop().create_task(self.on_new_block.run(number=number, chain=chain))
                        # These are staying here because we need the homechain block events as well
                        asyncio.get_event_loop().create_task(self.__handle_scheduled_events(number, chain=chain))
                        asyncio.get_event_loop().create_task(self.liveness_recorder.advance_time(number))
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
                        logger.error('Invalid event type from polyswarmd: %s', resp)
        except websockets.exceptions.ConnectionClosed:
            logger.error('Websocket connection to polyswarmd closed, retrying')
            raise
        except (OSError, websockets.exceptions.InvalidHandshake):
            logger.error('Websocket connection to polyswarmd refused, retrying')
            raise
        except asyncio.TimeoutError:
            logger.error('Websocket connection to polyswarmd timed out, retrying')
            raise
