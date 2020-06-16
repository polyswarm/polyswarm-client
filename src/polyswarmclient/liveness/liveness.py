import asyncio
import logging
import math
import time

from abc import ABC, abstractmethod
from dataclasses import dataclass

from polyswarmclient.liveness.exceptions import LivenessReadError

logger = logging.getLogger(__name__)


@dataclass
class Liveness:
    last_iteration: int
    average_wait: int


class LivenessCheck(ABC):
    def __init__(self, loop_iteration_threshold=5, average_wait_threshold=10):
        self.loop_iteration_threshold = loop_iteration_threshold
        self.average_wait_threshold = average_wait_threshold

    @abstractmethod
    def get_liveness(self):
        raise NotImplementedError('get_liveness is not implemented')

    def check(self):
        """Determine if participant is running smoothly, based on given inputs"""
        try:
            liveness = self.get_liveness()
        except LivenessReadError:
            return False

        time_since_last_loop = int(math.floor(time.time())) - liveness.last_iteration
        print('Last loop was {0} seconds ago, with an average wait of {1}'.format(time_since_last_loop, liveness.average_wait))
        return time_since_last_loop < self.loop_iteration_threshold and \
            liveness.average_wait < self.average_wait_threshold


class Task:
    def __init__(self, recorder, key, start_time):
        self.recorder = recorder
        self.key = key
        self.start_time = start_time

    async def __aenter__(self):
        await self.recorder.add_waiting_task(self.key, self.start_time)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.recorder.remove_waiting_task(self.key)


class LivenessRecorder(ABC):
    def __init__(self):
        self.waiting = {}
        self.block_number = 0
        self.liveness = Liveness(last_iteration=0, average_wait=0)
        self.waiting_lock = None
        self.record_lock = None

    async def start(self):
        loop = asyncio.get_event_loop()
        await self.setup()
        loop.create_task(self.run_liveness_loop())

    async def run_liveness_loop(self):
        try:
            while True:
                await self.advance_loop()
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Clear all waiting tasks because we got cancelled
            async with self.waiting_lock:
                self.waiting = {}
            raise

    async def setup(self):
        self.waiting_lock = asyncio.Lock()
        self.record_lock = asyncio.Lock()

    async def advance_loop(self):
        """The loop is turning, and record the time of the latest iteration"""
        async with self.record_lock:
            self.liveness.last_iteration = int(math.floor(time.time()))
            await self.record()

    def waiting_task(self, key, start_time):
        """Add waiting task, but remove when done

        Use: async with liveness.waiting_task(key, start_time):

        Args:
            key: task key
            start_time: start time, in any units (either block number or time)
        """
        return Task(self, key, start_time)

    async def add_waiting_task(self, key, start_time):
        """Add some bounty as waiting to be processed.

        Args:
            key: task key
            start_time: start time, in any units (either block number or time)
        """
        asyncio.get_event_loop().create_task(self._add_waiting_task(key, start_time))

    async def _add_waiting_task(self, key, start_time):
        async with self.waiting_lock:
            if key not in self.waiting:
                self.waiting[key] = start_time

    async def remove_waiting_task(self, key):
        """Mark a task as done processing"""
        asyncio.get_event_loop().create_task(self._remove_waiting_task(key))

    async def _remove_waiting_task(self, key):
        async with self.waiting_lock:
            if key in self.waiting:
                del self.waiting[key]

    async def advance_time(self, current_time):
        """ Trigger an update to the average, based on the current time.
        For most cases, this is time in blocks, but it can be any unit

        Args:
            current_time: time in some units

        """
        time_units = 0
        async with self.waiting_lock:
            for start_time in self.waiting.values():
                time_units += current_time - start_time
        average_wait = time_units / max(len(self.waiting), 1)

        async with self.record_lock:
            self.liveness.average_wait = average_wait
            await self.record()

    @abstractmethod
    async def record(self):
        """Record the liveness values"""
        raise NotImplementedError()
