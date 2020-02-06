import asyncio
import logging
import os
import sys
import uuid

from hexbytes import HexBytes
from web3 import Web3
from concurrent.futures import ThreadPoolExecutor

import base58

logger = logging.getLogger(__name__)

TASK_TIMEOUT = 1.0
MAX_WAIT = int(os.getenv('WORKER_BACKOFF', '15'))
MAX_WORKERS = 4


def to_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return bytes(value, 'utf-8')
    if isinstance(value, int):
        return bytes(str(value), 'utf-8')


def sha3(seed):
    return Web3.keccak(to_bytes(seed))


def int_to_bytes(i):
    h = hex(i)[2:]
    return bytes.fromhex('0' * (64 - len(h)) + h)


def int_from_bytes(b):
    return int.from_bytes(b, byteorder='big')


def bool_list_to_int(bs):
    return sum([1 << n if b else 0 for n, b in enumerate(bs)])


def int_to_bool_list(i, expected_size):
    # return empty list when 0 and no items expected (Return actual value if > 0)
    if expected_size == 0 and i == 0:
        return []
    s = format(i, 'b')
    bool_list = [x == '1' for x in s[::-1]]
    diff = expected_size - len(bool_list)
    bool_list.extend([False] * diff)
    if diff < 0:
        logger.warning('expected %s bool values when converting %s, found %s in %s', expected_size, i, len(bool_list),
                       bool_list)
    return bool_list


def guid_as_string(guid):
    return str(uuid.UUID(int=int(guid), version=4))


def calculate_commitment(account, verdicts, nonce=None):
    if nonce is None:
        nonce = os.urandom(32)
    if isinstance(nonce, int):
        nonce = int_to_bytes(nonce)
    account = int(account, 16)
    commitment = sha3(int_to_bytes(verdicts ^ int_from_bytes(sha3(nonce)) ^ account))
    return int_from_bytes(nonce), int_from_bytes(commitment)


def configure_event_loop():
    # Default event loop does not support pipes on Windows
    if sys.platform == 'win32':
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.SelectorEventLoop()

    # Default executor spawns way too many threads, set this to a reasonable default
    loop.set_default_executor(ThreadPoolExecutor(max_workers=MAX_WORKERS))
    asyncio.set_event_loop(loop)


def asyncio_join():
    """Gather all remaining tasks, assumes loop is not running"""
    loop = asyncio.get_event_loop()
    pending = asyncio.Task.all_tasks(loop)

    loop.run_until_complete(asyncio.wait(pending, loop=loop, timeout=TASK_TIMEOUT))


def asyncio_stop():
    """Stop the main event loop"""
    loop = asyncio.get_event_loop()
    pending = asyncio.Task.all_tasks(loop)

    for task in pending:
        task.cancel()


def check_response(response):
    """Check the status of responses from polyswarmd

    Args:
        response: Response dict parsed from JSON from polyswarmd
    Returns:
        (bool): True if successful else False
    """
    status = response.get('status')
    ret = status and status == 'OK'
    if not ret:
        logger.info('Received unexpected failure response from polyswarmd', extra={'extra': response})
    return ret


def is_valid_ipfs_uri(ipfs_uri):
    """Ensure that a given ipfs_uri is valid by checking length and base58 encoding.

    Args:
        ipfs_uri (str): ipfs_uri to validate

    Returns:
        bool: is this valid?
    """
    # TODO: Further multihash validation
    try:
        return len(ipfs_uri) < 100 and base58.b58decode(ipfs_uri)
    except TypeError:
        logger.error('Invalid IPFS URI: %s', ipfs_uri)
    except Exception as err:
        logger.exception('Unexpected error: %s', err)
    return False
