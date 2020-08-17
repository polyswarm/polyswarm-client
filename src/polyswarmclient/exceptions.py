from click import ClickException


class PolyswarmClientException(Exception):
    """
    polyswarm-client related errors
    """
    pass


class ApiKeyException(PolyswarmClientException):
    """
    Used an API key when not communicating over https, without explicitly allowing
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


class RateLimitedError(PolyswarmClientException):
    """
    Hit the rate limit from polyswarmd
    """
    pass


class NonceDesyncError(PolyswarmClientException):
    """
    Got a nonce too low or too high error
    """
    pass


class ReceiptError(PolyswarmClientException):
    """
    Failed to get receipt from polyswarmd
    """
    pass


class UnsupportedHashError(PolyswarmClientException):
    """
    Raised when a hash doesn't match the format of a hash we use
    """


class ScannerSetupFailedError(PolyswarmClientException):
    """
    Scanner reported an unsuccessful setup
    """


class FatalError(ClickException):
    def __init__(self, message='', exit_code=0):
        super().__init__(message)
        self.exit_code = exit_code


class SecurityWarning(Warning):
    """
     Warnings about disabled security features.
     """
    pass
