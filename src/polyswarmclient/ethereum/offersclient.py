import logging

logger = logging.getLogger(__name__)  # Initialize logger


class OffersClient(object):
    """
    OffersClient to handle offers. Presently stores a given client and parameters.
    """

    def __init__(self, client):
        self.__client = client
        self.parameters = {}
