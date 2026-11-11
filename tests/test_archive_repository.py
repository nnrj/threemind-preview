import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).parents[1] / "adapters"))

from threemind.archive import ArchiveRepository
from threemind import api
from threemind.manager import RuntimeManager
from threemind.model import ModelPackage
from threemind.runtime import ConsciousnessRuntime


def test_sqlite_archive_index_reads_new_package_headers_without_full_load(monkeypatch) -> None:
    root = Path(".archive-index-test-" + uuid.uuid4().hex)
    root.mkdir()
    repository = ArchiveRepository(root / "archive-index.sqlite3")
    try:
        runtime = ConsciousnessRuntime(ModelPackage.empty(name="indexed consciousness"))
        runtime.step(ticks=2)
        path = root / "manual-snapshot.tmind"
        runtime.snapshot(str(path), label="manual", automatic=False, reason="manual")

        # A new package contains metadata.json, so indexing it must not call
        # ModelPackage.load() and deserialize the entire graph payload.
        monkeypatch.setattr(ModelPackage, "load", classmethod(lambda cls, value: (_ for _ in ()).throw(AssertionError("full load is not allowed"))))
        item = repository.index_file(path)
        assert item["kind"] == "snapshot"
        assert item["label"] == "manual"
        assert item["automatic"] is False
        assert repository.list_archives(runtime.consciousness_id)[0]["path"] == str(path.resolve())
        consciousness = repository.list_consciousnesses()[0]
        assert consciousness["id"] == runtime.consciousness_id
        assert consciousness["snapshots"] == 1
    finally:
        repository.close()
        shutil.rmtree(root, ignore_errors=True)


def test_consciousness_list_uses_archive_index_not_package_scan(monkeypatch) -> None:
    root = Path(".archive-index-list-test-" + uuid.uuid4().hex)
    root.mkdir()
    repository = ArchiveRepository(root / "archive-index.sqlite3")
    try:
        stored = ConsciousnessRuntime(ModelPackage.empty(name="stored through index"))
        stored.step(ticks=1)
        path = root / "stored-snapshot.tmind"
        stored.snapshot(str(path), label="stored")
        repository.index_metadata(path, stored.package.catalog_metadata())

        live = ConsciousnessRuntime(ModelPackage.empty(name="live"))
        manager = RuntimeManager(live)
        monkeypatch.setattr(api, "archive_repository", repository)
        monkeypatch.setattr(api, "manager", manager)
        monkeypatch.setattr(
            ModelPackage,
            "load",
            classmethod(lambda cls, value: (_ for _ in ()).throw(AssertionError("consciousness listing must not scan packages"))),
        )
        result = api.consciousnesses()
        assert any(item["id"] == stored.consciousness_id for item in result["items"])
        assert any(item["id"] == live.consciousness_id for item in result["items"])
        # All three management catalogue paths must remain SQLite-only.  A
        # browser opening the management, archive, and package views together
        # must not deserialize every historic consciousness graph.
        assert api.snapshot_catalog()["items"][0]["path"] == str(path.resolve())
        assert api.packages()["items"][0]["path"] == str(path.resolve())
    finally:
        repository.close()
        shutil.rmtree(root, ignore_errors=True)
