from uuid import uuid4

import pytest

from threemind_lab.storage_files import StorageConflict, atomic_json, read_json
from threemind_lab.storage_journal import SelectionJournal


def test_large_fixed_selection_is_not_rewritten_with_small_progress(tmp_path):
    journal = SelectionJournal(tmp_path, "migrations", ("entries",))
    identity = str(uuid4())
    path = tmp_path / "migrations" / (identity + ".json")
    row = {"id": identity, "entries": [{"path": str(i), "sha256": "a" * 64} for i in range(10000)], "done": 0}
    journal.write(path, row)
    selection = tmp_path / row["selection_ref"]["path"]
    frozen = selection.read_bytes()
    before = selection.stat().st_mtime_ns
    for value in range(10):
        row["done"] = value
        journal.write(path, row)
    assert path.stat().st_size < 1024
    assert selection.stat().st_mtime_ns == before and selection.read_bytes() == frozen
    assert journal.read(path)["entries"] == row["entries"]
    assert read_json(path)["done"] == 9
    data = read_json(selection)
    data["fields"]["entries"][0]["path"] = "different"
    atomic_json(selection, data)
    with pytest.raises(StorageConflict, match="hash"):
        journal.read(path)


def test_legacy_inline_and_matching_full_receipts_remain_readable(tmp_path):
    journal = SelectionJournal(tmp_path, "root-changes", ("resources",))
    path = tmp_path / "old.json"
    legacy = {"id": str(uuid4()), "resources": ["first"], "state": "planned"}
    atomic_json(path, legacy)
    assert journal.read(path) == legacy
    journal.write(path, legacy)
    inflated = journal.read(path)
    atomic_json(path, inflated)
    assert journal.read(path) == inflated
    inflated["resources"] = ["wrong"]
    atomic_json(path, inflated)
    with pytest.raises(StorageConflict, match="conflicting"):
        journal.read(path)


def test_large_member_locations_cache_invalidates_on_corruption(tmp_path, monkeypatch):
    from threemind_lab import research_storage

    storage = research_storage.ResearchStorage(tmp_path / "control", repository_root=tmp_path / "repo")
    target = storage.register_target(tmp_path / "originals", "source")
    resource = storage.register_resource("large", storage.locator(target["id"], "study"), writer_mode="sealed")
    template = resource["locator"]
    locations = {
        f"checkpoints/{i:06}.tmind": template | {"relative_path": f"study/checkpoints/{i:06}.tmind"}
        for i in range(12000)
    }
    storage.publish_members(resource, locations)
    path = storage.control_dir / resource["member_manifest"]["path"]
    assert path.stat().st_size > 2 * 1024**2
    reads = []
    read = research_storage.read_json

    def counted(*args, **kwargs):
        reads.append(1)
        return read(*args, **kwargs)

    monkeypatch.setattr(research_storage, "read_json", counted)
    assert storage.member_locations(resource, copy_state=False) == locations
    assert storage.member_locations(resource, copy_state=False) == locations
    assert len(reads) == 1
    broken = read_json(path)
    broken["locations"].pop("checkpoints/000001.tmind")
    atomic_json(path, broken)
    with pytest.raises(StorageConflict, match="hash"):
        storage.member_locations(resource, copy_state=False)
