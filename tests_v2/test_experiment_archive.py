import hashlib
import io
import zipfile

import pytest

from threemind_lab.experiment_archive import CHUNK, ArchiveLimits, ArchiveReader, ArchiveWriter, canonical


def test_chunked_archive_roundtrip_and_deduplication():
    output = io.BytesIO()
    writer = ArchiveWriter(output, {"purpose": "fixture"})
    payload = b"a" * CHUNK + b"tail"
    writer.add("model.bin", [payload])
    writer.add("copy.bin", [payload])
    writer.json("protocol.json", {"steps": [1, 2], "meaning": "实际记录"})
    manifest = writer.finish()
    assert manifest["files"]["model.bin"]["chunks"] == manifest["files"]["copy.bin"]["chunks"]
    reader = ArchiveReader(output)
    assert reader.verify() == manifest
    assert reader.read("copy.bin", maximum=len(payload)) == payload
    assert reader.json("protocol.json")["meaning"] == "实际记录"
    assert len(reader.archive.infolist()) == 4
    reader.close()


def test_archive_rejects_hash_mismatch_duplicate_names_and_bombs():
    output = io.BytesIO()
    writer = ArchiveWriter(output, {})
    writer.json("a.json", {"n": 1})
    writer.finish()
    source = zipfile.ZipFile(output)
    manifest = source.read("manifest.json")
    chunk = next(x for x in source.namelist() if x.startswith("chunks/"))
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("manifest.json", manifest)
        archive.writestr(chunk, canonical({"n": 2}))
    reader = ArchiveReader(bad)
    with pytest.raises(ValueError, match="checksum"):
        reader.verify()
    reader.close()
    traversal = io.BytesIO()
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../escape", b"bad")
    with pytest.raises(ValueError, match="unexpected"):
        ArchiveReader(traversal)
    with pytest.raises(ValueError, match="expanded"):
        ArchiveReader(output, limits=ArchiveLimits(expanded=1))


def test_archive_budget_and_jsonl_stream_check():
    output = io.BytesIO()
    writer = ArchiveWriter(output, {}, limits=ArchiveLimits(expanded=3))
    with pytest.raises(ValueError, match="budget"):
        writer.add("a.bin", [b"four"])
    writer.close()
    output = io.BytesIO()
    writer = ArchiveWriter(output, {})
    raw = b'{"v":1}\n{"v":2}\n'
    writer.add("events.jsonl", [raw[:3], raw[3:]], media_type="application/x-ndjson")
    result = writer.finish()
    reader = ArchiveReader(output)
    assert list(reader.rows("events.jsonl")) == [{"v": 1}, {"v": 2}]
    assert result["files"]["events.jsonl"]["sha256"] == hashlib.sha256(raw).hexdigest()
    reader.close()
