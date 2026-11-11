import hashlib
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_api import client_for
from test_report_exports import artifact, fixture_document
from test_research_documents import save_body

from threemind_lab import auth, report_exports, report_shares, research_documents
from threemind_lab.database import LOCAL_USER, Conflict, Forbidden, NotFound
from threemind_lab.worker import Worker


def prepared(database, *, include_data=True, fmt="html"):
    project, document, source, spec = fixture_document(database)
    export = report_exports.request(
        database,
        project,
        LOCAL_USER,
        document,
        {
            "operation_id": str(uuid4()),
            "revision": 1,
            "format": fmt,
            "include_data": include_data,
        },
    )
    assert Worker(database).once()
    exported = report_exports.listing(database, project, document)["rows"][0]
    assert exported["status"] == "done", exported["error"]
    body = {
        "operation_id": str(uuid4()),
        "export_id": str(export["id"]),
        "expected_body_hash": exported["result"]["sha256"],
    }
    return project, document, source, spec, exported, body


def test_fixed_publication_scope_hashes_retry_revocation_and_immutable_bytes(database):
    project, document, _source, spec, export, body = prepared(database)
    research_documents.save(
        database, project, LOCAL_USER, document, save_body(spec | {"title": "New private revision"}, 1)
    )
    share = report_shares.create(database, project, LOCAL_USER, document, body)
    assert share["metadata"]["title"] == spec["title"] and share["revision"] == 1
    assert report_shares.create(database, project, LOCAL_USER, document, body)["replayed"]
    with pytest.raises(Conflict):
        report_shares.create(database, project, LOCAL_USER, document, body | {"include_bundle": True})
    anonymous_path = f"/api/v2/shared-documents/{share['id']}"
    with client_for(database, mode="server") as client:
        public = client.get(anonymous_path)
        assert public.status_code == 200, public.text
        assert public.headers["referrer-policy"] == "no-referrer"
        assert public.headers["cache-control"] == "no-store" and "noindex" in public.headers["x-robots-tag"]
        assert "project_id" not in public.json() and "actor_id" not in public.json()
        response = client.get(anonymous_path + "/files/body")
        assert response.content == artifact(database, project, export["result"]["artifact_id"])
        stream = report_shares.file_stream(database, report_shares.resolve(database, share["id"]), "body")
        try:
            assert next(stream)
            pool = database.pool.get_stats()
            assert pool["pool_available"] == pool["pool_size"]  # Slow readers must not hold DB connections.
        finally:
            stream.close()
        assert hashlib.sha256(response.content).hexdigest() == body["expected_body_hash"]
        assert (
            "attachment" in response.headers["content-disposition"]
            and "sandbox" in response.headers["content-security-policy"]
        )
        assert client.get(anonymous_path + "/files/bundle").status_code == 404
        assert client.get(f"/api/v2/projects/{project}/research-documents/{document}").status_code == 401
        assert client.get(f"/api/v2/shared-documents/{document}").status_code == 404
        assert client.get(anonymous_path + "/files/" + export["result"]["bundle_artifact_id"]).status_code == 422
        with database.tx() as db:
            assert db.execute("SELECT count(*) AS n FROM research_document_shares").fetchone()["n"] == 0
        for sql, values in [
            ("UPDATE artifact_chunks SET body='wrong' WHERE artifact_id=%s", (export["result"]["artifact_id"],)),
            ("DELETE FROM artifact_chunks WHERE artifact_id=%s", (export["result"]["artifact_id"],)),
            ("UPDATE artifacts SET name='changed' WHERE id=%s", (export["result"]["artifact_id"],)),
            ("UPDATE research_document_shares SET metadata=%s WHERE id=%s", (Jsonb({}), share["id"])),
            ("DELETE FROM research_document_shares WHERE id=%s", (share["id"],)),
        ]:
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), database.tx(project) as db:
                db.execute(sql, values)
        revoked = report_shares.revoke(database, project, LOCAL_USER, document, share["id"])
        assert (
            report_shares.revoke(database, project, LOCAL_USER, document, share["id"])["revoked_at"]
            == revoked["revoked_at"]
        )
        assert report_shares.create(database, project, LOCAL_USER, document, body)["revoked_at"] is not None
        assert client.get(anonymous_path).status_code == client.get(anonymous_path + "/files/body").status_code == 404
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), database.tx(project) as db:
            db.execute("UPDATE research_document_shares SET revoked_at=NULL WHERE id=%s", (share["id"],))


def test_publication_full_bundle_authorization_csrf_and_cross_project(database):
    project, document, _source, _spec, export, body = prepared(database)
    owner = auth.create_user(database, "publication-owner", "publication-test-password")
    researcher = auth.create_user(database, "publication-researcher", "publication-test-password")
    viewer = auth.create_user(database, "publication-viewer", "publication-test-password")
    with database.tx(project) as db:
        for user, role in ((owner, "owner"), (researcher, "researcher"), (viewer, "viewer")):
            db.execute("INSERT INTO members VALUES(%s,%s,%s)", (project, user["id"], role))
    other = database.create_project({"id": owner["id"]}, "Unrelated project")["id"]
    path = f"/api/v2/projects/{project}/research-documents/{document}/shares"
    with client_for(database, mode="server") as client:
        assert client.post(path, json=body).status_code == 401
        for user in (researcher, viewer):
            login = client.post(
                "/api/v2/login", json={"username": user["username"], "password": "publication-test-password"}
            ).json()
            client.headers["X-CSRF-Token"] = login["csrf"]
            assert client.post(path, json=body).status_code == client.get(path).status_code == 403
        login = client.post(
            "/api/v2/login", json={"username": owner["username"], "password": "publication-test-password"}
        ).json()
        assert client.post(path, json=body).status_code == 403  # stale CSRF
        client.headers["X-CSRF-Token"] = login["csrf"]
        assert client.post(path.replace(str(project), str(other)), json=body).status_code == 409
        shared = client.post(path, json=body | {"include_bundle": True})
        assert shared.status_code == 201, shared.text
        share = shared.json()
        client.cookies.clear()
        response = client.get(f"/api/v2/shared-documents/{share['id']}/files/bundle")
        assert response.content == artifact(database, project, export["result"]["bundle_artifact_id"])
        assert response.headers["x-content-sha256"] == export["result"]["bundle_sha256"]
        with database.tx(project) as db:
            db.execute("UPDATE users SET enabled=false WHERE id=%s", (owner["id"],))
        assert client.get(f"/api/v2/shared-documents/{share['id']}").status_code == 404
        assert report_shares.listing(database, project, LOCAL_USER, document)["rows"][0]["status"] == "unavailable"
        with database.tx(project) as db:
            db.execute("UPDATE users SET enabled=true WHERE id=%s", (owner["id"],))
            db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (project, owner["id"]))
        assert client.get(f"/api/v2/shared-documents/{share['id']}/files/body").status_code == 404
        with pytest.raises(Forbidden):
            report_shares.create(database, project, owner["id"], document, body)


def test_share_requires_prepared_integrity_and_explicit_complete_bundle(database):
    project, document, _source, _spec, export, body = prepared(database, include_data=False)
    with pytest.raises(Conflict, match="complete evidence"):
        report_shares.create(database, project, LOCAL_USER, document, body | {"include_bundle": True})
    with pytest.raises(Conflict, match="body changed"):
        report_shares.create(database, project, LOCAL_USER, document, body | {"expected_body_hash": "0" * 64})
    with pytest.raises(Conflict, match="completed HTML"):
        report_shares.create(database, project, LOCAL_USER, document, body | {"export_id": str(uuid4())})
    with database.tx(project) as db:
        db.execute("UPDATE artifact_chunks SET body='damaged' WHERE artifact_id=%s", (export["result"]["artifact_id"],))
    with pytest.raises(Conflict, match="integrity"):
        report_shares.create(database, project, LOCAL_USER, document, body)
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM research_document_shares").fetchone()["n"] == 0


def test_share_concurrent_retry_expiry_and_policy_cannot_mutate(database):
    project, document, _source, _spec, _export, body = prepared(database)
    with ThreadPoolExecutor(max_workers=2) as executor:
        values = list(
            executor.map(lambda _: report_shares.create(database, project, LOCAL_USER, document, body), range(2))
        )
    assert values[0]["id"] == values[1]["id"] and sum(v["replayed"] for v in values) == 1
    share_id = values[0]["id"]
    with database.tx() as db:
        db.execute("SELECT set_config('tm.shared_document_id',%s,true)", (str(share_id),))
        assert db.execute("SELECT count(*) AS n FROM research_document_shares").fetchone()["n"] == 1
        assert (
            db.execute(
                "UPDATE research_document_shares SET revoked_at=now() WHERE id=%s RETURNING id", (share_id,)
            ).fetchone()
            is None
        )
        assert db.execute("SELECT count(*) AS n FROM artifact_chunks").fetchone()["n"] == 0
    # Test-only clock fixture under the isolated schema owner, never an API capability.
    with psycopg.connect(database.test_migration_url) as db:
        db.execute("SET search_path TO tm2,pg_catalog")
        db.execute("SELECT set_config('tm.project_id',%s,true)", (str(project),))
        db.execute("ALTER TABLE research_document_shares DISABLE TRIGGER immutable_share")
        db.execute(
            "UPDATE research_document_shares SET created_at=now()-interval '2 days',expires_at=now()-interval '1 day' WHERE id=%s",
            (share_id,),
        )
        db.execute("ALTER TABLE research_document_shares ENABLE TRIGGER immutable_share")
    with pytest.raises(NotFound):
        report_shares.resolve(database, share_id)
    assert report_shares.listing(database, project, LOCAL_USER, document)["rows"][0]["status"] == "expired"


def test_manual_report_share_preserves_referenced_ai_authorship(database):
    import json

    from test_ai_providers import get_call
    from test_research_ai import ask, fixture, reply

    settings, project, _run, _cp, _image, _source, provider, scope, spec = fixture(database)
    call, _, _ = ask(database, settings, project, provider, scope)
    assert reply(database, settings, json.dumps(spec)).once()
    record = get_call(database, project, call)["result"]["document_id"]
    document = uuid4()
    manual = {
        "kind": "report",
        "title": "Manually assembled AI record reference",
        "blocks": [
            {
                "id": "reference",
                "type": "record_block",
                "record_id": record,
                "revision": 1,
                "block_id": spec["blocks"][-1]["id"],
            }
        ],
    }
    research_documents.save(database, project, LOCAL_USER, document, save_body(manual))
    export = report_exports.request(
        database, project, LOCAL_USER, document, {"operation_id": str(uuid4()), "revision": 1, "format": "html"}
    )
    assert Worker(database).once()
    exported = report_exports.listing(database, project, document)["rows"][0]
    assert exported["status"] == "done", exported["error"]
    shared = report_shares.create(
        database,
        project,
        LOCAL_USER,
        document,
        {
            "operation_id": str(uuid4()),
            "export_id": str(export["id"]),
            "expected_body_hash": exported["result"]["sha256"],
        },
    )
    assert shared["metadata"]["ai_generated"]
