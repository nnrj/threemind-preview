import hashlib
from uuid import uuid4

import psycopg
import pytest
from test_report_shares import prepared
from test_storage_root import local_files

from threemind_lab import report_shares
from threemind_lab.blob_store import object_chunks
from threemind_lab.database import LOCAL_USER


def test_published_body_and_bundle_move_without_changing_publication(database, tmp_path):
    storage = local_files(database, tmp_path)
    project, document, _source, _spec, export, body = prepared(database)
    share = report_shares.create(database, project, LOCAL_USER, document, body | {"include_bundle": True})
    target = storage.register_target(tmp_path / "relocated", "published originals")
    with database.tx(project) as db:
        publication = db.execute("SELECT * FROM research_document_shares WHERE id=%s", (share["id"],)).fetchone()
    for field, variant in [("artifact_id", "body"), ("bundle_artifact_id", "bundle")]:
        identity = export["result"][field]
        raw = b"".join(object_chunks(database, project, "artifact", identity))
        with database.tx(project) as db:
            original = db.execute("SELECT * FROM artifacts WHERE id=%s", (identity,)).fetchone()
        operation = uuid4()
        receipt = database.payloads.migrate(
            project, "artifact", identity, target["id"], operation_id=operation, actor=LOCAL_USER
        )
        assert database.payloads.migrate(
            project, "artifact", identity, target["id"], operation_id=operation, actor=LOCAL_USER
        ) == receipt
        with database.tx(project) as db:
            moved = db.execute("SELECT * FROM artifacts WHERE id=%s", (identity,)).fetchone()
            assert db.execute("SELECT * FROM research_document_shares WHERE id=%s", (share["id"],)).fetchone() == publication
        assert {k: v for k, v in moved.items() if k != "blob_id"} == {
            k: v for k, v in original.items() if k != "blob_id"
        }
        assert b"".join(report_shares.file_stream(database, report_shares.resolve(database, share["id"]), variant)) == raw
        path = storage.safe_path(target["id"], receipt["locator"]["key"])
        path.write_bytes(b"corrupt")
        with pytest.raises(ValueError):
            b"".join(report_shares.file_stream(database, report_shares.resolve(database, share["id"]), variant))
        path.write_bytes(raw)
        database.payloads.rollback(receipt)
        assert b"".join(object_chunks(database, project, "artifact", identity)) == raw
        with database.tx(project) as db:
            assert db.execute("SELECT * FROM artifacts WHERE id=%s", (identity,)).fetchone() == original


def test_publication_guard_rejects_metadata_chunks_and_wrong_content_pointers(database, tmp_path):
    storage = local_files(database, tmp_path)
    project, document, _source, _spec, export, body = prepared(database)
    report_shares.create(database, project, LOCAL_USER, document, body)
    identity = export["result"]["artifact_id"]
    raw = b"".join(object_chunks(database, project, "artifact", identity))
    target = storage.register_target(tmp_path / "candidates", "placement candidates")
    frozen = {"kind": target["kind"], "target_id": target["id"], "config_revision": target["config_revision"],
              "host_id": target["host_id"], "category": "export", "policy_revision": database.blobs.policies()["revision"]}
    for invalid in [bytes([raw[0] ^ 1]) + raw[1:], raw + b"extra"]:
        assert hashlib.sha256(invalid).hexdigest() != export["result"]["sha256"]
        candidate = database.blobs.prepare(project, "export", [invalid], frozen=frozen)
        with database.tx(project) as db:
            blob = database.blobs.attach(db, candidate)
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), database.tx(project) as db:
            db.execute("UPDATE artifacts SET blob_id=%s WHERE id=%s", (blob, identity))
    candidate = database.blobs.prepare(project, "export", [raw], frozen=frozen)
    with database.tx(project) as db:
        blob = database.blobs.attach(db, candidate)
    for statement, args in [
        ("UPDATE artifacts SET name='changed',blob_id=%s WHERE id=%s", (blob, identity)),
        ("UPDATE artifact_chunks SET body='wrong' WHERE artifact_id=%s", (identity,)),
        ("INSERT INTO artifact_chunks VALUES(%s,%s,999,'wrong')", (project, identity)),
        ("DELETE FROM artifacts WHERE id=%s", (identity,)),
    ]:
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), database.tx(project) as db:
            db.execute(statement, args)
    assert b"".join(object_chunks(database, project, "artifact", identity)) == raw
