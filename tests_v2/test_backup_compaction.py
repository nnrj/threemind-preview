import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from threemind_lab.storage_backup import compact_research, inspect
from threemind_lab.storage_files import atomic_json


def complete_backup(root):
    root.mkdir()
    raw = b"historical research original\n" * 8192
    original = root / "research/aa/original"
    original.parent.mkdir(parents=True)
    original.write_bytes(raw)
    dump = root / "database.dump"
    dump.write_bytes(b"database dump unchanged")

    def row(path):
        raw = path.read_bytes()
        return {"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

    evidence = row(original) | {"resource_id": "first", "member": "raw.json"}
    manifest = {
        "schema": "threemind.storage-backup/1",
        "state": "complete",
        "database": row(dump),
        "objects": [],
        "research_files": [evidence, evidence | {"resource_id": "second", "member": "other.json"}],
    }
    atomic_json(root / "manifest.json", manifest)
    return raw, original, manifest


def test_compaction_keeps_logical_identities_and_decoded_hashes(tmp_path):
    root = tmp_path / "backup"
    raw, old, before = complete_backup(root)
    first = compact_research(root)
    assert first["encoded_files"] == 1 and first["saved_bytes"] > len(raw) * 0.9
    assert not old.exists()
    after = inspect(root)
    assert after["database"] == before["database"]
    assert [r["resource_id"] for r in after["research_files"]] == ["first", "second"]
    assert [r["member"] for r in after["research_files"]] == ["raw.json", "other.json"]
    assert all(r["sha256"] == hashlib.sha256(raw).hexdigest() for r in after["research_files"])
    assert compact_research(root) == first
    encoded = root / after["research_files"][0]["path"]
    encoded.write_bytes(b"corrupt compressed backup")
    with pytest.raises(ValueError, match="corrupt"):
        inspect(root)


def test_cleanup_interruption_keeps_new_backup_valid_and_can_resume(tmp_path, monkeypatch):
    root = tmp_path / "backup"
    _, old, _ = complete_backup(root)
    unlink = Path.unlink

    def interrupted(path, *args, **kwargs):
        if path == old:
            raise OSError("injected interruption after manifest publication")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", interrupted)
    with pytest.raises(OSError, match="injected"):
        compact_research(root)
    assert inspect(root)["research_compaction"]["pending_cleanup"]
    monkeypatch.setattr(Path, "unlink", unlink)
    assert compact_research(root)["encoded_files"] == 1
    assert not inspect(root)["research_compaction"]["pending_cleanup"]


def test_unsupported_or_oversized_decoding_is_rejected(tmp_path):
    root = tmp_path / "backup"
    complete_backup(root)
    compact_research(root)
    manifest = inspect(root)
    bad = deepcopy(manifest)
    bad["research_files"][0]["bytes"] = 1
    atomic_json(root / "manifest.json", bad)
    with pytest.raises(ValueError, match="exceeds"):
        inspect(root)
    bad = deepcopy(manifest)
    bad["schema"] = "threemind.storage-backup/1"
    atomic_json(root / "manifest.json", bad)
    with pytest.raises(ValueError, match="version 2"):
        inspect(root)
    assert json.loads((root / "manifest.before-research-compaction.json").read_text(encoding="utf-8"))[
        "schema"
    ].endswith("/1")


def test_original_compressed_formats_keep_their_existing_representation(tmp_path):
    root = tmp_path / "backup"
    _, original, manifest = complete_backup(root)
    for row in manifest["research_files"]:
        row["member"] = "checkpoint.tmind"
    atomic_json(root / "manifest.json", manifest)
    assert compact_research(root)["encoded_files"] == 0
    assert original.exists()
    assert inspect(root) == manifest
