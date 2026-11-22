import hashlib
import io
import os
import zipfile

import pytest

from threemind_lab import storage_volumes as volumes
from threemind_lab.experiment_storage import ExperimentStorage
from threemind_lab.experiment_volumes import create_archive, export_member, extract_member, verify_archive
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import StorageConflict

MIB = 2**20


@pytest.fixture
def pool(tmp_path, monkeypatch):
    monkeypatch.delenv("THREEMIND_DATA_ROOT", raising=False)
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
    return ExperimentStorage(storage)


def setup_roots(pool, *, cap=4 * MIB):
    dirs = [
        {"id": k, "path": str(pool.storage.repository_root / k), "priority": i, "limit_bytes": cap}
        for i, k in enumerate(("primary", "portable"))
    ]
    pool.configure(dirs, 0)
    return dirs


def part(name, size, kind="data"):
    return {"name": name, "bytes": size, "kind": kind}


def test_single_directory_unchanged_then_priority_capacity_and_retry(pool):
    pre = pool.storage.workspace_path("legacy")
    assert not pool.file.exists() and not pre.exists()
    pre.mkdir(parents=True)
    dirs = setup_roots(pool)
    assert pool.storage.workspace_path("legacy") == pre
    with pytest.raises(StorageConflict, match="existing|already"):
        pool.reserve("legacy", [part("main", MIB)])
    a = pool.reserve("first", [part("main", 3 * MIB)])
    assert a["parts"][0]["directory"] == "primary"
    assert pool.reserve("first", [part("main", 3 * MIB)]) == a
    assert pool.storage.workspace_path("second", expected_bytes=2 * MIB).is_relative_to(
        pool.storage.repository_root / "portable"
    )
    with pytest.raises(StorageConflict, match="different placement"):
        pool.reserve("first", [part("main", 1)])
    with pytest.raises(StorageConflict, match="refresh"):
        pool.configure(dirs, 0)
    with pytest.raises(StorageConflict, match="disable"):
        pool.configure(dirs[1:], 1)
    assert pool.cancel("second")["status"] == "unreserved"


def test_experiment_can_pin_one_run_directory_without_changing_other_priorities(pool):
    setup_roots(pool)
    request = [part("worlds", 3 * MIB)]
    assert pool.preview("ordinary", request)["parts"][0]["directory"] == "primary"
    chosen = pool.reserve("pinned", request, directory_id="portable")
    assert chosen["parts"][0]["directory"] == "portable"
    assert pool.reserve("pinned", request, directory_id="portable") == chosen
    assert not pool.preview("pinned-too-large", request, directory_id="portable")["fits"]
    assert pool.preview("ordinary", request)["parts"][0]["directory"] == "primary"
    with pytest.raises(StorageConflict, match="registered"):
        pool.reserve("unknown", request, directory_id="missing")


def test_default_no_split_and_offline_never_falls_through(pool):
    setup_roots(pool)
    parts = [part("world-a", 3 * MIB), part("world-b", 2 * MIB)]
    failure = pool.preview("study", parts)
    assert not failure["fits"] and failure["split_would_fit"]
    assert not pool.status()["studies"]
    study = pool.reserve("study", parts, True)
    assert [p["directory"] for p in study["parts"]] == ["primary", "portable"]
    with pytest.raises(StorageConflict, match="spans"):
        pool.storage.workspace_path("study")
    root = pool.storage.repository_root / "portable"
    root.rename(root.with_name("unplugged"))
    root.mkdir()
    with pytest.raises(StorageConflict, match="offline"):
        pool.storage.workspace_path("study", part="world-b")
    root.rmdir()
    root.with_name("unplugged").rename(root)
    for p in parts:
        pool.path("study", p["name"]).mkdir(parents=True)
    pool.finish("study")
    assert all(d["reserved_bytes"] == 0 for d in pool.status()["directories"])
    assert pool.path("study", "world-b").is_dir()


def test_two_directories_on_one_volume_do_not_double_count_and_keep_max_floor(pool, monkeypatch):
    dirs = setup_roots(pool, cap=50 * MIB)
    monkeypatch.setattr(volumes, "free_bytes", lambda _: 7 * MIB)
    dirs[1]["reserve_bytes"] = 2 * MIB
    pool.configure(dirs, 1)
    assert not pool.preview("x", [part("a", 3 * MIB), part("b", 3 * MIB)], True)["fits"]
    pool.reserve("x", [part("a", 3 * MIB)])
    assert not pool.preview("y", [part("b", 3 * MIB)])["fits"]


def test_existing_files_count_toward_limit(pool):
    setup_roots(pool, cap=MIB)
    (pool.storage.repository_root / "primary" / "old.bin").write_bytes(os.urandom(MIB))
    assert pool.preview("x", [part("d", MIB)])["parts"][0]["directory"] == "portable"


def test_archive_crosses_capacity_roundtrips_as_standard_zip_and_detects_corruption(pool):
    setup_roots(pool, cap=3 * MIB)
    parts = [part("world", 2 * MIB), part("archive-1", MIB, "archive"), part("archive-2", MIB, "archive")]
    pool.reserve("aquatic", parts, True)
    data = pool.path("aquatic", "world")
    data.mkdir(parents=True)
    payload = os.urandom(MIB + 19000)
    (data / "trajectory.bin").write_bytes(payload)
    result = create_archive(pool, "aquatic")
    assert len(result["volumes"]) == 2
    files = [pool.path("aquatic", r["part"]) / "evidence.zip.part" for r in result["volumes"]]
    combined = io.BytesIO(b"".join(p.read_bytes() for p in files))
    with zipfile.ZipFile(combined) as z:
        assert z.read("world/trajectory.bin") == payload
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == r["sha256"] for p, r in zip(files, result["volumes"], strict=True)
    )
    assert create_archive(pool, "aquatic") == result
    pool.finish("aquatic")
    files[-1].write_bytes(b"invalid")
    with pytest.raises(StorageConflict, match="verification"):
        verify_archive(pool, "aquatic")


def test_restore_one_file_across_volumes_without_a_joined_zip(pool):
    setup_roots(pool, cap=10 * MIB)
    parts = [
        part("world", 2 * MIB),
        part("out-a", MIB, "archive"),
        part("out-b", MIB, "archive"),
        part("unused", MIB, "archive"),
        part("recovered", 2 * MIB, "readback"),
    ]
    pool.reserve("pond", parts, True)
    payload = os.urandom(MIB + 17000)
    original = pool.write_file("pond", "world", "sub/trace.bin", io.BytesIO(payload), len(payload))
    sha = hashlib.sha256(payload).hexdigest()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == sha
    assert len(create_archive(pool, "pond")["volumes"]) == 2
    result = extract_member(pool, "pond", "recovered", "world/sub/trace.bin")
    assert result["sha256"] == sha
    assert result == extract_member(pool, "pond", "recovered", "world/sub/trace.bin")
    assert pool.finish("pond")["status"] == "complete"
    target = pool.storage.repository_root / "recovered.bin"
    assert export_member(pool, "pond", "world/sub/trace.bin", target)["sha256"] == sha
    assert target.read_bytes() == payload
    assert not pool.path("pond", "unused").exists()


def test_incomplete_file_is_never_published_and_oversize_is_refused(pool):
    setup_roots(pool)
    pool.reserve("raw", [part("world", MIB)])
    for data, size, checksum in [(b"short", 10, None), (b"extra", 2, None), (b"ab", 2, "f" * 64)]:
        with pytest.raises(ValueError):
            pool.write_file("raw", "world", "a.bin", io.BytesIO(data), size, sha256=checksum)
        assert list(pool.path("raw", "world").iterdir()) == []
    with pytest.raises(StorageConflict, match="exceeds"):
        pool.write_file("raw", "world", "a.bin", io.BytesIO(), MIB + 1)


def test_study_host_uses_pinned_secondary_volume_and_existing_history(pool, monkeypatch):
    from lab.tools.service_study import StudyConfig

    monkeypatch.setenv("THREEMIND_STORAGE_CONTROL", str(pool.storage.control_dir))
    monkeypatch.setenv("THREEMIND_DATA_ROOT", str(pool.storage.repository_root / "primary"))
    setup_roots(pool)
    pool.reserve("claimed", [part("main", 3 * MIB)])
    settings = {
        "title": "test",
        "sources": pool.storage.repository_root,
        "usage_start": 0,
        "storage_soft": MIB,
        "storage_hard": 2 * MIB,
    }
    a = StudyConfig.for_experiment(name="new-study", **settings)
    assert a.work == pool.path("new-study", "main")
    assert a.work.is_relative_to(pool.storage.repository_root / "portable")
    assert a._pool_binding[1] == ("new-study", "main")
    old = pool.storage.repository_root / "primary" / "experiments" / "legacy"
    old.mkdir(parents=True)
    assert StudyConfig.for_experiment(name="legacy", **settings).work == old
    assert all(s["name"] != "legacy" for s in pool.status()["studies"])


def test_evidence_locator_rejects_replacement_and_other_disk_stays_usable(pool):
    setup_roots(pool)
    storage = pool.storage
    primary, portable = (pool.storage.repository_root / key for key in ("primary", "portable"))
    ident = volumes.directory_identity(portable)
    a = storage.register_target(portable, "Removable", configuration={"volume_identity": ident})
    loc = storage.locator(a["id"], "experiments/old")
    storage.register_resource("old-study", loc)
    portable.rename(portable.with_name("unplugged"))
    portable.mkdir()
    with pytest.raises(volumes.VolumeOffline):
        storage.resolve_resource("old-study")
    b = storage.register_target(primary, "Fixed")
    storage.register_resource("new-study", storage.locator(b["id"], "experiments/new"))
    portable.rmdir()
    portable.with_name("unplugged").rename(portable)
    assert storage.resolve_resource("old-study") == portable / "experiments" / "old"


def test_interrupted_archive_reuses_published_segment_on_retry(pool, monkeypatch):
    from threemind_lab.experiment_volumes import VolumeWriter, manifest_path
    from threemind_lab.storage_files import StorageBusy, file_lock

    setup_roots(pool, cap=3 * MIB)
    parts = [part("world", 2 * MIB), part("first", MIB, "archive"), part("second", MIB, "archive")]
    with file_lock(pool.lock), pytest.raises(StorageBusy):
        pool.reserve("retry", parts, True)
    assert not pool.status()["studies"]
    pool.reserve("retry", parts, True)
    data = os.urandom(MIB + 2001)
    pool.write_file("retry", "world", "events", io.BytesIO(data), len(data))
    start = VolumeWriter.start

    def unplug(writer):
        if writer.rows:
            raise StorageConflict("test disk offline")
        start(writer)

    with monkeypatch.context() as patch:
        patch.setattr(VolumeWriter, "start", unplug)
        with pytest.raises(StorageConflict, match="offline"):
            create_archive(pool, "retry")
    first = pool.path("retry", "first") / "evidence.zip.part"
    before = first.stat()
    assert not manifest_path(pool, "retry").exists()
    assert len(create_archive(pool, "retry")["volumes"]) == 2
    assert (first.stat().st_ino, first.stat().st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
