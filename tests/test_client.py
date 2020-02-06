import asyncio
import pytest
from polyswarmartifact import ArtifactType

import polyswarmclient
import random
import uuid

from unittest.mock import patch

import polyswarmclient.utils
from . import success, event, random_address, random_bitset, random_ipfs_uri


def test_check_response():
    valid_success_response = {'status': 'OK', 'result': 42}
    assert polyswarmclient.utils.check_response(valid_success_response)

    valid_error_response = {'status': 'FAIL', 'errors': 'Whoops'}
    assert not polyswarmclient.utils.check_response(valid_error_response)

    invalid_response = {'foo': 'bar', 'baz': 'qux'}
    assert not polyswarmclient.utils.check_response(invalid_response)


def test_is_valid_ipfs_uri():
    invalid_ipfs_uri = '#!$!'
    assert not polyswarmclient.utils.is_valid_ipfs_uri(invalid_ipfs_uri)

    valid_ipfs_uri = 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG'
    assert polyswarmclient.utils.is_valid_ipfs_uri(valid_ipfs_uri)


@patch('os.urandom', return_value=0x41)
def test_calculate_commitment(mock_fn):
    nonce, commitment = polyswarmclient.utils.calculate_commitment(
        "0x4141414141414141414141414141414141414141414141414141414141414141",
        polyswarmclient.utils.bool_list_to_int([True, True, True])
    )
    assert nonce == 65
    assert commitment == 16260335923677497924282686029038487427342546648292884828210727571478684022780


@pytest.mark.asyncio
async def test_update_base_nonce(mock_client):
    mock_client.http_mock.get(mock_client.url_with_parameters('/nonce', params={'ignore_pending': ' '}, chain='home'), body=success(42))
    mock_client.http_mock.get(mock_client.url_with_parameters('/pending', chain='home'), body=success([]))

    home = polyswarmclient.ethereum.transaction.NonceManager(mock_client, 'home')
    await home.setup()
    await home.reserve(1)

    assert home.base_nonce == 43

    mock_client.http_mock.get(mock_client.url_with_parameters('/nonce', params={'ignore_pending': ' '}, chain='side'), body=success(1336))
    mock_client.http_mock.get(mock_client.url_with_parameters('/pending', chain='side'), body=success([]))

    side = polyswarmclient.ethereum.transaction.NonceManager(mock_client, 'side')
    await side.setup()
    await side.reserve(1)

    assert side.base_nonce == 1337


@pytest.mark.asyncio
async def test_list_artifacts(mock_client):
    invalid_ipfs_uri = '#!$!'
    assert await mock_client.list_artifacts(invalid_ipfs_uri) == []

    valid_ipfs_uri = 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG'
    valid_response = [
        {'hash': 'QmZTR5bcpQD7cFgTorqxZDYaew1Wqgfbd2ud9QqGPAkK2V', 'name': 'about'},
        {'hash': 'QmYCvbfNbCwFR45HiNP45rwJgvatpiW38D961L5qAhUM5Y', 'name': 'contact'},
    ]

    mock_client.http_mock.get(mock_client.url_with_parameters('/artifacts/{0}'.format(valid_ipfs_uri), chain='side'),
                              body=success(valid_response))
    assert await mock_client.list_artifacts(valid_ipfs_uri) == [(x['name'], x['hash']) for x in valid_response]


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_new_block(mock_client):
    home_done = asyncio.Event()
    side_done = asyncio.Event()

    home_number = 42
    side_number = 1337

    async def handle_new_block(number, chain):
        if chain == 'home':
            assert number == home_number
            home_done.set()
        elif chain == 'side':
            assert number == side_number
            side_done.set()
        else:
            raise ValueError('Invalid chain')

    mock_client.on_new_block.register(handle_new_block)
    await mock_client.home_ws_mock.send(event('block', {'number': home_number}))
    await mock_client.side_ws_mock.send(event('block', {'number': side_number}))

    await asyncio.wait([home_done.wait(), side_done.wait()])


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_new_bounty(mock_client):
    home_done = asyncio.Event()
    side_done = asyncio.Event()

    def make_bounty():
        return {
            'guid': str(uuid.uuid4()),
            'artifact_type': ArtifactType.to_string(ArtifactType.FILE),
            'author': random_address(),
            'amount': random.randint(0, 10 ** 18),
            'uri': random_ipfs_uri(),
            'expiration': random.randint(0, 1000),
            'metadata': None,
        }

    home_bounty = make_bounty()
    side_bounty = make_bounty()

    async def handle_new_bounty(guid, artifact_type, author, amount, uri, expiration, metadata, block_number, txhash, chain):
        new_bounty = {
            'guid': guid,
            'artifact_type': ArtifactType.to_string(artifact_type),
            'author': author,
            'amount': amount,
            'uri': uri,
            'expiration': expiration,
            'metadata': metadata,
        }

        if chain == 'home':
            assert new_bounty == home_bounty
            home_done.set()
        elif chain == 'side':
            assert new_bounty == side_bounty
            side_done.set()
        else:
            raise ValueError('Invalid chain')

    mock_client.on_new_bounty.register(handle_new_bounty)
    await mock_client.home_ws_mock.send(event('bounty', home_bounty))
    await mock_client.side_ws_mock.send(event('bounty', side_bounty))

    await asyncio.wait([home_done.wait(), side_done.wait()])


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_new_assertion(mock_client):
    home_done = asyncio.Event()
    side_done = asyncio.Event()

    def make_assertion():
        return {
            'bounty_guid': str(uuid.uuid4()),
            'author': random_address(),
            'index': random.randint(0, 10),
            'bid': random.randint(0, 10 ** 18),
            'mask': random_bitset(),
            'commitment': random.randint(0, 10 ** 18),
        }

    home_assertion = make_assertion()
    side_assertion = make_assertion()

    async def handle_new_assertion(bounty_guid, author, index, bid, mask, commitment, block_number, txhash, chain):
        new_assertion = {
            'bounty_guid': bounty_guid,
            'author': author,
            'index': index,
            'bid': bid,
            'mask': mask,
            'commitment': commitment,
        }

        if chain == 'home':
            assert new_assertion == home_assertion
            home_done.set()
        elif chain == 'side':
            assert new_assertion == side_assertion
            side_done.set()
        else:
            raise ValueError('Invalid chain')

    mock_client.on_new_assertion.register(handle_new_assertion)
    await mock_client.home_ws_mock.send(event('assertion', home_assertion))
    await mock_client.side_ws_mock.send(event('assertion', side_assertion))

    await asyncio.wait([home_done.wait(), side_done.wait()])


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_reveal_assertion(mock_client):
    home_done = asyncio.Event()
    side_done = asyncio.Event()

    def make_reveal():
        return {
            'bounty_guid': str(uuid.uuid4()),
            'author': random_address(),
            'index': random.randint(0, 10),
            'nonce': random.randint(0, 10 ** 18),
            'verdicts': random_bitset(),
            'metadata': 'hello world',
        }

    home_reveal = make_reveal()
    side_reveal = make_reveal()

    async def handle_reveal_assertion(bounty_guid, author, index, nonce, verdicts, metadata, block_number, txhash,
                                      chain):
        new_reveal = {
            'bounty_guid': bounty_guid,
            'author': author,
            'index': index,
            'nonce': nonce,
            'verdicts': verdicts,
            'metadata': metadata,
        }

        if chain == 'home':
            assert new_reveal == home_reveal
            home_done.set()
        elif chain == 'side':
            assert new_reveal == side_reveal
            side_done.set()
        else:
            raise ValueError('Invalid chain')

    mock_client.on_reveal_assertion.register(handle_reveal_assertion)
    await mock_client.home_ws_mock.send(event('reveal', home_reveal))
    await mock_client.side_ws_mock.send(event('reveal', side_reveal))

    await asyncio.wait([home_done.wait(), side_done.wait()])


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_new_vote(mock_client):
    home_done = asyncio.Event()
    side_done = asyncio.Event()

    def make_vote():
        return {
            'bounty_guid': str(uuid.uuid4()),
            'votes': random_bitset(),
            'voter': random_address(),
        }

    home_vote = make_vote()
    side_vote = make_vote()

    async def handle_new_vote(bounty_guid, votes, voter, block_number, txhash, chain):
        new_vote = {
            'bounty_guid': bounty_guid,
            'votes': votes,
            'voter': voter,
        }

        if chain == 'home':
            assert new_vote == home_vote
            home_done.set()
        elif chain == 'side':
            assert new_vote == side_vote
            side_done.set()
        else:
            raise ValueError('Invalid chain')

    mock_client.on_new_vote.register(handle_new_vote)
    await mock_client.home_ws_mock.send(event('vote', home_vote))
    await mock_client.side_ws_mock.send(event('vote', side_vote))

    await asyncio.wait([home_done.wait(), side_done.wait()])


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_quorum_reached(mock_client):
    home_done = asyncio.Event()
    side_done = asyncio.Event()

    def make_quorum():
        return {
            'bounty_guid': str(uuid.uuid4()),
        }

    home_quorum = make_quorum()
    side_quorum = make_quorum()

    async def handle_new_vote(bounty_guid, block_number, txhash, chain):
        new_quorum = {
            'bounty_guid': bounty_guid,
        }

        if chain == 'home':
            assert new_quorum == home_quorum
            home_done.set()
        elif chain == 'side':
            assert new_quorum == side_quorum
            side_done.set()
        else:
            raise ValueError('Invalid chain')

    mock_client.on_quorum_reached.register(handle_new_vote)
    await mock_client.home_ws_mock.send(event('quorum', home_quorum))
    await mock_client.side_ws_mock.send(event('quorum', side_quorum))

    await asyncio.wait([home_done.wait(), side_done.wait()])


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_settled_bounty(mock_client):
    home_done = asyncio.Event()
    side_done = asyncio.Event()

    def make_settle():
        return {
            'bounty_guid': str(uuid.uuid4()),
            'settler': random_address(),
            'payout': random.randint(0, 1000) * 10 ** 18,
        }

    home_settle = make_settle()
    side_settle = make_settle()

    async def handle_settled_bounty(bounty_guid, settler, payout, block_number, txhash, chain):
        new_settle = {
            'bounty_guid': bounty_guid,
            'settler': settler,
            'payout': payout,
        }

        if chain == 'home':
            assert new_settle == home_settle
            home_done.set()
        elif chain == 'side':
            assert new_settle == side_settle
            side_done.set()
        else:
            raise ValueError('Invalid chain')

    mock_client.on_settled_bounty.register(handle_settled_bounty)
    await mock_client.home_ws_mock.send(event('settled_bounty', home_settle))
    await mock_client.side_ws_mock.send(event('settled_bounty', side_settle))

    await asyncio.wait([home_done.wait(), side_done.wait()])


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_initialized_channel(mock_client):
    done = asyncio.Event()

    def make_initialized_channel():
        return {
            'guid': str(uuid.uuid4()),
            'ambassador': random_address(),
            'expert': random_address(),
            'multi_signature': random_address(),
        }

    initialized_channel = make_initialized_channel()

    async def handle_initialized_channel(guid, ambassador, expert, multi_signature, block_number, txhash):
        new_initialized_channel = {
            'guid': guid,
            'ambassador': ambassador,
            'expert': expert,
            'multi_signature': multi_signature,
        }

        assert new_initialized_channel == initialized_channel
        done.set()

    mock_client.on_initialized_channel.register(handle_initialized_channel)
    await mock_client.home_ws_mock.send(event('initialized_channel', initialized_channel))

    await done.wait()
