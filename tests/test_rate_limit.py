import asyncio
import asynctest
import pytest

from polyswarmclient.request_rate_limit import RequestRateLimit


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_rate_limit_trigger_debounce(event_loop):
    rate_limit = await RequestRateLimit.build()
    original = rate_limit.rate_limit_event.set
    rate_limit.rate_limit_event.set = asynctest.CoroutineMock()
    rate_limit.rate_limit_event.set.side_effect = original

    # Really sync the trigger moment
    event = asyncio.Event()

    async def sync_trigger():
        await event.wait()
        await rate_limit.trigger()

    async def gather_trigger():
        await asyncio.gather(*[sync_trigger(), sync_trigger()])

    task = event_loop.create_task(gather_trigger())
    event.set()
    task.add_done_callback(lambda: rate_limit.rate_limit_event.set.assert_called_once())


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_rate_limit_stops_calls(event_loop):
    rate_limit = await RequestRateLimit.build()
    # Make it wait at first
    rate_limit.rate_limit_event.clear()

    # Build mock
    async def side_effect():
        await asyncio.sleep(0)

    mock = asynctest.CoroutineMock()
    mock.side_effect = side_effect

    async def wait():
        await rate_limit.check()
        await mock()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(wait(), timeout=1)

    mock.assert_not_called()

    await rate_limit.trigger()
    await wait()
    mock.assert_called_once()
