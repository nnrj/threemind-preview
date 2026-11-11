from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
from threading import Event
from uuid import uuid4

import pytest

from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import StorageBusy, StorageConflict, file_lock
from threemind_lab.storage_migration import MigrationService


@pytest.fixture
def migration(tmp_path):
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
    storage.register_target(tmp_path / "old", target_id="old")
    storage.register_target(tmp_path / "new", target_id="new")
    source = tmp_path / "old/e66"
    (source / "nested/empty").mkdir(parents=True)
    (source / "core.bin").write_bytes(bytes(range(256)) * 16)
    (source / "nested/peripheral.bin").write_bytes(b"learned state\x00\xff")
    storage.register_resource("e66", storage.locator("old", "e66"), writer_mode="cooperative",
                              registered_work_path=".work/e66")
    return storage, MigrationService(storage, min_free_bytes=0), source, tmp_path / "new/e66"


def finish(service, plan):
    assert service.execute(plan["id"])["state"] == "copied"
    assert service.verify(plan["id"])["state"] == "verified"
    return service.activate(plan["id"])


def test_copy_verify_and_explicit_activation_preserve_original_evidence(migration):
    storage, service, source, destination = migration
    original = (source / "core.bin").read_bytes()
    plan = service.plan("e66", "new", expected_revision=1)
    assert plan["originals_retained"] is True
    assert not destination.exists()
    assert service.execute(plan["id"])["state"] == "copied"
    assert (destination / "core.bin").read_bytes() == original
    assert (destination / "nested/empty").is_dir()
    assert storage.resolve_resource("e66") == source
    with pytest.raises(StorageBusy):
        with storage.writer("e66"):
            pass
    with pytest.raises(StorageConflict, match="verify"):
        service.activate(plan["id"])
    service.verify(plan["id"])
    with pytest.raises(StorageConflict, match="changed"):
        service.activate(plan["id"], expected_revision=0)
    active = service.activate(plan["id"], expected_revision=1)
    assert active["state"] == "activated"
    assert storage.resolve_resource("e66") == destination
    assert storage.resolve_legacy(".work/e66/core.bin") == destination / "core.bin"
    assert storage.resource("e66")["registered_work_path"] == ".work/e66"
    assert (source / "core.bin").read_bytes() == original
    reboot = MigrationService(ResearchStorage(storage.control_dir, repository_root=storage.repository_root),
                              min_free_bytes=0)
    assert reboot.activate(plan["id"])["state"] == "activated"
    assert reboot.rollback(plan["id"])["state"] == "rolled_back"
    assert storage.resolve_resource("e66") == source
    assert destination.exists()


def test_plan_request_identity_replays_and_rejects_different_arguments(migration):
    _, service, _, _ = migration
    request = str(uuid4())
    first = service.plan("e66", "new", request_id=request)
    assert service.plan("e66", "new", request_id=request)["id"] == first["id"]
    with pytest.raises(StorageConflict, match="identity"):
        service.plan("e66", "new", relative_path="other", request_id=request)


def test_unknown_or_actively_writing_resource_cannot_be_planned(migration):
    storage, service, _, _ = migration
    with storage.writer("e66"):
        with pytest.raises(StorageBusy):
            service.plan("e66", "new")
    storage.register_resource("e66", storage.locator("old", "e66"), expected_revision=1)
    assert service.inspect("e66")["can_migrate"] is False
    with pytest.raises(StorageBusy, match="sealed"):
        service.plan("e66", "new")


def test_existing_legacy_worker_lock_is_held_during_checks(migration):
    _, service, source, _ = migration
    legacy = source / "worker.lock"
    legacy.write_bytes(b"legacy lock content")
    with file_lock(legacy, create=False):
        with pytest.raises(StorageBusy):
            service.plan("e66", "new")
    plan = service.plan("e66", "new")
    assert not any(e["path"] == "worker.lock" for e in plan["entries"])
    finish(service, plan)
    assert legacy.read_bytes() == b"legacy lock content"


@pytest.mark.parametrize("change", ["member", "addition"])
def test_source_mutation_refuses_copy_and_cancel_releases_the_reservation(migration, change):
    storage, service, source, destination = migration
    plan = service.plan("e66", "new")
    if change == "member":
        (source / "core.bin").write_bytes(b"new data")
    else:
        (source / "added.bin").write_bytes(b"new data")
    with pytest.raises(StorageConflict, match="source changed"):
        service.execute(plan["id"])
    assert service.status(plan["id"])["state"] == "failed"
    assert storage.resource("e66")["migration_id"] == plan["id"]
    assert not destination.exists()
    assert service.cancel(plan["id"])["state"] == "cancelled"
    assert storage.resource("e66")["migration_id"] is None


def test_destination_conflict_does_not_overwrite_data(migration):
    _, service, _, destination = migration
    plan = service.plan("e66", "new")
    destination.mkdir(parents=True)
    (destination / "keep.bin").write_bytes(b"keep")
    with pytest.raises(StorageConflict, match="destination"):
        service.execute(plan["id"])
    assert (destination / "keep.bin").read_bytes() == b"keep"
    service.cancel(plan["id"])
    with pytest.raises(StorageConflict, match="different"):
        service.plan("e66", "new")


def test_fault_then_new_service_resumes_only_verified_file_boundaries(migration, monkeypatch):
    storage, service, source, destination = migration
    plan = service.plan("e66", "new")
    original_copy = service._copy_file
    calls = 0

    def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated process interruption")
        return original_copy(*args)

    monkeypatch.setattr(service, "_copy_file", fail_second)
    with pytest.raises(OSError, match="interruption"):
        service.execute(plan["id"])
    assert service.status(plan["id"])["completed_files"] == 1
    assert not destination.exists()
    restarted = MigrationService(ResearchStorage(storage.control_dir, repository_root=storage.repository_root),
                                 min_free_bytes=0)
    completed = restarted.resume(plan["id"])
    assert completed["copied_bytes"] == plan["bytes"]
    assert completed["completed_files"] == 2
    assert (destination / "core.bin").read_bytes() == (source / "core.bin").read_bytes()
    assert restarted.resume(plan["id"])["state"] == "copied"
    assert storage.resolve_resource("e66") == source


def test_cancel_running_copy_has_durable_request_without_losing_progress(migration, monkeypatch):
    storage, service, source, destination = migration
    plan = service.plan("e66", "new")
    copying, continue_copy = Event(), Event()
    original_copy = service._copy_file
    calls = 0

    def pause_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            copying.set()
            assert continue_copy.wait(10)
        return original_copy(*args)

    monkeypatch.setattr(service, "_copy_file", pause_second)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(service.execute, plan["id"])
        assert copying.wait(10)
        requested = service.cancel(plan["id"])
        assert requested["cancel_requested"] is True
        assert requested["completed_files"] == 1
        continue_copy.set()
        assert future.result(timeout=10)["state"] == "cancelled"
    assert storage.resource("e66")["migration_id"] is None
    assert source.exists() and not destination.exists()
    monkeypatch.setattr(service, "_copy_file", original_copy)
    assert service.resume(plan["id"])["state"] == "copied"


def test_activation_then_new_writer_epoch_blocks_even_unchanged_byte_rollback(migration):
    storage, service, _, destination = migration
    plan = service.plan("e66", "new")
    finish(service, plan)
    with storage.writer("e66") as current:
        assert current == destination
    with pytest.raises(StorageConflict, match="post-activation"):
        service.rollback(plan["id"])
    assert storage.resolve_resource("e66") == destination


def test_target_configuration_change_does_not_retarget_a_saved_plan(migration, tmp_path):
    storage, service, _, destination = migration
    plan = service.plan("e66", "new")
    storage.register_target(tmp_path / "third", target_id="new", expected_revision=1)
    finish(service, plan)
    assert storage.resolve_resource("e66") == destination
    assert not (tmp_path / "third").exists()


def test_copy_verify_rejects_destination_corruption(migration):
    storage, service, source, destination = migration
    plan = service.plan("e66", "new")
    service.execute(plan["id"])
    (destination / "core.bin").write_bytes(b"corrupted")
    with pytest.raises(StorageConflict, match="destination"):
        service.verify(plan["id"])
    assert storage.resolve_resource("e66") == source


def test_plan_rejects_nonfilesystem_target_and_overlapping_paths(migration):
    storage, service, source, _ = migration
    storage.register_target(kind="s3", target_id="cloud", configuration={"bucket": "not-contacted"})
    with pytest.raises(ValueError, match="filesystem"):
        service.plan("e66", "cloud")
    with pytest.raises(ValueError, match="overlap"):
        service.plan("e66", "old", "e66/nested")
    with pytest.raises(ValueError, match="staging"):
        service.plan("e66", "new", ".threemind-migrations/content")
    assert source.exists()


def test_scan_and_disk_reserve_budgets_refuse_before_copy(migration):
    storage, _, _, destination = migration
    with pytest.raises(ValueError, match="member budget"):
        MigrationService(storage, max_files=1, min_free_bytes=0).plan("e66", "new")
    with pytest.raises(StorageConflict, match="free-disk"):
        MigrationService(storage, min_free_bytes=1024**6).plan("e66", "new")
    assert not destination.exists()


def test_single_file_resources_are_supported(migration):
    storage, service, source, _ = migration
    standalone = source.parent / "standalone.bin"
    standalone.write_bytes((source / "core.bin").read_bytes())
    storage.register_resource("single", storage.locator("old", "standalone.bin"), writer_mode="sealed")
    plan = service.plan("single", "new", "standalone.bin")
    finish(service, plan)
    assert storage.resolve_resource("single").read_bytes() == (source / "core.bin").read_bytes()


def test_journal_save_failure_after_mapping_commit_is_recoverable(migration, monkeypatch):
    storage, service, _, destination = migration
    plan = service.plan("e66", "new")
    service.execute(plan["id"])
    service.verify(plan["id"])
    save = service._save

    def interrupted(row, **kwargs):
        if row["state"] == "activated":
            raise OSError("journal interrupted after registry commit")
        return save(row, **kwargs)

    monkeypatch.setattr(service, "_save", interrupted)
    with pytest.raises(OSError, match="registry commit"):
        service.activate(plan["id"])
    assert service.status(plan["id"])["state"] == "activated"
    assert storage.resolve_resource("e66") == destination
    assert service.rollback(plan["id"])["state"] == "rolled_back"


def test_racing_destination_creator_is_not_replaced(migration, monkeypatch):
    from threemind_lab import storage_migration

    _, service, source, destination = migration
    plan = service.plan("e66", "new")
    original_publish = storage_migration.publish_directory

    def racing_publish(stage, target):
        target.mkdir()
        (target / "unrelated.bin").write_bytes(b"do not overwrite")
        original_publish(stage, target)

    monkeypatch.setattr(storage_migration, "publish_directory", racing_publish)
    with pytest.raises(OSError):
        service.execute(plan["id"])
    assert (destination / "unrelated.bin").read_bytes() == b"do not overwrite"
    assert source.exists()


def test_another_registered_tree_cannot_be_replaced_by_activation(migration):
    storage, service, source, destination = migration
    plan = service.plan("e66", "new")
    service.execute(plan["id"])
    service.verify(plan["id"])
    storage.register_resource("another", storage.locator("new", "e66"), writer_mode="cooperative")
    with pytest.raises(StorageConflict, match="overlap"):
        service.activate(plan["id"])
    assert storage.resolve_resource("e66") == source
    assert storage.resolve_resource("another") == destination


@pytest.mark.skipif(os.name != "nt", reason="Windows junction defense")
def test_junction_inside_source_cannot_escape_inventory(migration, tmp_path):
    _, service, source, _ = migration
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.bin").write_bytes(b"not research")
    link = source / "escape"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
    if result.returncode:
        pytest.skip("host cannot create a junction fixture")
    with pytest.raises(ValueError, match="reparse"):
        service.plan("e66", "new")
