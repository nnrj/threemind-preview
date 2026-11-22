import os

import pytest

from threemind_lab import experiment_transfer_files as files
from threemind_lab import storage_volumes as volumes
from threemind_lab.experiment_storage import ExperimentStorage
from threemind_lab.experiment_transfers import ExperimentTransfers
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import StorageConflict, file_lock


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.delenv("THREEMIND_DATA_ROOT", raising=False)
    pool = ExperimentStorage(ResearchStorage(tmp_path / "control", repository_root=tmp_path))
    pool.configure(
        [
            {"id": d, "path": str(tmp_path / d), "role": role, "priority": i, "limit_bytes": 16 * 2**20}
            for i, (d, role) in enumerate([("cold", "archive"), ("e", "run"), ("h", "run")])
        ],
        0,
    )
    src = tmp_path / "e" / "experiments" / "old"
    (src / "nested" / "empty").mkdir(parents=True)
    (src / "nested" / "data").write_bytes(b"first")
    (src / "worker.lock").write_bytes(b"0")
    for p in [src, *src.rglob("*")]:
        meta = files.times(p.stat())
        meta["mtime_ns"] = 1600000000123456700
        if "birth_ns" in meta:
            meta["birth_ns"] = 1500000000765432100
        files.set_times(p, meta)
    svc = ExperimentTransfers(pool)
    assert svc.discover("e") == ["old"]
    svc.adopt("old", "e")
    return svc, src, tmp_path


def transfer(svc, op, dest, **kwargs):
    return svc.run(svc.create(op, "old", dest, **kwargs)["id"])


def test_incremental_sync_and_versioned_portable_restore(service):
    svc, src, tmp = service
    same = svc.preview("archive", "old", "cold")
    assert same["source_bytes_on_other_volumes"] == 0 and same["source_allocated_bytes"] > 0
    first = transfer(svc, "sync", "cold")
    replica = tmp / "cold" / first["target_base"]
    assert files.inventory({"main": replica}) == files.inventory({"main": src})
    (replica / "extra").write_text("keep")
    assert transfer(svc, "sync", "cold")["copied_files"] == 0
    v1 = transfer(svc, "backup", "cold")
    (src / "nested" / "data").write_bytes(b"second")
    assert transfer(svc, "sync", "cold")["copied_files"] == 1
    assert (replica / "extra").read_text() == "keep"
    v2 = transfer(svc, "backup", "cold")
    assert v1["id"] != v2["id"]
    transfer(svc, "restore", "h", backup=v1["id"], restore_as="restored")
    assert (svc.pool.path("restored") / "nested/data").read_bytes() == b"first"
    fresh = ExperimentTransfers(ExperimentStorage(ResearchStorage(tmp / "new-control", repository_root=tmp)))
    fresh.pool.configure(
        [{"id": "portable", "path": str(tmp / "cold"), "role": "backup"}, {"id": "run", "path": str(tmp / "h")}], 0
    )
    fresh.import_backup("old", "portable", v2["id"])
    transfer(fresh, "restore", "run", backup=v2["id"], restore_as="recovered")
    assert files.inventory({"main": fresh.pool.path("recovered")}) == files.inventory({"main": src})


def test_cold_archive_reuses_sync_releases_and_unarchives(service):
    svc, src, tmp = service
    target = svc.storage.register_target(tmp / "e", "runtime")
    loc = svc.storage.locator(target["id"], "experiments/old/nested")
    svc.storage.register_resource("evidence", loc, writer_mode="sealed")
    original = files.inventory({"main": src})
    sync = transfer(svc, "sync", "cold")
    moved = transfer(svc, "archive", "cold")
    assert moved["target_base"] == sync["target_base"] and moved["copied_bytes"] == 0
    assert src.is_dir() and svc.pool.study("old")["residency"] == "archived"
    assert svc.storage.resolve_member("evidence", "data") == svc.pool.path("old") / "nested/data"
    assert svc.release(moved["id"])["status"] == "released" and not src.exists()
    (tmp / "cold").rename(tmp / "disconnected")
    assert svc.catalog()["studies"][0]["residency"] == "archived"
    with pytest.raises(volumes.VolumeOffline):
        svc.pool.path("old")
    (tmp / "disconnected").rename(tmp / "cold")
    home = transfer(svc, "unarchive", "h")
    assert files.inventory({"main": svc.pool.path("old")}) == original
    assert svc.release(home["id"])["status"] == "released"
    assert svc.storage.resolve_member("evidence", "data").read_bytes() == b"first"


def test_busy_writer_interruption_changes_and_capacity(service, monkeypatch):
    svc, src, _ = service
    assert svc.pool.reserve("different", [{"name": "main", "bytes": 8192}])["parts"][0]["directory"] == "e"
    job = svc.create("migrate", "old", "h")
    with file_lock(src / "worker.lock", create=False), pytest.raises(StorageConflict):
        svc.run(job["id"])
    assert svc.job(job["id"])["status"] == "paused"
    with monkeypatch.context() as m:
        m.setattr(volumes, "free_bytes", lambda _: 1)
        with pytest.raises(StorageConflict, match="insufficient"):
            svc.run(job["id"])
    assert svc.pool.path("old") == src
    svc.run(job["id"])
    (src / "new").write_text("later")
    with pytest.raises(StorageConflict, match="changed"):
        svc.release(job["id"])
    assert (src / "new").is_file()


def test_split_move_then_refuse_release_of_shared_file(service):
    svc, _, tmp = service
    parts = [{"name": name, "bytes": 10 * 2**20} for name in ("a", "b")]
    study = svc.pool.reserve("split", parts, allow_split=True)
    assert len({p["directory"] for p in study["parts"]}) == 2
    for part in ("a", "b"):
        root = svc.pool.path("split", part)
        root.mkdir(parents=True)
        (root / "file").write_text(part)
    svc.pool.finish("split")
    root = svc.pool.path("split", "a")
    os.link(root / "file", tmp / "also-used")
    job = svc.run(svc.create("archive", "split", "cold")["id"])
    assert (svc.pool.path("split") / "b/file").read_text() == "b"
    with pytest.raises(StorageConflict, match="hard-linked"):
        svc.release(job["id"])
    assert (root / "file").exists() and (tmp / "also-used").read_text() == "a"
    (tmp / "also-used").unlink()
    svc.release(job["id"])
    assert not root.parent.exists()
    svc.run(svc.create("unarchive", "split", "e")["id"])
    assert (svc.pool.path("split") / "a/file").read_text() == "a"
    assert (svc.pool.path("split") / "b/file").read_text() == "b"


def test_interrupted_copy_continues_and_cli_uses_catalog(service, monkeypatch, capsys):
    import json

    from threemind_lab.data_cli import storage_main

    svc, src, tmp = service
    job = svc.create("migrate", "old", "h")
    copy = files.copy_file
    calls = []

    def fail_second(source, *args):
        calls.append(source)
        if len(calls) == 2:
            raise OSError("disconnected")
        copy(source, *args)

    with monkeypatch.context() as m:
        m.setattr(files, "copy_file", fail_second)
        with pytest.raises(OSError, match="disconnected"):
            svc.run(job["id"])
    assert svc.pool.path("old") == src
    monkeypatch.setenv("THREEMIND_STORAGE_CONTROL", str(tmp / "control"))
    storage_main(["transfer", "resume", "--local", "--job", job["id"]])
    assert json.loads(capsys.readouterr().out)["copied_files"] == 1
    assert files.inventory({"main": src}) == files.inventory({"main": svc.pool.path("old")})
    (svc.pool.path("old") / "nested/data").write_bytes(b"damaged")
    with pytest.raises(StorageConflict, match="active copy differs"):
        svc.release(job["id"])
    assert src.exists()


def test_source_release_resumes_without_deleting_new_files(service, monkeypatch):
    from pathlib import Path

    svc, src, _ = service
    job = transfer(svc, "archive", "cold")
    unlink = Path.unlink

    def interrupt(path, *args, **kwargs):
        if ".threemind-retired" in path.parts and path.name == "data":
            raise OSError("interrupted halfway through release")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(Path, "unlink", interrupt)
        with pytest.raises(OSError, match="halfway"):
            svc.release(job["id"])
    assert not src.exists() and svc.job(job["id"])["release_parts"] == {"main": "pruning"}
    retired = src.parents[1] / ".threemind-retired" / job["id"] / "main"
    (retired / "unexpected").write_text("independent")
    with pytest.raises(StorageConflict, match="changed"):
        svc.release(job["id"])
    assert (retired / "unexpected").read_text() == "independent"
    (retired / "unexpected").unlink()
    assert svc.release(job["id"])["status"] == "released"
    assert (svc.pool.path("old") / "nested/data").read_bytes() == b"first"


def test_offline_cancel_and_backup_only_configuration(service, tmp_path):
    svc, _, _ = service
    job = svc.create("sync", "old", "cold")
    (tmp_path / "cold").rename(tmp_path / "offline")
    assert svc.cancel(job["id"])["status"] == "cancelled"
    other = ExperimentStorage(ResearchStorage(tmp_path / "control2", repository_root=tmp_path))
    ordinary = other.storage.workspace_path("ordinary")
    other.configure([{"id": "library", "role": "archive", "path": str(tmp_path / "library")}], 0)
    assert other.storage.workspace_path("ordinary", expected_bytes=4096) == ordinary


def test_sync_does_not_overwrite_independent_changes(service):
    svc, src, tmp = service
    first = transfer(svc, "sync", "cold")
    local = tmp / "cold" / first["target_base"] / "nested/data"
    local.write_text("destination edit")
    (src / "nested/data").write_text("source edit")
    job = svc.create("sync", "old", "cold")
    with pytest.raises(StorageConflict, match="independent"):
        svc.run(job["id"])
    svc.cancel(job["id"])
    assert local.read_text() == "destination edit"


@pytest.mark.skipif(not os.getenv("THREEMIND_TRANSFER_TEST_DISK"), reason="requires an explicit second test volume")
def test_two_physical_volumes_preserve_native_times(service):
    from pathlib import Path
    from tempfile import TemporaryDirectory

    svc, src, tmp = service
    other = Path(os.environ["THREEMIND_TRANSFER_TEST_DISK"]).resolve(strict=True)
    assert volumes.volume(other)[0] != volumes.volume(src)[0]
    with TemporaryDirectory(dir=other, prefix=".threemind-transfer-test-") as scratch:
        cfg = svc.pool.status()
        svc.pool.configure(
            [*cfg["directories"], {"id": "removable", "role": "archive", "path": str(Path(scratch) / "cold")}],
            cfg["revision"],
        )
        (src / "frames.bin").write_bytes(os.urandom(2 * 1024**2 + 51))
        forecast = svc.preview("archive", "old", "removable")
        assert forecast["source_bytes_on_other_volumes"] == forecast["source_allocated_bytes"] > 0
        devices = {d["id"]: d.get("physical_disks") for d in svc.pool.status()["directories"]}
        if os.name == "nt":
            assert devices["e"] and devices["removable"] and set(devices["e"]).isdisjoint(devices["removable"])
        original = files.inventory({"main": src})
        synced = transfer(svc, "sync", "removable")
        archived = transfer(svc, "archive", "removable")
        assert synced["target_base"] == archived["target_base"] and archived["copied_bytes"] == 0
        assert files.inventory({"main": svc.pool.path("old")}) == original
        svc.release(archived["id"])
        assert not src.exists()
        restored = transfer(svc, "unarchive", "e")
        svc.release(restored["id"])
        assert svc.pool.path("old") == tmp / "e/experiments/old"
        assert files.inventory({"main": svc.pool.path("old")}) == original
