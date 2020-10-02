import pytest
from polyswarmartifact import ArtifactType

from polyswarmclient import events
from polyswarmclient.server.events import Bounty


@pytest.mark.asyncio
async def test_callback():
    cb = events.Callback()

    async def one_times(x):
        return x

    async def two_times(x):
        return 2 * x

    async def three_times(x):
        return 3 * x

    cb.register(one_times)
    cb.register(two_times)
    cb.register(three_times)

    assert await cb.run(2) == [2, 4, 6]

    cb.remove(three_times)

    assert await cb.run(3) == [3, 6]

    def four_times(x):
        return 4 * x

    cb.register(four_times)

    # Non-async callback
    with pytest.raises(TypeError):
        await cb.run(4)


@pytest.mark.asyncio
async def test_on_run_callback():
    cb = events.OnRunCallback()

    async def check_parameters(chain):
        return chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(chain='home') == [True]
    assert await cb.run(chain='side') == [False]

    async def invalid_signature(chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(chain='home')


@pytest.mark.asyncio
async def test_on_new_bounty_callback():
    cb = events.OnNewBountyCallback()

    async def check_parameters(bounty: Bounty):
        return bounty.guid == 'guid' and bounty.artifact_type == ArtifactType.FILE.name.lower() and bounty.artifact_url == 'uri'\
               and bounty.expiration == '2020-10-02T10:38:34.225746' and bounty.response_url == 'response' \
               and bounty.phase == 'assertion'

    cb.register(check_parameters)

    bounty = Bounty(guid='guid', artifact_type='file', artifact_url='uri', sha256='sha256', mimetype='text/html',
                    expiration='2020-10-02T10:38:34.225746', response_url='response', phase='assertion', rules=[])

    assert await cb.run(bounty) == [True]

    bounty = Bounty(guid='not guid', artifact_type='file', artifact_url='uri', sha256='sha256', mimetype='text/html',
                    expiration='2020-10-02T10:38:34.225746', response_url='response', phase='assertion', rules=[])
    assert await cb.run(bounty) == [False]

    async def invalid_signature(guid, artifact_type, author, amount, uri, expiration, metadata, chain, block_number, txhash, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty)
