import copy
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

from threemind_core import Engine, StateImage, Stimulus
from threemind_lab.blob_store import BlobStore, object_chunks
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import StorageConflict
from threemind_lab.storage_migration import MigrationService
from threemind_lab.storage_root import RootChanges
from threemind_runtime.host import NativeEngine


def local_files(database, tmp_path):
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path / "repo")
    (tmp_path / "repo").mkdir(exist_ok=True)
    database.blobs = BlobStore(storage)
    database.blobs.location_resolver = database.payloads.location
    return storage


def test_selected_originals_keep_source_reports_and_reversible_member_references(tmp_path):
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
    source = tmp_path / "old"
    source.mkdir()
    (source / "report.md").write_text("frozen report")
    (source / "raw").mkdir()
    (source / "raw/evidence.bin").write_bytes(b"actual evidence")
    a = storage.register_target(source, "source")
    b = storage.register_target(tmp_path / "new", "destination")
    storage.register_resource("experiment", storage.locator(a["id"], "raw"), writer_mode="sealed")
    service = MigrationService(storage, min_free_bytes=0)
    plan = service.plan("experiment", b["id"], "archived", members=["evidence.bin"])
    service.execute(plan["id"])
    service.verify(plan["id"])
    service.activate(plan["id"])
    assert storage.resolve_member("experiment", "evidence.bin") == tmp_path / "new/archived/evidence.bin"
    assert storage.resolve_resource("experiment") == source / "raw"
    assert (source / "report.md").read_text() == "frozen report"
    assert storage.resolve_legacy(source / "raw/evidence.bin") == tmp_path / "new/archived/evidence.bin"
    service.rollback(plan["id"])
    assert storage.resolve_member("experiment", "evidence.bin") == source / "raw/evidence.bin"


@pytest.mark.parametrize("engine_type", [Engine, NativeEngine])
def test_filesystem_delta_checkpoints_preserve_full_context_trajectory_and_db_projection(
    database, tmp_path, engine_type
):
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "file checkpoint")["id"]
    run = database.create_run(project, "whole subject", {})
    engine = engine_type()
    engine.inject(Stimulus(0, tuple((i, 0.6) for i in range(40))))
    engine.advance_to(100000)
    image = engine.capture_state()
    context = {
        "initialized": True,
        "body_tools": {"body": {"position": [1, 2]}},
        "readouts": {"recent": [11]},
        "random_state": [123, 456],
        "mappings": {"11": "shape"},
        "peripheral": {"weights": [0.2, 0.7], "optimizer": [0.9]},
    }
    cp = database.save_checkpoint(project, run["id"], image, expected_revision=0, context=context)
    assert cp["blob_id"] is None and database.checkpoint_backend == "database"
    database.checkpoint_backend = "filesystem"
    before = image.to_dict()
    changed = copy.deepcopy(before)
    changed["nodes"][0]["activation"] += 0.01
    second = StateImage.from_dict(changed)
    engine = engine_type(state=second)
    cp2 = database.save_checkpoint(
        project, run["id"], second, expected_revision=1, context=context, previous=(cp, before)
    )
    assert cp2["blob_id"] and cp2["delta_depth"] == 1
    recovered, restored = database.load_checkpoint(project, run["id"])
    assert restored.digest == second.digest
    assert all(recovered["context"][k] == v for k, v in context.items())
    with database.tx(project) as db:
        assert (
            db.execute("SELECT count(*) n FROM state_chunks WHERE checkpoint_id=%s", (cp2["id"],)).fetchone()["n"] == 0
        )
    assert len(database.query_graph(project, run["id"])["rows"]) == len(second.to_dict()["nodes"])
    resumed = engine_type(state=restored)
    for e in (engine, resumed):
        e.inject(Stimulus(400000, ((12, 0.9),)))
        e.advance_to(500000)
    assert engine.capture_state().digest == resumed.capture_state().digest
    locator = storage.target(database.blobs.freeze("checkpoint")["target_id"])
    root = locator["configuration"]["path"]
    assert str(tmp_path / "repo/data/checkpoints") == root
    with database.tx(project) as db:
        blob = db.execute("SELECT * FROM stored_blobs WHERE id=%s", (cp2["blob_id"],)).fetchone()
    storage.safe_path(blob["locator"]["target_id"], blob["locator"]["key"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="corrupt|length"):
        database.load_checkpoint(project, run["id"])


def test_failed_file_save_has_no_visible_checkpoint_and_no_silent_location_upgrade(database, tmp_path, monkeypatch):
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "fenced file save")["id"]
    run = database.create_run(project, "fence", {})
    database.checkpoint_backend = "filesystem"
    with pytest.raises(Conflict):
        database.save_checkpoint(project, run["id"], Engine().capture_state(), expected_revision=8)
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) n FROM checkpoints").fetchone()["n"] == 0
    assert list((storage.control_dir / "blob-candidates").glob("*.json"))
    target = storage.register_target(tmp_path / "old", "original")
    storage.register_resource("old-evidence", storage.locator(target["id"], "evidence"), writer_mode="sealed")
    monkeypatch.setenv("THREEMIND_DATA_ROOT", str(tmp_path / "requested"))
    assert storage.root_info()["migration_required"]
    with pytest.raises(StorageConflict, match="root-change"):
        database.save_checkpoint(project, run["id"], Engine().capture_state(), expected_revision=0)


def artifact(database, project, raw):
    job = database.enqueue(project, "export")
    ident = uuid4()
    with database.tx(project) as db:
        db.execute("UPDATE jobs SET status='done' WHERE id=%s", (job["id"],))
        db.execute(
            "INSERT INTO artifacts(id,project_id,job_id,name,media_type,bytes,sha256) VALUES(%s,%s,%s,'original','application/octet-stream',%s,%s)",
            (ident, project, job["id"], len(raw), hashlib.sha256(raw).hexdigest()),
        )
        db.execute("INSERT INTO artifact_chunks VALUES(%s,%s,0,%s)", (project, ident, raw))
    return ident


def test_database_payload_move_exact_idempotent_strict_reads_and_retained_source_rollback(database, tmp_path):
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "original migration")["id"]
    raw = b"formal evidence" * 100
    ident = artifact(database, project, raw)
    target = storage.register_target(tmp_path / "new-root", "new originals")
    op = uuid4()
    receipt = database.payloads.migrate(project, "artifact", ident, target["id"], operation_id=op, actor=LOCAL_USER)
    assert b"".join(object_chunks(database, project, "artifact", ident)) == raw
    assert receipt == database.payloads.migrate(
        project, "artifact", ident, target["id"], operation_id=op, actor=LOCAL_USER
    )
    with pytest.raises(StorageConflict, match="arguments"):
        database.payloads.migrate(project, "artifact", uuid4(), target["id"], operation_id=op, actor=LOCAL_USER)
    other = database.create_project({"id": LOCAL_USER}, "other project")["id"]
    with pytest.raises(ValueError, match="unavailable"):
        b"".join(object_chunks(database, other, "artifact", ident))
    path = storage.safe_path(target["id"], receipt["locator"]["key"])
    path.write_bytes(b"corruption")
    with pytest.raises(ValueError, match="corrupt|length"):
        b"".join(object_chunks(database, project, "artifact", ident))
    path.write_bytes(raw)
    database.payloads.rollback(receipt)
    assert b"".join(object_chunks(database, project, "artifact", ident)) == raw
    with database.tx(project) as db:
        assert db.execute("SELECT blob_id FROM artifacts WHERE id=%s", (ident,)).fetchone()["blob_id"] is None
        assert (
            bytes(db.execute("SELECT body FROM artifact_chunks WHERE artifact_id=%s", (ident,)).fetchone()["body"])
            == raw
        )


def test_external_blob_location_versions_keep_original_locator_and_failure_no_fallback(database, tmp_path):
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "versioned placement")["id"]
    a = storage.register_target(tmp_path / "a", "A")
    b = storage.register_target(tmp_path / "b", "B")
    database.blobs.set_policy("export", a["id"], expected_revision=0)
    original = database.blobs.prepare(project, "export", [b"old external original"])
    ident = artifact(database, project, b"old external original")
    with database.tx(project) as db:
        blob_id = database.blobs.attach(db, original)
        db.execute("UPDATE artifacts SET blob_id=%s WHERE id=%s", (blob_id, ident))
    receipt = database.payloads.migrate(
        project, "blob", original["id"], b["id"], operation_id=uuid4(), actor=LOCAL_USER
    )
    with database.tx(project) as db:
        row = db.execute("SELECT * FROM stored_blobs WHERE id=%s", (original["id"],)).fetchone()
        assert row["locator"] == original["locator"]
        assert db.execute("SELECT count(*) n FROM blob_location_versions").fetchone()["n"] == 1
    assert b"".join(database.blobs.read(row)) == b"old external original"
    new = storage.safe_path(b["id"], receipt["locator"]["key"])
    new.rename(new.with_suffix(".unavailable"))
    with pytest.raises(FileNotFoundError):
        b"".join(database.blobs.read(row))
    new.with_suffix(".unavailable").rename(new)
    database.payloads.rollback(receipt)
    assert b"".join(database.blobs.read(row)) == b"old external original"


def test_root_batch_single_service_and_resume_rollback(database, tmp_path, monkeypatch):
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "root orchestration")["id"]
    ident = artifact(database, project, b"preserved")
    service = RootChanges(database)
    monkeypatch.setattr(service, "_tracked", lambda: set())
    service.migrations.min_free_bytes = 0
    actor = {"id": LOCAL_USER, "admin": True}
    op = uuid4()
    plan = service.plan(tmp_path / "moved", actor, operation_id=op, expected_revision=0)
    assert plan["payload_count"] == 1
    result = service.execute(op)
    assert result["state"] == "complete"
    assert storage.root_info()["path"] == str(tmp_path / "moved")
    assert database.checkpoint_backend == "database"
    assert service.verify(op)["incomplete"] is False
    assert b"".join(object_chunks(database, project, "artifact", ident)) == b"preserved"
    assert service.execute(op)["state"] == "complete"
    from threemind_lab.storage_files import atomic_json

    interrupted = service.status(op)
    interrupted["state"] = "running"
    interrupted.pop("root_revision", None)
    atomic_json(service._path(op), interrupted)
    assert service.execute(op, resume=True)["state"] == "complete"
    assert storage.root_info()["revision"] == 1
    assert service.rollback(op)["state"] == "rolled_back"
    assert storage.root_info()["path"] == str(tmp_path / "repo/data")


def test_checkpoint_archiving_rejects_unsealed_and_continuing_subjects(database, tmp_path):
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "seal guards")["id"]
    run = database.create_run(project, "continuing", {})
    cp = database.save_checkpoint(project, run["id"], Engine().capture_state(), expected_revision=0, status="paused")
    target = storage.register_target(tmp_path / "archive", "archive")
    with pytest.raises(StorageConflict, match="sealed"):
        database.payloads.migrate(project, "checkpoint", cp["id"], target["id"], operation_id=uuid4())
    assert not any(r["kind"] == "checkpoint" for r in database.payloads.inventory(project))
    with pytest.raises(StorageConflict, match="stopped completed"):
        database.payloads.seal(project, run["id"])


def test_private_image_migration_preserves_original_bytes_and_ownership(database, tmp_path):
    import psycopg

    from threemind_lab.notebooks import asset, save_asset

    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "private images")["id"]
    stream = io.BytesIO()
    Image.new("RGB", (3, 3), "blue").save(stream, format="PNG")
    image = stream.getvalue()
    ident = uuid4()
    save_asset(database, project, LOCAL_USER, ident, "private.png", image)
    other = uuid4()
    with database.tx(project) as db:
        db.execute("INSERT INTO users(id,username,admin) VALUES(%s,%s,true)", (other, "other-" + other.hex))
        db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (project, other))
    target = storage.register_target(tmp_path / "images", "moved")
    assert not database.payloads.inventory(project, actor=other)
    receipt = database.payloads.migrate(
        project, "note-image", ident, target["id"], operation_id=uuid4(), actor=LOCAL_USER
    )
    assert bytes(asset(database, project, LOCAL_USER, ident)["content"]) == image
    with pytest.raises(psycopg.Error, match="immutable"), database.tx(project) as db:
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(LOCAL_USER),))
        db.execute("UPDATE note_assets SET sha256=%s WHERE id=%s", ("0" * 64, ident))
    with database.tx(project) as db:
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(LOCAL_USER),))
        assert bytes(db.execute("SELECT content FROM note_assets WHERE id=%s", (ident,)).fetchone()["content"]) == image
    assert not database.payloads.inventory(project, actor=other)
    with pytest.raises(StorageConflict, match="authorized"):
        database.payloads.migrate(
            project, "blob", receipt["new_blob_id"], target["id"], operation_id=uuid4(), actor=other
        )
    database.payloads.rollback(receipt)
    assert bytes(asset(database, project, LOCAL_USER, ident)["content"]) == image


def test_copy_cancellation_and_space_guard_leave_sources_and_root_unchanged(database, tmp_path, monkeypatch):
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "safe cancellation")["id"]
    ident = artifact(database, project, b"never discarded")
    target = storage.register_target(tmp_path / "cancelled", "cancelled")
    with pytest.raises(InterruptedError):
        database.payloads.migrate(
            project, "artifact", ident, target["id"], operation_id=uuid4(), cancelled=lambda: True
        )
    assert b"".join(object_chunks(database, project, "artifact", ident)) == b"never discarded"
    with database.tx(project) as db:
        assert db.execute("SELECT blob_id FROM artifacts WHERE id=%s", (ident,)).fetchone()["blob_id"] is None
    service = RootChanges(database)
    monkeypatch.setattr(service, "_tracked", lambda: set())
    plan = service.plan(tmp_path / "too-small", {"id": LOCAL_USER}, operation_id=uuid4(), expected_revision=0)
    monkeypatch.setattr(service.migrations, "_space", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    assert service.execute(plan["id"])["state"] == "blocked"
    assert storage.root_info()["revision"] == 0
    cancelled = service.plan(tmp_path / "stop", {"id": LOCAL_USER}, operation_id=uuid4(), expected_revision=0)
    assert service.cancel(cancelled["id"])["state"] == "cancelled"


def test_root_guard_rechecks_writers_and_cancelled_task_can_resume(database, tmp_path, monkeypatch):
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "writer guard")["id"]
    artifact(database, project, b"fixed")
    service = RootChanges(database)
    monkeypatch.setattr(service, "_tracked", lambda: set())
    service.migrations.min_free_bytes = 0
    plan = service.plan(tmp_path / "new", {"id": LOCAL_USER}, operation_id=uuid4(), expected_revision=0)
    job = database.enqueue(project, "export")
    assert service.execute(plan["id"])["state"] == "blocked"
    assert storage.root_info()["revision"] == 0
    with database.tx(project) as db:
        db.execute("UPDATE jobs SET status='done' WHERE id=%s", (job["id"],))
    service.cancel(plan["id"])
    assert service.execute(plan["id"], resume=True)["state"] == "complete"


def test_root_cancel_cache_observes_another_controller(database, tmp_path, monkeypatch):
    local_files(database, tmp_path)
    service = RootChanges(database)
    monkeypatch.setattr(service, "_tracked", lambda: set())
    plan = service.plan(tmp_path / "new", {"id": LOCAL_USER}, operation_id=uuid4(), expected_revision=0)
    assert not service._cancelled(plan)
    RootChanges(database).cancel(plan["id"])
    assert service._cancelled(plan)


def test_sealed_checkpoint_migration_export_and_new_location_revision_after_rollback(database, tmp_path):
    from test_data_bundles import leased

    from threemind_lab.data_archive import DataReader
    from threemind_lab.data_bundles import DataBundles
    from threemind_lab.data_catalog import DataCatalog

    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "sealed checkpoint")["id"]
    run = database.create_run(project, "completed", {})
    engine = Engine()
    engine.inject(Stimulus(0, ((1, 0.6),)))
    engine.advance_to(50000)
    image = engine.capture_state()
    cp = database.save_checkpoint(
        project,
        run["id"],
        image,
        expected_revision=0,
        status="completed",
        context={"initialized": True, "implementation": {"backend": "reference"}, "random_state": [777]},
    )
    database.payloads.seal(project, run["id"])
    assert any(r["kind"] == "checkpoint" for r in database.payloads.inventory(project))
    target = storage.register_target(tmp_path / "sealed", "sealed")
    receipt = database.payloads.migrate(project, "checkpoint", cp["id"], target["id"], operation_id=uuid4())
    restored, state = database.load_checkpoint(project, run["id"])
    assert state == image and restored["context"]["random_state"] == [777]
    second = storage.register_target(tmp_path / "second", "second")
    moved = database.payloads.migrate(project, "blob", receipt["new_blob_id"], second["id"], operation_id=uuid4())
    database.payloads.rollback(moved)
    assert database.payloads.rollback(moved)["state"] == "rolled_back"
    removed = database.payloads.migrate(project, "blob", receipt["new_blob_id"], second["id"], operation_id=uuid4())
    assert removed["placement_revision"] == 2 and removed["source_placement_revision"] == 0
    assert database.load_checkpoint(project, run["id"])[1] == image
    plan = DataCatalog(database).export_plan(project, LOCAL_USER, {"kind": "run", "ids": [str(run["id"])]})
    service = DataBundles(database)
    job = leased(database, project, service.export(project, LOCAL_USER, plan["id"], uuid4()))
    result = service._export_job(SimpleNamespace(db=database), job)
    raw = b"".join(service.chunks(project, LOCAL_USER, result["bundle_id"]))
    with DataReader(io.BytesIO(raw)) as reader:
        item = reader.objects["run:" + str(run["id"])]
        payload = reader.json(item["payload"])
        entries = payload["checkpoint_payloads"]
        assert len(entries) == 1 and entries[0]["checkpoint_id"] == str(cp["id"])
        assert hashlib.sha256(b"".join(reader.chunks(entries[0]["bytes_entry"]))).hexdigest() == receipt["sha256"]


@pytest.mark.parametrize("compact", [False, True])
def test_union_backup_restores_moved_member_file_checkpoint_and_blob_without_old_sources(
    database, tmp_path, compact, monkeypatch
):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    from threemind_lab.database import Database
    from threemind_lab.storage_backup import compact_research, create, inspect, restore

    pg_bin = Path("D:/Program Files/PostgreSQL/17/bin")
    if not (pg_bin / "pg_dump.exe").exists():
        pytest.skip("PostgreSQL backup utilities absent")
    storage = local_files(database, tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "union backup")["id"]
    database.checkpoint_backend = "filesystem"
    run = database.create_run(project, "continuing file checkpoint", {})
    image = Engine().capture_state()
    database.save_checkpoint(project, run["id"], image, expected_revision=0, context={"random_state": [888]})
    ident = artifact(database, project, b"retained artifact")
    target = storage.register_target(tmp_path / "originals", "originals")
    database.payloads.migrate(project, "artifact", ident, target["id"], operation_id=uuid4(), actor=LOCAL_USER)
    source = tmp_path / "evidence-source"
    source.mkdir()
    raw = b"member bytes" * 8192
    (source / "evidence.bin").write_bytes(raw)
    a = storage.register_target(source, "source")
    storage.register_resource("mixed", storage.locator(a["id"], "sub"), writer_mode="sealed")
    (source / "sub").mkdir()
    (source / "sub/evidence.bin").write_bytes(raw)
    migration = MigrationService(storage, min_free_bytes=0)
    plan = migration.plan("mixed", target["id"], "research", members=["evidence.bin"])
    migration.execute(plan["id"])
    migration.verify(plan["id"])
    migration.activate(plan["id"])
    # The exact declared historical manifest is the same source consumed by P1.
    from threemind_lab import data_api

    original_registered = data_api.registered_artifacts
    data_api.registered_artifacts = lambda _: [
        {
            "archive_path": str(source / "sub/evidence.bin"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    ]
    params = conninfo_to_dict(database.test_url)
    params.pop("password", None)
    params["user"] = "threemind_test"
    admin = make_conninfo(**params)
    backup = tmp_path / "backup"
    name = "tm2_test_restore_" + uuid4().hex[:12]
    resource_reads = []
    resource_list = storage.resources

    def counted_resources():
        resource_reads.append(1)
        return resource_list()

    monkeypatch.setattr(storage, "resources", counted_resources)
    try:
        create(admin, backup, blobs=database.blobs, pg_bin=pg_bin)
        assert len(resource_reads) == 1
        assert len(inspect(backup)["research_files"]) == 1
        if compact:
            assert compact_research(backup)["encoded_files"] == 1
            assert inspect(backup)["schema"] == "threemind.storage-backup/2"
        destination = tmp_path / "restored"
        restore(admin, backup, name, destination, pg_bin=pg_bin)
        # Physically hide every old source tree before reading the restored copy.
        for path in (tmp_path / "originals", tmp_path / "repo/data/checkpoints", source):
            path.rename(path.with_name(path.name + "-unavailable"))
        restored = Database(make_conninfo(**(params | {"dbname": name})), allow_owner=True)
        try:
            local = ResearchStorage(destination / "control", repository_root=tmp_path / "repo")
            local.registry_path = destination / "registry.restore.json"
            restored.blobs = BlobStore(local)
            restored.blobs.location_resolver = restored.payloads.location
            assert restored.load_checkpoint(project, run["id"])[1] == image
            assert b"".join(object_chunks(restored, project, "artifact", ident)) == b"retained artifact"
            assert local.resolve_member("mixed", "evidence.bin").read_bytes() == raw
        finally:
            restored.close()
    finally:
        data_api.registered_artifacts = original_registered
        with psycopg.connect(admin, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
