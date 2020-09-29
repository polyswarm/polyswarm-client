import logging

from polyswarmclient.abstractarbiter import AbstractArbiter
from microengine.clamav import Scanner as ClamAvScanner

logger = logging.getLogger(__name__)  # Initialize logger


class Arbiter(AbstractArbiter):
    """
    Arbiter which scans samples through clamd.

    Re-uses the scanner from the clamav microengine

    Args:
        client (`Client`): Client to use
        testing (int): How many test bounties to respond to
        chains (set[str]): Chain(s) to operate on
    """

    def __init__(self, client, **kwargs):
        """Initialize a ClamAV arbiter"""
        scanner = ClamAvScanner()
        super().__init__(client, scanner, **kwargs)
