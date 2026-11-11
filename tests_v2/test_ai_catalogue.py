"""Unified service catalogue and project-free diagnostics use the real isolated queue."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from threemind_lab import auth, permissions
from threemind_lab.ai_worker import AIWorker
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER

pytestmark = pytest.mark.session_auth
PASSWORD = "isolated catalogue account password"


@contextmanager
def host(database):
    settings = Settings(database_url=database.test_url, authentication="session", backend="reference",
                        secret_keys=(Fernet.generate_key().decode(),))
    auth.setup_local(database, PASSWORD)
    with TestClient(create_app(settings, database)) as client:
        token = client.post("/api/v2/auth/token", json={"username": "local", "password": PASSWORD}).json()
        client.headers["Authorization"] = "Bearer " + token["access_token"]
        yield client, settings


def provider(client):
    response = client.post("/api/v2/admin/ai/providers", json={
        "config": {"name": "global fixture", "base_url": "http://127.0.0.1:12345/v1", "model": "fixture",
                   "enabled": True, "stream": False, "input_usd_per_million": 1, "output_usd_per_million": 2},
        "api_key": "isolated-provider-secret", "expected_revision": 0,
    })
    assert response.status_code == 201, response.text
    return response.json()


def response(_):
    return httpx.Response(200, json={"choices": [{"message": {"content": "diagnostic result"},
                                                "finish_reason": "stop"}],
                                   "usage": {"prompt_tokens": 2, "completion_tokens": 3}})


def submit(client, saved, rid=None):
    value = client.post(f"/api/v2/ai/providers/{saved['id']}/test",
                        json={"request_id": str(rid or uuid4()), "prompt": "test text"})
    assert value.status_code == 202, value.text
    return value.json()


def test_unified_catalogue_versions_no_project_diagnostic_and_receipt(database):
    with host(database) as (client, settings):
        saved = provider(client)
        assert saved["project_id"] is None and saved["original_project_id"] is None
        catalogue = client.get("/api/v2/ai/providers").json()
        assert catalogue["providers"][0]["id"] == saved["id"]
        assert catalogue["providers"][0]["authorized_projects"] == []
        assert "isolated-provider-secret" not in str(catalogue)
        edit = client.put(f"/api/v2/admin/ai/providers/{saved['id']}",
                          json={"expected_revision": 1, "config": saved["config"]})
        assert edit.status_code == 200, edit.text
        versions = client.get(f"/api/v2/admin/ai/providers/{saved['id']}/versions").json()["items"]
        assert [v["revision"] for v in versions] == [2, 1]
        assert {v["source"] for v in versions} == {"saved"}
        assert "isolated-provider-secret" not in str(versions)
        saved = edit.json()
        request_id = uuid4()
        call = submit(client, saved, request_id)
        assert submit(client, saved, request_id)["id"] == call["id"]
        with database.tx(ai_admin=True) as db:
            assert db.execute("SELECT count(*) AS n FROM projects").fetchone()["n"] == 0
            job = db.execute("SELECT * FROM jobs WHERE id=%s", (call["job_id"],)).fetchone()
            assert job["project_id"] is None and job["params"]["execution_actor"]["user_id"] == str(LOCAL_USER)
        sent = []
        def complete(request):
            sent.append(request)
            return response(request)
        worker = AIWorker(database, settings, transport=httpx.MockTransport(complete))
        assert worker.once()
        status = client.get(f"/api/v2/ai/calls/{call['id']}/status").json()
        assert status["status"] == "completed", status
        assert status["response_text"] == "diagnostic result" and status["usage"]["total_tokens"] == 5
        assert float(status["cost_usd"]) == 0.000008
        assert len(sent) == 1
        with database.tx(ai_admin=True) as db:
            db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (call["job_id"],))
        assert worker.once() and len(sent) == 1
        exported = client.get(f"/api/v2/ai/calls/{call['id']}/export")
        assert exported.status_code == 200 and "isolated-provider-secret" not in exported.text
        assert client.get("/api/v2/ai/calls").json()["items"][0]["id"] == call["id"]
        cancelled = submit(client, saved)
        assert client.post(f"/api/v2/ai/calls/{cancelled['id']}/cancel").json()["cancel_requested"]
        assert worker.once()
        assert client.get(f"/api/v2/ai/calls/{cancelled['id']}").json()["status"] == "cancelled"
        assert len(sent) == 1


def test_management_permission_does_not_grant_paid_service_use(database):
    with host(database) as (client, _):
        saved = provider(client)
        administrator = permissions.enrich(database, {"id": LOCAL_USER})
        user = auth.create_user(database, "catalogue-manager", PASSWORD)
        role = permissions.save_role(database, administrator, key="catalogue-management", name="manager",
                                     grants=[{"action": "services.manage", "scope": "platform"},
                                             {"action": "services.read", "scope": "platform"}])
        permissions.assign_roles(database, administrator, user["id"], [role["id"]])
        token = client.post("/api/v2/auth/token", json={"username": user["username"], "password": PASSWORD}).json()
        header = {"Authorization": "Bearer " + token["access_token"]}
        assert client.get("/api/v2/ai/providers", headers=header).status_code == 200
        denied = client.post(f"/api/v2/ai/providers/{saved['id']}/test", headers=header,
                             json={"request_id": str(uuid4()), "prompt": "must not send"})
        assert denied.status_code == 403, denied.text
        with database.tx(ai_admin=True) as db:
            assert not db.execute("SELECT id FROM ai_calls").fetchall()


def test_ordinary_tool_configuration_does_not_require_paid_service_permission(database):
    from test_ai_tools import configured

    with host(database) as (client, _):
        project, run, _checkpoint, image, config, _provider = configured(database, client)
        administrator = permissions.enrich(database, {"id": LOCAL_USER})
        user = auth.create_user(database, "tool-configuration-only", PASSWORD)
        role = permissions.save_role(database, administrator, key="tool-config-only", name="configure tools",
            grants=[{"action": "runs.configure", "scope": "member_projects"},
                    {"action": "runs.read", "scope": "member_projects"}])
        permissions.assign_roles(database, administrator, user["id"], [role["id"]])
        with database.tx(project) as db:
            db.execute("INSERT INTO members VALUES(%s,%s,'researcher')", (project, user["id"]))
        token = client.post("/api/v2/auth/token", json={"username": user["username"], "password": PASSWORD}).json()
        header = {"Authorization": "Bearer " + token["access_token"]}
        path = f"/api/v2/projects/{project}/runs/{run}/ai-tools"
        saved = client.put(path, headers=header, json={"expected_revision": 1,
                                                      "config": config.model_dump(mode="json")})
        assert saved.status_code == 200, saved.text
        assert saved.json()["revision"] == 2
        denied = client.post(path + "/requests", headers=header,
                             json={"request_id": str(uuid4()), "purpose": "environment"})
        assert denied.status_code == 403, denied.text
        with database.tx(project) as db:
            assert not db.execute("SELECT id FROM ai_calls").fetchall()
        assert database.load_checkpoint(project, run)[1].digest == image.digest


def test_service_delegation_reused_then_revoked_before_send_preserves_completed_evidence(database):
    with host(database) as (client, settings):
        saved = provider(client)
        signed = client.post("/api/v2/account/delegations", json={
            "name": "AI service fixture", "source": "ai", "actions": [
                {"action": "services.read", "scope": "platform"},
                {"action": "services.use", "scope": "platform"}],
            "resources": [{"kind": "service", "id": saved["id"]}],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        })
        assert signed.status_code == 201, signed.text
        grant = signed.json()
        owner_header = dict(client.headers)
        client.headers["Authorization"] = "Bearer " + grant["access_token"]
        assert client.get("/api/v2/ai/providers").json()["providers"][0]["id"] == saved["id"]
        call = submit(client, saved)
        sent = []
        worker = AIWorker(database, settings, transport=httpx.MockTransport(lambda r: sent.append(r) or response(r)))
        assert worker.once()
        with database.tx(ai_admin=True) as db:
            completed = db.execute("SELECT response_text,cost_usd,status FROM ai_calls WHERE id=%s", (call["id"],)).fetchone()
            lineage = db.execute("SELECT params FROM jobs WHERE id=%s", (call["job_id"],)).fetchone()["params"]["execution_actor"]
        assert lineage["delegation_id"] == grant["delegation"]["id"] and lineage["source"] == "ai"
        pending = submit(client, saved)
        client.headers.update(owner_header)
        assert client.delete("/api/v2/account/delegations/" + grant["delegation"]["id"]).status_code == 200
        assert worker.once()
        assert client.get(f"/api/v2/ai/calls/{pending['id']}").json()["status"] == "failed"
        with database.tx(ai_admin=True) as db:
            db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (call["job_id"],))
        assert worker.once() and len(sent) == 1
        with database.tx(ai_admin=True) as db:
            assert db.execute("SELECT response_text,cost_usd,status FROM ai_calls WHERE id=%s", (call["id"],)).fetchone() == completed


def test_platform_sent_request_is_uncertain_and_never_resent(database):
    with host(database) as (client, settings):
        saved = provider(client)
        call = submit(client, saved)
        with database.tx(ai_admin=True) as db:
            db.execute("UPDATE ai_calls SET sent_at=now(),status='sending' WHERE id=%s", (call["id"],))
        sent = []
        assert AIWorker(database, settings, transport=httpx.MockTransport(lambda r: sent.append(r) or response(r))).once()
        row = client.get(f"/api/v2/ai/calls/{call['id']}").json()
        assert row["status"] == "uncertain" and not sent


def test_global_request_identity_serializes_cross_provider_conflicts_but_not_accounts(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from threemind_lab import ai_providers
    from threemind_lab.database import Conflict

    with host(database) as (client, settings):
        first, second = provider(client), provider(client)
        request_id, gate = uuid4(), Barrier(2)

        def send(saved):
            gate.wait(5)
            try:
                return ai_providers.enqueue(database, settings, None, LOCAL_USER, saved["id"],
                    request_id=request_id, purpose="provider_test", prompt={"system": "test", "user": "same identifier"})
            except Conflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, (first, second)))
        assert sum(value is not None for value in results) == 1
        root = permissions.enrich(database, {"id": LOCAL_USER})
        user = auth.create_user(database, "second-diagnostic-account", PASSWORD)
        role = permissions.save_role(database, root, key="diagnostic-fixture", name="diagnostics",
            grants=[{"action": "services.read", "scope": "platform"}, {"action": "services.use", "scope": "platform"}])
        permissions.assign_roles(database, root, user["id"], [role["id"]])
        other = ai_providers.enqueue(database, settings, None, user["id"], first["id"],
            request_id=request_id, purpose="provider_test", prompt={"system": "test", "user": "same identifier"})
        assert other["actor_id"] == user["id"]
        with database.tx(ai_admin=True) as db:
            assert db.execute("SELECT count(*) AS n FROM ai_calls").fetchone()["n"] == 2


def test_paid_service_delegation_cannot_inject_and_revoked_stimulation_preserves_response(database):
    from lease_helpers import claim_as
    from psycopg.types.json import Jsonb
    from test_ai_providers import chat_response
    from test_ai_tools import configured

    from threemind_lab import ai_tools

    with host(database) as (client, settings):
        project, run, _cp, image, _config, _provider = configured(database, client)
        owner_headers = dict(client.headers)
        actions = [{"action": "services.use", "scope": "member_projects"}]
        definition = {"name": "limited AI environment", "source": "ai", "actions": actions,
            "resources": [{"kind": "project", "id": str(project)}],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}
        signed = client.post("/api/v2/account/delegations", json=definition).json()
        client.headers["Authorization"] = "Bearer " + signed["access_token"]
        endpoint = f"/api/v2/projects/{project}/runs/{run}/ai-tools/requests"
        denied = client.post(endpoint, json={"request_id": str(uuid4()), "purpose": "environment"})
        assert denied.status_code == 403, denied.text
        with database.tx(project) as db:
            assert not db.execute("SELECT id FROM ai_calls").fetchall()
        client.headers.update(owner_headers)
        definition["actions"] = actions + [{"action": "runs.stimulate", "scope": "member_projects"}]
        signed = client.post("/api/v2/account/delegations", json=definition).json()
        client.headers["Authorization"] = "Bearer " + signed["access_token"]
        allowed = client.post(endpoint, json={"request_id": str(uuid4()), "purpose": "environment"})
        assert allowed.status_code == 202, allowed.text
        call = allowed.json()
        job = claim_as(database, "fixture-before-permission-change", queue="ai")
        worker = AIWorker(database, settings, transport=httpx.MockTransport(lambda _: chat_response("diagnostic result")))
        assert worker.run(job)["status"] == "completed"
        with database.tx(project) as db:
            db.execute("UPDATE platform_delegations SET actions=%s WHERE id=%s",
                       (Jsonb(actions), signed["delegation"]["id"]))
        # Reclaim the original delegation under its current narrower permissions.
        permissions.restore_execution_actor(database, job["params"]["execution_actor"],
            action="services.use", project=project,
            resources=[{"kind": "project", "id": str(project)}])
        result = ai_tools.apply_completed(database, job)
        assert result["application_status"] == "rejected"
        with database.tx(project) as db:
            assert not db.execute("SELECT id FROM input_envelopes WHERE source='ai-environment'").fetchall()
            original = db.execute("SELECT response_text,status FROM ai_calls WHERE id=%s", (call["id"],)).fetchone()
            assert original == {"response_text": "diagnostic result", "status": "completed"}
        assert database.load_checkpoint(project, run)[1].digest == image.digest
