import asyncio
import io
import os

import pytest
from polyswarmclient.utils import AsyncArtifactTempfile, finalize_polyswarmd_addr


def is_gone(path):
    return not os.path.exists(path)


def read_file(filename):
    with open(str(filename), 'rb') as of:
        return of.read()


@pytest.fixture(
    params=[
        b'hello world',
        bytes(),
        # invalid utf8/ascii & ucs-2
        b'\xD8' + bytes(4096).translate(bytes.maketrans(b'\x00', b'\xFF'))
    ],
    ids=['hello world', 'empty', 'big_surrogate'],
)
def blob(request):
    yield request.param


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_artifact_tempfile_basic_io(blob):
    ## make sure basic io operations work outside ctxmgr
    aat = AsyncArtifactTempfile()
    filename = aat.name
    await aat.write(blob)
    await aat.seek(0)
    assert blob == await aat.read()
    assert not is_gone(filename)
    await aat.close()
    assert is_gone(filename)


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_artifact_tempfile_new_blob(blob):
    ## make sure we create a new, temporary file filled with `blob``
    filename = None
    async with AsyncArtifactTempfile(blob) as f:
        filename = f.name
        assert read_file(filename) == blob
        assert await f.read() == blob
    assert is_gone(filename)


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_artifact_tempfile(blob):
    ## make sure we create a new, temporary file that can be written to in ctxmgr
    filename = None
    async with AsyncArtifactTempfile() as f:
        filename = f.name
        await f.write(blob)
        assert read_file(filename) == blob
        await f.seek(0)
        assert blob == await f.read()
    assert is_gone(filename)


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_artifact_tempfile_filename_blob(blob, tmp_path):
    ## make sure we overwrite an existing file with `blob`
    p = tmp_path / 'existing.exe'
    p.write_bytes(b'this should not be read')
    filename = str(p)
    async with AsyncArtifactTempfile(blob, filename=filename) as f:
        assert f.name == filename
        assert read_file(filename) == blob
        assert await f.read() == blob
    assert is_gone(filename)


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_artifact_tempfile_filename(blob, tmp_path):
    # make sure we can read the existing file if no blob was passed in
    # while still being able to write to it in the ctxmgr
    p = tmp_path / 'existing.exe'
    filename = str(p)
    other = b'other blob'
    p.write_bytes(other)
    async with AsyncArtifactTempfile(filename=filename) as f:
        assert read_file(f.name) == other
        assert f.name == filename
        await f.write(blob)
        await f.read() == blob
    assert is_gone(filename)


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_artifact_tempfile_nonexistent_filename_blob(blob, tmp_path):
    ## make sure we create a file with the contents of `blob`
    filename = str(tmp_path / 'newfile.exe')
    async with AsyncArtifactTempfile(blob, filename=filename) as f:
        assert f.name == filename
        assert await f.read() == blob
        assert read_file(filename) == blob
    assert is_gone(filename)


@pytest.mark.asyncio
@pytest.mark.timeout(1)
async def test_async_artifact_tempfile_nonexistent_filename(blob, tmp_path):
    ## make sure we create and write to a file and write to it inside the ctxmgr
    filename = str(tmp_path / 'newfile.exe')
    async with AsyncArtifactTempfile(filename=filename) as f:
        assert read_file(filename) == b''
        assert f.name == filename
        await f.write(blob)
        await f.seek(0)
        assert await f.read() == blob
    assert is_gone(filename)


def test_add_default_https():
    url = 'polyswarmd-fast-e2e:31337/v1'
    allow_key_over_http = False
    insecure_transport = False
    api_key = None

    assert 'https://polyswarmd-fast-e2e:31337/v1' == finalize_polyswarmd_addr(url, api_key, allow_key_over_http,
                                                                              insecure_transport)


def test_no_change_https_no_key():
    url = 'https://polyswarmd-fast-e2e:31337/v1'
    allow_key_over_http = False
    insecure_transport = False
    api_key = None

    assert 'https://polyswarmd-fast-e2e:31337/v1' == finalize_polyswarmd_addr(url, api_key, allow_key_over_http,
                                                                              insecure_transport)


def test_no_changes_https_with_key():
    url = 'https://polyswarmd-fast-e2e:31337/v1'
    allow_key_over_http = False
    insecure_transport = False
    api_key = 'api-key'

    assert 'https://polyswarmd-fast-e2e:31337/v1' == finalize_polyswarmd_addr(url, api_key, allow_key_over_http,
                                                                              insecure_transport)


def test_add_http_insecure_transport():
    url = 'polyswarmd-fast-e2e:31337/v1'
    allow_key_over_http = False
    insecure_transport = True
    api_key = None

    assert 'http://polyswarmd-fast-e2e:31337/v1' == finalize_polyswarmd_addr(url, api_key, allow_key_over_http,
                                                                             insecure_transport)


def test_raises_add_scheme_with_key():
    url = 'polyswarmd-fast-e2e:31337/v1'
    allow_key_over_http = False
    insecure_transport = True
    api_key = 'api-key'

    with pytest.raises(ValueError):
        finalize_polyswarmd_addr(url, api_key, allow_key_over_http, insecure_transport)


def test_add_http_with_key_allowed():
    url = 'polyswarmd-fast-e2e:31337/v1'
    allow_key_over_http = True
    insecure_transport = True
    api_key = 'api-key'

    assert 'http://polyswarmd-fast-e2e:31337/v1' == finalize_polyswarmd_addr(url, api_key, allow_key_over_http,
                                                                             insecure_transport)


def test_no_changes_http_no_key():
    url = 'http://polyswarmd-fast-e2e:31337/v1'
    allow_key_over_http = False
    insecure_transport = False
    api_key = None

    finalize_polyswarmd_addr(url, api_key, allow_key_over_http, insecure_transport)


def test_raises_http_with_key():
    url = 'http://polyswarmd-fast-e2e:31337/v1'
    allow_key_over_http = False
    insecure_transport = False
    api_key = 'api-key'

    with pytest.raises(ValueError):
        finalize_polyswarmd_addr(url, api_key, allow_key_over_http, insecure_transport)
