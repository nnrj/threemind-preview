from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from threemind_lab import execution_health, notifications, worker_health
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER
from threemind_lab.health_schema import HealthConfig, HealthRule
from threemind_lab.notification_schema import NotificationConfig, NotificationEdit
from threemind_lab.notification_worker import NotificationWorker


def test_sampled_health_cached_values_missing_and_inactivity_do_not_accumulate_false_holds():
    config = HealthConfig(
        enabled=True, rules=[HealthRule(id="rss", metric="worker_rss_mib", threshold=100, hold_us=10_000_000)]
    )

    def sample(time, value=110, signature="a", applicable=True):
        return {
            "metrics": {
                "worker_rss_mib": {
                    "value": value,
                    "time_us": str(time),
                    "sample_signature": signature,
                    "applicable": applicable,
                }
            }
        }

    entries, state = execution_health.evaluate(config, sample(0), {}, {})
    assert not entries and state["rss"]["status"] == "pending"
    entries, state = execution_health.evaluate(config, sample(20_000_000), state, {})
    assert not entries and state["rss"]["status"] == "pending"
    entries, state = execution_health.evaluate(config, sample(21_000_000, signature="b"), state, {})
    assert [e["code"] for e in entries] == ["triggered"]
    assert entries[0]["version"] == execution_health.VERSION
    entries, state = execution_health.evaluate(config, sample(30_000_000, None, signature="stale"), state, {})
    assert [e["code"] for e in entries] == ["missing_evidence"]
    entries, state = execution_health.evaluate(config, sample(35_000_000, 110, signature="c"), state, {})
    assert not entries and state["rss"]["status"] == "pending"
    entries, state = execution_health.evaluate(config, sample(40_000_000, applicable=False), state, {})
    assert not entries and state["rss"]["status"] == "inactive"
    with pytest.raises(ValueError):
        HealthConfig(enabled=True, rules=[{"id": "rss", "metric": "activation_intent"}])


def policy(database, project, **health):
    config = NotificationConfig(enabled=True, execution_health=HealthConfig(enabled=True, **health))
    row = notifications.save_policy(
        database, Settings(database_url=database.test_url), project, LOCAL_USER, NotificationEdit(config=config)
    )
    return row


def test_execution_warning_pipeline_evidence_immutable_no_mail_and_project_boundaries(database):
    project = database.create_project({"id": LOCAL_USER}, "Execution health fixture")["id"]
    settings = Settings(database_url=database.test_url)
    rule = HealthRule(id="waiting", threshold=0, hold_us=0, cooldown_us=300_000_000)
    saved = policy(database, project, rules=[rule])
    task = uuid4()
    with database.tx(project) as db:
        db.execute("INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'analysis','{}')", (task, project))
        db.execute(
            "UPDATE jobs SET available_at=clock_timestamp()-interval '20 seconds',status_changed_at=clock_timestamp()-interval '20 seconds' WHERE id=%s",
            (task,),
        )
    watcher = NotificationWorker(database, settings)
    assert not watcher.once()  # Local facts are recorded; no mail job is made.
    with database.tx(project) as db:
        row = db.execute("SELECT * FROM execution_health_monitors").fetchone()
        notices = db.execute("SELECT * FROM notifications WHERE kind='execution_health'").fetchall()
        assert row["snapshot"]["metrics"]["ready_wait_s"]["ready_tasks"] == 1
        assert len(notices) == 1 and notices[0]["facts"]["code"] == "triggered"
        assert notices[0]["email_status"] == "disabled"
        assert db.execute("SELECT count(*) AS n FROM jobs").fetchone()["n"] == 1
        assert not db.execute("SELECT 1 FROM runs").fetchone()
    execution_health.process(database, project)
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM notifications").fetchone()["n"] == 1
        # Force unknown history; it cannot be silently represented as wait=0.
        db.execute("UPDATE jobs SET status_changed_at=NULL WHERE id=%s", (task,))
    execution_health.process(database, project)
    with database.tx(project) as db:
        latest = db.execute("SELECT facts FROM notifications ORDER BY ordinal DESC LIMIT 1").fetchone()["facts"]
        assert latest["code"] == "missing_evidence"
        db.execute("UPDATE jobs SET status='done' WHERE id=%s", (task,))
    with TestClient(create_app(settings, database)) as client:
        root = f"/api/v2/projects/{project}/notifications"
        assert client.get(root + "/execution-health").json()["monitor"]["policy_revision"] == saved["revision"]
        other = client.post("/api/v2/projects", json={"name": "Other health boundary"}).json()["id"]
        assert client.get(root.replace(str(project), other) + "/execution-health").json()["monitor"] is None
        with database.tx(other) as db:
            assert not db.execute("SELECT * FROM execution_health_monitors").fetchall()
        disabled = NotificationConfig(enabled=True, execution_health=HealthConfig())
        response = client.put(
            root + "/settings",
            json={"expected_revision": saved["revision"], "config": disabled.model_dump(mode="json")},
        )
        assert response.status_code == 200
        assert not client.get(root + "/execution-health").json()["monitor"]["enabled"]


def test_worker_resource_coverage_expired_lease_and_status_age_are_explicit(database):
    project = database.create_project({"id": LOCAL_USER}, "Health resource fixture")["id"]
    now = datetime.now(UTC) + timedelta(seconds=1)
    database.announce_worker("health-fixture", {"features": {}})
    health = worker_health.sample()
    assert health["version"] == "threemind.worker-health/1"
    assert health["sample_id"] == worker_health.sample()["sample_id"]
    job = uuid4()
    with database.tx(project) as db:
        db.execute(
            "INSERT INTO jobs(id,project_id,kind,status,worker_id,lease_until,params) VALUES(%s,%s,'analysis','leased','health-fixture',%s,'{}')",
            (job, project, now + timedelta(seconds=60)),
        )
        row = execution_health.snapshot(db, project, now=now)
        memory = row["metrics"]["worker_rss_mib"]
        assert memory["applicable"] and memory["known_workers"] == 1 and memory["value"] > 0
        assert row["metrics"]["commit_age_s"]["applicable"] is False
        db.execute("UPDATE workers SET health_received_at=%s WHERE id='health-fixture'", (now - timedelta(seconds=46),))
        stale = execution_health.snapshot(db, project, now=now)
        assert stale["metrics"]["worker_rss_mib"]["value"] is None
        assert stale["metrics"]["worker_rss_mib"]["known_workers"] == 0
        db.execute("UPDATE jobs SET lease_until=%s WHERE id=%s", (now - timedelta(seconds=1), job))
        expired = execution_health.snapshot(db, project, now=now)
        assert expired["metrics"]["expired_leases"]["value"] == 1
        assert not expired["metrics"]["worker_rss_mib"]["applicable"]
        db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (job,))
        assert (
            db.execute("SELECT status_changed_at FROM jobs WHERE id=%s", (job,)).fetchone()["status_changed_at"]
            is not None
        )


def test_population_task_failures_emit_existing_notifications_without_marking_core_dead(database):
    project = database.create_project({"id": LOCAL_USER}, "Population failure fixture")["id"]
    # Use the normal task state trigger with explicit engineering fixtures.
    policy(database, project, rules=[])
    with database.tx(project) as db:
        for kind in ("ecology", "evolution", "report_source", "study"):
            job = uuid4()
            db.execute(
                "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,%s,%s)", (job, project, kind, Jsonb({}))
            )
            db.execute("UPDATE jobs SET status='failed',error='fixture execution failure' WHERE id=%s", (job,))
        notices = db.execute("SELECT kind,facts FROM notifications ORDER BY ordinal").fetchall()
        assert len(notices) == 4 and all(n["kind"] == "job_failed" for n in notices)
        assert {n["facts"]["job_kind"] for n in notices} == {"ecology", "evolution", "report_source", "study"}
        assert not db.execute("SELECT 1 FROM notifications WHERE kind='run_dead'").fetchone()


def test_observer_failure_is_visible_redacted_and_does_not_stop_other_projects(database, monkeypatch):
    project = database.create_project({"id": LOCAL_USER}, "Health exception isolation")["id"]
    policy(database, project, rules=[])
    other = database.create_project({"id": LOCAL_USER}, "Unaffected health project")["id"]
    policy(database, other, rules=[])
    original = execution_health.snapshot

    def broken(*args, **kwargs):
        if str(args[1]) != str(project):
            return original(*args, **kwargs)
        raise RuntimeError("sensitive diagnostic text must not be copied")

    monkeypatch.setattr(execution_health, "snapshot", broken)
    assert not NotificationWorker(database, Settings(database_url=database.test_url)).once()
    with database.tx(project) as db:
        row = db.execute("SELECT * FROM execution_health_monitors").fetchone()
        assert not row["enabled"] and "RuntimeError" in row["error"]
        assert "sensitive" not in row["error"] and not row["snapshot"]
        assert not db.execute("SELECT 1 FROM jobs").fetchone()
    with database.tx(other) as db:
        row = db.execute("SELECT * FROM execution_health_monitors").fetchone()
        assert row["enabled"] and row["snapshot"]["observed_at"] and row["error"] is None


def test_old_mail_worker_cannot_claim_policy_with_execution_health_fields(database):
    project = database.create_project({"id": LOCAL_USER}, "Health capability admission")["id"]
    database.announce_worker("old-mail", {"features": {"worker.notifications": {"state": "available"}}})
    with database.tx(project) as db:
        db.execute("INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'notification','{}')", (uuid4(), project))
    assert database.claim("old-mail", queue="notification") is None
