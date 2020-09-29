import logging


logger = logging.getLogger(__name__)  # Initialize logger


class Callback(object):
    """
    Abstract callback class which is the parent to a number of child
    callback classes to be used in different scenarios.

    Note:
        Classes which extend `Callback` are expected to impliment the
        `run` method.
    """

    def __init__(self):
        self.cbs = []

    def register(self, f):
        """
        Register a function to this Callback.

        Args:
            f (function): Function to register.
        """
        self.cbs.append(f)

    def remove(self, f):
        """
        Remove a function previously assigned to this Callback.

        Args:
            f (function): Function to remove.
        """
        self.cbs.remove(f)

    async def run(self, *args, **kwargs):
        """
        Run all of the registered callback functions.

        Returns:
            results (List[any]): Results returned from the callback functions
        """
        results = []
        for cb in self.cbs:
            local_ret = await cb(*args, **kwargs)
            if local_ret is not None:
                results.append(local_ret)

        if results:
            logger.info('%s callback results', type(self).__name__, extra={'extra': results})

        return results


# Create these subclasses so we can document the parameters to each callback
class OnRunCallback(Callback):
    """Called upon entering the event loop for the first time, use for initialization"""

    async def run(self, chain=None):
        """Run the registered callbacks
        """
        return await super().run(chain)


class OnStopCallback(Callback):
    """Called when the client is stopping

        This can happen on errors, or due to a signal
    """

    async def run(self):
        """Run the registered callbacks

        """
        return await super().run()


class OnNewBountyCallback(Callback):
    """Called upon receiving a new bounty"""

    async def run(self, bounty):
        """Run the registered callbacks

        Args:
            bounty (Bounty): Bounty to scan
        """
        return await super().run(bounty)
