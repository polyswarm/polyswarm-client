import base58
import json
import random
import os

from web3 import Web3


def success(result):
    return json.dumps({'status': 'OK', 'result': result})


def failure(errors):
    return json.dumps({'status': 'FAIL', 'errors': errors})


def event(event, data, block_number=0, txhash='0x0'):
    return json.dumps({'event': event, 'data': data, 'block_number': block_number, txhash: txhash})


def random_address():
    return Web3().toChecksumAddress(os.urandom(20).hex())


def random_bitset():
    x = random.getrandbits(256)
    return [(1 << i) & x != 0 for i in range(256)]


def random_ipfs_uri():
    return base58.b58encode(b'\x12' + os.urandom(32)).decode('utf-8')
