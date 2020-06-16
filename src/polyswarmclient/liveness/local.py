import asyncio
import dataclasses
import json
import os
import logging
import platform
import tempfile


from polyswarmclient.liveness.exceptions import LivenessReadError
from polyswarmclient.liveness.liveness import LivenessCheck, Liveness, LivenessRecorder

logger = logging.getLogger(__name__)


class FileLock:
    """Locks a file so that only LivelinessRecorder or LivelinessChecker can access at any moment"""
    def __init__(self, fileno):
        self.fileno = fileno

    def acquire(self):
        if 'Windows' not in platform.system():
            self.acquire_unix()
        else:
            self.acquire_windows()

    def release(self):
        if 'Windows' not in platform.system():
            self.release_unix()

    # noinspection PyUnresolvedReferences
    def acquire_unix(self):
        from fcntl import lockf, LOCK_EX
        lockf(self.fileno, LOCK_EX)

    # noinspection PyUnresolvedReferences
    def acquire_windows(self):
        from msvcrt import locking, LK_LOCK
        locking(self.fileno, LK_LOCK, 1)

    # noinspection PyUnresolvedReferences
    def release_unix(self):
        from fcntl import lockf, LOCK_UN
        lockf(self.fileno, LOCK_UN)

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class LocalLivenessCheck(LivenessCheck):
    """Checks the liveness by reading a tempfile which should contain liveness information"""
    def __init__(self, loop_iteration_threshold=5, average_wait_threshold=10):
        self.path = os.path.join(tempfile.gettempdir(), 'liveness')
        super().__init__(loop_iteration_threshold, average_wait_threshold)

    def get_liveness(self):
        if not os.path.exists(self.path) or not os.path.isfile(self.path):
            raise LivenessReadError()

        with open(self.path, 'r+') as f:
            try:
                with FileLock(f.fileno()):
                    content = f.read()
                    logger.debug('Liveliness contents %s', content)
                    return Liveness(**json.loads(content))
            except OSError:
                logger.exception('Unable to lock file')
                raise LivenessReadError()

    def get_average_task_wait(self):
        pass


class LocalLivenessRecorder(LivenessRecorder):
    """Record liveness data in a tempfile"""
    def __init__(self):
        self.path = os.path.join(tempfile.gettempdir(), 'liveness')
        super().__init__()

    async def record(self):
        asyncio.get_event_loop().create_task(self.write_async())

    async def write_async(self):
        """Get the json format of Liveliness, and write to the file"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None,
                                   self.write_sync,
                                   json.dumps(dataclasses.asdict(self.liveness)))

    def write_sync(self, content):
        """ Write the given content to the file at the given path.

        Args:
            content: content to write into the file
        """
        with open(self.path, 'w') as f:
            try:
                with FileLock(f.fileno()):
                    f.write(content)
            except OSError:
                logger.exception('Unable to lock file')
