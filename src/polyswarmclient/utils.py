import asyncio
import base58
import functools
import logging
import os
import sys
import tempfile
import uuid
import urllib3.util
import warnings

from urllib3.util import Url

from polyswarmclient.exceptions import SecurityWarning

from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

TASK_TIMEOUT = 1.0
MAX_WAIT = int(os.getenv('WORKER_BACKOFF', '15'))
MAX_WORKERS = 4


def bool_list_to_int(bs):
    return sum([1 << n if b else 0 for n, b in enumerate(bs)])


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
    pending = asyncio.all_tasks(loop)

    loop.run_until_complete(asyncio.wait(pending, loop=loop, timeout=TASK_TIMEOUT))


def asyncio_stop():
    """Stop the main event loop"""
    loop = asyncio.get_event_loop()
    pending = asyncio.all_tasks(loop)

    for task in pending:
        task.cancel()


def is_valid_uri(uri):
    """
    Ensure that a given uri is valid among any of the support hash types
    :param uri: uri to validate
    :return: is this valid
    """
    return is_valid_ipfs_uri(uri) or is_valid_sha256(uri)


def is_valid_sha256(uri):
    """Ensure that a given uri is a valid sha256 hash by checking length, and converting to an int

        Args:
            uri (str): uri to validate

        Returns:
            bool: is this valid
        """
    try:
        return len(uri) == 64 and int(uri, 16)
    except ValueError:
        # not a sha256 uri
        pass
    except Exception as err:
        logger.exception('Unexpected error: %s', err)
    return False


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
    except ValueError:
        # not an ipfs URI
        pass
    except (TypeError, ValueError):
        logger.error('Invalid IPFS URI: %s', ipfs_uri)
    except Exception as err:
        logger.exception('Unexpected error: %s', err)
    return False


class AsyncArtifactTempfile:
    """asynchronous ctxmgr for temporary artifacts

    Notes::

    The following underlying file's methods are awaited:

        flush, peek, read, seek, write

    You can use the object like an ordinary context manager
    or supply the binary blob to be written as the first argument

        >>> blob = b'hello world'
        >>> async with AsyncArtifactTempfile(blob) as f:
        >>>     with open(f.name, 'rb') as of:
        >>>         of.read()
        b'hello world'
        >>> async with AsyncArtifactTempfile() as f:
        >>>     await f.write(blob)
        >>>     await f.read()
        b'hello world'


    The underlying file is always deleted after ctxmgr exits
    """
    def __init__(self, blob: 'bytes' = None, filename: 'str' = None, mode: 'str' = 'w+b'):
        if not filename:
            filename = os.path.join(tempfile.gettempdir(), f'artifact-{uuid.uuid4()}')
        self.name = filename

        flags = (
            os.O_RDWR | # open fd for both reading and writing
            os.O_CREAT | # create if doesn't already exist
            getattr(os, 'O_BINARY', 0) | # WinNT requires this for binary files
            getattr(os, 'O_SEQUENTIAL', 0) # optimize for (but don't require) sequential access
        )

        fd = os.open(self.name, flags, 0o666)
        try:
            self.file = open(fd, mode, buffering=0, closefd=True)
        except:  # noqa
            os.close(fd)

        self.closed = False
        self.blob = blob
        self._loop = asyncio.get_event_loop()

    async def run_in_loop(self, func, *args):
        return await self._loop.run_in_executor(None, func, *args)

    async def close(self):
        if not self.closed:
            try:
                await self.run_in_loop(self.file.close)
            finally:
                self.closed = True
                os.unlink(self.name)

    def __del__(self):
        if not self.closed:
            self.file.close()

    def __getattr__(self, name):
        a = getattr(self.__dict__['file'], name)
        if callable(a) and name in {'flush', 'peek', 'read', 'seek', 'write', 'truncate'}:
            a = functools.partial(self.run_in_loop, a)
        if not isinstance(a, int):
            setattr(self, name, a)
        return a

    async def __aenter__(self):
        await self.run_in_loop(self.file.__enter__)
        if self.blob is not None:
            await self.truncate()
            written = await self.write(self.blob)
            logger.info('wrote %d bytes to %s', written, self.name)
            await self.seek(0)
            self.blob = None
        return self

    # trap __aexit__ to ensure the file gets deleted when used in `async with`
    async def __aexit__(self, exc, value, tb):
        result = await self.run_in_loop(self.file.__exit__, exc, value, tb)
        await self.close()
        return result


def return_on_exception(exceptions=(Exception, ), default=None):
    def outer_wrapper(func):
        if not asyncio.iscoroutinefunction(func):
            raise ValueError('return_on_exception decorator can only be used on coroutines')

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except exceptions:
                return default

        return wrapper
    return outer_wrapper
