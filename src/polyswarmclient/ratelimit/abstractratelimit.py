from abc import ABC, abstractmethod


class AbstractRateLimit(ABC):
    """
    Abstract class for building a limit for scans, based on a third party requirement (Such as api key limit for a vendor)
    Allows different implementations
    """

    @abstractmethod
    async def use(self, *args, peek=False, **kwargs):
        """
        Mark that some value of the limit was used.

        Args:
            *args:
            peek (Bool): Check rate limit without incrementing
            **kwargs:

        Returns: True if within limit
        """
        raise NotImplementedError('Use not implemented')

    async def setup(self):
        """
        Setup the RateLimit connections
        """
        pass
