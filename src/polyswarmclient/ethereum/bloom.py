# Based on eth-bloom (https://github.com/ethereum/eth-bloom, used under MIT
# license) with modifications
import logging
import numbers
import operator
from web3 import Web3

FILTER_BITS = 8 * 256
if FILTER_BITS > (1 << 16):
    raise ValueError('Filter bits must be less than 65536')

HASH_FUNCS = 8


logger = logging.getLogger(__name__)  # Initialize logger


class BloomFilter(numbers.Number):
    # TODO: Unit tests for BloomFilter?
    value = None

    def __init__(self, value=0):
        self.value = value

    def __int__(self):
        return self.value

    def add(self, value):
        """
        Add a single byte value to the Bloom filter.

        Args:
            value (bytes): Byte encoded value to add to Bloom filter.
        """
        if not isinstance(value, bytes):
            raise TypeError('Value must be of type `bytes`')
        for bloom_bits in self.get_bloom_bits(value):
            self.value |= bloom_bits

    def extend(self, iterable):
        """
        Add an iterable of byte values to the bloom filter.

        Args:
            iterable (Iterable[bytes]): Iterable of byte values.
        """
        for value in iterable:
            self.add(value)

    @classmethod
    def from_iterable(cls, iterable):
        """
        Instantiate a bloom filter from a given iterable.

        Args:
            iterable (Iterable[bytes]): Iterable of byte values.
        Returns:
            BloomFilter: Instantiated BloomFilter.
        """
        bloom = cls()
        bloom.extend(iterable)
        return bloom

    def __contains__(self, value):
        if not isinstance(value, bytes):
            raise TypeError('Value must be of type `bytes`')
        return all(
            self.value & bloom_bits
            for bloom_bits
            in self.get_bloom_bits(value)
        )

    def __index__(self):
        return operator.index(self.value)

    def _combine(self, other):
        if not isinstance(other, (int, BloomFilter)):
            raise TypeError(
                'The `or` operator is only supported for other `BloomFilter` instances'
            )
        return BloomFilter(int(self) | int(other))

    def __or__(self, other):
        return self._combine(other)

    def __add__(self, other):
        return self._combine(other)

    def _icombine(self, other):
        if not isinstance(other, (int, BloomFilter)):
            raise TypeError(
                'The `or` operator is only supported for other `BloomFilter` instances'
            )
        self.value |= int(other)
        return self

    def __ior__(self, other):
        return self._icombine(other)

    def __iadd__(self, other):
        return self._icombine(other)

    @staticmethod
    def get_bloom_bits(value):
        """
        Bloom filter helper function. Get the Bloom bits of a
        given value.

        Args:
            value (bytes): Value to be encoded into the Bloom filter.
        """
        # Could decode the ipfs_hash and use it as is, but instead hash the
        # multihash representation to side-step different hash formats going
        # forward. Should rexamine this decision
        value_hash = Web3.keccak(value)
        for chunk in BloomFilter.get_chunks_for_bloom(value_hash):
            bloom_bits = BloomFilter.chunk_to_bloom_bits(chunk)
            yield bloom_bits

    @staticmethod
    def get_chunks_for_bloom(value_hash):
        """
        Bloom filter helper function. Turn a value hash into
        a series of chunks.

        Args:
            value_hash (bytes): Hash of to be encoded into the Bloom filter.
        Yields:
            chunk (bytes): Chunks of the value hash.
        """
        if HASH_FUNCS * 2 > len(value_hash):
            raise ValueError("Input is too long ")

        for i in range(0, HASH_FUNCS):
            yield value_hash[2 * i:2 * (i + 1)]

    @staticmethod
    def chunk_to_bloom_bits(chunk):
        """
        Bloom filter helper function. Turn a chunk into a series of
        actual bytes.

        Args:
            chunk (bytes): Byte encoded chunk.
        """
        high, low = bytearray(chunk)
        return 1 << ((low + (high << 8)) & (FILTER_BITS - 1))
