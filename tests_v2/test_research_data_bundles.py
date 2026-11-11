import io
from contextlib import ExitStack
from uuid import uuid4

import pytest

from threemind_lab.data_archive import DataReader
from threemind_lab.research_data_bundles import export, receipt
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import StorageBusy, StorageConflict, read_json


def source(tmp_path, *, writer_mode="sealed"):
    directory = tmp_path / "experiments/study"
    directory.mkdir(parents=True)
    (directory / "empty").mkdir()
    (directory / "protocol.md").write_bytes(b"Original experiment criteria\r\n")
    raw = bytes(range(256)) * 400
    (directory / "original.bin").write_bytes(raw)
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
    target = storage.register_target(tmp_path / "experiments", "isolated archived originals")
    storage.register_resource("study", storage.locator(target["id"], "study"), writer_mode=writer_mode)
    return storage, directory, raw


def test_directory_roundtrip_multivolume_and_registered_request_replay(tmp_path):
    storage, directory, raw = source(tmp_path)
    destination, operation = tmp_path / "package", uuid4()
    result = export(storage, "study", destination, operation_id=operation, volume_bytes=16384, expected_revision=1)
    assert len(result["volumes"]) > 1 and result["private"]
    assert receipt(destination, operation_id=operation) == result
    assert export(storage, "study", destination, operation_id=operation)["replayed"]
    with ExitStack() as stack:
        master = stack.enter_context((destination / result["filename"]).open("rb"))
        volumes = [stack.enter_context((destination / v["filename"]).open("rb")) for v in result["volumes"]]
        with DataReader({"manifest": master, "volumes": volumes}) as reader:
            assert b"".join(reader.chunks("research/files/original.bin")) == raw
            assert reader.manifest["recovery"]["source_project"] is None
            assert reader.manifest["recovery"]["source_scope"] == "host-research-resource"
            assert not reader.preflight()["can_restore"] and not reader.preflight()["can_resume"]
            assert reader.json("research/resource.json")["entries"][1]["kind"] == "directory"
    assert (directory / "original.bin").read_bytes() == raw
    volume = destination / result["volumes"][0]["filename"]
    volume.write_bytes(b"damaged")
    with pytest.raises((ValueError, StorageConflict)):
        receipt(destination, operation_id=operation)


def test_directory_requires_declared_writer_preview_revision_and_disjoint_roots(tmp_path):
    storage, directory, raw = source(tmp_path, writer_mode="unknown")
    with pytest.raises(StorageBusy):
        export(storage, "study", tmp_path / "package", operation_id=uuid4())
    row = storage.resource("study")
    storage.register_resource("study", row["locator"], writer_mode="sealed", expected_revision=1)
    with pytest.raises(StorageConflict, match="revision"):
        export(storage, "study", tmp_path / "package", operation_id=uuid4(), expected_revision=1)
    with pytest.raises(ValueError, match="disjoint"):
        export(storage, "study", directory / "package", operation_id=uuid4())
    assert (directory / "original.bin").read_bytes() == raw


def test_directory_interrupted_export_never_publishes_complete_receipt(tmp_path):
    storage, directory, raw = source(tmp_path)
    destination = tmp_path / "package"
    operation = uuid4()
    count = 0

    def cancelled():
        nonlocal count
        count += 1
        if count > 1:
            raise InterruptedError("isolated cancellation")

    with pytest.raises(InterruptedError):
        export(storage, "study", destination, operation_id=operation, check=cancelled)
    assert read_json(destination / "receipt.json")["state"] == "incomplete"
    with pytest.raises(StorageConflict, match="incomplete"):
        export(storage, "study", destination, operation_id=operation)
    assert (directory / "original.bin").read_bytes() == raw


def test_host_directory_package_imports_as_private_readonly_origin(database, tmp_path):
    from threemind_lab.data_bundles import DataBundles
    from threemind_lab.database import LOCAL_USER

    storage, _, raw = source(tmp_path)
    destination = tmp_path / "package"
    result = export(storage, "study", destination, operation_id=uuid4())
    project = database.create_project({"id": LOCAL_USER}, "isolated directory import")["id"]
    service = DataBundles(database)
    package = io.BytesIO((destination / result["volumes"][0]["filename"]).read_bytes())
    imported = service.import_register(project, LOCAL_USER, package, uuid4())
    assert imported["private"]
    with service._open(project, LOCAL_USER, imported["id"]) as reader:
        assert b"".join(reader.chunks("research/files/original.bin")) == raw
        assert not reader.preflight()["can_restore"] and not reader.preflight()["can_resume"]
    details = service.detail(project, LOCAL_USER, imported["id"])
    assert details["mode"] == "read_only_original"
    with database.tx(project) as db:
        for table in ("runs", "studies", "jobs"):
            assert db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"] == 0
