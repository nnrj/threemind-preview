"""Isolated AI permission timing and automatic delegation provenance; no real provider."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from psycopg.types.json import Jsonb
from test_ai_catalogue import host
from test_ai_providers import chat_response
from test_ai_providers import create as provider
from test_ai_tools import configured
from test_ecology_store import setup

from threemind_lab import ai_scheduler, ecology_ai, permissions
from threemind_lab.ai_worker import AIWorker
from threemind_lab.database import LOCAL_USER

pytestmark = pytest.mark.session_auth


def delegated(client, project, *actions):
    response = client.post("/api/v2/account/delegations", json={
        "name": "bounded automatic fixture", "source": "ai",
        "actions": [{"action": action, "scope": "member_projects"} for action in actions],
        "resources": [{"kind": "project", "id": str(project)}],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    })
    assert response.status_code == 201, response.text
    return response.json()


def invalidate(database, client, project, signed, owner_headers, reason):
    client.headers.update(owner_headers)
    if reason == "revoked":
        assert client.delete("/api/v2/account/delegations/" + signed["delegation"]["id"]).status_code == 200
    else:
        with database.tx(project) as db:
            db.execute("UPDATE platform_delegations SET expires_at=now()-interval '1 second' WHERE id=%s",
                       (signed["delegation"]["id"],))


@pytest.mark.parametrize("purpose,required", [("environment", "runs.stimulate"), ("interpretation", "runs.observe")])
def test_worker_rechecks_target_permission_before_sending_frozen_prompt(database, purpose, required):
    with host(database) as (client, settings):
        project, run, _cp, image, _config, _provider = configured(database, client)
        signed = delegated(client, project, "services.use", required)
        client.headers["Authorization"] = "Bearer " + signed["access_token"]
        response = client.post(f"/api/v2/projects/{project}/runs/{run}/ai-tools/requests",
                               json={"request_id": str(uuid4()), "purpose": purpose})
        assert response.status_code == 202, response.text
        call = response.json()
        # Narrow the still-valid delegation: service spending stays permitted,
        # but the target operation that authorized this prompt no longer does.
        with database.tx(project) as db:
            db.execute("UPDATE platform_delegations SET actions=%s WHERE id=%s",
                (Jsonb([{"action": "services.use", "scope": "member_projects"}]), signed["delegation"]["id"]))
        sent = []
        assert AIWorker(database, settings,
                        transport=httpx.MockTransport(lambda r: sent.append(r) or chat_response("unused"))).once()
        with database.tx(project) as db:
            stopped = db.execute("SELECT status,sent_at,response_text,cost_usd FROM ai_calls WHERE id=%s",
                                 (call["id"],)).fetchone()
        assert stopped["status"] == "failed" and stopped["sent_at"] is None and stopped["response_text"] == ""
        assert float(stopped["cost_usd"]) == 0
        assert not sent and database.load_checkpoint(project, run)[1].digest == image.digest


def test_automatic_enable_requires_service_and_specific_target_operation(database):
    with host(database) as (client, _):
        project, run, _cp, image, config, _provider = configured(database, client)
        signed = delegated(client, project, "runs.configure", "services.use")
        client.headers["Authorization"] = "Bearer " + signed["access_token"]
        config.environment.automatic = True
        response = client.put(f"/api/v2/projects/{project}/runs/{run}/ai-tools",
            json={"expected_revision": 1, "config": config.model_dump(mode="json")})
        assert response.status_code == 403, response.text
        with database.tx(project) as db:
            assert db.execute("SELECT revision FROM ai_run_tools WHERE run_id=%s", (run,)).fetchone()["revision"] == 1
            assert not db.execute("SELECT id FROM ai_calls").fetchall()
        assert database.load_checkpoint(project, run)[1].digest == image.digest


def test_revoked_already_sent_request_stays_uncertain_and_preserves_partial_evidence(database):
    with host(database) as (client, settings):
        project, run, _cp, image, _config, _provider = configured(database, client)
        owner_headers = dict(client.headers)
        signed = delegated(client, project, "services.use", "runs.stimulate")
        client.headers["Authorization"] = "Bearer " + signed["access_token"]
        response = client.post(f"/api/v2/projects/{project}/runs/{run}/ai-tools/requests",
                               json={"request_id": str(uuid4()), "purpose": "environment"})
        assert response.status_code == 202, response.text
        call = response.json()
        with database.tx(project) as db:
            db.execute("UPDATE ai_calls SET status='sending',sent_at=now(),response_text='partial remote evidence' WHERE id=%s",
                       (call["id"],))
        invalidate(database, client, project, signed, owner_headers, "revoked")
        sent = []
        assert AIWorker(database, settings,
                        transport=httpx.MockTransport(lambda r: sent.append(r) or chat_response("unused"))).once()
        with database.tx(project) as db:
            row = db.execute("SELECT status,sent_at,response_text FROM ai_calls WHERE id=%s", (call["id"],)).fetchone()
        assert row["status"] == "uncertain" and row["sent_at"] is not None
        assert row["response_text"] == "partial remote evidence"
        assert not sent and database.load_checkpoint(project, run)[1].digest == image.digest


@pytest.mark.parametrize("reason", ["revoked", "expired"])
def test_run_scheduler_preserves_original_delegation_and_never_borrows_callers_root(database, reason):
    with host(database) as (client, settings):
        project, run, _cp, image, config, _provider = configured(database, client)
        owner_headers = dict(client.headers)
        signed = delegated(client, project, "runs.configure", "services.use", "runs.stimulate")
        client.headers["Authorization"] = "Bearer " + signed["access_token"]
        config.environment.automatic = True
        config.environment.frequency_s = 1.0
        config.environment.random_frequency = False
        saved = client.put(f"/api/v2/projects/{project}/runs/{run}/ai-tools",
                          json={"expected_revision": 1, "config": config.model_dump(mode="json")})
        assert saved.status_code == 200, saved.text
        with database.tx(project) as db:
            state = db.execute("SELECT state FROM ai_tool_schedules WHERE run_id=%s", (run,)).fetchone()["state"]
            assert state["environment"]["execution_actor"]["delegation_id"] == signed["delegation"]["id"]
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
        owner = permissions.enrich(database, {"id": LOCAL_USER})
        permissions.actor_context.set(owner)
        now = datetime.now(UTC) + timedelta(seconds=2)
        ai_scheduler.process(database, settings, project, run, now=now)
        assert permissions.current_actor()["superadmin"]
        with database.tx(project) as db:
            call = db.execute("SELECT * FROM ai_calls WHERE run_id=%s", (run,)).fetchone()
            lineage = db.execute("SELECT params FROM jobs WHERE id=%s", (call["job_id"],)).fetchone()["params"]["execution_actor"]
        assert lineage["delegation_id"] == signed["delegation"]["id"] and lineage["source"] == "ai"
        invalidate(database, client, project, signed, owner_headers, reason)
        ai_scheduler.process(database, settings, project, run, now=now + timedelta(hours=1))
        assert permissions.current_actor()["superadmin"]
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM ai_calls").fetchone()["n"] == 1
            state = db.execute("SELECT state FROM ai_tool_schedules WHERE run_id=%s", (run,)).fetchone()["state"]
            assert state["environment"]["last_error"]
        sent = []
        assert AIWorker(database, settings,
                        transport=httpx.MockTransport(lambda r: sent.append(r) or chat_response("unused"))).once()
        assert not sent and database.load_checkpoint(project, run)[1].digest == image.digest
        # Resaving the same automatic configuration with a newly signed
        # delegation is an explicit renewal, not an implicit account fallback.
        renewed = delegated(client, project, "runs.configure", "services.use", "runs.stimulate")
        client.headers["Authorization"] = "Bearer " + renewed["access_token"]
        saved = client.put(f"/api/v2/projects/{project}/runs/{run}/ai-tools",
            json={"expected_revision": 2, "config": config.model_dump(mode="json")})
        assert saved.status_code == 200, saved.text
        ai_scheduler.process(database, settings, project, run, now=now + timedelta(hours=2))
        with database.tx(project) as db:
            state = db.execute("SELECT state FROM ai_tool_schedules WHERE run_id=%s", (run,)).fetchone()["state"]
            assert state["environment"]["execution_actor"]["delegation_id"] == renewed["delegation"]["id"]
            assert db.execute("SELECT count(*) AS n FROM ai_calls").fetchone()["n"] == 2
            latest = db.execute("SELECT params FROM jobs WHERE id=(SELECT job_id FROM ai_calls ORDER BY ordinal DESC LIMIT 1)").fetchone()
            assert latest["params"]["execution_actor"]["delegation_id"] == renewed["delegation"]["id"]


@pytest.mark.parametrize("reason", ["revoked", "expired"])
def test_ecology_scheduler_keeps_delegation_and_stops_after_expiry_or_revocation(database, reason):
    with host(database) as (client, settings):
        project, campaign, worker = setup(database)
        assert worker.once()
        external = provider(database, settings, project)
        owner_headers = dict(client.headers)
        signed = delegated(client, project, "services.use", "research.write")
        client.headers["Authorization"] = "Bearer " + signed["access_token"]
        config = ecology_ai.AIConfig(enabled=True, automatic=True, provider_id=external["id"])
        response = client.post(f"/api/v2/projects/{project}/ecologies/{campaign['id']}/observer/ai/configuration",
            json={"configuration": config.model_dump(mode="json"), "expected_revision": 0})
        assert response.status_code == 200, response.text
        with database.tx(project) as db:
            state = ecology_ai.current(db, campaign["id"])["state"]
            assert state["execution_actor"]["delegation_id"] == signed["delegation"]["id"]
            before = db.execute("SELECT id,state_hash FROM ecology_checkpoints ORDER BY id").fetchall()
        invalidate(database, client, project, signed, owner_headers, reason)
        owner = permissions.enrich(database, {"id": LOCAL_USER})
        permissions.actor_context.set(owner)
        ecology_ai.process(database, settings, project, campaign["id"], now=datetime.now(UTC) + timedelta(hours=1))
        assert permissions.current_actor()["superadmin"]
        with database.tx(project) as db:
            row = ecology_ai.current(db, campaign["id"])
            assert row["state"]["blocked"] and row["state"]["last_error"] and not row["enabled"]
            assert not db.execute("SELECT id FROM ai_calls").fetchall()
            assert db.execute("SELECT id,state_hash FROM ecology_checkpoints ORDER BY id").fetchall() == before
