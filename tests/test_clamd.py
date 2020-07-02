import aiohttp
import pytest

from microengine_utils.malwarerepoclient import DummyMalwareRepoClient
from polyswarmartifact import ArtifactType
from microengine.clamav import Scanner

from tests.utils.fixtures import not_listening_on_port


@pytest.mark.skipif(not_listening_on_port(3310), reason='ClamAV is not running')
@pytest.mark.asyncio
async def test_scan_random_mal_not():
    scanner = Scanner()
    scanner.session = aiohttp.ClientSession()
    await scanner.setup()

    for t in [True, False]:
        mal_md, mal_content = DummyMalwareRepoClient().get_random_file(malicious_filter=t)
        result = await scanner.scan("nocare", ArtifactType.FILE, mal_content, None, "home")
        assert result.verdict == t

    await scanner.session.close()
