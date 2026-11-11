from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from threemind_lab import auth, browsing, notebooks, permissions
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Conflict, Forbidden, NotFound
from threemind_lab.permission_api import register_permission_routes

pytestmark = pytest.mark.session_auth
PASSWORD = "isolated platform account password"


def host(database):
    app = FastAPI()
    app.state.db = database
    app.state.settings = Settings(database_url=database.test_url, authentication="session", backend="reference")
    for error, status in ((Forbidden, 403), (Conflict, 409), (NotFound, 404), (ValueError, 422)):
        def handler(_, exc, status=status):
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(error, handler)
    register_permission_routes(app)

    @app.post("/api/v2/logout")
    def logout(request: Request, response: Response):
        result = auth.logout(request)
        response.delete_cookie("tm_session")
        return result

    @app.get("/api/v2/projects/{project}/runs/{run_id}")
    def protected(project: UUID, run_id: UUID, request: Request):
        user = auth.identity(request)
        permissions.require(database, user, "runs.read", project=project)
        return {"user_id": str(user["id"]), "source": user["source"]}

    @app.get("/api/v2/projects/{project}/runs")
    def project_runs(project: UUID, request: Request):
        user = auth.identity(request)
        permissions.require(database, user, "runs.read", project=project)
        return []
    return TestClient(app)


def root(database):
    if auth.setup_status(database)["required"]:
        _, _, actor = auth.setup_local(database, PASSWORD)
    else:
        actor = permissions.enrich(database, {"id": LOCAL_USER})
    permissions.actor_context.set(actor)
    return actor


def run(database, actor=None):
    actor = actor or root(database)
    project = database.create_project(actor, "isolated authority")
    run_id = uuid4()
    with database.tx(project["id"]) as db:
        permissions.set_context(db, actor, project["id"])
        db.execute("INSERT INTO runs(id,project_id,name,spec) VALUES(%s,%s,'metadata-only',%s)",
                   (run_id, project["id"], Jsonb({})))
    return project["id"], run_id


def test_local_first_setup_remember_refresh_bearer_and_cookie_csrf(database):
    with host(database) as client:
        assert client.get("/api/v2/me").status_code == 401
        assert client.get("/api/v2/auth/setup/status").json()["required"]
        initial = client.post("/api/v2/auth/setup", json={"password": PASSWORD, "username": "local-admin"})
        assert initial.status_code == 200, initial.text
        assert initial.json()["user"]["id"] == str(LOCAL_USER)
        assert initial.json()["user"]["superadmin"]
        assert client.post("/api/v2/auth/setup", json={"password": PASSWORD}).status_code == 409
        assert client.post("/api/v2/auth/refresh").status_code == 403
        refreshed = client.post("/api/v2/auth/refresh", headers={"X-CSRF-Token": initial.json()["csrf"]})
        assert refreshed.status_code == 200, refreshed.text
        token = client.post("/api/v2/auth/token", json={"username": "local-admin", "password": PASSWORD,
                                                       "remember": True, "source": "script"}).json()
        assert datetime.fromisoformat(token["expires_at"]) - datetime.now(UTC) > timedelta(days=29)
        header = {"Authorization": "Bearer " + token["access_token"]}
        me = client.get("/api/v2/me", headers=header).json()["user"]
        assert me["id"] == str(LOCAL_USER) and me["auth_type"] == "bearer"
        rotation = client.post("/api/v2/auth/refresh", headers=header)
        assert rotation.status_code == 200
        assert client.get("/api/v2/me", headers=header).status_code == 401
        header["Authorization"] = "Bearer " + rotation.json()["access_token"]
        assert client.post("/api/v2/logout", headers=header).status_code == 200
        assert client.get("/api/v2/me", headers=header).status_code == 401


def test_pairs_do_not_mix_and_admin_flags_do_not_grant_root(database):
    administrator = root(database)
    project, _ = run(database, administrator)
    user = auth.create_user(database, "scope-reader", PASSWORD)
    reader = permissions.save_role(database, administrator, key="global-reader", name="reader",
        grants=[{"action": "runs.read", "scope": "all_projects"}])
    writer = permissions.save_role(database, administrator, key="member-writer", name="writer",
        grants=[{"action": "runs.stimulate", "scope": "member_projects"}])
    permissions.assign_roles(database, administrator, user["id"], [reader["id"], writer["id"]])
    forged = user | {"superadmin": True, "admin": True}
    assert permissions.allows(database, forged, "runs.read", project=project)
    assert not permissions.allows(database, forged, "runs.stimulate", project=project)
    assert not permissions.enrich(database, forged)["superadmin"]
    admin = auth.create_user(database, "ordinary-admin", PASSWORD, admin=True)
    with pytest.raises(Forbidden):
        permissions.save_role(database, admin, key="escalate-reader", name="bad",
            grants=[{"action": "runs.read", "scope": "all_projects"}])
    with pytest.raises(Forbidden):
        permissions.assign_roles(database, admin, admin["id"], [reader["id"]])
    with pytest.raises(Conflict):
        permissions.set_enabled(database, administrator, administrator["id"], False)


def test_superadmin_private_note_read_revision_and_original_protection(database):
    administrator = root(database)
    author = auth.create_user(database, "private-author", PASSWORD)
    peer = auth.create_user(database, "private-peer", PASSWORD, admin=True)
    project = database.create_project(author, "private notebook")["id"]
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'researcher')", (project, peer["id"]))
    note_id = uuid4()
    value = {"operation_id": str(uuid4()), "expected_revision": 0, "title": "private original", "kind": "draft",
             "body": {"format": "markdown", "text": "private scientific evidence"}}
    permissions.actor_context.set(author)
    notebooks.save_note(database, project, author["id"], note_id, value)
    permissions.actor_context.set(peer)
    with pytest.raises(NotFound):
        notebooks.note(database, project, peer["id"], note_id)
    permissions.actor_context.set(administrator)
    assert notebooks.note(database, project, administrator["id"], note_id)["owner_id"] == author["id"]
    newer = value | {"operation_id": str(uuid4()), "expected_revision": 1, "title": "append correction"}
    assert notebooks.save_note(database, project, administrator["id"], note_id, newer)["revision"] == 2
    assert notebooks.note(database, project, administrator["id"], note_id, 1)["title"] == "append correction"
    with database.tx(project) as db:
        permissions.set_context(db, administrator, project)
        original = db.execute("SELECT metadata FROM note_versions WHERE note_id=%s AND revision=1", (note_id,)).fetchone()
    assert original["metadata"]["title"] == "private original"
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), database.tx(project) as db:
        permissions.set_context(db, administrator, project)
        db.execute("UPDATE note_versions SET body='{}' WHERE note_id=%s", (note_id,))


def test_run_delegation_is_not_root_restricted_revocable_and_fresh(database):
    administrator = root(database)
    project, rid = run(database, administrator)
    with host(database) as client:
        token = client.post("/api/v2/auth/token", json={"username": "local", "password": PASSWORD}).json()["access_token"]
        signed = client.post("/api/v2/account/delegations", headers={"Authorization": "Bearer " + token}, json={
            "name": "AI reader", "source": "ai", "actions": [{"action": "runs.read", "scope": "all_projects"}],
            "resources": [{"kind": "run", "id": str(rid)}],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        })
        assert signed.status_code == 201, signed.text
        delegation = signed.json()
        headers = {"Authorization": "Bearer " + delegation["access_token"]}
        user = client.get("/api/v2/me", headers=headers).json()["user"]
        assert not user["superadmin"] and user["id"] == str(LOCAL_USER) and user["source"] == "ai"
        assert client.get(f"/api/v2/projects/{project}/runs/{rid}", headers=headers).status_code == 200
        assert client.get(f"/api/v2/projects/{project}/runs/{uuid4()}", headers=headers).status_code == 403
        assert client.get(f"/api/v2/projects/{project}/runs", headers=headers).status_code == 403
        assert client.post("/api/v2/auth/refresh", headers=headers).status_code == 403
        assert client.get("/api/v2/account/delegations", headers=headers).status_code == 403
        with database.tx() as db:
            stored = db.execute("SELECT token_hash FROM platform_delegations WHERE id=%s", (delegation["delegation"]["id"],)).fetchone()
        assert stored["token_hash"] == auth.digest(delegation["access_token"])
        assert delegation["access_token"] not in str(stored)
        assert client.delete("/api/v2/account/delegations/" + delegation["delegation"]["id"],
                             headers={"Authorization": "Bearer " + token}).status_code == 200
        assert client.get("/api/v2/me", headers=headers).status_code == 401


def test_browse_totals_only_contain_authorized_kinds(database):
    administrator = root(database)
    project, _ = run(database, administrator)
    user = auth.create_user(database, "metadata-only", PASSWORD)
    role = permissions.save_role(database, administrator, key="read-runs-only", name="run only",
        grants=[{"action": "runs.read", "scope": "all_projects"}])
    permissions.assign_roles(database, administrator, user["id"], [role["id"]])
    permissions.actor_context.set(None)
    overview = browsing.overview(database, user)
    assert overview["totals"] == {"run": 1, "development": 0, "language": 0}
    listed = browsing.listing(database, user, kinds=["run", "note"])
    assert listed["total"] == 1 and all(r["kind"] == "run" for r in listed["rows"])
    assert listed["rows"][0]["project_id"] == project


def test_delegation_roles_narrow_and_disabled_account_stops_lineage(database):
    administrator = root(database)
    user = auth.create_user(database, "delegation-owner", PASSWORD)
    project, _ = run(database, user)
    permissions.actor_context.set(user)
    signed = auth.delegate(database, user, name="repeatable script", source="script",
        actions=[{"action": "runs.read", "scope": "member_projects"},
                 {"action": "runs.stimulate", "scope": "member_projects"}],
        resources=[{"kind": "project", "id": str(project)}], expires_at=datetime.now(UTC) + timedelta(hours=1))
    delegated = {"id": user["id"], "delegation_id": signed["delegation"]["id"]}
    resources = [{"kind": "project", "id": str(project)}]
    assert permissions.allows(database, delegated, "runs.stimulate", project=project, resources=resources)
    permissions.actor_context.set(administrator)
    role = permissions.save_role(database, administrator, key="narrow-script-reader", name="read only",
        grants=[{"action": "runs.read", "scope": "member_projects"}])
    permissions.assign_roles(database, administrator, user["id"], [role["id"]])
    assert permissions.allows(database, delegated, "runs.read", project=project, resources=resources)
    assert not permissions.allows(database, delegated, "runs.stimulate", project=project, resources=resources)
    lineage = permissions.execution_actor(permissions.enrich(database, delegated))
    assert lineage["delegation_id"] == str(signed["delegation"]["id"])
    permissions.set_enabled(database, administrator, user["id"], False)
    with pytest.raises(Forbidden):
        permissions.restore_execution_actor(database, lineage, action="runs.read", project=project, resources=resources)


def test_distinct_control_actions():
    assert permissions.command_action("pause") == "runs.pause"
    assert permissions.command_action("stimulus") == "runs.stimulate"
    assert permissions.command_action("intervene") == "runs.intervene"
    assert permissions.command_action("intervention") == "runs.intervene"
    assert permissions.command_action("robot_control") == "runs.intervene"
    assert permissions.command_action("readout_observe") == "runs.observe"


def test_authenticated_ai_repeated_text_run_and_research_receipts(database):
    """Engineering acceptance only; no research subject or accuracy claim."""
    from threemind_lab.api import create_app
    from threemind_lab.worker import Worker

    permissions.actor_context.set(None)
    account = auth.create_user(database, "engineering-ai", PASSWORD)
    settings = Settings(database_url=database.test_url, authentication="session", backend="reference")
    with TestClient(create_app(settings, database)) as client:
        def login():
            response = client.post("/api/v2/auth/token", json={
                "username": "engineering-ai", "password": PASSWORD, "source": "ai", "remember": True,
            })
            assert response.status_code == 200, response.text
            assert response.json()["user"]["id"] == str(account["id"])
            assert not response.json()["user"]["superadmin"]
            return {"Authorization": "Bearer " + response.json()["access_token"],
                    "X-ThreeMind-Execution-Source": "ai"}

        headers = login()
        response = client.post("/api/v2/projects", headers=headers, json={"name": "Isolated AI recording acceptance"})
        assert response.status_code == 201, response.text
        project = response.json()["id"]
        base = f"/api/v2/projects/{project}"
        records = base + "/records"
        registration = {"request_id": str(uuid4()), "spec": {
            "source_key": "engineering-ai-authenticated-repetition", "title": "Engineering recording acceptance",
            "classification": "development", "executor": "ai", "execution_status": "planned",
            "question": "Do authenticated ordinary AI operations preserve accepted input and recording receipts?",
            "protocol": "A new isolated individual receives the same text three times at declared simulation times.",
            "metadata": {"engineering_only": True, "accuracy_assessment": False},
        }}
        registered = client.post(records, headers=headers, json=registration)
        assert registered.status_code == 200, registered.text
        experiment = registered.json()["id"]
        spec = client.get("/api/v2/configuration/defaults", headers=headers).json()["spec"]
        spec.update(environment="manual", clock="unbounded", duration_s=0.5, sample_us=50000, checkpoint_us=100000)
        for key in ("host_telemetry", "process_telemetry", "runtime_telemetry"):
            spec[key]["enabled"] = False
        spec["text_sensor"]["enabled"] = True
        prepared = client.post(base + "/runs", headers=headers, json={
            "name": "Three repeated carriers", "spec": spec, "start_immediately": False,
            "record_executor": "ai", "record_classification": "development",
        })
        assert prepared.status_code == 201, prepared.text
        run_id = prepared.json()["id"]
        runtime = base + "/runs/" + run_id
        assert prepared.json()["status"] == "paused" and prepared.json()["revision"] == 0
        assert client.post(runtime + "/commands", headers=headers, json={"kind": "resume"}).status_code == 200
        envelope_ids = []
        declared_times = [0, 100000, 200000]
        for when in declared_times:
            request_id = str(uuid4())
            accepted = client.post(runtime + "/inputs", headers=headers, json={
                "adapter_id": "text-sensor", "payload": {"text": "红色圆形", "intensity": 1.0},
                "request_id": request_id, "requested_time_us": str(when), "source_id": "cli-text",
            })
            assert accepted.status_code == 202, accepted.text
            envelope_ids.append(request_id)
        # Logging out removes authority for new operations, without retracting the
        # three durable inputs or the already admitted run job.
        assert client.post("/api/v2/logout", headers=headers).status_code == 200
        assert client.get(runtime, headers=headers).status_code == 401
        permissions.actor_context.set(None)
        assert Worker(database, backend="reference").once()
        headers = login()
        actual = client.get(runtime, headers=headers)
        assert actual.status_code == 200, actual.text
        assert actual.json()["status"] == "completed" and actual.json()["revision"] > 0, actual.text
        envelopes = client.get(runtime + "/inputs", headers=headers).json()["rows"]
        assert {row["id"] for row in envelopes} == set(envelope_ids)
        assert all(row["status"] == "completed" and row["delivered_count"] == row["frame_count"] > 0
                   for row in envelopes)
        actual_times = []
        for identity in envelope_ids:
            delivered = client.get(runtime + "/inputs/" + identity, headers=headers).json()
            assert delivered["envelope"]["actor_id"] == str(account["id"])
            assert delivered["envelope"]["payload"]["text"] == "红色圆形"
            actual_times.append(int(delivered["frames"][0]["delivered_time_us"]))
        assert actual_times == declared_times
        checkpoints = client.get(runtime + "/checkpoints", headers=headers).json()
        assert checkpoints
        checkpoint = checkpoints[0]
        with database.tx(project) as db:
            job = db.execute("SELECT params,status FROM jobs WHERE run_id=%s AND kind='run'", (run_id,)).fetchone()
            assert job["status"] == "done"
            assert job["params"]["execution_actor"] == {"user_id": str(account["id"]), "source": "ai"}

        endpoint = records + "/" + experiment
        for kind, identity in (("run", run_id), ("checkpoint", checkpoint["id"])):
            result = client.post(endpoint + "/evidence", headers=headers, json={
                "request_id": str(uuid4()), "evidence": {"logical_id": kind + ":" + identity,
                    "role": "subject" if kind == "run" else "checkpoint", "label": "Actual " + kind,
                    "format": "threemind." + kind, "locator": {"kind": kind, "id": identity}},
            })
            assert result.status_code == 200, result.text
        for kind in ("protocol", "report", "note"):
            saved = client.post(endpoint + "/texts", headers=headers, json={
                "request_id": str(uuid4()), "identity": str(uuid4()), "kind": kind,
                "title": "Engineering " + kind,
                "markdown": "Engineering acceptance: three repeated text carriers delivered; no cognition claim.",
            })
            assert saved.status_code == 200, saved.text
        appended = client.post(endpoint + "/entries", headers=headers, json={
            "request_id": str(uuid4()), "kind": "result", "original_key": "actual-delivery",
            "content": {"run_id": run_id, "delivered_times_us": actual_times,
                        "checkpoint_id": checkpoint["id"], "engineering_only": True},
        })
        assert appended.status_code == 200, appended.text
        verified = client.get(endpoint + "/verify", headers=headers, params={"hashes": True})
        assert verified.status_code == 200 and verified.json()["coverage"] == "verified", verified.text
        final = {"request_id": str(uuid4()), "execution_status": "completed"}
        finalized = client.post(endpoint + "/finalize", headers=headers, json=final)
        assert finalized.status_code == 200, finalized.text
        retry = client.post(endpoint + "/finalize", headers=headers, json=final)
        assert retry.status_code == 200 and retry.json()["replayed"], retry.text
        receipt = client.get(records + "/receipts/" + final["request_id"], headers=headers)
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["result"]["coverage"] == "indexed"
        assert receipt.json()["result"]["finalized"]


def test_report_operations_do_not_require_or_inherit_ai_service_authority(database):
    from test_report_exports import fixture_document

    from threemind_lab import report_exports, report_shares, report_sources
    from threemind_lab.api import create_app
    from threemind_lab.worker import Worker

    administrator = root(database)
    project, document, _source, _ = fixture_document(database)
    author = auth.create_user(database, "report-only-author", PASSWORD)
    ai_only = auth.create_user(database, "service-only-member", PASSWORD)
    report_role = permissions.save_role(database, administrator, key="report-only", name="Only report operations",
        grants=[{"action": action, "scope": "member_projects"}
                for action in ("reports.read", "reports.write", "reports.export", "reports.share")])
    service_role = permissions.save_role(database, administrator, key="service-only", name="Only AI calls",
        grants=[{"action": "services.use", "scope": "member_projects"}])
    permissions.assign_roles(database, administrator, author["id"], [report_role["id"]])
    permissions.assign_roles(database, administrator, ai_only["id"], [service_role["id"]])
    with database.tx(project) as db:
        for user in (author, ai_only):
            db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (project, user["id"]))
        run_id = db.execute("SELECT id FROM runs LIMIT 1").fetchone()["id"]
    permissions.actor_context.set(permissions.enrich(database, author))
    captured = report_sources.request(database, project, author["id"], {
        "operation_id": str(uuid4()), "kind": "trajectory", "run_id": str(run_id), "metrics": ["activation"],
    })
    assert Worker(database, backend="reference").once()
    assert report_sources.get_source(database, project, captured["id"])["manifest"]
    requested = report_exports.request(database, project, author["id"], document, {
        "operation_id": str(uuid4()), "revision": 1, "format": "html",
    })
    assert Worker(database, backend="reference").once()
    exported = next(row for row in report_exports.listing(database, project, document)["rows"]
                    if row["id"] == requested["id"])
    assert exported["status"] == "done", exported["error"]
    publication = {"operation_id": str(uuid4()), "export_id": str(requested["id"]),
                   "expected_body_hash": exported["result"]["sha256"]}
    share = report_shares.create(database, project, author["id"], document, publication)
    assert report_shares.resolve(database, share["id"])["id"] == share["id"]
    assert not permissions.allows(database, author, "services.use", project=project)
    permissions.actor_context.set(permissions.enrich(database, ai_only))
    with pytest.raises(Forbidden):
        report_sources.request(database, project, ai_only["id"], {
            "operation_id": str(uuid4()), "kind": "trajectory", "run_id": str(run_id), "metrics": ["activation"],
        })
    with pytest.raises(Forbidden):
        report_exports.request(database, project, ai_only["id"], document, {
            "operation_id": str(uuid4()), "revision": 1, "format": "html",
        })
    with pytest.raises(Forbidden):
        report_shares.create(database, project, ai_only["id"], document, publication | {"operation_id": str(uuid4())})
    with TestClient(create_app(Settings(database_url=database.test_url, authentication="session", backend="reference"), database)) as client:
        def token(user):
            result = client.post("/api/v2/auth/token", json={"username": user["username"], "password": PASSWORD})
            assert result.status_code == 200, result.text
            return {"Authorization": "Bearer " + result.json()["access_token"]}

        headers = token(author)
        prefix = f"/api/v2/projects/{project}/research-documents/{document}"
        response = client.get(prefix + "/exports", headers=headers)
        assert response.status_code == 200, response.text
        response = client.post(prefix + "/exports", headers=headers,
            json={"operation_id": str(uuid4()), "revision": 1, "format": "markdown"})
        assert response.status_code == 202, response.text
        response = client.post(prefix + "/shares", headers=headers, json=publication | {"operation_id": str(uuid4())})
        assert response.status_code == 201, response.text
        headers = token(ai_only)
        assert client.get(prefix + "/exports", headers=headers).status_code == 403
        assert client.post(prefix + "/exports", headers=headers,
            json={"operation_id": str(uuid4()), "revision": 1, "format": "markdown"}).status_code == 403


def test_project_management_and_fork_creation_use_their_specific_permissions(database):
    from threemind_lab.api import create_app
    from threemind_lab.protocols import RunSpec
    from threemind_runtime import create_engine

    administrator = root(database)
    manager = auth.create_user(database, "project-manager-only", PASSWORD)
    reader = auth.create_user(database, "project-reader-only", PASSWORD)
    writer = auth.create_user(database, "research-writer-only", PASSWORD)
    creator = auth.create_user(database, "fork-creator-only", PASSWORD)
    unread_creator = auth.create_user(database, "fork-without-source-read", PASSWORD)
    member = auth.create_user(database, "added-project-member", PASSWORD)
    role_specs = ((manager, "project-manager-role", ["projects.manage"]),
                  (reader, "project-reader-role", ["projects.read"]),
                  (writer, "research-writer-role", ["research.write"]),
                  (creator, "fork-creator-role", ["runs.create", "runs.read"]),
                  (unread_creator, "unread-fork-role", ["runs.create"]))
    for user, key, actions in role_specs:
        role = permissions.save_role(database, administrator, key=key, name=key,
            grants=[{"action": action, "scope": "member_projects"} for action in actions])
        permissions.assign_roles(database, administrator, user["id"], [role["id"]])
    project = database.create_project(administrator, "Specific project operations")["id"]
    with database.tx(project) as db:
        for user, _key, _actions in role_specs:
            db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (project, user["id"]))
    spec = RunSpec(environment="manual", clock="unbounded", duration_s=0.5).model_dump()
    runtime = database.create_run(project, "Saved source", spec)
    engine = create_engine(backend="reference", kernel_id=spec["kernel_id"], config=spec["config"])
    checkpoint = database.save_checkpoint(project, runtime["id"], engine.capture_state(),
        expected_revision=0, context={"protocol": spec}, status="paused")
    with TestClient(create_app(Settings(database_url=database.test_url, authentication="session", backend="reference"), database)) as client:
        def token(user):
            response = client.post("/api/v2/auth/token", json={"username": user["username"], "password": PASSWORD})
            assert response.status_code == 200, response.text
            return {"Authorization": "Bearer " + response.json()["access_token"]}

        base = f"/api/v2/projects/{project}"
        headers = token(reader)
        assert client.get(base, headers=headers).status_code == 200
        assert client.get(base + "/members", headers=headers).status_code == 200
        assert client.put(base, headers=headers, json={"name": "Reader cannot rename"}).status_code == 403
        headers = token(manager)
        assert client.get(base, headers=headers).status_code == 403
        assert client.get(base + "/members", headers=headers).status_code == 403
        renamed = client.put(base, headers=headers, json={"name": "Renamed by project manager"})
        assert renamed.status_code == 200, renamed.text
        response = client.post(base + "/members", headers=headers,
            json={"username": member["username"], "role": "researcher"})
        assert response.status_code == 200, response.text
        defaults = client.put(base + "/configuration/defaults", headers=headers,
            json={"spec": spec, "expected_revision": 0})
        assert defaults.status_code == 200, defaults.text
        assert client.get(base + "/configuration/defaults", headers=token(reader)).json()["revision"] == 1
        assert client.put("/api/v2/configuration/defaults", headers=headers,
            json={"spec": spec, "expected_revision": 0}).status_code == 403
        rules = client.put(base + "/notifications/settings", headers=headers,
            json={"service_id": None, "config": {"enabled": True}, "expected_revision": 0})
        assert rules.status_code == 200, rules.text
        assert client.get(base + "/notifications/settings", headers=token(reader)).status_code == 200
        headers = token(writer)
        assert client.put(base, headers=headers, json={"name": "Unauthorized rename"}).status_code == 403
        assert client.post(base + "/members", headers=headers,
            json={"username": member["username"], "role": "viewer"}).status_code == 403
        assert client.put(base + "/configuration/defaults", headers=headers,
            json={"spec": spec, "expected_revision": 1}).status_code == 403
        assert client.put(base + "/notifications/settings", headers=headers,
            json={"service_id": None, "config": {"enabled": False}, "expected_revision": 1}).status_code == 403
        headers = token(creator)
        fork = client.post(base + f"/runs/{runtime['id']}/forks", headers=headers,
            json={"name": "Authorized exact fork", "paused": True})
        assert fork.status_code == 201, fork.text
        assert fork.json()["parent_id"] == str(runtime["id"])
        assert fork.json()["origin_hash"] == engine.capture_state().digest
        assert fork.json()["spec"]["kernel_id"] == spec["kernel_id"]
        assert not permissions.allows(database, creator, "runs.control", project=project)
        headers = token(unread_creator)
        denied = client.post(base + f"/runs/{runtime['id']}/forks", headers=headers,
            json={"name": "Source reading forbidden", "paused": True})
        assert denied.status_code == 403, denied.text
    permissions.actor_context.set(administrator)
    assert database.load_checkpoint(project, runtime["id"])[0]["id"] == checkpoint["id"]
    assert database.load_checkpoint(project, runtime["id"])[1].digest == engine.capture_state().digest
