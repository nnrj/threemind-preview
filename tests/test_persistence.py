from pathlib import Path
import shutil
import uuid

from threemind import api
from threemind.archive import ArchiveRepository
from threemind.history import HistoryCheckpointWriter
from threemind.manager import RuntimeManager
from threemind.model import ModelPackage
from threemind.persistence import FileBackendTooLarge, SQLiteBackend, build_backend
from threemind.runtime import ConsciousnessRuntime


def test_sqlite_backend_roundtrip():
    tmp_path = Path(".persistence-test-" + uuid.uuid4().hex); tmp_path.mkdir()
    backend = SQLiteBackend(tmp_path / "threemind.sqlite3")
    backend.put("one", {"id": "one", "value": 3})
    assert backend.get("one")["value"] == 3
    assert backend.all()[0]["id"] == "one"
    backend.delete("one")
    assert backend.get("one") is None
    backend.close()
    shutil.rmtree(tmp_path)


def test_backend_factory_file():
    tmp_path = Path(".persistence-test-" + uuid.uuid4().hex); tmp_path.mkdir()
    backend = build_backend("file", tmp_path)
    backend.put("x", {"id": "x"})
    assert backend.get("x")["id"] == "x"
    shutil.rmtree(tmp_path)


def test_file_backend_refuses_oversized_document_before_json_decode() -> None:
    """A legacy JSON document must not be expanded into memory at startup."""
    root = Path(".persistence-too-large-" + uuid.uuid4().hex)
    root.mkdir()
    try:
        path = root / "records.json"
        path.write_bytes(b"{" + b"x" * 64 + b"}")
        try:
            build_backend("file", root, {"max_eager_bytes": 32})
        except FileBackendTooLarge as error:
            assert error.path == path
            assert error.size == path.stat().st_size
        else:
            raise AssertionError("oversized legacy document was decoded")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_history_checkpoint_writer_persists_a_complete_runtime_history() -> None:
    root = Path(".history-checkpoint-test-" + uuid.uuid4().hex)
    root.mkdir()
    backend = SQLiteBackend(root / "history.sqlite3")
    runtime = ConsciousnessRuntime(ModelPackage.empty(name="durable history"))
    runtime.record_observation({"kind": "passive_readout", "readout": "observed", "tick": runtime.tick})
    writer = HistoryCheckpointWriter(lambda: backend)
    try:
        writer.start()
        writer.schedule(runtime)
        assert writer.flush(timeout=3.0)
        saved = backend.get(HistoryCheckpointWriter.key(runtime.consciousness_id))
        assert saved is not None
        assert saved["record_type"] == "history_checkpoint"
        assert saved["observations"][0]["readout"] == "observed"
        assert saved["events"]
    finally:
        writer.stop(flush=True)
        backend.close()
        shutil.rmtree(root, ignore_errors=True)


def test_history_log_endpoint_falls_back_to_one_indexed_snapshot(monkeypatch) -> None:
    root = Path(".history-archive-fallback-" + uuid.uuid4().hex)
    root.mkdir()
    repository = ArchiveRepository(root / "archive-index.sqlite3")
    backend = SQLiteBackend(root / "history.sqlite3")
    stored = ConsciousnessRuntime(ModelPackage.empty(name="stored history"))
    stored.record_observation({"kind": "passive_readout", "readout": "from archive", "tick": stored.tick})
    path = root / "stored-snapshot.tmind"
    stored.snapshot(str(path), label="history fallback")
    repository.index_metadata(path, stored.package.catalog_metadata())
    live = ConsciousnessRuntime(ModelPackage.empty(name="other live consciousness"))
    try:
        monkeypatch.setattr(api, "manager", RuntimeManager(live))
        monkeypatch.setattr(api, "archive_repository", repository)
        monkeypatch.setattr(api, "persistence", backend)
        result = api.instance_logs("observations", stored.consciousness_id, limit=0)
        assert result["origin"] == "archive"
        assert result["items"][0]["readout"] == "from archive"
    finally:
        repository.close()
        backend.close()
        shutil.rmtree(root, ignore_errors=True)


def test_history_log_endpoint_reads_durable_checkpoint_after_runtime_is_gone(monkeypatch) -> None:
    root = Path(".history-durable-read-" + uuid.uuid4().hex)
    root.mkdir()
    backend = SQLiteBackend(root / "history.sqlite3")
    repository = ArchiveRepository(root / "archive-index.sqlite3")
    stored = ConsciousnessRuntime(ModelPackage.empty(name="checkpoint history"))
    stored.record_observation({"kind": "passive_readout", "readout": "from persistence", "tick": stored.tick})
    writer = HistoryCheckpointWriter(lambda: backend)
    live = ConsciousnessRuntime(ModelPackage.empty(name="other live consciousness"))
    try:
        writer.start()
        writer.schedule(stored)
        assert writer.flush(timeout=3.0)
        monkeypatch.setattr(api, "manager", RuntimeManager(live))
        monkeypatch.setattr(api, "archive_repository", repository)
        monkeypatch.setattr(api, "persistence", backend)
        result = api.instance_logs("observations", stored.consciousness_id, limit=0)
        assert result["origin"] == "persistence"
        assert result["items"][0]["readout"] == "from persistence"
    finally:
        writer.stop(flush=True)
        repository.close()
        backend.close()
        shutil.rmtree(root, ignore_errors=True)
