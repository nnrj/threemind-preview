import io
import json
import zipfile
import pytest
from lab.tools.streaming_evidence import ZipStream


def test_streamed_archive_preserves_bytes_crc_and_non_ascii_name(tmp_path):
    p=tmp_path/'one.bin';p.write_bytes(bytes(range(256))*18000)
    q=tmp_path/'说明.md';q.write_text('原始记录\n',encoding='utf-8')
    stream=ZipStream([('one.bin',p),('说明.md',q)])
    try:
        data=b''.join(iter(lambda:stream.read(65536),b''))
        assert stream.finished and stream.bytes_read==len(data)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert z.read('one.bin')==p.read_bytes() and z.read('说明.md')==q.read_bytes()
            m=json.loads(z.read('archive-manifest.json'));assert len(m['files'])==2
            assert all(f['zip_crc32']==f'{z.getinfo(f["path"]).CRC:08x}' for f in m['files'])
    finally:stream.close()
    assert not stream.thread.is_alive()


def test_producer_failure_reaches_consumer_instead_of_valid_truncated_archive(tmp_path):
    stream=ZipStream([('missing',tmp_path/'missing')])
    try:
        with pytest.raises(RuntimeError,match='production failed'):
            while stream.read(1024):pass
    finally:stream.close()


def test_closing_consumer_unblocks_producer(tmp_path):
    import os
    p=tmp_path/'large.gz';p.write_bytes(os.urandom(12*2**20))
    stream=ZipStream([('large.gz',p)]);assert stream.read(100)
    stream.close();assert not stream.thread.is_alive()
