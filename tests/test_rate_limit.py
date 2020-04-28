import asyncio
import asynctest
import pytest

from polyswarmclient.request_rate_limit import RequestRateLimit


@pytest.mark.asyncio
async def test_rate_limit_trigger_debounce():
    rate_limit = await RequestRateLimit.build()
    original = rate_limit.limit
    rate_limit.limit = asynctest.CoroutineMock()
    rate_limit.limit.side_effect = original
    await asyncio.gather(*[rate_limit.trigger(), rate_limit.trigger()])
    rate_limit.limit.assert_called_once()
