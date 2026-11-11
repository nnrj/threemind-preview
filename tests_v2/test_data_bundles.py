import hashlib
import io
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

from threemind_lab.blob_store import BlobStore, object_chunks
from threemind_lab.data_archive import RECOVERY_SCHEMA, SCHEMA, DataReader
from threemind_lab.data_bundles import DataBundles
from threemind_lab.data_catalog import DataCatalog
from threemind_lab.database import LOCAL_USER, Conflict, Forbidden, NotFound
from threemind_lab.experiment_archive import ArchiveWriter
from threemind_lab.notebooks import note, save_asset, save_note
from threemind_lab.research_documents import get, save
from threemind_lab.research_storage import ResearchStorage


def note_body(text):
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


@pytest.fixture
def records(database, tmp_path):
    database.blobs = BlobStore(ResearchStorage(tmp_path / "control", repository_root=tmp_path))
    actor = LOCAL_USER
    project = database.create_project({"id": actor}, "Original project")["id"]
    target = database.create_project({"id": actor}, "Target project")["id"]
    doc_id, note_id, asset_id = uuid4(), uuid4(), uuid4()
    image = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(image, format="PNG")
    save_asset(database, project, actor, asset_id, "image.png", image.getvalue())
    for revision in range(2):
        save(database, project, actor, doc_id, {
            "operation_id": str(uuid4()), "expected_revision": revision, "review": "draft",
            "spec": {"kind": "report", "title": "Original report", "sources": [],
                     "blocks": [{"id": "body", "type": "commentary", "markdown": f"version {revision + 1}"}]},
        })
        body = note_body(f"version {revision + 1}")
        if revision == 0:
            body["content"].append({"type": "image", "attrs": {"src": f"/api/v2/projects/{project}/note-assets/{asset_id}"}})
        save_note(database, project, actor, note_id, {
            "operation_id": str(uuid4()), "expected_revision": revision,
            "title": "Original note", "kind": "note", "body": {"content": body, "format": "document"},
        })
    return database, project, target, actor, doc_id, note_id, asset_id


def leased(database, project, job):
    with database.tx(project) as db:
        return db.execute("UPDATE jobs SET status='leased',worker_id='data-test',generation=generation+1,"
                          "lease_until=clock_timestamp()+interval '5 minutes' WHERE id=%s RETURNING *", (job["id"],)).fetchone()


def export_records(records):
    database, project, _, actor, doc_id, note_id, _ = records
    plan = DataCatalog(database).export_plan(project, actor, {"resources": [
        {"kind": "document", "id": str(doc_id)}, {"kind": "note", "id": str(note_id)},
    ]})
    service = DataBundles(database)
    job = leased(database, project, service.export(project, actor, plan["id"], uuid4()))
    result = service._export_job(SimpleNamespace(db=database), job)
    return service, result["bundle_id"], plan


def test_catalog_queries_and_frozen_history_and_dependencies(records):
    database, project, _, actor, doc_id, note_id, asset_id = records
    catalog = DataCatalog(database)
    assert catalog.list(project, actor, {"q": "Original", "kind": "report"})["rows"][0]["id"] == str(doc_id)
    op_id = uuid4()
    plan = catalog.export_plan(project, actor, {"kind": "note", "ids": [str(note_id)]}, op_id=op_id)
    assert any(o["object_id"] == "note_asset:" + str(asset_id) for o in plan["objects"])
    assert plan["complete_history"] and plan["private"]
    assert catalog.export_plan(project, actor, {"kind": "note", "ids": [str(note_id)]}, op_id=op_id)["id"] == plan["id"]
    with pytest.raises(Conflict):
        catalog.export_plan(project, actor, {"kind": "report", "ids": [str(doc_id)]}, op_id=op_id)


def test_formal_record_roundtrip_preserves_all_versions_and_remaps_old_image_link(records):
    database, project, target, actor, doc_id, note_id, asset_id = records
    service, bundle_id, _ = export_records(records)
    raw = b"".join(service.chunks(project, actor, bundle_id))
    preflight = service.preflight(target, actor, io.BytesIO(raw))
    assert not preflight["missing_required"]
    op_id = uuid4()
    imported = service.import_register(target, actor, io.BytesIO(raw), op_id)
    assert service.import_register(target, actor, io.BytesIO(raw), op_id)["id"] == imported["id"]
    assert imported["id"] != bundle_id
    restore = leased(database, target, service.restore_records(target, actor, imported["id"], uuid4()))
    result = service._restore_job(SimpleNamespace(db=database), restore)
    mappings = {row["old_id"]: row for row in result["mappings"]}
    new_doc, new_note, new_asset = (mappings[str(identity)]["new_id"] for identity in (doc_id, note_id, asset_id))
    assert new_doc != str(doc_id) and new_note != str(note_id)
    assert get(database, target, new_doc, 1)["spec"]["blocks"][0]["markdown"] == "version 1"
    assert get(database, target, new_doc, 2)["spec"]["blocks"][0]["markdown"] == "version 2"
    restored = note(database, target, actor, new_note, 1)
    assert str(target) in str(restored["body"]) and new_asset in str(restored["body"])
    original = service.object(target, actor, imported["id"], "note:" + str(note_id))
    assert str(project) in str(original["original"]["versions"][0]["body"])
    assert original["mapping"]["original_hash"] != original["mapping"]["projection_hash"]
    assert service._restore_job(SimpleNamespace(db=database), restore)["replayed"]


def test_private_note_export_and_bundle_download_never_gain_owner_bypass(records):
    database, project, _, actor, _, _, _ = records
    outsider = uuid4()
    with database.tx(project) as db:
        db.execute("INSERT INTO users(id,username,admin) VALUES(%s,%s,true)", (outsider, "outsider-" + outsider.hex))
        db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (project, outsider))
    assert DataCatalog(database).list(project, outsider, {"kind": "note"})["rows"] == []
    service, bundle_id, _ = export_records(records)
    with pytest.raises(NotFound):
        service.detail(project, outsider, bundle_id)
    with pytest.raises(NotFound):
        b"".join(service.chunks(project, outsider, bundle_id))
    with pytest.raises(Forbidden):
        DataCatalog(database).list(uuid4(), actor)


def make_unknown(*, outer=SCHEMA, dependency=None):
    raw = b"unknown future object"
    file = {"name": "future.bin", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "parts": [{"volume": 0, "name": "future/part-0"}]}
    objects = [{"object_id": "future:1", "kind": "future", "schema": "future/999", "source_id": "1",
                "source_project": str(uuid4()), "payload": "future.bin", "dependencies": dependency or []}]
    recovery = {"schema": RECOVERY_SCHEMA, "objects": objects, "files": [file], "source_project": str(uuid4()),
                "private": False, "limitations": []}
    stream = io.BytesIO()
    writer = ArchiveWriter(stream, {"bundle_id": str(uuid4()), "volume": 0, "volume_count": 1, "recovery": recovery}, schema=outer)
    writer.add("future/part-0", [raw])
    writer.finish()
    return stream


def test_unknown_outer_is_rejected_and_unknown_object_bytes_remain_read_only():
    with pytest.raises(ValueError, match="schema"):
        DataReader(make_unknown(outer="future.outer/1"))
    with DataReader(make_unknown()) as reader:
        preview = reader.preflight()
        assert preview["readonly_unknown"] == ["future:1"]
        assert not preview["can_restore"] and not preview["can_resume"]
        assert b"".join(reader.chunks("future.bin")) == b"unknown future object"


def test_missing_required_or_optional_dependencies_are_distinct():
    with DataReader(make_unknown(dependency=[{"object_id": "missing:required", "required": True},
                                            {"object_id": "missing:optional", "required": False}])) as reader:
        preview = reader.preflight()
        assert preview["missing_required"] == ["missing:required"]
        assert preview["missing_optional"] == ["missing:optional"]
        assert not preview["can_restore"]


def export_selection(database, project, actor, selection, *, volume_bytes=7 * 1024**3):
    service = DataBundles(database, volume_bytes=volume_bytes)
    plan = DataCatalog(database).export_plan(project, actor, selection)
    job = leased(database, project, service.export(project, actor, plan["id"], uuid4()))
    result = service._export_job(SimpleNamespace(db=database), job)
    database.finish(job, result=result)
    detail = service.detail(project, actor, result["bundle_id"])
    streams = [io.BytesIO(b"".join(service.chunks(project, actor, detail["id"], v["ordinal"]))) for v in detail["volumes"]]
    return service, detail, {"manifest": detail["manifest"], "volumes": streams}


def artifact_fixture(database, project, raw, metadata=None):
    job = leased(database, project, database.enqueue(project, "export", {"fixture": True}))
    artifact = database.put_artifact(job, "fixture.bin", "application/octet-stream", raw, metadata or {"kind": "fixture"})
    database.finish(job, result={"artifact_id": str(artifact["id"])})
    return artifact


def test_fixed_native_sources_and_artifacts_remain_readable_in_new_project(records):
    from test_research_documents import capture, setup

    from threemind_lab import report_sources, research_documents

    database, _, target, actor, *_ = records
    project, run, _, _ = setup(database)
    source, _ = capture(database, project, run)
    artifact = artifact_fixture(database, project, b"original attachment")
    record, report = uuid4(), uuid4()
    original_markdown = f"Original run {run['id']}; [attachment](/api/v2/projects/{project}/artifacts/{artifact['id']})"
    spec = research_documents.defaults(database, project, source["id"])
    save(database, project, actor, record, {"operation_id": str(uuid4()), "expected_revision": 0, "spec": spec})
    for revision in range(2):
        save(database, project, actor, report, {"operation_id": str(uuid4()), "expected_revision": revision,
            "spec": {"kind": "report", "title": "Fixed source report", "sources": [str(source["id"])], "blocks": [
                {"id": "proof", "type": "fact", "source": str(source["id"]), "metric": "activation", "statistic": "maximum"},
                {"id": "fixed", "type": "record_block", "record_id": str(record), "revision": 1, "block_id": spec["blocks"][0]["id"]},
                {"id": "origin", "type": "commentary", "markdown": original_markdown},
            ]}})
    service, _detail, stream = export_selection(database, project, actor, {"kind": "report", "ids": [str(report)]})
    assert service.preflight(target, actor, stream)["can_restore"]
    imported = service.import_register(target, actor, stream, uuid4())
    job = leased(database, target, service.restore_records(target, actor, imported["id"], uuid4()))
    restored = service._restore_job(SimpleNamespace(db=database), job)
    database.finish(job, result=restored)
    maps = {m["object_id"]: m for m in restored["mappings"]}
    source_id = maps["source:" + str(source["id"])]["new_id"]
    artifact_id = maps["artifact:" + str(artifact["id"])]["new_id"]
    assert b"".join(object_chunks(database, target, "artifact", artifact_id)) == b"original attachment"
    restored_source = report_sources.get_source(database, target, source_id)
    assert restored_source["row_count"] == source["row_count"]
    original_rows = report_sources.data_rows(database, project, source["id"])["rows"]
    restored_rows = report_sources.data_rows(database, target, source_id)["rows"]
    assert original_rows == restored_rows
    with database.tx(target) as db:
        request = db.execute("SELECT * FROM report_source_requests WHERE id=%s", (source_id,)).fetchone()
        assert request["run_id"] is None and request["checkpoint_id"] is None and request["analysis_artifact_id"] is None
        assert request["job_id"] == job["id"] and str(request["origin_bundle_id"]) == str(imported["id"])
        assert request["provenance"]["original_capture"]["run_name"] == run["name"]
    new_report = maps["document:" + str(report)]["new_id"]
    for revision in (1, 2):
        rendered = research_documents.render(database, target, new_report, revision=revision)
        assert rendered["blocks"][0]["value"] == 77
        document = get(database, target, new_report, revision)
        assert str(target) in document["spec"]["blocks"][-1]["markdown"]
        assert artifact_id in document["spec"]["blocks"][-1]["markdown"]
        assert str(run["id"]) in document["spec"]["blocks"][-1]["markdown"]
    original = service.object(target, actor, imported["id"], "document:" + str(report))
    assert original["original"]["versions"][0]["spec"]["blocks"][-1]["markdown"] == original_markdown
    assert source["content_hash"] != maps["source:" + str(source["id"])]["projection_hash"]


def test_multivolume_requires_entire_verified_set_and_preserves_bytes(records):
    database, project, target, actor, *_ = records
    raw = os.urandom(150000)
    artifact = artifact_fixture(database, project, raw)
    service, detail, stream = export_selection(database, project, actor, {"resources": [{"kind": "artifact", "id": str(artifact["id"])}]}, volume_bytes=32768)
    assert len(detail["volumes"]) > 1
    assert service.preflight(target, actor, stream)["can_restore"]
    with pytest.raises(ValueError):
        service.preflight(target, actor, {"manifest": detail["manifest"], "volumes": stream["volumes"][:-1]})
    with pytest.raises(ValueError):
        service.preflight(target, actor, {"manifest": detail["manifest"], "volumes": list(reversed(stream["volumes"]))})
    bad = dict(detail["manifest"], volumes=[dict(v) for v in detail["volumes"]])
    bad["volumes"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="size/hash"):
        service.preflight(target, actor, {"manifest": bad, "volumes": stream["volumes"]})
    imported = service.import_register(target, actor, stream, uuid4())
    job = leased(database, target, service.restore_records(target, actor, imported["id"], uuid4()))
    result = service._restore_job(SimpleNamespace(db=database), job)
    assert b"".join(object_chunks(database, target, "artifact", result["mappings"][0]["new_id"])) == raw


def test_cancel_stale_lease_and_revoked_actor_publish_no_partial_package(records):
    database, project, _, actor, doc_id, *_ = records
    catalog, service = DataCatalog(database), DataBundles(database)
    plan = catalog.export_plan(project, actor, {"kind": "report", "ids": [str(doc_id)]})
    for mode in ("cancel", "stale", "revoked"):
        job = leased(database, project, service.export(project, actor, plan["id"], uuid4()))
        if mode == "cancel":
            service.cancel(project, actor, job["id"])
        elif mode == "stale":
            with database.tx(project) as db:
                db.execute("UPDATE jobs SET generation=generation+1 WHERE id=%s", (job["id"],))
        else:
            with database.tx(project) as db:
                db.execute("DELETE FROM members WHERE project_id=%s AND user_id=%s", (project, actor))
        from threemind_lab.experiment_bundles import TransferCancelled
        with pytest.raises((TransferCancelled, Conflict, Forbidden)):
            service._export_job(SimpleNamespace(db=database), job)
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM data_bundles WHERE job_id=%s", (job["id"],)).fetchone()["n"] == 0
    assert get(database, project, doc_id, 1)["spec"]["title"] == "Original report"


def test_remap_uses_typed_identity_and_keeps_bare_original_text():
    from threemind_lab.data_bundles import _remap
    identity, project, target = (str(uuid4()) for _ in range(3))
    mappings = {project: target, "source:" + identity: "source-new", "document:" + identity: "document-new", "artifact:" + identity: "artifact-new"}
    original = {"title": identity, "sources": [identity], "text": identity, "record_id": identity,
                "markdown": f"Original {identity}, /api/v2/projects/{project}/artifacts/{identity}"}
    remapped = _remap(original, mappings)
    assert remapped["title"] == identity and remapped["text"] == identity
    assert remapped["sources"] == ["source-new"] and remapped["record_id"] == "document-new"
    assert remapped["markdown"] == f"Original {identity}, /api/v2/projects/{target}/artifacts/artifact-new"


def test_language_whole_state_paused_restore_preserves_frozen_mapping_and_future_response(records):
    from threemind_lab.provenance import capture_implementation
    from threemind_transformer.language_bundle import pack
    from threemind_transformer.language_protocol import LanguageProtocol
    from threemind_transformer.language_session import LanguageSession

    database, project, target, actor, *_ = records
    protocol = LanguageProtocol(response_us=10000, sample_us=1000)
    original = LanguageSession(protocol.model_dump(), backend="native")
    original.turn("fixture signal")
    context, image = original.context(), original.engine.capture_state()
    raw = pack(image, context)
    artifact = artifact_fixture(database, project, raw, {"kind": "language-bundle", "fixture": True})
    service, _, stream = export_selection(database, project, actor, {"resources": [{"kind": "artifact", "id": str(artifact["id"])}]})
    imported = service.import_register(target, actor, stream, uuid4())
    object_id = "artifact:" + str(artifact["id"])
    plan = service.resume_plan(target, actor, imported["id"], object_id, backend="native")
    assert plan["can_resume"] and not plan["starts_running"]
    with pytest.raises(Conflict, match="acknowledge"):
        service.resume(target, actor, imported["id"], object_id, uuid4())
    job = leased(database, target, service.resume(target, actor, imported["id"], object_id, uuid4(), acknowledge_external_changes=True))
    worker = SimpleNamespace(db=database, backend="native", implementation=capture_implementation("native"))
    result = service._resume_job(worker, job)
    assert result["status"] == "paused" and database.get_run(target, result["run_id"])["status"] == "paused"
    checkpoint, restored_image = database.load_checkpoint(target, result["run_id"])
    assert image.digest == restored_image.digest and checkpoint["context"]["language"] == context
    clone = LanguageSession(protocol.model_dump(), image=restored_image, context=checkpoint["context"]["language"], backend="native")
    left, right = original.turn("next fixture signal"), clone.turn("next fixture signal")
    assert left["after_hash"] == right["after_hash"] and left["process"] == right["process"]
    assert service._resume_job(worker, job)["replayed"]


def test_invalid_specialized_language_state_stays_read_only(records):
    database, project, target, actor, *_ = records
    artifact = artifact_fixture(database, project, b"invalid language bytes", {"kind": "language-bundle"})
    service, _, stream = export_selection(database, project, actor, {"resources": [{"kind": "artifact", "id": str(artifact["id"])}]})
    preflight = service.preflight(target, actor, stream)
    assert preflight["can_restore"] and not preflight["can_resume"]
    imported = service.import_register(target, actor, stream, uuid4())
    plan = service.resume_plan(target, actor, imported["id"], "artifact:" + str(artifact["id"]))
    assert not plan["can_resume"] and plan["blockers"]
    assert service.object(target, actor, imported["id"], "artifact:" + str(artifact["id"]))["mode"] == "read_only_original"


def test_native_experiment_formal_wrapper_restores_complete_paused_boundary(records):
    from test_api import client_for
    from test_research_operations import advance, fixture

    from threemind_lab.experiment_bundles import export_bundle
    from threemind_lab.worker import Worker

    database, _, target, actor, *_ = records
    with client_for(database) as client:
        project, run_id, _, _ = fixture(database, client)
    worker = Worker(database, backend="native")
    advance(database, project, run_id, 1, duration_us=2000)
    assert worker.once()
    original_checkpoint, original_image = database.load_checkpoint(project, run_id)
    job = leased(database, project, database.enqueue(project, "experiment_bundle_export", {
        "actor_id": str(actor), "expected_revision": original_checkpoint["revision"], "checkpoint_id": str(original_checkpoint["id"]), "name": "Whole fixture",
    }, run_id=run_id))
    origin = export_bundle(worker, job)
    database.finish(job, result=origin)
    service, _, stream = export_selection(database, project, actor, {"resources": [{"kind": "experiment_bundle", "id": origin["bundle_id"]}]})
    imported = service.import_register(target, actor, stream, uuid4())
    key = "experiment_bundle:" + origin["bundle_id"]
    plan = service.resume_plan(target, actor, imported["id"], key, backend="native")
    assert plan["can_resume"], plan
    assert plan["starts_running"] is False
    restore = leased(database, target, service.resume(target, actor, imported["id"], key, uuid4(), acknowledge_external_changes=True))
    result = service._resume_job(worker, restore)
    assert database.get_run(target, result["run_id"])["status"] == "paused"
    restored_checkpoint, restored_image = database.load_checkpoint(target, result["run_id"])
    assert original_image.digest == restored_image.digest
    from threemind_lab.experiment_bundles import remap_context
    assert remap_context(original_checkpoint["context"]["readouts"], {str(run_id): str(result["run_id"])}) == restored_checkpoint["context"]["readouts"]
    assert original_checkpoint["context"]["next_observation_us"] == restored_checkpoint["context"]["next_observation_us"]
    assert database.get_run(project, run_id)["revision"] == original_checkpoint["revision"]
    assert service._resume_job(worker, restore)["replayed"]
    # A self-consistent archive index cannot waive the actual checkpoint gate.
    class MissingBoundary:
        def __init__(self):
            self.manifest = {"metadata": {"implementation": original_checkpoint["context"]["implementation"]}}
        def json(self, name, **kwargs):
            if name == "run.json":
                return {"spec": database.get_run(project, run_id)["spec"]}
            return {"context": {"initialized": False}}
    with pytest.raises(ValueError, match="checkpoint implementation"):
        service._experiment_boundary(MissingBoundary(), "native", {"blockers": [], "external_changes": []})


@pytest.mark.parametrize("backend", ["filesystem", "s3"])
@pytest.mark.parametrize("fault", ["missing", "corrupt"])
def test_existing_media_original_must_verify_before_mapping_and_source_target_is_required(records, tmp_path, backend, fault):
    database, project, target, actor, *_ = records
    raw = b"registered original media"
    sha = hashlib.sha256(raw).hexdigest()
    storage = database.blobs.storage
    if backend == "filesystem":
        directory = tmp_path / "existing-media"
        directory.mkdir()
        storage_target = storage.register_target(directory)
        reader = None
    else:
        botocore = pytest.importorskip("botocore.exceptions")
        class Reader:
            state = "good"
            def get_object(self, **kwargs):
                if self.state == "missing":
                    raise botocore.ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
                return {"Body": io.BytesIO(raw if self.state == "good" else b"corrupt")}
        reader = Reader()
        storage_target = storage.register_target(kind="s3", configuration={"bucket": "isolated-fixture", "encrypted_secret": "fixture"})
        database.blobs.s3_factory = lambda config: reader
    locator = {"kind": backend, "target_id": storage_target["id"], "config_revision": storage_target["config_revision"],
               "host_id": storage_target["host_id"], "key": "objects/existing-fixture"}
    if backend == "filesystem":
        path = storage.safe_path(storage_target["id"], locator["key"])
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
    for owner_project in (project, target):
        candidate = {"id": str(uuid4()), "project_id": str(owner_project), "bytes": len(raw), "sha256": sha, "locator": locator}
        with database.tx(owner_project) as db:
            blob_id = database.blobs.attach(db, candidate)
            db.execute("INSERT INTO media_assets(project_id,sha256,byte_length,blob_id) VALUES(%s,%s,%s,%s)", (owner_project, sha, len(raw), blob_id))
    catalog, service = DataCatalog(database), DataBundles(database)
    plan = catalog.export_plan(project, actor, {"resources": [{"kind": "media", "id": sha}]})
    export = service.export(project, actor, plan["id"], uuid4())
    key = f"storage.target:{storage_target['id']}:{storage_target['config_revision']}@{storage_target['host_id']}"
    assert key in export["required_features"] and export["params"]["source_targets"] == [{k: locator[k] for k in ("kind", "target_id", "config_revision", "host_id")}]
    job = leased(database, project, export)
    result = service._export_job(SimpleNamespace(db=database), job)
    database.finish(job, result=result)
    stream = io.BytesIO(b"".join(service.chunks(project, actor, result["bundle_id"])))
    imported = service.import_register(target, actor, stream, uuid4())
    restore = service.restore_records(target, actor, imported["id"], uuid4())
    assert key in restore["required_features"]
    database.announce_worker("missing-source", {"queue": "runtime", "backend": "native", "features": {
        feature: {"state": "available"} for feature in restore["required_features"] if feature != key}})
    assert database.claim("missing-source") is None
    restore = leased(database, target, restore)
    if backend == "filesystem":
        if fault == "missing":
            path.unlink()
        else:
            path.write_bytes(b"corrupt")
    else:
        reader.state = fault
    with pytest.raises((OSError, ValueError), match="unavailable|corrupt|registered"):
        service._restore_job(SimpleNamespace(db=database), restore)
    with database.tx(target) as db:
        assert db.execute("SELECT count(*) AS n FROM data_import_mappings WHERE bundle_id=%s", (imported["id"],)).fetchone()["n"] == 0
        assert db.execute("SELECT blob_id FROM media_assets WHERE sha256=%s", (sha,)).fetchone()["blob_id"] is not None


def test_private_nested_legacy_archive_cannot_be_reexported_or_downloaded_by_peer(records):
    from threemind_lab.data_catalog import authorized
    database, project, _, actor, *_ = records
    artifact = artifact_fixture(database, project, b"private original archive")
    bundle_id = uuid4()
    with authorized(database, project, actor, write=True) as db:
        db.execute("INSERT INTO experiment_bundles(id,project_id,actor_id,name,job_id,artifact_id,sha256,bytes,manifest,private) "
            "VALUES(%s,%s,%s,'Private legacy',%s,%s,%s,%s,'{}',true)",
            (bundle_id, project, actor, artifact["job_id"], artifact["id"], artifact["sha256"], artifact["bytes"]))
    catalog = DataCatalog(database)
    plan = catalog.export_plan(project, actor, {"resources": [{"kind": "experiment_bundle", "id": str(bundle_id)}]})
    assert plan["private"] and next(o for o in plan["objects"] if o["kind"] == "experiment_bundle")["private"]
    service, outer, _ = export_selection(database, project, actor, {"resources": [{"kind": "experiment_bundle", "id": str(bundle_id)}]})
    assert outer["private"]
    peer = uuid4()
    with database.tx(project) as db:
        db.execute("INSERT INTO users(id,username,admin) VALUES(%s,%s,true)", (peer, "peer-" + peer.hex))
        db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (project, peer))
    with pytest.raises(NotFound):
        service.detail(project, peer, outer["id"])
    with pytest.raises(ValueError, match="unavailable"):
        b"".join(object_chunks(database, project, "artifact", artifact["id"], actor=peer))
    assert b"".join(object_chunks(database, project, "artifact", artifact["id"], actor=actor)) == b"private original archive"
    with authorized(database, project, peer) as db:
        assert db.execute("SELECT count(*) AS n FROM artifact_chunks WHERE artifact_id=%s", (artifact["id"],)).fetchone()["n"] == 0
    assert catalog.list(project, peer, {"kind": "experiment_bundle"})["rows"] == []


def test_imported_ai_revision_survives_private_package_and_public_peer_sharing(records):
    import json

    from test_ai_providers import get_call
    from test_research_ai import ask, fixture, reply

    from threemind_lab import report_exports, report_shares
    from threemind_lab.data_catalog import authorized
    from threemind_lab.worker import Worker

    database, _, target, actor, *_ = records
    settings, project, _, _, _, _, provider, scope, spec = fixture(database)
    call, _, _ = ask(database, settings, project, provider, scope)
    assert reply(database, settings, json.dumps(spec)).once()  # Isolated mock transport only.
    ai_record = get_call(database, project, call)["result"]["document_id"]
    save(database, project, actor, ai_record, {"operation_id": str(uuid4()), "expected_revision": 1, "spec": spec})
    report, private_note = uuid4(), uuid4()
    save(database, project, actor, report, {"operation_id": str(uuid4()), "expected_revision": 0,
        "spec": {"kind": "report", "title": "Fixed imported AI provenance", "blocks": [{
            "id": "ref", "type": "record_block", "record_id": ai_record, "revision": 1,
            "block_id": spec["blocks"][-1]["id"]}]}})
    save_note(database, project, actor, private_note, {"operation_id": str(uuid4()), "expected_revision": 0,
        "title": "Private package member", "kind": "note", "body": {"format": "document", "content": note_body("private")}})
    service, outer, stream = export_selection(database, project, actor, {"resources": [
        {"kind": "document", "id": str(report)}, {"kind": "note", "id": str(private_note)}]})
    assert outer["private"]
    imported = service.import_register(target, actor, stream, uuid4())
    job = leased(database, target, service.restore_records(target, actor, imported["id"], uuid4()))
    result = service._restore_job(SimpleNamespace(db=database), job)
    database.finish(job, result=result)
    mappings = {m["object_id"]: m for m in result["mappings"]}
    restored_ai = mappings["document:" + ai_record]["new_id"]
    restored_report = mappings["document:" + str(report)]["new_id"]
    with authorized(database, target, actor) as db:
        rows = db.execute("SELECT revision,ai_call_id,import_ai_generated FROM research_document_versions WHERE document_id=%s ORDER BY revision", (restored_ai,)).fetchall()
        assert all(row["ai_call_id"] is None for row in rows)
        assert [row["import_ai_generated"] for row in rows] == [True, False]
        assert db.execute("SELECT provenance FROM data_import_mappings WHERE bundle_id=%s AND new_id=%s", (imported["id"], restored_ai)).fetchone()["provenance"]["ai_generated_revisions"] == ["1"]
    peer = uuid4()
    with database.tx(target) as db:
        db.execute("INSERT INTO users(id,username) VALUES(%s,%s)", (peer, "peer-" + peer.hex))
        db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (target, peer))
    with authorized(database, target, peer) as db:
        assert db.execute("SELECT count(*) AS n FROM data_import_mappings WHERE bundle_id=%s", (imported["id"],)).fetchone()["n"] == 0
    export = report_exports.request(database, target, peer, restored_report,
        {"operation_id": str(uuid4()), "revision": 1, "format": "html"})
    assert Worker(database).once()
    exported = report_exports.listing(database, target, restored_report)["rows"][0]
    assert exported["status"] == "done", exported["error"]
    html = b"".join(object_chunks(database, target, "artifact", exported["result"]["artifact_id"], actor=peer)).decode()
    assert "导入记录" in html or "imported record" in html
    shared = report_shares.create(database, target, peer, restored_report, {"operation_id": str(uuid4()),
        "export_id": str(export["id"]), "expected_body_hash": exported["result"]["sha256"]})
    assert shared["metadata"]["ai_generated"]
    # A second transfer preserves the fixed per-version projection fact.
    _, _, repeated = export_selection(database, target, actor, {"kind": "document", "ids": [restored_ai]})
    with DataReader(repeated) as reader:
        payload = reader.json(reader.objects["document:" + restored_ai]["payload"])
        assert payload["ai_generated_revisions"] == ["1"]


def test_probe_archive_closes_fixed_calibration_results_and_restores_sources(records):
    from test_temporal_reports import source

    from threemind_core import Config
    from threemind_lab import calibration, report_sources
    from threemind_lab.protocols import RunSpec
    from threemind_lab.worker import Worker
    from threemind_runtime.host import create_engine

    database, project, target, actor, *_ = records
    engine = create_engine(Config(propagation_rate=0, activation_decay_enabled=False, inhibition_gain=0))
    spec = RunSpec(environment="manual", text_sensor={"enabled": False}, config=engine.config.to_dict())
    run = database.create_run(project, "Read-only calibration fixture", spec.model_dump())
    database.save_checkpoint(project, run["id"], engine.capture_state(), expected_revision=0,
        status="completed", context={"protocol": spec.model_dump()})
    probe = calibration.request(database, project, run["id"], actor, operation_id=uuid4(),
        protocol={"mode": "temporal", "cues": ["甲。", "乙。"]})
    assert Worker(database).once()
    captured, original_rows = source(database, project, kind="temporal_windows", calibration_id=str(probe["id"]))
    service, _, stream = export_selection(database, project, actor, {"kind": "source", "ids": [str(captured["id"])]})
    with DataReader(stream) as reader:
        descriptor = reader.objects["probe:" + str(probe["id"])]
        payload = reader.json(descriptor["payload"])
        execution = payload["execution"]
        for field, checksum in (("artifact_id", "result_sha256"), ("bundle_artifact_id", "bundle_sha256")):
            artifact = reader.json(reader.objects["artifact:" + execution["result"][field]]["payload"])
            assert reader.files[artifact["bytes_entry"]]["sha256"] == execution["result"][checksum]
    assert service.preflight(target, actor, stream)["can_restore"]
    imported = service.import_register(target, actor, stream, uuid4())
    job = leased(database, target, service.restore_records(target, actor, imported["id"], uuid4()))
    result = service._restore_job(SimpleNamespace(db=database), job)
    database.finish(job, result=result)
    mapping = next(m for m in result["mappings"] if m["kind"] == "source")
    assert report_sources.data_rows(database, target, mapping["new_id"])["rows"] == original_rows
    with database.tx(target) as db:
        request = db.execute("SELECT * FROM report_source_requests WHERE id=%s", (mapping["new_id"],)).fetchone()
        assert request["calibration_id"] is None and request["run_id"] is None
        assert request["provenance"]["original_capture"]["calibration_id"] == str(probe["id"])
        assert db.execute("SELECT count(*) AS n FROM probe_calibrations").fetchone()["n"] == 0
    assert "probe:" + str(probe["id"]) in result["readonly_objects"]
    # A changed metadata assertion is rejected before a misleading complete export.
    with database.tx(project) as db:
        db.execute("UPDATE jobs SET result=jsonb_set(result,'{bundle_sha256}',to_jsonb(%s::text)) WHERE id=%s", ("0" * 64, probe["job_id"]))
    with pytest.raises(ValueError, match="hash"):
        DataCatalog(database).export_plan(project, actor, {"kind": "probe", "ids": [str(probe["id"])]})


def test_private_artifact_cross_actor_restore_rebinds_projection_and_keeps_original_owner(records):
    database, project, target, actor, *_ = records
    original_job = leased(database, project, database.enqueue(project, "export", {"fixture": True, "actor_id": str(actor)}))
    original = database.put_artifact(original_job, "private.bin", "application/octet-stream", b"private fixture bytes",
        {"private": True, "private_actor_id": str(actor)})
    database.finish(original_job, result={"artifact_id": str(original["id"])})
    service, _, stream = export_selection(database, project, actor, {"kind": "artifact", "ids": [str(original["id"])]})
    importing_actor = uuid4()
    with database.tx(target) as db:
        db.execute("INSERT INTO users(id,username) VALUES(%s,%s)", (importing_actor, "importer-" + importing_actor.hex))
        db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (target, importing_actor))
    imported = service.import_register(target, importing_actor, stream, uuid4())
    job = leased(database, target, service.restore_records(target, importing_actor, imported["id"], uuid4()))
    restored = service._restore_job(SimpleNamespace(db=database), job)
    new_id = restored["mappings"][0]["new_id"]
    assert b"".join(object_chunks(database, target, "artifact", new_id, actor=importing_actor)) == b"private fixture bytes"
    with pytest.raises(ValueError, match="unavailable"):
        b"".join(object_chunks(database, target, "artifact", new_id, actor=actor))
    source = service.object(target, importing_actor, imported["id"], "artifact:" + str(original["id"]))
    assert source["original"]["record"]["metadata"]["private_actor_id"] == str(actor)
