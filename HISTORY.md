# Release History

### 2.5.1 (2019-10-23)

* **Feature** - Add view-balance and view-stake sub commands in balancemanager

### 2.5.0 (2019-10-16)

* **Fix** - Recover from `timeout during wait for transaction`
* **Fix** - Fix metadata responses in default micronegine backends
* **Fix** - Support paths in polyswarmd-addr
* **Fix** - Remove platform assumptions in default microengine backends
* **Fix** - Match `Deprecated()` event changes by removing address
* **Fix** - Timeout producer scans with `asyncio.wait_for` to timeout more expediently
* **Fix** - Slow bounty timeout in producer frontend by 2 seconds
* **Fix** - Catch decode errors when decoding artifact content
* **Feature** - Use default api endpoint as default polyswarmd-addr
* **Feature** - Optionally limit daily scans with producer backends
* **Feature** - Add error level log when websocket connection reestablished
* **Feature** - Add environment var to control number of artifacts per bounty in filesystem ambassador backend
* **Feature** - Add liveliness cli tool to check if participant is still responding to bounties
* **Feature** - Add a bid per artifact in bounty

#### Breaking Changes
1. Only compatible with polyswarmd version `2.0.0` or later
1. `AbstractMicroengine.bid()` and `BidStrategyBase.bid()` returns a `list[int]` of bids that are each above the minimum
1. `OnNewAssertionCallback` passes a `list[int]` of bids
1. `OnDeprecatedCallback` no longer passed the contract address
1. `AbstractScanner.scan()` implementations should not decode URL content

### 2.4.1 (2019-09-10)

* **Fix** - Decode content before passing to the scan function, if required.

#### Breaking Changes
1. No longer need to run `content.decode('utf-8')` to get the URL for URL bounties

### 2.4.0 (2019-08-26)

* **Fix** - Use exec-form CMD directive on windows
* **Fix** - Fix crash where blocking while waiting for Scanner results would cause an engine to stop responding
* **Fix** - Reduce ambassador log output outside of testing mode
* **Feature** - Add default Eicar Arbiter
* **Feature** - Add favor/penalize filters to adjust confidence up or down 20% based on artifact metadata
* **Feature** - Add relational filters for rejecting/accepting artifacts based on metadata
* **Fix** - Clean up help output for all commands line tools
* **Fix** - Pin version of polyswarm-artifact

#### Supported relational numerical (or numeric strings) filters

* `>` - Greater than
* `>=` - Greater than or equal to
* `==` - Equal to
* `<=` - Less than or equal to
* `<` - Less than

#### Supported relational string filters

* `==` - Equal to
* `contains` - Contains
* `endswith` - Ends with
* `regex` - Regular expression
* `startswith` - Starts with

#### Deprecation

2. `--accept` and `--exclude` are deprecated, use `--filter <accept|reject> <field> <comparison> <value>`

### 2.3.1 (2019-07-06)

* **Fix** - Use empty dict instead of `None` when padding bounty metadata.

### 2.3.0 (2019-07-03)

* **Feature** - Add `--accept` and `--exclude` options in microengine to filter based on bounty metadata
* **Feature** - Add helper function `AbstractAmbassador.generate_metadata()` to make adding metadata easy.
* **Feature** - Handle changes to bounty in contracts (additional metadata)

#### Breaking Changes
1. `AbstractMicroengine.connect()` passes `accept` and `except` as kwargs to Microengine objects. Suggest add `**kwargs` to `__init__()` definition and `super().__init__()`
1. `AbstractMicroengine.fetch_and_scan_all()` parameters changed to `(self, guid, artifact_type, uri, duration, metadata, chain)`
1. `AbstractMicroengine.scan()` parameters changed to `(self, guid, artifact_type, content, metadata, chain)`
1. `AbstractArbiter.fetch_and_scan_all()` parameters changed to `(self, guid, artifact_type, uri, vote_round_end, metadata, chain)`
1. `AbstractArbiter.scan()` parameters changed to `(self, guid, artifact_type, content, metadata, chain)`
1. `AbstractScanner.scan()` parameters changed to `(self, guid, artifact_type, content, metadata, chain)`
1. `OnNewBountyCallback.run()` parameters changed to `(guid, artifact_type, author, amount, uri, expiration, metadata, block_number, txhash, chain)`
1. `AbstractAmbassador.on_after_bounty_posted()` parameters changed to `(self, guid, artifact_type, amount, ipfs_uri, expiration, chain, metadata=None)`
1. `AbstractAmbassador.on_bounty_post_failed()` parameters changed to `(self, artifact_type, amount, ipfs_uri, duration, chain, metadata=None)`
1. `AbstractAmbassador.on_before_bounty_posted()` parameters changed to `(self, artifact_type, amount, ipfs_uri, duration, chain, metadata=None)`

### 2.2.2 (2019-07-02)

* **Fix** - Don't block Redis connections when waiting on results in producer/consumer mode.
* **Fix** - Improved E2E
* **Feature** - Add support for contract deprecation.

### 2.2.1 (2019-06-14)

* **Fix** - Catch `NotImplementedError` for windows when adding up signal handler in worker event loop

### 2.2.0 (2019-06-13)

* **Feature** - All Microengines and Ambassadors attempt settle on quorum event, and other participant settle events
* **Feature** - Exit Worker gracefully on SIGTERM
* **Feature** - Add BidStrategyBase & default implementations for scaling bids with confidence

#### Breaking Changes
1. `AbstractMicroengine` subclasses must add `bid_strategy` as the last arg in `__init__(self, ...)`

### 2.1.1 (2019-06-07)

* **Fix** - Use polyswarm-artifact 1.1.1 with `architecture` fix

### 2.1.0 (2019-06-06)

* **Feature** - Push metadata to IPFS if it matches the Verdict Schema in polyswarm-artifact (Not breaking)
* **Feature** - Add Ambassador bounty submission env vars to dynamically set rate of bounty submissions
* **Fix** - Pass artifact type on second on_bounty_post_failed call
* **Fix** - Remove stop and join when scanner setup fails

### 2.0.2 (2019-05-24)

* **Feature** - Add `setup()` to `AbstractScanner` for setting up AV services in a worker

### 2.0.1 (2019-05-23)

* **Fix** - Increment counter on scan results for use in horizontal scaling of workers
* **Fix** - Reset failed tries counter on successful worker response

### 2.0.0 (2019-05-22)

* **Fix** - Cap websocket retry connection backoff wait time
* **Feature** - Add artifact type handling & filtering

#### Breaking Changes
1. `AbstractAmbassador.push_bounty()` parameters changed to `(self, artifact_type, amount, ipfs_uri, duration, chain, api_key)`
1. `AbstractAmbassador.on_bounty_post_failed()` parameters changed to `(self, artifact_type, amount, ipfs_uri, expiration, chain)`
1. `AbstractAmbassador.on_before_bounty_posted()` parameters changed to `(self, artifact_type, amount, ipfs_uri, expiration, chain)`
1. `AbstractAmbassador.on_after_bounty_posted()` parameters changed to `(self, guid, artifact_type, amount, ipfs_uri, expiration, chain)`
1. `AbstractMicroengine` and `AbstractArbiter` `.fetch_and_scan_all()` parameters changed to `(self, guid, artifact_type, uri, vote_round_end, chain)`
1. `AbstractMicroengine` and `AbstractArbiter` `.scan()` parameters changed to `(self, guid, artifact_type, content, chain)`
1. `AbstractScanner.scan()` parameters changed to `(self, guid, artifact_type, content, chain)`
1. `PolyswarmClient.on_new_bounty` event parameters changed to `(self, guid, artifact_type, author, amount, uri, expiration, block_number, txhash, chain)`
1. `Producer.scan()` parameters changed to ` (guid, artifact_type, uri, expiration_blocks, chain)`

### 1.5.6 (2019-05-16)

* **Fix** - Handle ServerDisconnectError

### 1.5.5 (2019-05-14)

* **Feature** - Add arbiter producer backend
* **Fix** - Reduce CancelledError log severity

### 1.5.4 (2019-05-14)

* **Fix** - added correct image that runs the linuxbase job

### 1.5.3 (2019-05-14)

* **Fix** - Fix docker build syntax

### 1.5.2 (2019-05-14)

* **Fix** - Fix Windows build

### 1.5.1 (2019-05-13)

* **Feature** - Standardize exit and improve failure logging
* **Feature** - Build, test, and install from polyswarm-client root on Windows
* **Feature** - Add `--denomination` and `--all` options to balancemanager

### 1.5.0 (2019-05-08)

* **Feature** - Skip expired jobs in worker, and unblock redis connection pool during worker response timeouts
* **Fix** - Check additional direct dictionary accesses i.e `var['value']` uses
* **Fix** - Remove custom pyethash
* **Feature** - Add `--client-log` option for specifying `polyswarmclient` module log level

The update from 1.4.3 to 1.5.0 is a breaking change for the microengine producer backend and workers.
Existing queued jobs will not be handled by the new worker.  

### 1.4.3 (2019-05-03)

* **Fix** - Reconnect to Redis on failure
* **Fix** - Handle Redis OOM error

### 1.4.2 (2019-04-26)

* **Feature** - Add Dockerfile to build a base Windows docker image containing polyswarm-client
* **Fix** - Clean up logging; remove polyswarmclient from loggers
* **Fix** - Clean up imports and dependencies to make polyswarm-client easier to build on Windows (remove pyethereum)

### 1.4.1 (2019-04-12)

* **Fix** - Add a timestamp (ts) key into the message payload in the producer
* **Fix** - Add a sane backoff when worker fails to process a message
* **Fix** - Error handling for mismatching keys on message processing
* **Fix** - Remove dynamically increasing/decreasing log levels via SIGUSR1/SIGUSR2
* **Fix** - Update versions for aiodns and aiohttp

### 1.4.0 (2019-04-05)

* **Feature** - Move to python3.6 by default for both Docker and tests
* **Feature** - Allow dynamically increasing/decreasing log levels via SIGUSR1/SIGUSR2
* **Feature** - Allow a configurable arbiter vote window
* **Feature** - Validate API keys passed via command line
* **Fix** - Handle invalid polyswarmd responses more robustly
* **Fix** - Adjust logging levels for insufficient balance conditions
* **Fix** - Remove "reporter" functionality (obsolete)

### 1.3.0 (2019-03-13)

* **Fix** - Fix tasks running on wrong event loop after top level exception handler
* **Fix** - Fix ambassador blocking event loop if no bounties queued

### 1.2.5 (2019-03-11)

* **Fix** - Better handling of rate limits
* **Fix** - Use fixed version of ethash for windows
* **Fix** - Fix bug with deposit/withdraw tasks not exiting cleanly
* **Fix** - Fix regression handling nonce gaps

### 1.2.4 (2019-02-22)

* **Fix** - Fix event checks for relay deposits and withdrawals in relayclient
* **Fix** - Fix handling of timeouts when fetching artifacts via workers

### 1.2.3 (2019-02-20)

* **Fix** - Fix invalid None result from transaction send

### 1.2.2 (2019-02-19)

* **Fix** - Fix issues recovering from nonce gaps
* **Fix** - Fix issues detecting artifact download failure from producer microengine backend

### 1.2.1 (2019-02-14)

* **Fix** - Fix issues handling errors and parsing events from transactions

### 1.2.0 (2019-02-12)

* **Feature** - Support reporting confidence from scan used to weight bids
* **Feature** - Redis backed producer/consumer microengine
* **Feature** - Support assertion and vote retrieval methods
* **Fix** - Pad boolean list representation of votes, verdicts and masks to an expected length

### 1.1.0 (2019-02-06)

* **Feature** - Support parameter object changes
* **Fix** - Use separated `/transactions` routes to recover from known transaction errors
* **Feature** - Calculate commitment hash locally.

### 1.0.3 (2019-01-25)

* **Feature** - Increase default log level to WARNING
* **Fix** - Add filename when one isn't provided for artifact uploads
* **Fix** - Bump aiohttp to 3.5.1 for python 3.7 support
* **Feature** - Separate polyswarm-client logger from root logger
* **Feature** - Add a submission rate option to slow ambassador bounty submissions

### 1.0.2 (2019-01-22)

* **Feature** - Change nonce handling for less lock time and faster throughput
* **Fix** - Notify on bounty post failure due to low balance
* **Feature** - Pass mask, verdicts, metadata to bid
* **Fix** - Remove block event logs
* **Fix** - Recover from unhandled exception
* **Fix** - Fix eicar ambassador bad method name

### 1.0.1 (2019-01-03)

* **Fix** - Client should exit with `os._exit` when running under Windows
* **Fix** - Make default handler methods private
* **Feature** - Submit bounties via a queue with backpressure
* **Fix** - Remove default backend of 'scratch'

### 1.0 (2019-01-01)

No change from rc6. Releasing 1.0.

### 1.0rc6 (2018-12-31)

* **Fix** - catch timeouts during requests to polyswarmd

### 1.0rc5 (2018-12-28)

* **Feature** - add clamav as an example arbiter
* **Fix** - create asyncio locks after we change the event loop
* **Fix** - attempt reconnect on connection errors
* **Fix** - do not trust polyswarmd

### 1.0rc4 (2018-12-24)

* **Fix** - check transaction responses
* **Fix** - return empty dict instead of None on transaction error
* **Fix** - better handling of polyswarmd responses
* **Fix** - don't clobber API key if one is set
* **Fix** - revise clamav example microengine to use async socket
* **Fix** - asyncio loop change detection for windows hosts

### 1.0rc3 (2018-12-15)

* **Fix** - function name corrections that were missed in rc2
* **Fix** - remove awaits added in rc2 that don't belong

### 1.0rc2 (2018-12-14)

* **Fix** - duplicate bounty event handing
* **Fix** - enhance log messages with more useful content
* **Feature** - allow overriding API key per request
* **Fix** - code cleanup and formatting; enhance events class to include block_number and txhash as function args

### 1.0rc1 (2018-12-11)

* **Fix** - corrected minimum python3 version

### 1.0rc0 (2018-12-07)

Leading up to our PolySwarm 1.0 release, we reset the numbering to 1.0 with release candidates.

* **Feature** - This is the first release published to PyPi.

### 0.2.0 (2018-11-28)

* **Feature**: Converted ambassador, arbiter, microengine, and scanner classes to be abstract classes. Updated sample engines to use new design patterns.

The update from 0.1.2 to 0.2.0 is a breaking change for Ambassadors, Arbiters, and Microengines.

#### polyswarmclient <= 0.1.2 used this pattern:

**Ambassadors**
```
from polyswarmclient.ambassador import Ambassador
class CustomAmbassador(Ambassador):
    # Ambassador implementation here
```

**Arbiters**
```
from polyswarmclient.arbiter import Arbiter
class CustomArbiter(Arbiter):
    # Arbiter implementation here
```

**Microengines**
```
from polyswarmclient.microengine import Microengine
class CustomMicroengine(Microengine):
    # Microengine implementation here
```

#### polyswarmclient >= 0.2.0, instead use the following pattern:

**Ambassadors**
```
from polyswarmclient.abstractambassador import AbstractAmbassador
class Ambassador(AbstractAmbassador):
    # Ambassador implementation here
```

**Arbiters**
```
from polyswarmclient.abstractarbiter import AbstractArbiter
class Arbiter(AbstractArbiter):
    # Arbiter implementation here
```

**Microengines**
```
from polyswarmclient.abstractmicroengine import AbstractMicroengine

class Microengine(AbstractMicroengine):
    # Microengine implementation here
```

This implies that custom microengines now only need to provide their python module name to the `--backend` argument
instead of `module_name:CustomMicroengine`.

Additionally, as of `polyswarmclient >= 0.2.0`:

* `AbstractArbiter.scan()` and `AbstractMicroengine.scan()` will now raise an exception if it
has not been overridden by a sub-class and the subclass did not provide a scanner to the constructor.
* `AbstractAmbassador.next_bounty()` will now raise an exception if not overridden by sub-class.

