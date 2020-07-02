from polyswarmclient.utils import sha3


def test_verifier_sha3():
    ABIS = [(b'\xa9\x05\x9c\xbb', ('transfer', ['address', 'uint256'])),
            (b'\x9b\x1c\xda\xd4', ('postBounty', ['uint128', 'uint256', 'string', 'uint256', 'uint256', 'uint256[8]']))]
    for result, abi in ABIS:
        method, args = abi
        assert result == sha3('{}({})'.format(method, ','.join(args)))[:4]
