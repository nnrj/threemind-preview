import hashlib
import io
import json
import os
import time
from uuid import uuid4

import psycopg
import pytest
from cryptography.fernet import Fernet

from threemind_lab.ai_secrets import SecretBox
from threemind_lab.blob_store import BlobStore, object_chunks
from threemind_lab.database import LOCAL_USER, Conflict, NotFound
from threemind_lab.research_storage import ResearchStorage


def filesystem(tmp_path, *, maximum_bytes=1024**3):
    root = tmp_path / "objects"
    root.mkdir()
    storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
    target = storage.register_target(root, "isolated files")
    blobs = BlobStore(storage, maximum_bytes=maximum_bytes)
    for category in ("media-original", "note-image", "export"):
        blobs.set_policy(category, target["id"], expected_revision=blobs.policies()["revision"])
    return blobs, target


def test_immutable_targets_new_policy_and_corrupt_read(tmp_path):
    blobs, target = filesystem(tmp_path)
    project = uuid4()
    raw = b"first original"
    frozen = blobs.freeze("media-original")
    original = blobs.prepare(project, "media-original", [raw], frozen=frozen)
    new_root = tmp_path / "new-objects"
    new_root.mkdir()
    replacement = blobs.storage.register_target(new_root, "new files", target_id=target["id"], expected_revision=1)
    blobs.set_policy("media-original", replacement["id"], expected_revision=3)
    assert b"".join(blobs.read(original)) == raw
    assert blobs.freeze("media-original")["config_revision"] == 2
    assert blobs.prepare(project, "media-original", [raw], frozen=frozen)["locator"] == original["locator"]
    path = blobs.storage.safe_path(target["id"], original["locator"]["key"], config_revision=1)
    path.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="corrupt|length"):
        b"".join(blobs.read(original))
    assert blobs.freeze("checkpoint")["kind"] == "db"


def test_default_db_has_no_host_side_effects_and_bounded_failure(tmp_path):
    storage = ResearchStorage(tmp_path / "absent-control", repository_root=tmp_path)
    blobs = BlobStore(storage)

    def never_consume():
        raise AssertionError("database policy must leave bytes to the original DB writer")
        yield b""

    assert blobs.prepare(uuid4(), "export", never_consume()) is None
    assert not storage.control_dir.exists()
    (tmp_path / "limited").mkdir()
    limited, _ = filesystem(tmp_path / "limited", maximum_bytes=4)
    with pytest.raises(ValueError, match="budget"):
        limited.prepare(uuid4(), "media-original", [b"oversized"])
    assert not list((limited.storage.control_dir / "blob-staging").glob("*.tmp"))


def claim_export(database, project):
    job = database.enqueue(project, "bundle_export")
    with database.tx(project) as db:
        required = db.execute("SELECT required_features FROM jobs WHERE id=%s", (job["id"],)).fetchone()[
            "required_features"
        ]
    database.announce_worker(
        "storage-test",
        {"queue": "runtime", "backend": "reference", "features": {k: {"state": "available"} for k in required}},
    )
    return database.claim("storage-test")


def test_external_artifact_scope_failure_fence_and_candidates(database, tmp_path):
    database.blobs, _ = filesystem(tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "external artifacts")["id"]
    job = claim_export(database, project)
    raw = b"export original" * 100
    artifact = database.put_artifact(job, "evidence.bin", "application/octet-stream", raw)
    assert artifact["blob_id"]
    assert b"".join(object_chunks(database, project, "artifact", artifact["id"])) == raw
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM artifact_chunks").fetchone()["n"] == 0
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), db.transaction():
            db.execute("UPDATE stored_blobs SET sha256=%s", ("a" * 64,))
    other = database.create_project({"id": LOCAL_USER}, "other")["id"]
    with pytest.raises(ValueError, match="unavailable"):
        b"".join(object_chunks(database, other, "artifact", artifact["id"]))
    with database.tx() as db:
        db.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (job["id"],))
    with pytest.raises(Conflict):
        database.put_artifact(job, "stale.bin", "application/octet-stream", b"stale lease")
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM artifacts").fetchone()["n"] == 1
    candidates = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in (database.blobs.storage.control_dir / "blob-candidates").glob("*.json")
    ]
    assert len(candidates) == 2
    inventory = database.blobs.candidate_inventory(database, project)
    assert len(inventory["rows"]) == 1
    assert inventory["rows"][0]["bytes"] == len(b"stale lease")
    assert "sha256" not in inventory["rows"][0]
    assert not inventory["rows"][0]["reclaimable_candidate"]
    for row in candidates:
        preview = database.blobs.cleanup_preview(database, project, row["id"])
        assert not preview["allowed"]
        if row["id"] == str(artifact["blob_id"]):
            assert not {"bytes", "sha256", "locator", "version_id"} & preview.keys()


def test_existing_graph_export_obeys_frozen_export_policy(database, tmp_path):
    import zipfile

    from threemind_core import Engine, Stimulus
    from threemind_lab.protocols import RunSpec
    from threemind_lab.worker import Worker

    database.blobs, target = filesystem(tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "graph export policy")["id"]
    run = database.create_run(project, "graph source", RunSpec().model_dump())
    engine = Engine()
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    engine.advance_to(20000)
    checkpoint = database.save_checkpoint(project, run["id"], engine.capture_state(), expected_revision=0)
    job = database.enqueue(
        project,
        "data_export",
        {"table": "nodes", "format": "jsonl", "checkpoint_id": str(checkpoint["id"]), "minimum": 0},
        run_id=run["id"],
    )
    assert job["params"]["storage_policy"]["target_id"] == target["id"]
    # A later category change cannot redirect already queued work.
    database.blobs.storage.register_target(kind="db", target_id="database", name="database bytes")
    database.blobs.set_policy("export", "database", expected_revision=3)
    worker = Worker(database, backend="reference")
    assert worker.once()
    with database.tx(project) as db:
        saved = db.execute("SELECT * FROM artifacts WHERE job_id=%s", (job["id"],)).fetchone()
        done = db.execute("SELECT status,required_features FROM jobs WHERE id=%s", (job["id"],)).fetchone()
    assert done["status"] == "done"
    assert saved["blob_id"]
    with zipfile.ZipFile(io.BytesIO(b"".join(object_chunks(database, project, "artifact", saved["id"])))) as package:
        raw = package.read("nodes.jsonl")
        assert json.loads(package.read("selection.json"))["checkpoint_id"] == str(checkpoint["id"])
    decoded = [json.loads(line) for line in raw.splitlines()]
    assert len(decoded) == 2
    assert database.blobs.freeze("export")["target_id"] == "database"


def test_expired_cleanup_tombstone_and_new_upload(database, tmp_path):
    database.blobs, _ = filesystem(tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "candidate cleanup")["id"]
    row = database.blobs.prepare(project, "export", [b"unreferenced"])
    path = database.blobs.storage.control_dir / "blob-candidates" / (row["id"] + ".json")
    old = time.time() - 86401
    os.utime(path, (old, old))
    preview = database.blobs.cleanup_preview(database, project, row["id"])
    assert preview["allowed"]
    assert database.blobs.candidate_inventory(database, project)["rows"][0]["reclaimable_candidate"]
    with pytest.raises(ValueError, match="blocked|changed"):
        database.blobs.cleanup_execute(database, project, row["id"], token=preview["token"], confirm_name="wrong")
    assert database.blobs.cleanup_execute(database, project, row["id"], token=preview["token"], confirm_name=row["id"])[
        "removed"
    ]
    with database.tx(project) as db, pytest.raises(ValueError, match="retired"):
        database.blobs.attach(db, row)
    fresh = database.blobs.prepare(project, "export", [b"unreferenced"])
    assert fresh["id"] != row["id"] and b"".join(database.blobs.read(fresh)) == b"unreferenced"


def test_note_private_original_and_media_roundtrip(database, tmp_path):
    from PIL import Image

    from threemind_lab import auth, media_store, notebooks
    from threemind_lab.protocols import RunSpec

    database.blobs, _ = filesystem(tmp_path)
    project = database.create_project({"id": LOCAL_USER}, "external carriers")["id"]
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(stream, format="PNG")
    raw, asset_id = stream.getvalue(), uuid4()
    notebooks.save_asset(database, project, LOCAL_USER, asset_id, "private.png", raw)
    assert notebooks.asset(database, project, LOCAL_USER, asset_id)["content"] == raw
    user = auth.create_user(database, "private-image-viewer", "isolated-test-password")
    with database.tx(project) as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'researcher')", (project, user["id"]))
    with pytest.raises(NotFound):
        notebooks.asset(database, project, user["id"], asset_id)
    assert database.blobs.audit(database, project, actor=user["id"])["rows"] == []
    assert len(database.blobs.audit(database, project, actor=LOCAL_USER, verify=True)["rows"]) == 1
    assert database.blobs.audit(database, project)["summary"]["objects"] == 0
    spec = RunSpec(environment="manual", visual_sensor={"enabled": True})
    run = database.create_run(project, "media", spec.model_dump())
    accepted = media_store.accept(
        database, project, run["id"], {"id": LOCAL_USER}, raw, kind="image", filename="red.png", request_id=uuid4()
    )
    assert accepted
    assert b"".join(object_chunks(database, project, "media", hashlib.sha256(raw).hexdigest())) == raw


def test_s3_local_service_multipart_version_and_integrity(tmp_path, monkeypatch):
    boto3 = pytest.importorskip("boto3")
    server_class = pytest.importorskip("moto.server").ThreadedMotoServer
    server = server_class(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    try:
        host, port = server.get_host_and_port()
        endpoint = f"http://{host}:{port}"
        client = boto3.client(
            "s3", endpoint_url=endpoint, region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
        )
        client.create_bucket(Bucket="threemind-isolated")
        client.put_bucket_versioning(Bucket="threemind-isolated", VersioningConfiguration={"Status": "Enabled"})
        secrets = SecretBox((Fernet.generate_key().decode(),))
        storage = ResearchStorage(tmp_path / "control", repository_root=tmp_path)
        target = storage.register_target(
            kind="s3",
            name="local emulator",
            configuration={
                "endpoint": endpoint,
                "bucket": "threemind-isolated",
                "encrypted_secret": secrets.seal({"access_key_id": "test", "secret_access_key": "test"}),
            },
        )
        blobs = BlobStore(storage, secret_box=secrets)
        blobs.set_policy("media-original", target["id"], expected_revision=0)
        row = blobs.prepare(uuid4(), "media-original", [b"a" * 1024**2 for _ in range(9)])
        assert [p.stem for p in (storage.control_dir / "blob-candidates").glob("*.json")] == [row["id"]]
        assert row["version_id"] and len(b"".join(blobs.read(row))) == 9 * 1024**2
        # A later key version cannot alter this object's frozen version.
        client.put_object(Bucket="threemind-isolated", Key=row["locator"]["key"], Body=b"different")
        assert len(b"".join(blobs.read(row))) == row["bytes"]
        missing = row | {"version_id": "unknown-version"}
        with pytest.raises(OSError, match="unavailable"):
            b"".join(blobs.read(missing))
        assert client.list_multipart_uploads(Bucket="threemind-isolated").get("Uploads", []) == []
        blobs.s3_factory = lambda target: client

        def failed_part(**kwargs):
            raise RuntimeError("isolated upload fault")

        monkeypatch.setattr(client, "upload_part", failed_part)
        with pytest.raises(RuntimeError, match="isolated upload fault"):
            blobs.prepare(uuid4(), "media-original", [b"b" * 1024**2 for _ in range(9)])
        assert client.list_multipart_uploads(Bucket="threemind-isolated").get("Uploads", []) == []
        receipts = [
            json.loads(p.read_text(encoding="utf-8")) for p in (storage.control_dir / "blob-candidates").glob("*.json")
        ]
        assert sum(r["state"] == "upload_failed" for r in receipts) == 1
    finally:
        server.stop()


def test_live_packet_failed_commit_keeps_causal_state_and_retry_exact(database, tmp_path, monkeypatch):
    from threemind_lab import live_capture
    from threemind_lab.protocols import RunSpec
    from threemind_runtime.live_media import LivePacket, encode_packet

    database.blobs, _ = filesystem(tmp_path)
    actor = {"id": LOCAL_USER}
    project = database.create_project(actor, "isolated live fault")["id"]
    spec = RunSpec(
        environment="manual",
        clock="realtime",
        duration_s=2,
        auditory_sensor={"enabled": True, "encoding": "waveform", "waveform_bins": 4},
        live_capture={"microphone_enabled": True},
    )
    run = database.create_run(project, "carrier transaction", spec.model_dump())["id"]
    with database.tx(project) as db:
        db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
    session = uuid4()
    live_capture.create(
        database,
        project,
        run,
        actor,
        session_id=session,
        name="fault test",
        kind="audio",
        source_clock={"kind": "synthetic"},
    )
    raw = encode_packet(LivePacket("audio", 0, 0, False, sample_rate=16000, channels=1, samples=tuple([0.3] * 3200)))
    with database.tx(project) as db:
        before = db.execute(
            "SELECT encoder_state,next_sequence,byte_count FROM capture_sessions WHERE id=%s", (session,)
        ).fetchone()
    with monkeypatch.context() as fault:

        def failed_submit(*args, **kwargs):
            raise RuntimeError("isolated causal commit fault")

        fault.setattr(live_capture, "submit", failed_submit)
        with pytest.raises(RuntimeError, match="isolated causal commit fault"):
            live_capture.accept_packet(database, project, run, session, actor, raw)
    with database.tx(project) as db:
        after = db.execute(
            "SELECT encoder_state,next_sequence,byte_count FROM capture_sessions WHERE id=%s", (session,)
        ).fetchone()
        assert after == before
        for table in ("capture_packets", "media_assets", "input_envelopes", "input_frames"):
            assert db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"] == 0
    assert len(database.blobs.candidate_inventory(database, project)["rows"]) == 1
    accepted = live_capture.accept_packet(database, project, run, session, actor, raw)
    assert not accepted["duplicate"]
    retried = live_capture.accept_packet(database, project, run, session, actor, raw)
    assert retried["duplicate"] and retried["envelope_id"] == accepted["envelope_id"]
    with database.tx(project) as db:
        assert (
            db.execute("SELECT next_sequence FROM capture_sessions WHERE id=%s", (session,)).fetchone()["next_sequence"]
            == 1
        )
        assert db.execute("SELECT count(*) AS n FROM capture_packets").fetchone()["n"] == 1
