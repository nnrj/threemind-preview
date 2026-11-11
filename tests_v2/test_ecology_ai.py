import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from test_ai_providers import create as provider
from test_ai_providers import get_call
from test_ecology_observer_api import drain
from test_ecology_store import setup
from test_research_ai import reply

from threemind_lab import ecology_ai, ecology_observers
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_runtime.ecology_observer import ObserverConfig, WarningRule


def fixture(database, **configuration):
    project, campaign, worker = setup(database)
    assert worker.once()
    settings = Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),))
    external = provider(database, settings, project)
    config = ecology_ai.AIConfig(enabled=True, provider_id=external["id"], **configuration)
    ecology_ai.configure(database, settings, project, campaign["id"], LOCAL_USER, config, 0)
    with database.tx(project) as db:
        final = ecology_observers.subject(db, campaign["id"])
    scope = ecology_ai.Scope(configuration_revision=1, checkpoint_id=final["checkpoint_id"])
    return project, campaign, worker, settings, config, scope


def ask(database, settings, project, identity, scope):
    with database.tx(project, repeatable=True) as db:
        preview = ecology_ai.prepare(db, identity, scope)
    body = scope.model_dump(mode="json") | {"operation_id": str(uuid4()), "evidence_hash": preview["evidence_hash"]}
    return ecology_ai.request(database, settings, project, identity, LOCAL_USER, body), body, preview


def proposal(evidence):
    return {
        "summary": {
            "text": "完整提交范围的生态摘要，不能据此断定意识。",
            "source_refs": [evidence["source_refs"]["population"]],
        },
        "observations": [{"text": "事件计数包含全部已记录事件。", "source_refs": [evidence["source_refs"]["events"]]}],
        "hypotheses": [],
        "suggestions": [
            {"text": "后续可显式配置隔离评估以检验假设。", "source_refs": [evidence["source_refs"]["warnings"]]}
        ],
        "limitations": ["只覆盖已提交恢复点；没有证明意识、意图或统计独立。"],
    }


def hashes(database, project):
    with database.tx(project) as db:
        return db.execute("SELECT id,state_hash FROM ecology_checkpoints ORDER BY id").fetchall(), db.execute(
            "SELECT checkpoint_id,state_hash FROM ecology_checkpoint_members ORDER BY checkpoint_id"
        ).fetchall()


def test_ecology_ai_complete_frozen_evidence_rules_mock_output_and_no_core_effects(database):
    project, campaign, worker, settings, _config, scope = fixture(database)
    ecology_observers.configure(
        database,
        project,
        campaign["id"],
        LOCAL_USER,
        ObserverConfig(
            enabled=True, start_from="beginning", rules=[WarningRule(id="births", metric="births", threshold=1)]
        ),
        0,
    )
    drain(database, worker, campaign["id"])
    before = hashes(database, project)
    call, body, preview = ask(database, settings, project, campaign["id"], scope)
    evidence = preview["evidence"]
    with database.tx(project) as db:
        assert (
            evidence["facts"]["events"]["total"]
            == db.execute("SELECT count(*) AS n FROM ecology_events").fetchone()["n"]
        )
    assert evidence["facts"]["warnings"]["counts"]
    assert evidence["facts"]["population"]["individuals"] == 6
    assert evidence["facts"]["population"]["births"] == 4
    assert ecology_ai.request(database, settings, project, campaign["id"], LOCAL_USER, body)["id"] == call["id"]
    with pytest.raises(Conflict):
        ecology_ai.request(database, settings, project, campaign["id"], LOCAL_USER, body | {"first_revision": 2})
    old = {"queue": "ai", "features": {"worker.ai": {"state": "available"}}}
    assert database.claim("old-observation-ai", queue="ai", capabilities=old) is None
    received = []
    ai = reply(database, settings, json.dumps(proposal(evidence)), received)
    assert ai.once()
    result = get_call(database, project, call)["result"]
    assert result["application_status"] == "recorded" and result["review_status"] == "unreviewed"
    assert result["intervention_performed"] is False and len(received) == 1
    assert before == hashes(database, project)
    # Retry the completed job: apply/output are idempotent and never re-send.
    with database.tx(project) as db:
        db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (get_call(database, project, call)["job_id"],))
    assert ai.once() and len(received) == 1


def test_ecology_ai_rejects_forged_refs_facts_stale_scope_and_changed_config(database):
    project, campaign, _worker, settings, config, scope = fixture(database)
    call, body, preview = ask(database, settings, project, campaign["id"], scope)
    invalid = proposal(preview["evidence"]) | {"facts": {"births": 99999}}
    assert reply(database, settings, json.dumps(invalid)).once()
    assert get_call(database, project, call)["result"]["application_status"] == "rejected"
    call, _, _ = ask(database, settings, project, campaign["id"], scope)
    invalid = proposal(preview["evidence"])
    invalid["summary"]["source_refs"] = ["unprovided-source"]
    assert reply(database, settings, json.dumps(invalid)).once()
    assert get_call(database, project, call)["result"]["application_status"] == "rejected"
    with pytest.raises(Conflict):
        ecology_ai.request(
            database,
            settings,
            project,
            campaign["id"],
            LOCAL_USER,
            body | {"operation_id": str(uuid4()), "evidence_hash": "0" * 64},
        )
    call, _, _ = ask(database, settings, project, campaign["id"], scope)
    ecology_ai.configure(
        database, settings, project, campaign["id"], LOCAL_USER, config.model_copy(update={"enabled": False}), 1
    )
    received = []
    assert reply(database, settings, json.dumps(proposal(preview["evidence"])), received).once()
    assert not received
    assert get_call(database, project, call)["status"] == "cancelled"
    assert hashes(database, project)[0]


def test_ecology_ai_scheduler_terminal_summary_once_and_failure_stop(database):
    project, campaign, _worker, settings, _config, _scope = fixture(database, automatic=True)
    at = datetime(2030, 1, 1, tzinfo=UTC)
    ecology_ai.process(database, settings, project, campaign["id"], now=at)
    with database.tx(project) as db:
        row = ecology_ai.current(db, campaign["id"])
        call = get_call(database, project, {"id": row["state"]["pending"]})
    assert "finished_summary" in call["evidence"]["trigger"]
    assert call["evidence"]["scope"]["first_revision"] == 1
    ecology_ai.process(database, settings, project, campaign["id"], now=at + timedelta(hours=1))
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM ai_calls").fetchone()["n"] == 1
    assert reply(database, settings, json.dumps(proposal(call["evidence"]))).once()
    ecology_ai.process(database, settings, project, campaign["id"], now=at + timedelta(hours=2))
    with database.tx(project) as db:
        assert not ecology_ai.current(db, campaign["id"])["enabled"]
    # Explicitly configure another revision. A malformed response blocks its
    # schedule; later ticks do not repeatedly spend on the same failed summary.
    config = ecology_ai.AIConfig(enabled=True, automatic=True, provider_id=call["provider_id"])
    ecology_ai.configure(database, settings, project, campaign["id"], LOCAL_USER, config, 1)
    ecology_ai.process(database, settings, project, campaign["id"], now=at)
    assert reply(database, settings, '{"summary":"invalid"}').once()
    ecology_ai.process(database, settings, project, campaign["id"], now=at + timedelta(hours=1))
    with database.tx(project) as db:
        row = ecology_ai.current(db, campaign["id"])
        assert row["state"]["blocked"] and not row["enabled"]
        count = db.execute("SELECT count(*) AS n FROM ai_calls").fetchone()["n"]
    for n in range(3):
        ecology_ai.process(database, settings, project, campaign["id"], now=at + timedelta(days=n + 1))
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM ai_calls").fetchone()["n"] == count


def test_ecology_ai_api_project_revision_privileges_and_limits(database):
    project, campaign, _worker, settings, _config, scope = fixture(database, maximum_calls=1)
    root = f"/api/v2/projects/{project}/ecologies/{campaign['id']}/observer/ai"
    with TestClient(create_app(settings, database)) as client:
        assert not client.get(root).json()["defaults"]["enabled"]
        assert client.post(root + "/validate", json={"enabled": "false"}).status_code == 422
        assert (
            client.post(root + "/configuration", json={"configuration": {}, "expected_revision": 0}).status_code == 409
        )
        assert client.get(root + "/revisions").json()["rows"][0]["revision"] == 1
        call, _body, preview = ask(database, settings, project, campaign["id"], scope)
        assert reply(database, settings, json.dumps(proposal(preview["evidence"]))).once()
        assert client.get(root + "/calls").json()["rows"][0]["id"] == str(call["id"])
        with pytest.raises(Conflict, match="上限"):
            ask(database, settings, project, campaign["id"], scope)
        other = client.post("/api/v2/projects", json={"name": "Other AI scope"}).json()["id"]
        assert client.get(root.replace(str(project), other)).status_code == 404
        with database.tx(other) as db:
            assert not db.execute("SELECT * FROM ecology_ai_sources").fetchall()
            assert not db.execute("SELECT * FROM ecology_ai_schedules").fetchall()
        with pytest.raises(psycopg.Error), database.tx(project) as db:
            db.execute("UPDATE ecology_ai_revisions SET configuration='{}' WHERE campaign_id=%s", (campaign["id"],))
        with database.tx(project) as db:
            db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (project, LOCAL_USER))
        assert client.post(root + "/preview", json=scope.model_dump(mode="json")).status_code == 403
        assert client.get(root + "/calls").status_code == 200


def test_ecology_ai_periodic_clock_coalescing_late_warnings_and_scheduler_scope(database):
    project, campaign, worker, settings, config, scope = fixture(
        database,
        automatic=True,
        cadence_clock="model",
        on_finished=False,
        on_body_failure=False,
        on_birth_deferred=False,
    )
    identity = campaign["id"]
    # Only the external job status is held open for this scheduler fixture.
    # The already committed model clocks and brain evidence are not changed.
    with database.tx(project) as db:
        db.execute("UPDATE ecology_campaigns SET status='active' WHERE id=%s", (identity,))
    at = datetime(2030, 1, 1, tzinfo=UTC)
    before = hashes(database, project)
    ecology_ai.process(database, settings, project, identity, now=at)
    with database.tx(project) as db:
        row = ecology_ai.current(db, identity)
        first = get_call(database, project, {"id": row["state"]["pending"]})
    assert first["evidence"]["trigger"] == ["periodic"]
    assert reply(database, settings, json.dumps(proposal(first["evidence"]))).once()
    # Advancing only the host clock cannot satisfy a model-time interval.
    ecology_ai.process(database, settings, project, identity, now=at + timedelta(days=10))
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM ai_calls").fetchone()["n"] == 1
    # Observation arrives late from much earlier checkpoints. Its warning must
    # widen the declared evidence range; it cannot be cited but omitted.
    ecology_observers.configure(
        database,
        project,
        identity,
        LOCAL_USER,
        ObserverConfig(
            enabled=True, start_from="beginning", rules=[WarningRule(id="births", metric="births", threshold=1)]
        ),
        0,
    )
    with database.tx(project) as db:
        db.execute("UPDATE ecology_campaigns SET status='completed' WHERE id=%s", (identity,))
    drain(database, worker, identity)
    ecology_ai.process(database, settings, project, identity, now=at + timedelta(days=11))
    with database.tx(project) as db:
        row = ecology_ai.current(db, identity)
        second = get_call(database, project, {"id": row["state"]["pending"]})
    assert second["evidence"]["trigger"] == ["warning"]
    assert any(item["code"] == "triggered" for item in second["evidence"]["facts"]["warnings"]["counts"])
    assert (
        second["evidence"]["scope"]["first_revision"]
        < scope.configuration_revision + first["evidence"]["last_checkpoint"]["revision"]
    )
    assert reply(database, settings, json.dumps(proposal(second["evidence"]))).once()
    assert before == hashes(database, project)
    # A deployment scheduler discovers due subscriptions through the explicit
    # admin context, while another project cannot read their state.
    ecology_ai.configure(
        database, settings, project, identity, LOCAL_USER, config.model_copy(update={"on_finished": True}), 1
    )
    ecology_ai.tick(database, settings)
    with database.tx(project) as db:
        assert ecology_ai.current(db, identity)["state"].get("pending")
