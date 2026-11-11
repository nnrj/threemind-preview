"""Isolated filesystem/S3 byte paths, fixed publication and whole-subject resume."""

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from test_api import client_for
from test_blob_store import claim_export, filesystem
from test_experiment_bundles import completed
from test_media_v2 import png, protocol
from test_notebooks import edit
from test_report_shares import prepared

from threemind_lab import auth, experiment_bundles, notebooks, report_shares
from threemind_lab.ai_secrets import SecretBox
from threemind_lab.api import create_app
from threemind_lab.blob_store import BlobStore, object_chunks
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.worker import Worker


@pytest.fixture(params=["filesystem", "s3"])
def external_store(request, tmp_path, database):
    database.test_storage_keys = ()
    if request.param == "filesystem":
        blobs, _ = filesystem(tmp_path)
        client = None
        server = None
    else:
        boto3 = pytest.importorskip("boto3")
        server_type = pytest.importorskip("moto.server").ThreadedMotoServer
        server = server_type(ip_address="127.0.0.1", port=0, verbose=False)
        server.start()
        host, port = server.get_host_and_port()
        endpoint = f"http://{host}:{port}"
        client = boto3.client(
            "s3", endpoint_url=endpoint, region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
        )
        client.create_bucket(Bucket="isolated-byte-paths")
        client.put_bucket_versioning(Bucket="isolated-byte-paths", VersioningConfiguration={"Status": "Enabled"})
        database.test_storage_keys = (Fernet.generate_key().decode(),)
        secrets = SecretBox(database.test_storage_keys)
        storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
        target = storage.register_target(
            kind="s3",
            name="isolated local S3",
            configuration={
                "endpoint": endpoint,
                "bucket": "isolated-byte-paths",
                "encrypted_secret": secrets.seal({"access_key_id": "test", "secret_access_key": "test"}),
            },
        )
        blobs = BlobStore(storage, secret_box=secrets)
        for category in ("media-original", "note-image", "export"):
            blobs.set_policy(category, target["id"], expected_revision=blobs.policies()["revision"])
    database.blobs = blobs

    def remove(row):
        locator = row["locator"]
        if client:
            client.delete_object(Bucket="isolated-byte-paths", Key=locator["key"], VersionId=row["version_id"])
        else:
            blobs.storage.safe_path(
                locator["target_id"], locator["key"], config_revision=locator["config_revision"]
            ).unlink()

    try:
        yield remove
    finally:
        if server:
            server.stop()


def storage_client(database):
    return TestClient(
        create_app(Settings(database_url=database.test_url, secret_keys=database.test_storage_keys), database)
    )


def assert_external_io_releases_transactions(database, monkeypatch):
    depth = ContextVar("byte_path_transaction_depth", default=0)
    original_tx, original_read, original_prepare = database.tx, database.blobs.read, database.blobs.prepare

    @contextmanager
    def tracked_tx(*args, **kwargs):
        token = depth.set(depth.get() + 1)
        try:
            with original_tx(*args, **kwargs) as db:
                yield db
        finally:
            depth.reset(token)

    def checked_read(row):
        assert depth.get() == 0, "external object read holds a PG transaction"
        for chunk in original_read(row):
            assert depth.get() == 0
            yield chunk

    def checked_prepare(*args, **kwargs):
        assert depth.get() == 0, "external object upload holds a PG transaction"
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(database, "tx", tracked_tx)
    monkeypatch.setattr(database.blobs, "read", checked_read)
    monkeypatch.setattr(database.blobs, "prepare", checked_prepare)


def job_row(database, project, response, worker):
    assert response.status_code == 202, response.text
    assert worker.once()
    with database.tx(project) as db:
        return db.execute("SELECT * FROM jobs WHERE id=%s", (response.json()["id"],)).fetchone()


def test_external_originals_notes_exports_and_complete_resume(database, external_store, monkeypatch):
    worker = Worker(database)
    # The worker captures its loaded implementation once. Other agents can edit
    # unrelated source files during this isolated integration test; keep the API
    # check on the same declared snapshot, without changing production identity.
    from threemind_lab import bundle_api

    monkeypatch.setattr(bundle_api, "capture_implementation", lambda backend: worker.implementation)
    with storage_client(database) as client:
        project = client.post("/api/v2/projects", json={"name": "isolated original subject"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        run = client.post(base + "/runs", json={"name": "subject", "spec": protocol()}).json()
        url = base + f"/runs/{run['id']}"
        assert client.post(url + "/commands", json={"kind": "pause"}).status_code == 200
        assert worker.once()
        boundary = database.get_run(project, run["id"])
        media = png()
        sha = hashlib.sha256(media).hexdigest()
        accepted = client.post(
            url + "/media",
            params={"kind": "image", "filename": "original.png", "request_id": str(uuid4())},
            content=media,
        )
        assert accepted.status_code == 202, accepted.text
        image_id, note_id = uuid4(), uuid4()
        notebooks.save_asset(database, project, LOCAL_USER, image_id, "private.png", media)
        notebooks.save_note(database, project, LOCAL_USER, note_id, edit(f"![original]({base}/note-assets/{image_id})"))
        artifact_job = claim_export(database, project)
        original_export = database.put_artifact(artifact_job, "original.json", "application/json", b'{"original":true}')
        database.finish(artifact_job, result={})
        assert_external_io_releases_transactions(database, monkeypatch)
        assert notebooks.asset(database, project, LOCAL_USER, image_id)["content"] == media
        saved = completed(
            database,
            worker,
            project,
            client.post(
                url + "/bundles",
                json={
                    "expected_revision": boundary["revision"],
                    "note_ids": [str(note_id)],
                    "artifact_ids": [str(original_export["id"])],
                },
            ),
        )
        with database.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(LOCAL_USER),))
            bundle = experiment_bundles.get_bundle(db, saved["bundle_id"])
            original_blob = db.execute(
                "SELECT b.* FROM stored_blobs b JOIN media_assets a ON a.blob_id=b.id WHERE a.sha256=%s", (sha,)
            ).fetchone()
        with experiment_bundles.open_bundle(database, project, bundle) as archive:
            archive.verify()
            assert archive.read(f"media/{sha}/body") == media
            assert archive.read(f"note-assets/{image_id}/body") == media
            assert archive.read(f"artifacts/{original_export['id']}/body") == b'{"original":true}'
            for name in (
                f"media/{sha}/metadata.json",
                f"note-assets/{image_id}/metadata.json",
                f"artifacts/{original_export['id']}/metadata.json",
            ):
                assert "blob_id" not in archive.json(name)
        download = client.get(base + f"/bundles/{saved['bundle_id']}/download").content
        assert hashlib.sha256(download).hexdigest() == bundle["sha256"]
        # Capture the uninterrupted baseline's actual subsequent sensory result.
        assert client.post(url + "/commands", json={"kind": "resume"}).status_code == 200
        assert worker.once()
        _, expected = database.load_checkpoint(project, run["id"])
        external_store(original_blob)
        # A same-project copy cannot silently accept its missing existing original.
        failed = job_row(
            database,
            project,
            client.post(
                base + f"/bundles/{saved['bundle_id']}/resumes",
                json={"name": "missing original", "request_id": str(uuid4())},
            ),
            worker,
        )
        assert failed["status"] == "failed"
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM runs").fetchone()["n"] == 1
        # The portable package itself is sufficient in a fresh project: originals
        # are restored from its verified bytes, never old host locators.
        destination = client.post("/api/v2/projects", json={"name": "isolated restored project"}).json()["id"]
        target = f"/api/v2/projects/{destination}"
        upload = client.post(
            target + "/bundle-uploads",
            json={
                "request_id": str(uuid4()),
                "name": "original package",
                "bytes": len(download),
                "sha256": bundle["sha256"],
            },
        ).json()
        assert client.put(target + f"/bundle-uploads/{upload['id']}/chunks/0", content=download).status_code == 200
        imported = completed(
            database, worker, destination, client.post(target + f"/bundle-uploads/{upload['id']}/complete")
        )
        restored = completed(
            database,
            worker,
            destination,
            client.post(
                target + f"/bundles/{imported['bundle_id']}/resumes",
                json={"name": "restored subject", "request_id": str(uuid4())},
            ),
        )
        assert b"".join(object_chunks(database, destination, "media", sha)) == media
        with database.tx(destination) as db:
            assert db.execute("SELECT blob_id FROM media_assets WHERE sha256=%s", (sha,)).fetchone()["blob_id"] is None
        assert client.post(target + f"/runs/{restored['run_id']}/commands", json={"kind": "resume"}).status_code == 200
        assert worker.once()
        _, actual = database.load_checkpoint(destination, restored["run_id"])
        assert actual.digest == expected.digest


def test_external_public_body_bundle_scope_integrity_and_missing_bytes(database, external_store, monkeypatch):
    project, document, _, _, export, body = prepared(database)
    assert_external_io_releases_transactions(database, monkeypatch)
    share = report_shares.create(database, project, LOCAL_USER, document, body | {"include_bundle": True})
    publication = report_shares.resolve(database, share["id"])
    for kind, result_key in (("body", "sha256"), ("bundle", "bundle_sha256")):
        stream = report_shares.file_stream(database, publication, kind)
        first = next(stream)
        pool = database.pool.get_stats()
        assert pool["pool_available"] == pool["pool_size"]
        raw = first + b"".join(stream)
        assert hashlib.sha256(raw).hexdigest() == export["result"][result_key]
    unrelated = database.create_project({"id": LOCAL_USER}, "unrelated bytes")["id"]
    with pytest.raises(ValueError, match="unavailable"):
        b"".join(object_chunks(database, unrelated, "artifact", publication["body_artifact_id"]))
    with database.tx(project) as db:
        blob = db.execute(
            "SELECT b.* FROM stored_blobs b JOIN artifacts a ON a.blob_id=b.id WHERE a.id=%s",
            (publication["bundle_artifact_id"],),
        ).fetchone()
    external_store(blob)
    with pytest.raises((OSError, ValueError)):
        b"".join(report_shares.file_stream(database, publication, "bundle"))
    with pytest.raises(Conflict, match="integrity"):
        report_shares.create(
            database, project, LOCAL_USER, document, body | {"operation_id": str(uuid4()), "include_bundle": True}
        )
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM research_document_shares").fetchone()["n"] == 1


def test_external_preload_freezes_identity_and_cleans_temporary_files(database, external_store, tmp_path, monkeypatch):
    project = database.create_project({"id": LOCAL_USER}, "preload race")["id"]
    job = claim_export(database, project)
    artifact = database.put_artifact(job, "small.bin", "application/octet-stream", b"original")
    database.finish(job, result={})
    monkeypatch.setenv("THREEMIND_SCRATCH_DIR", str(tmp_path))
    params = {"actor_id": str(LOCAL_USER), "artifact_ids": [str(artifact["id"])]}
    with database.tx(project) as db:
        params["source_targets"] = experiment_bundles.export_source_targets(db, uuid4(), params)
    assert_external_io_releases_transactions(database, monkeypatch)
    with experiment_bundles.preload_external(database, project, uuid4(), params, lambda: None) as selected:
        stream = selected["artifact", str(artifact["id"])]["stream"]
        with pytest.raises(Conflict, match="变化"):
            b"".join(experiment_bundles.preloaded_chunks(selected, "artifact", artifact | {"blob_id": uuid4()}))
        assert b"".join(experiment_bundles.preloaded_chunks(selected, "artifact", artifact)) == b"original"
    assert stream.closed
    with (
        pytest.raises(ValueError, match="源存储目标"),
        experiment_bundles.preload_external(database, project, uuid4(), params | {"source_targets": []}, lambda: None),
    ):
        raise AssertionError("undeclared source must fail before reading its bytes")


def test_bundle_jobs_freeze_input_targets_separately_from_output(database, external_store, tmp_path, monkeypatch):
    from threemind_lab import bundle_api

    worker = Worker(database)
    monkeypatch.setattr(bundle_api, "capture_implementation", lambda backend: worker.implementation)
    with storage_client(database) as client:
        project = client.post("/api/v2/projects", json={"name": "isolated target matching"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        run = client.post(base + "/runs", json={"name": "subject", "spec": protocol()}).json()
        url = base + f"/runs/{run['id']}"
        assert client.post(url + "/commands", json={"kind": "pause"}).status_code == 200
        assert worker.once()
        boundary = database.get_run(project, run["id"])
        artifact_job = claim_export(database, project)
        original = database.put_artifact(artifact_job, "source.json", "application/json", b'{"source":true}')
        database.finish(artifact_job, result={})
        source = database.blobs.freeze("export")
        output_path = tmp_path / "different-output"
        output_path.mkdir()
        output = database.blobs.storage.register_target(output_path, "different destination")
        database.blobs.set_policy("export", output["id"], expected_revision=database.blobs.policies()["revision"])
        queued = client.post(
            url + "/bundles", json={"expected_revision": boundary["revision"], "artifact_ids": [str(original["id"])]}
        )
        assert queued.status_code == 202, queued.text
        targets = queued.json()["params"]["source_targets"]
        assert targets == [{key: source[key] for key in experiment_bundles.TARGET_FIELDS}]
        source_key = f"storage.target:{source['target_id']}:{source['config_revision']}@{source['host_id']}"
        output_key = f"storage.target:{output['id']}:{output['config_revision']}@{output['host_id']}"
        with database.tx(project) as db:
            required = db.execute("SELECT required_features FROM jobs WHERE id=%s", (queued.json()["id"],)).fetchone()[
                "required_features"
            ]
        assert source_key in required and output_key in required
        database.announce_worker(
            "no-original-target",
            {"queue": "runtime", "features": {key: {"state": "available"} for key in required if key != source_key}},
        )
        assert database.claim("no-original-target") is None
        saved = completed(database, worker, project, queued)
        resumed = client.post(
            base + f"/bundles/{saved['bundle_id']}/resumes", json={"name": "copy", "request_id": str(uuid4())}
        )
        assert resumed.status_code == 202, resumed.text
        assert resumed.json()["params"]["source_targets"] == [
            {key: output[key] for key in experiment_bundles.TARGET_FIELDS}
        ]
        with database.tx(project) as db:
            required = db.execute("SELECT required_features FROM jobs WHERE id=%s", (resumed.json()["id"],)).fetchone()[
                "required_features"
            ]
        assert output_key in required
        database.announce_worker(
            "no-package-target",
            {"queue": "runtime", "features": {key: {"state": "available"} for key in required if key != output_key}},
        )
        assert database.claim("no-package-target") is None
        completed(database, worker, project, resumed)


def test_legacy_private_bundle_keeps_author_boundary_on_export_import_and_resume(database, monkeypatch):
    from threemind_lab import bundle_api

    password = "isolated private bundle password"
    author = auth.create_user(database, "bundle-author", password)
    peer = auth.create_user(database, "bundle-peer", password, admin=True)
    project = database.create_project(author, "private bundle authors")["id"]
    with database.tx(project) as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (project, peer["id"]))
    worker = Worker(database)
    monkeypatch.setattr(bundle_api, "capture_implementation", lambda backend: worker.implementation)
    base = f"/api/v2/projects/{project}"
    with client_for(database, "server") as client:

        def login(username):
            client.cookies.clear()
            result = client.post("/api/v2/login", json={"username": username, "password": password})
            assert result.status_code == 200, result.text
            client.headers["X-CSRF-Token"] = result.json()["csrf"]

        login("bundle-author")
        run = client.post(base + "/runs", json={"name": "private subject", "spec": protocol()}).json()
        url = base + f"/runs/{run['id']}"
        assert client.post(url + "/commands", json={"kind": "pause"}).status_code == 200
        assert worker.once()
        boundary = database.get_run(project, run["id"])
        note_id = uuid4()
        notebooks.save_note(database, project, author["id"], note_id, edit("private original observations"))
        saved = completed(
            database,
            worker,
            project,
            client.post(url + "/bundles", json={"expected_revision": boundary["revision"], "note_ids": [str(note_id)]}),
        )
        endpoint = base + f"/bundles/{saved['bundle_id']}"
        detail = client.get(endpoint)
        assert detail.status_code == 200 and detail.json()["private"] is True
        raw = client.get(endpoint + "/download").content
        assert hashlib.sha256(raw).hexdigest() == saved["sha256"]
        wrapped = completed(
            database,
            worker,
            project,
            client.post(
                url + "/bundles",
                json={"expected_revision": boundary["revision"], "artifact_ids": [saved["artifact_id"]]},
            ),
        )
        assert client.get(base + f"/bundles/{wrapped['bundle_id']}").json()["private"] is True
        raw = client.get(base + f"/bundles/{wrapped['bundle_id']}/download").content
        upload = client.post(
            base + "/bundle-uploads",
            json={
                "request_id": str(uuid4()),
                "name": "private imported evidence",
                "bytes": len(raw),
                "sha256": wrapped["sha256"],
            },
        ).json()
        assert client.put(base + f"/bundle-uploads/{upload['id']}/chunks/0", content=raw).status_code == 200
        imported = completed(database, worker, project, client.post(base + f"/bundle-uploads/{upload['id']}/complete"))
        assert client.get(base + f"/bundles/{imported['bundle_id']}").json()["private"] is True
        status = client.get(base + f"/bundle-uploads/{upload['id']}")
        assert status.status_code == 200 and status.json()["chunks"][0]["bytes"] == len(raw)
        assert client.put(base + f"/bundle-uploads/{upload['id']}/chunks/0", content=raw).json()["replayed"]
        assert (
            client.post(base + f"/bundle-uploads/{upload['id']}/complete").json()["result"]["bundle_id"]
            == imported["bundle_id"]
        )
        login("bundle-peer")
        assert client.get(base + f"/bundle-uploads/{upload['id']}").status_code == 403
        assert client.put(base + f"/bundle-uploads/{upload['id']}/chunks/0", content=raw).status_code == 403
        assert client.post(base + f"/bundle-uploads/{upload['id']}/complete").status_code == 403
        assert client.get(base + "/bundles").json()["rows"] == []
        for bundle_id in (saved["bundle_id"], imported["bundle_id"], wrapped["bundle_id"]):
            endpoint = base + f"/bundles/{bundle_id}"
            for suffix in ("", "/download", "/entry?name=run.json"):
                assert client.get(endpoint + suffix).status_code == 404
            assert (
                client.post(endpoint + "/resumes", json={"name": "denied", "request_id": str(uuid4())}).status_code
                == 404
            )
        assert client.get(base + f"/artifacts/{saved['artifact_id']}").status_code == 404
        assert client.get(base + f"/artifacts/{wrapped['artifact_id']}").status_code == 404
        login("bundle-author")
        completed(
            database,
            worker,
            project,
            client.post(
                base + f"/bundles/{imported['bundle_id']}/resumes",
                json={"name": "private retained copy", "request_id": str(uuid4())},
            ),
        )


def test_binary_reader_budget_closes_stream(monkeypatch):
    from threemind_lab import binary_reads

    closed = []

    def chunks(*args):
        try:
            yield b"abc"
            yield b"def"
        finally:
            closed.append(True)

    monkeypatch.setattr(binary_reads, "object_chunks", chunks)
    with pytest.raises(ValueError, match="budget"):
        binary_reads.object_bytes(None, None, "artifact", None, maximum=4)
    assert closed == [True]


def test_edit_imported_ai_head_inherits_only_trusted_current_revision(database, tmp_path):
    import json
    from types import SimpleNamespace

    from test_ai_providers import get_call
    from test_data_bundles import export_selection, leased
    from test_research_ai import ask, fixture, reply

    from threemind_lab import research_documents

    database.blobs = BlobStore(ResearchStorage(tmp_path / "control", repository_root=tmp_path))
    settings, project, _, _, _, _, provider, scope, spec = fixture(database)
    call, _, _ = ask(database, settings, project, provider, scope)
    assert reply(database, settings, json.dumps(spec)).once()
    generated = get_call(database, project, call)
    assert generated["status"] == "completed", generated.get("error")
    original = generated["result"]["document_id"]
    target = database.create_project({"id": LOCAL_USER}, "isolated edited AI import")["id"]
    service, _, stream = export_selection(database, project, LOCAL_USER, {"kind": "document", "ids": [original]})
    imported = service.import_register(target, LOCAL_USER, stream, uuid4())
    job = leased(database, target, service.restore_records(target, LOCAL_USER, imported["id"], uuid4()))
    result = service._restore_job(SimpleNamespace(db=database), job)
    database.finish(job, result=result)
    restored = next(item["new_id"] for item in result["mappings"] if item["kind"] == "document")
    restored_record = research_documents.get(database, target, restored)
    assert restored_record["import_ai_generated"] is True
    edited = research_documents.save(
        database,
        target,
        LOCAL_USER,
        restored,
        {
            "operation_id": str(uuid4()),
            "expected_revision": 1,
            "spec": restored_record["spec"] | {"title": "Human edit of imported AI draft"},
        },
    )
    current = research_documents.get(database, target, restored)
    assert current["revision"] == edited["revision"] == 2
    assert current["import_ai_generated"] is True and current["ai_call_id"] is None
    assert research_documents.get(database, target, restored, 1)["import_ai_generated"] is True
    manual = uuid4()
    manual_spec = {
        "kind": "record",
        "title": "Independent manual record",
        "blocks": [{"id": "body", "type": "commentary", "markdown": "A new manual observation"}],
    }
    research_documents.save(
        database,
        target,
        LOCAL_USER,
        manual,
        {"operation_id": str(uuid4()), "expected_revision": 0, "spec": manual_spec},
    )
    assert research_documents.get(database, target, manual)["import_ai_generated"] is False
    with pytest.raises(ValueError):
        research_documents.save(
            database,
            target,
            LOCAL_USER,
            manual,
            {"operation_id": str(uuid4()), "expected_revision": 1, "spec": spec, "import_ai_generated": True},
        )


def test_package_original_descriptor_cannot_disagree_with_scientific_record():
    import io

    from threemind_lab.experiment_archive import ArchiveWriter

    package = ArchiveWriter(io.BytesIO(), {})
    try:
        row = {"id": str(uuid4()), "bytes": 8, "sha256": hashlib.sha256(b"original").hexdigest()}
        with pytest.raises(ValueError, match="实际字节"):
            experiment_bundles.add_original(package, "artifact/body", [b"modified"], row, "artifact")
    finally:
        package.close()


def test_scientific_weights_stay_in_database_with_external_policy(database, external_store, monkeypatch):
    from threemind_lab import language_tools, transformer_tools

    project = database.create_project({"id": LOCAL_USER}, "isolated scientific bytes")["id"]
    queued = database.enqueue(project, "transformer")
    with database.tx(project) as db:
        required = db.execute("SELECT required_features FROM jobs WHERE id=%s", (queued["id"],)).fetchone()[
            "required_features"
        ]
    database.announce_worker(
        "isolated-byte-reader",
        {"queue": "runtime", "backend": "reference", "features": {key: {"state": "available"} for key in required}},
    )
    job = database.claim("isolated-byte-reader")
    assert job is not None
    originals = {}
    for kind in ("language-head", "language-scratch", "tiny-transformer"):
        raw = (kind + ": exact scientific original").encode()
        row = database.put_artifact(job, kind + ".json", "application/json", raw, {"kind": kind})
        assert row["blob_id"] is None
        originals[kind] = row, raw
    database.finish(job, result={})
    assert_external_io_releases_transactions(database, monkeypatch)
    for kind in ("language-head", "language-scratch"):
        row, raw = originals[kind]
        assert language_tools.artifact(database, project, row["id"], kind) == raw
    row, raw = originals["tiny-transformer"]
    assert transformer_tools.artifact_bytes(database, project, row["id"]) == raw
