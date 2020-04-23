from click import ClickException


class PolyswarmClientException(Exception):
    """
    polyswarm-client related errors
    """
    pass


class ApiKeyException(PolyswarmClientException):
    """
    Used an API key when not communicating over https.
    """
    pass


class ExpiredException(PolyswarmClientException):
    """
    Worker skipped scanning some artifact due to the bounty expiring before getting scanned.
    Seen when the worker was down for a period of time, or when there aren't enough workers to keep up with load.
    """
    pass


class InvalidBidError(PolyswarmClientException):
    """
    Fault in bid logic that resulted in a bid that is not between the min and max values provided by polyswarmd
    """
    pass


class LowBalanceError(PolyswarmClientException):
    """
    Not enough NCT to complete the requested action
    """
    pass


class TransactionError(PolyswarmClientException):
    """
    A transaction failed
    """
    pass


class InvalidMetadataError(PolyswarmClientException):
    """
    Metadata does not match the valid schema
    """


class UnsupportedHashError(PolyswarmClientException):
    """
    Raised when a hash doesn't match the format of a hash we use
    """


class FatalError(ClickException):
    def __init__(self, message='', exit_code=0):
        super().__init__(message)
        self.exit_code = exit_code
