import shutil
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).parents[1] / "adapters"))

from threemind import api
from threemind.archive import ArchiveRepository
from threemind.persistence import SQLiteBackend
from threemind.storage import scan_data_directory


def test_storage_scan_is_metadata_only_and_protects_configuration() -> None:
    root = Path(".storage-scan-" + uuid.uuid4().hex)
    root.mkdir()
    try:
        (root / "records.json").write_text("{}", encoding="utf-8")
        (root / "kept.tmind").write_bytes(b"not opened during scan")
        (root / "old.tmind.tmp").write_bytes(b"partial")
        (root / "recent.tmind.tmp").write_bytes(b"partial")
        (root / "ui-settings.json").write_text("{}", encoding="utf-8")
        old = time.time() - 120
        (root / "old.tmind.tmp").touch()
        import os
        os.utime(root / "old.tmind.tmp", (old, old))

        result = scan_data_directory(root, active_persistence="sqlite")
        items = {item["id"]: item for item in result["items"]}
        assert items["file:records.json"]["selectable"] is True
        assert items["file:kept.tmind"]["selectable"] is True
        assert items["file:old.tmind.tmp"]["selectable"] is True
        assert items["file:recent.tmind.tmp"]["selectable"] is False
        assert items["file:ui-settings.json"]["selectable"] is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_storage_cleanup_only_removes_selected_current_scan_items(monkeypatch) -> None:
    root = Path(".storage-cleanup-" + uuid.uuid4().hex)
    root.mkdir()
    legacy = root / "records.json"
    temporary = root / "interrupted.tmind.tmp"
    protected = root / "ui-settings.json"
    legacy.write_text("{}", encoding="utf-8")
    temporary.write_bytes(b"partial")
    protected.write_text("{}", encoding="utf-8")
    old = time.time() - 120
    import os
    os.utime(temporary, (old, old))
    repository = ArchiveRepository(root / "archive-index.sqlite3")

    class Writer:
        def status(self):
            return {"queued": 0, "pending": 0}

    try:
        monkeypatch.setattr(api, "DATA_DIR", root)
        monkeypatch.setattr(api, "archive_repository", repository)
        monkeypatch.setattr(api, "archive_writer", Writer())
        result = api.storage_cleanup(api.StorageCleanupRequest(
            item_ids=["file:records.json", "file:interrupted.tmind.tmp", "file:ui-settings.json"],
            confirmation="DELETE",
        ))
        assert set(result["deleted"]) == {"records.json", "interrupted.tmind.tmp"}
        assert not legacy.exists()
        assert not temporary.exists()
        assert protected.exists()
        assert result["skipped"][0]["id"] == "file:ui-settings.json"
    finally:
        repository.close()
        shutil.rmtree(root, ignore_errors=True)


def test_storage_cleanup_can_clear_durable_records_without_touching_runtime(monkeypatch) -> None:
    root = Path(".storage-history-" + uuid.uuid4().hex)
    root.mkdir()
    backend = SQLiteBackend(root / "threemind.sqlite3")
    backend.put("history:one", {"record_type": "history_checkpoint"})
    repository = ArchiveRepository(root / "archive-index.sqlite3")

    class Writer:
        def status(self):
            return {"queued": 0, "pending": 0}

    class HistoryWriter:
        def flush(self, timeout=0.0):
            return True

    try:
        monkeypatch.setattr(api, "DATA_DIR", root)
        monkeypatch.setattr(api, "persistence", backend)
        monkeypatch.setattr(api, "archive_repository", repository)
        monkeypatch.setattr(api, "archive_writer", Writer())
        monkeypatch.setattr(api, "history_writer", HistoryWriter())
        result = api.storage_cleanup(api.StorageCleanupRequest(
            item_ids=["persistence:records"],
            confirmation="DELETE",
        ))
        assert result["cleared"] == ["persistence:records"]
        assert backend.all() == []
    finally:
        repository.close()
        backend.close()
        shutil.rmtree(root, ignore_errors=True)
