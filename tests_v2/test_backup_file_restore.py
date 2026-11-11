import hashlib
import io
import json
from contextlib import contextmanager
from uuid import uuid4

import pytest

from threemind_lab import storage_backup
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import atomic_json


def backup_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "subject").mkdir()
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
    target = storage.register_target(source, "Historical originals", target_id="historical-source:legacy")
    storage.register_resource(
        "formal:subject",
        {"host_id": storage.host_info()["host_id"], "target_id": target["id"],
         "config_revision": 1, "relative_path": "subject"},
        writer_mode="sealed",
    )
    root = tmp_path / "backup"
    root.mkdir()

    def record(path):
        raw = path.read_bytes()
        return {"path": path.relative_to(root).as_posix(), "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest()}

    dump = root / "database.dump"
    dump.write_bytes(b"immutable database witness")
    control = root / "control/registry.json"
    control.parent.mkdir()
    control.write_bytes(storage.registry_path.read_bytes())
    files = []
    for name in ("first.json", "second.json"):
        raw = name.encode() * 1024
        (source / "subject" / name).write_bytes(raw)
        original = root / "research" / name
        original.parent.mkdir(exist_ok=True)
        original.write_bytes(raw)
        files.append(record(original) | {"resource_id": "formal:subject", "member": name})
    manifest = {
        "schema": storage_backup.SCHEMA, "id": str(uuid4()), "state": "complete",
        "database": record(dump), "source_host": storage.host_info(),
        "targets": {}, "objects": [], "research_files": files,
        "control_files": [record(control) | {"name": "registry.json"}],
    }
    atomic_json(root / "manifest.json", manifest)
    return root, manifest, source


def test_historical_target_identity_is_not_a_windows_path(tmp_path):
    root, manifest, source = backup_files(tmp_path)
    output = tmp_path / "restored"
    result = storage_backup.restore_external(root, "isolated_verified_database", output)
    assert result["state"] == "external_files_restored_unactivated"
    assert result["database_checked"] is False
    registry = json.loads((output / "registry.restore.json").read_text(encoding="utf-8"))
    assert "historical-source:legacy" in registry["targets"]
    original_locator = json.loads((root / "control/registry.json").read_bytes())["resources"]["formal:subject"]["locator"]
    assert registry["resources"]["formal:subject"]["locator"] == original_locator
    source.rename(tmp_path / "source-hidden")
    reader = ResearchStorage(output / "control", repository_root=tmp_path)
    reader.registry_path = output / "registry.restore.json"
    for row in manifest["research_files"]:
        path = reader.resolve_member(row["resource_id"], row["member"])
        assert path.is_relative_to(output)
        assert storage_backup._hash(path) == {k: row[k] for k in ("bytes", "sha256")}


def test_interrupted_file_restore_resumes_without_republishing_valid_members(tmp_path, monkeypatch):
    root, _, _ = backup_files(tmp_path)
    output = tmp_path / "restored"
    original = storage_backup._member

    class Interrupted(io.BytesIO):
        def read(self, size=-1):
            if self.tell():
                raise OSError("injected file interruption")
            return super().read(size)

    @contextmanager
    def interrupted(destination, row):
        with original(destination, row) as stream:
            if row.get("member") == "second.json":
                yield Interrupted(stream.read())
            else:
                yield stream

    monkeypatch.setattr(storage_backup, "_member", interrupted)
    with pytest.raises(OSError, match="injected"):
        storage_backup.restore_external(root, "same_database", output)
    first = next(output.glob("targets/*/1/subject/first.json"))
    signature = first.stat().st_mtime_ns
    assert not list(output.glob("targets/*/1/subject/second.json"))
    assert list((output / ".restore-staging").iterdir())
    monkeypatch.setattr(storage_backup, "_member", original)
    storage_backup.restore_external(root, "same_database", output)
    assert first.stat().st_mtime_ns == signature
    assert len(list(output.glob("targets/*/1/subject/*.json"))) == 2
    assert not list((output / ".restore-staging").iterdir())


def test_restore_refuses_conflicts_instead_of_overwriting(tmp_path):
    root, _, _ = backup_files(tmp_path)
    output = tmp_path / "restored"
    storage_backup.restore_external(root, "same_database", output)
    with pytest.raises(ValueError, match="different backup or target"):
        storage_backup.restore_external(root, "different_database", output)
    first = next(output.glob("targets/*/1/subject/first.json"))
    first.write_bytes(b"changed by another writer")
    with pytest.raises(ValueError, match="no overwrite"):
        storage_backup.restore_external(root, "same_database", output)
    assert first.read_bytes() == b"changed by another writer"
    unknown = tmp_path / "unowned"
    unknown.mkdir()
    (unknown / "sentinel").write_bytes(b"preserve")
    with pytest.raises(ValueError, match="no matching intent"):
        storage_backup.restore_external(root, "same_database", unknown)
    assert (unknown / "sentinel").read_bytes() == b"preserve"
