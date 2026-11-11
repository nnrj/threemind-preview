import hashlib

import pytest

import threemind_lab.research_storage as storage_module
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import StorageBusy, StorageConflict, atomic_json, checked_path, relative_key


def storage_at(tmp_path):
    return ResearchStorage(tmp_path / "control", repository_root=tmp_path)


def test_construction_and_reads_do_not_create_control_files(tmp_path):
    storage = storage_at(tmp_path)
    assert storage.host_info()["initialized"] is False
    assert storage.targets() == storage.resources() == []
    assert not (tmp_path / "control").exists()
    first = storage.initialize()
    assert first["host_id"]
    assert storage_at(tmp_path).initialize() == first


def test_small_registry_cache_is_private_and_detects_external_replacement(tmp_path, monkeypatch):
    storage = storage_at(tmp_path)
    storage.initialize()
    storage._registry_cache = None
    reads = []
    original_read = storage_module.read_json

    def counted_read(path):
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(storage_module, "read_json", counted_read)
    first = storage._load()
    first["host_id"] = "caller-mutation"
    assert storage.host_info()["host_id"] != "caller-mutation"
    assert len(reads) == 1

    with pytest.raises(RuntimeError, match="cancel edit"), storage._edit() as state:
        state["host_id"] = "unfinished-edit"
        raise RuntimeError("cancel edit")
    assert storage.host_info()["host_id"] != "unfinished-edit"
    assert len(reads) == 1

    # Another tool can atomically replace the registry between two lookups.
    storage_at(tmp_path).register_target(tmp_path / "files", target_id="research")
    assert storage.target("research")["configuration"]["path"] == str(tmp_path / "files")
    assert len(reads) == 3  # The other instance reads once; this instance reloads once.

    replacement = original_read(storage.registry_path)
    replacement["schema"] = "unsupported-registry"
    atomic_json(storage.registry_path, replacement)
    with pytest.raises(ValueError, match="unsupported"):
        storage.host_info()


def test_large_registry_is_not_cached(tmp_path):
    storage = storage_at(tmp_path)
    storage.initialize()
    state = storage._load()
    state["extra_metadata"] = "x" * (1024**2)
    atomic_json(storage.registry_path, state)
    assert storage._load()["extra_metadata"] == state["extra_metadata"]
    assert storage._registry_cache is None


def test_target_versions_pin_locations_and_compare_registration_revision(tmp_path):
    storage = storage_at(tmp_path)
    first = storage.register_target(tmp_path / "a", target_id="research")
    locator = storage.locator("research", "e66/checkpoint.bin")
    second = storage.register_target(tmp_path / "b", target_id="research", expected_revision=1)
    assert second["host_id"] == first["host_id"]
    assert second["config_revision"] == 2
    assert storage.resolve_locator(locator) == tmp_path / "a/e66/checkpoint.bin"
    assert storage.safe_path("research", "e66/checkpoint.bin") == tmp_path / "b/e66/checkpoint.bin"
    with pytest.raises(StorageConflict):
        storage.register_target(tmp_path / "c", target_id="research", expected_revision=1)
    with pytest.raises(ValueError):
        storage.target("research", 0)
    assert not (tmp_path / "a").exists()


def test_cloud_metadata_does_not_probe_or_become_a_directory(tmp_path):
    storage = storage_at(tmp_path)
    row = storage.register_target(
        kind="s3", target_id="cloud", configuration={"endpoint": "https://invalid.invalid", "bucket": "b",
                                                     "encrypted_secret": "ciphertext"},
    )
    assert row["kind"] == "s3"
    assert storage_at(tmp_path).target("cloud")["configuration"]["encrypted_secret"] == "ciphertext"
    with pytest.raises(ValueError, match="filesystem"):
        storage.locator("cloud", "e66")
    with pytest.raises(ValueError, match="plaintext"):
        storage.register_target(kind="s3", configuration={"password": "do-not-store"})


@pytest.mark.parametrize("key", ["../outside", "a/../outside", "/absolute", "a\\b", "a//b", "NUL.txt",
                                 "drive:name", "a/trailing.", "a/trailing ", "a/*"])
def test_portable_keys_reject_path_aliases(key):
    with pytest.raises(ValueError):
        relative_key(key)


def test_roots_cannot_contain_host_control_or_private_metadata(tmp_path):
    storage = storage_at(tmp_path)
    for root in (tmp_path, tmp_path / "control/child", tmp_path / ".Git/objects"):
        with pytest.raises(ValueError):
            storage.register_target(root)
    assert not (tmp_path / "control").exists()


def test_symbolic_link_components_are_rejected(tmp_path):
    original = tmp_path / "real"
    original.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(original, target_is_directory=True)
    except OSError:
        pytest.skip("host does not grant symlink creation")
    with pytest.raises(ValueError, match="links"):
        checked_path(link / "file.bin")
    with pytest.raises(ValueError, match="links"):
        storage_at(tmp_path).register_target(link)


def test_registered_original_work_path_and_writer_exclusion(tmp_path):
    storage = storage_at(tmp_path)
    storage.register_target(tmp_path / "files", target_id="research")
    row = storage.register_resource(
        "e66", storage.locator("research", "e66"), registered_work_path=".work/e66",
        writer_mode="cooperative",
    )
    assert row["registered_work_path"] == ".work/e66"
    assert storage.resolve_legacy(".work/e66/peripheral.bin") == tmp_path / "files/e66/peripheral.bin"
    with storage.writer("e66") as directory:
        assert directory == tmp_path / "files/e66"
        with pytest.raises(StorageBusy), storage_at(tmp_path).writer("e66"):
            pass
    assert storage.resource("e66")["write_epoch"] == 1
    storage.register_resource(
        "e66", storage.locator("research", "e66"), registered_work_path="rewritten", expected_revision=1,
    )
    assert storage.resource("e66")["registered_work_path"] == ".work/e66"
    assert storage.resolve_legacy(".work/e66/peripheral.bin") == tmp_path / "files/e66/peripheral.bin"
    with pytest.raises(StorageBusy), storage.writer("e66"):
        pass


def test_overlapping_resources_cannot_have_independent_writer_locks(tmp_path):
    storage = storage_at(tmp_path)
    storage.register_target(tmp_path / "files", target_id="research")
    storage.register_resource("whole", storage.locator("research", "e66"), writer_mode="cooperative")
    with pytest.raises(StorageConflict, match="overlap"):
        storage.register_resource("part", storage.locator("research", "e66/peripheral.bin"),
                                  writer_mode="cooperative")


def test_exact_artifact_manifest_mapping_does_not_expose_its_parent(tmp_path):
    storage = storage_at(tmp_path)
    archive = tmp_path / "data/experiments/e66/checkpoint.bin"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"original bytes")
    atomic_json(tmp_path / "lab/artifact-index/test-relocations.json", {
        "schema": "threemind.research-artifact-relocations/1",
        "entries": [{"legacy_path": "lab/e66/checkpoint.bin", "archive_path": "data/experiments/e66/checkpoint.bin",
                     "state": "verified", "bytes": 14, "sha256": hashlib.sha256(b"original bytes").hexdigest()}],
    })
    assert storage.resolve_legacy("lab/e66/checkpoint.bin") == archive
    assert storage.resolve_legacy(tmp_path / "lab/e66/checkpoint.bin") == archive
    for path in ("lab/e66", "lab/e66/undeclared.bin", "lab/e66/checkpoint.bin/child"):
        with pytest.raises(ValueError, match="not registered"):
            storage.resolve_legacy(path)
    assert not storage.control_dir.exists()
    archive.write_bytes(b"different data")
    with pytest.raises(StorageConflict, match="hash"):
        storage.resolve_legacy("lab/e66/checkpoint.bin")
    assert storage.resolve_legacy("lab/e66/checkpoint.bin", verify=False) == archive


def test_manifest_rejects_paths_outside_explicit_archive(tmp_path):
    storage = storage_at(tmp_path)
    atomic_json(tmp_path / "lab/artifact-index/test-relocations.json", {
        "schema": "threemind.research-artifact-relocations/1",
        "entries": [{"legacy_path": "lab/e66/checkpoint.bin", "archive_path": "private.bin", "state": "verified"}],
    })
    with pytest.raises(ValueError, match="escapes"):
        storage.resolve_legacy("lab/e66/checkpoint.bin")
