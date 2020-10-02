import aiohttp
import asyncio
import datetime
import json
import pytest
import uuid

import polyswarmclient.utils

from polyswarmartifact import ArtifactType
from polyswarmclient.server.events import Bounty
from polyswarmclient.server.base import Server

from tests.utils.fixtures import test_client


def test_is_valid_sha256():
    invalid_sha256 = 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG'
    assert not polyswarmclient.utils.is_valid_sha256(invalid_sha256)

    valid_sha256 = '275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f'
    assert polyswarmclient.utils.is_valid_sha256(valid_sha256)


def test_is_valid_ipfs_uri():
    invalid_ipfs_uri = '275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f'
    assert not polyswarmclient.utils.is_valid_ipfs_uri(invalid_ipfs_uri)

    valid_ipfs_uri = 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG'
    assert polyswarmclient.utils.is_valid_ipfs_uri(valid_ipfs_uri)


def test_is_valid_uri():
    invalid_uri = '#!$!'
    assert not polyswarmclient.utils.is_valid_uri(invalid_uri)

    valid_ipfs_uri = 'QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG'
    assert polyswarmclient.utils.is_valid_uri(valid_ipfs_uri)

    valid_sha256 = '275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f'
    assert polyswarmclient.utils.is_valid_uri(valid_sha256)


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_on_new_bounty(test_client):
    bounty_done = asyncio.Event()

    test_bounty = {
        'guid': str(uuid.uuid4()),
        'artifact_type': ArtifactType.to_string(ArtifactType.FILE),
        'artifact_url': 'url',
        'sha256': ['1'] * 64,
        'mimetype': 'text/plain',
        'expiration': datetime.datetime.now().isoformat(),
        'phase': 'assertion',
        'response_url': 'http://localhost:5000/',
        'rules': [],
    }

    async def handle_new_bounty(bounty: Bounty):
        bounty_done.set()

    test_client.on_new_bounty.register(handle_new_bounty)

    content = json.dumps(test_bounty)
    signature = Server.generate_hmac(('0' * 32).encode('utf-8'), content.encode('utf-8'))
    headers = {
        'X-POLYSWARM-EVENT': 'bounty',
        'X-POLYSWARM-SIGNATURE': signature,
    }
    async with aiohttp.ClientSession(raise_for_status=True) as session:
        async with session.post('http://localhost:8080/', data=content, headers=headers):
            pass

    await bounty_done.wait()
