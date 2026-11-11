import sys
import shutil
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).parents[1] / "adapters"))

from threemind import api
from threemind.archive import ArchiveIndexer, ArchiveRepository, ArchiveWriter
from threemind.manager import RuntimeManager
from threemind.model import ModelPackage
from threemind.runtime import ConsciousnessRuntime


def test_runtime_manager_can_start_and_return_to_an_empty_host_state() -> None:
    manager = RuntimeManager()

    assert manager.active_id is None
    assert manager.list() == []
    with pytest.raises(KeyError, match="no active consciousness"):
        manager.active()

    runtime = ConsciousnessRuntime(ModelPackage.empty(name="first consciousness"))
    manager.add(runtime)
    assert manager.active() is runtime

    manager.remove(runtime.consciousness_id, reason="test cleanup")
    assert manager.active_id is None
    assert manager.list() == []


def test_auto_snapshot_master_switch_is_a_hard_gate(monkeypatch) -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(name="snapshot gate"))
    artifact_dir = Path("test-artifacts") / "auto-snapshot-gate"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for artifact in artifact_dir.glob("*.tmind"):
        artifact.unlink()
    repository = ArchiveRepository(artifact_dir / "archive-index.sqlite3")
    writer = ArchiveWriter(repository)
    monkeypatch.setattr(api, "DATA_DIR", artifact_dir)
    monkeypatch.setattr(api, "archive_repository", repository)
    monkeypatch.setattr(api, "archive_indexer", ArchiveIndexer(repository, artifact_dir))
    monkeypatch.setattr(api, "archive_writer", writer)
    monkeypatch.setattr(api, "ui_settings", {
        "ai": {"auto_snapshot": {
            "enabled": False,
            "frequency_ticks": 1,
            "on_repeatable_structure": True,
            "on_interpreter_important": True,
        }},
    })

    api._maybe_auto_snapshot(runtime, "repeatable_structure")
    assert not list(artifact_dir.glob("*.tmind"))

    api.ui_settings["ai"]["auto_snapshot"]["enabled"] = True
    api._maybe_auto_snapshot(runtime, "repeatable_structure")
    rows = []
    for _ in range(100):
        rows = api._archive_catalog_items(runtime.consciousness_id)
        if rows:
            break
        time.sleep(.01)
    assert len(rows) == 1
    assert rows[0]["automatic"] is True
    assert rows[0]["reason"] == "repeatable_structure"
    assert api._snapshot_candidate(runtime.consciousness_id)["path"] == rows[0]["path"]
    writer.stop()
    repository.close()
    shutil.rmtree(artifact_dir, ignore_errors=True)


def test_continue_hydrates_the_latest_snapshot_for_a_stored_consciousness(monkeypatch) -> None:
    artifact_dir = Path("test-artifacts") / "continue-from-snapshot"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for artifact in artifact_dir.glob("*.tmind"):
        artifact.unlink()
    repository = ArchiveRepository(artifact_dir / "archive-index.sqlite3")
    writer = ArchiveWriter(repository)

    source = ConsciousnessRuntime(ModelPackage.empty(name="stored consciousness"))
    source.step(ticks=3)
    path = artifact_dir / f"{source.consciousness_id}-{source.tick}-snapshot.tmind"
    source.snapshot(str(path), label="latest manual state")
    repository.index_metadata(path, source.package.catalog_metadata())

    initial = ConsciousnessRuntime(ModelPackage.empty(name="other live consciousness"))
    manager = RuntimeManager(initial)

    class RuntimeSlot:
        runtime: ConsciousnessRuntime

    scheduler = RuntimeSlot()
    interpreter = RuntimeSlot()
    scheduler.runtime = initial
    interpreter.runtime = initial
    monkeypatch.setattr(api, "DATA_DIR", artifact_dir)
    monkeypatch.setattr(api, "archive_repository", repository)
    monkeypatch.setattr(api, "archive_indexer", ArchiveIndexer(repository, artifact_dir))
    monkeypatch.setattr(api, "archive_writer", writer)
    monkeypatch.setattr(api, "manager", manager)
    monkeypatch.setattr(api, "runtime", initial)
    monkeypatch.setattr(api, "scheduler", scheduler)
    monkeypatch.setattr(api, "interpreter", interpreter)

    result = api.continue_consciousness(source.consciousness_id)
    restored = manager.get(source.consciousness_id)
    try:
        assert result["snapshot"]["path"] == str(path.resolve())
        assert manager.active_id == source.consciousness_id
        assert restored.tick == source.tick
        assert restored.running()
    finally:
        restored.stop("test cleanup")
        initial.stop("test cleanup")
        writer.stop()
        repository.close()
        shutil.rmtree(artifact_dir, ignore_errors=True)


def test_archive_indexer_reads_pre_rename_packages() -> None:
    artifact_dir = Path("test-artifacts") / "pre-rename-package"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    package_path = artifact_dir / "preserved-snapshot.bbx"
    runtime = ConsciousnessRuntime(ModelPackage.empty(name="preserved consciousness"))
    runtime.snapshot(str(package_path), label="pre-rename snapshot")
    repository = ArchiveRepository(artifact_dir / "archive-index.sqlite3")
    indexer = ArchiveIndexer(repository, artifact_dir)
    try:
        indexer.start()
        for _ in range(100):
            if not indexer.status()["running"]:
                break
            time.sleep(.01)
        rows = repository.list_archives(runtime.consciousness_id)
        assert len(rows) == 1
        assert rows[0]["path"] == str(package_path.resolve())
    finally:
        indexer.stop()
        repository.close()
        shutil.rmtree(artifact_dir, ignore_errors=True)
