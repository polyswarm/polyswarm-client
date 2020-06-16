import logging
from abc import ABCMeta, abstractmethod

from eth_abi import decode_abi
from eth_abi.exceptions import InsufficientDataBytes
from hexbytes import HexBytes
from polyswarmartifact import ArtifactType

from polyswarmclient.utils import int_to_bool_list, guid_as_string, sha3

logger = logging.getLogger(__name__)

UNKNOWN_PARAMETER = 'XXX'


class DecodedTransaction:
    """This is a decoded representation of the transaction object returned by polyswarmd."""

    def __init__(self, to, value, data, abi, signature, parameters):
        self.to = to
        self.value = value
        self.data = data
        self.abi = abi
        self.signature = signature
        self.parameters = parameters

    @classmethod
    def from_transaction(cls, transaction, abi):
        """Parse a transaction from data returned from polyswarmd.

        Args:
            transaction (dict): Transaction to be simplified
            abi (str, list[str]): ABI of the expected function call
        Returns:
            DecodedTransaction: If valid, returns a SimplifiedTransaction
        Raises:
            ValueError: If invalid transaction is provided
        """
        transaction_data = transaction.get('data')
        if transaction_data is None:
            raise ValueError('No data field in this transaction')

        transaction_to = transaction.get('to')
        if transaction_to is None:
            raise ValueError('No recipient field in this transaction')

        value = transaction.get('value')
        if value is None:
            raise ValueError('No value field in this transaction')

        to = transaction_to.lower()

        byte_data = bytes(HexBytes(transaction_data))
        sig = byte_data[:4]
        data = bytes(HexBytes(byte_data[4:]))

        method, args = abi
        expected_sig = sha3('{}({})'.format(method, ','.join(args)))[:4]
        if sig != expected_sig:
            raise ValueError(
                'Method signature did not match expected, got {} expected {} ({})'.format(sig, expected_sig, method))

        try:
            parameters = decode_abi(args, data)
        except InsufficientDataBytes:
            raise ValueError(
                'Transaction data did not match expected ABI (expected {}({}))'.format(method, ','.join(args)))

        return cls(to, value, data, abi, sig, parameters)

    def __repr__(self):
        method, args = self.abi

        # Display readable guids
        parameters = [guid_as_string(p) if t == 'uint128' else p for p, t in zip(self.parameters, args)]
        return '{}({})'.format(method, ', '.join(['{}:{}'.format(v, t) for v, t in zip(parameters, args)]))


class AbstractTransactionVerifier(metaclass=ABCMeta):
    """Verifier is used to verify the details of a single transaction."""
    ABI = ('', [])

    def __init__(self, parameters):
        self.parameters = parameters

    @abstractmethod
    def verify(self, transaction):
        """Called when a list of transactions were returned from polyswarmd.
        This function will verify the transactions, and determines if the transactions are expected.

        Args:
            transaction: Transaction representation returned from polyswarmd
        Returns:
            True if valid and expected
        """
        raise NotImplementedError('Verify is not implemented')

    def __repr__(self):
        method, args = self.ABI
        return '{}({})'.format(method, ', '.join(['{}:{}'.format(v, t) for v, t in zip(self.parameters, args)]))


class NctApproveVerifier(AbstractTransactionVerifier):
    ABI = ('approve', ['address', 'uint256'])

    def __init__(self, amount):
        super().__init__((UNKNOWN_PARAMETER, amount))
        self.amount = amount

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        account, amount = decoded.parameters

        return decoded.value == 0 and amount == self.amount


class NctTransferVerifier(AbstractTransactionVerifier):
    ABI = ('transfer', ['address', 'uint256'])

    def __init__(self, amount):
        super().__init__((UNKNOWN_PARAMETER, amount))
        self.amount = amount

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        account, amount = decoded.parameters

        return decoded.value == 0 and amount == self.amount


class PostBountyVerifier(AbstractTransactionVerifier):
    ABI = ('postBounty', ['uint128', 'uint256', 'uint256', 'string', 'uint256', 'uint256', 'uint256[8]', 'string'])

    def __init__(self, artifact_type, amount, artifact_uri, num_artifacts, duration, bloom, metadata):
        super().__init__((UNKNOWN_PARAMETER, amount, artifact_uri, num_artifacts, duration, bloom, metadata))

        self.artifact_type = ArtifactType.from_string(artifact_type)
        self.amount = amount
        self.artifact_uri = artifact_uri
        self.num_artifacts = num_artifacts
        self.duration = duration
        self.bloom = bloom
        self.metadata = metadata

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        guid, artifact_type, amount, artifact_uri, num_artifacts, duration, bloom, metadata = decoded.parameters

        bloom_value = 0
        for b in bloom:
            bloom_value = bloom_value << 256 | int(b)

        artifact_type = ArtifactType(int(artifact_type))

        return decoded.value == 0 and \
            artifact_type == self.artifact_type and \
            artifact_uri == self.artifact_uri and \
            num_artifacts == self.num_artifacts and \
            duration == self.duration and \
            bloom_value == self.bloom and \
            amount == self.amount and \
            metadata == self.metadata


class PostAssertionVerifier(AbstractTransactionVerifier):
    ABI = ('postAssertion', ['uint128', 'uint256[]', 'uint256', 'uint256'])

    def __init__(self, bounty_guid, bid, mask, commitment):
        super().__init__((bounty_guid, bid, mask, commitment))

        self.bounty_guid = bounty_guid
        self.bid = bid
        self.mask = mask
        self.commitment = commitment

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        bounty_guid, bid, mask, commitment = decoded.parameters

        return decoded.value == 0 and \
            guid_as_string(bounty_guid) == self.bounty_guid and \
            all((contract_bid == given_bid for contract_bid, given_bid in zip(bid, self.bid))) and \
            commitment == self.commitment and \
            int_to_bool_list(mask, len(self.mask)) == self.mask


class RevealAssertionVerifier(AbstractTransactionVerifier):
    ABI = ('revealAssertion', ['uint128', 'uint256', 'uint256', 'uint256', 'string'])

    def __init__(self, bounty_guid, index, nonce, verdicts, metadata):
        super().__init__((bounty_guid, index, nonce, verdicts, metadata))

        self.bounty_guid = bounty_guid
        self.index = index
        self.nonce = nonce
        self.verdicts = verdicts
        self.metadata = metadata

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        bounty_guid, index, nonce, verdicts, metadata = decoded.parameters

        # If there is a 1 anywhere beyond the length of items we expect, fail it
        if verdicts >> len(self.verdicts) > 0:
            return False

        return decoded.value == 0 and \
            guid_as_string(bounty_guid) == self.bounty_guid and \
            index == self.index and \
            nonce == self.nonce and \
            int_to_bool_list(verdicts, len(self.verdicts)) == self.verdicts and \
            metadata == self.metadata


class PostVoteVerifier(AbstractTransactionVerifier):
    ABI = ('voteOnBounty', ['uint128', 'uint256', 'bool'])

    def __init__(self, bounty_guid, votes, valid_bloom):
        super().__init__((bounty_guid, votes, valid_bloom))

        self.bounty_guid = bounty_guid
        self.votes = votes
        self.valid_bloom = valid_bloom

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        bounty_guid, votes, valid_bloom = decoded.parameters

        return decoded.value == 0 and \
            guid_as_string(bounty_guid) == self.bounty_guid and \
            int_to_bool_list(votes, len(self.votes)) == self.votes and \
            valid_bloom == self.valid_bloom


class SettleBountyVerifier(AbstractTransactionVerifier):
    ABI = ('settleBounty', ['uint128'])

    def __init__(self, bounty_guid):
        super().__init__((bounty_guid,))
        self.bounty_guid = bounty_guid

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        bounty_guid, = decoded.parameters

        return decoded.value == 0 and \
            guid_as_string(bounty_guid) == self.bounty_guid


class StakingDepositVerifier(AbstractTransactionVerifier):
    ABI = ('deposit', ['uint256'])

    def __init__(self, amount):
        super().__init__((amount,))
        self.amount = amount

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        amount, = decoded.parameters

        return decoded.value == 0 and \
            amount == self.amount


class StakingWithdrawVerifier(AbstractTransactionVerifier):
    ABI = ('withdraw', ['uint256'])

    def __init__(self, amount):
        super().__init__((amount,))
        self.amount = amount

    def verify(self, transaction):
        try:
            decoded = DecodedTransaction.from_transaction(transaction, self.ABI)
        except ValueError as e:
            logger.error('Transaction verification failed: %s', str(e))
            return False

        logger.debug('Expected: %s, Actual: %s', self, decoded)
        amount, = decoded.parameters

        return decoded.value == 0 and \
            amount == self.amount
