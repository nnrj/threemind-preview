import json

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_ecology_store import setup

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, NotFound
from threemind_lab.ecology_observers import configure, detail, execute
from threemind_runtime.ecology_observer import ObserverConfig, WarningRule
from threemind_runtime.world_schema import digest


def drain(database, worker, identity):
    for _ in range(100):
        with database.tx() as db:
            # Test-clock release of this fixture's observer only; no real sleeps.
            db.execute(
                "UPDATE jobs SET available_at='1970-01-01 00:00:00+00' WHERE kind='ecology_observe' AND params->>'campaign_id'=%s",
                (str(identity),),
            )
        if not worker.once():
            return
    raise AssertionError("observer did not finish its finite fixture")


def test_observer_pipeline_freezes_sources_and_never_mutates_population(database):
    project, campaign, worker = setup(database)
    assert worker.once()
    with database.tx(project) as db:
        before = db.execute(
            "SELECT id,state_hash FROM ecology_checkpoints WHERE campaign_id=%s ORDER BY revision", (campaign["id"],)
        ).fetchall()
        brain_before = db.execute(
            "SELECT checkpoint_id,state_hash FROM ecology_checkpoint_members ORDER BY checkpoint_id"
        ).fetchall()
    config = ObserverConfig(
        enabled=True, start_from="beginning", rules=[WarningRule(id="births", metric="births", threshold=1)]
    )
    configure(database, project, campaign["id"], LOCAL_USER, config, 0)
    drain(database, worker, campaign["id"])
    with database.tx(project) as db:
        state = detail(db, campaign["id"])["observer"]
        assert state["job_status"] == "done", state["job_error"]
        records = db.execute("SELECT * FROM ecology_observer_entries ORDER BY id").fetchall()
        assert {e["kind"] for e in records} == {"event", "summary", "warning"}
        assert any(e["body"]["code"] == "triggered" for e in records)
        assert (
            before
            == db.execute(
                "SELECT id,state_hash FROM ecology_checkpoints WHERE campaign_id=%s ORDER BY revision",
                (campaign["id"],),
            ).fetchall()
        )
        assert (
            brain_before
            == db.execute(
                "SELECT checkpoint_id,state_hash FROM ecology_checkpoint_members ORDER BY checkpoint_id"
            ).fetchall()
        )
        for row in records:
            content = row["body"].copy()
            assert content.pop("content_hash") == digest(content)
            assert row["body"]["source"]["configuration_hash"] == digest(config.model_dump(mode="json"))
    root = f"/api/v2/projects/{project}/ecologies/{campaign['id']}/observer"
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        assert client.get(root).json()["observer"]["job_status"] == "done"
        bad = config.model_dump(mode="json") | {"enabled": "false"}
        assert client.post(root + "/validate", json=bad).status_code == 422
        assert (
            client.post(
                root + "/configuration", json={"configuration": config.model_dump(mode="json"), "expected_revision": 0}
            ).status_code
            == 409
        )
        feed = client.get(root + "/entries").json()
        assert feed["rows"]
        baseline = client.get(root + "/live?configuration_revision=1").json()
        assert baseline["baseline"] and not baseline["rows"]
        live = client.get(root + "/live?configuration_revision=1&after=0").json()
        presentation = [record for record in records if record["kind"] in ("summary", "warning")]
        assert len(live["rows"]) <= 3 and live["omitted"] + len(live["rows"]) == len(presentation)
        assert [int(row["id"]) for row in live["rows"]] == [row["id"] for row in presentation[-3:]]
        assert live["cursor"] == baseline["cursor"]
        assert (
            client.get(root + "/live", params={"configuration_revision": 1, "after": live["cursor"]}).json()["rows"]
            == []
        )
        # A historical ceiling never leaks later checkpoint narratives.
        first = client.get(root + "/entries", params={"checkpoint_id": str(before[0]["id"])}).json()
        assert all(e["body"]["source"]["checkpoint_revision"] == 1 for e in first["rows"])
        response = client.get(root + "/export?configuration_revision=1")
        assert response.status_code == 200
        exported = [json.loads(line) for line in response.content.splitlines()]
        assert exported[0]["entry_count"] == len(records) == len(exported) - 1
        assert {e["content_hash"] for e in exported[1:]} == {e["body"]["content_hash"] for e in records}
        switched = client.post(
            root + "/configuration",
            json={"configuration": ObserverConfig().model_dump(mode="json"), "expected_revision": 1},
        )
        assert switched.status_code == 200
        assert client.get(root + "/entries").json()["rows"] == []
        assert client.get(root + "/entries?configuration_revision=1").json()["rows"]
        assert client.post(root + "/retry", json={"expected_revision": 2}).status_code == 409
        other = client.post("/api/v2/projects", json={"name": "Observer boundary"}).json()["id"]
        foreign = root.replace(str(project), other)
        for suffix in (
            "",
            "/entries",
            "/export?configuration_revision=1",
            "/revisions",
            "/live?configuration_revision=1",
        ):
            assert client.get(foreign + suffix).status_code == 404
        with database.tx(project) as db:
            db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (project, LOCAL_USER))
        assert (
            client.post(
                root + "/configuration",
                json={"configuration": ObserverConfig().model_dump(mode="json"), "expected_revision": 2},
            ).status_code
            == 403
        )
        assert client.get(root + "/entries?configuration_revision=1").status_code == 200


def test_pending_observer_superseded_configuration_does_not_block_training(database):
    project, campaign, worker = setup(database)
    enabled = ObserverConfig(enabled=True)
    result = configure(database, project, campaign["id"], LOCAL_USER, enabled, 0)
    # The original simulation job predates the observer and remains runnable.
    assert worker.once()
    configure(database, project, campaign["id"], LOCAL_USER, ObserverConfig(), 1)
    assert worker.once()  # Retires the obsolete observer, without generating facts.
    with database.tx(project) as db:
        assert (
            db.execute("SELECT status FROM ecology_campaigns WHERE id=%s", (campaign["id"],)).fetchone()["status"]
            == "completed"
        )
        assert not db.execute("SELECT 1 FROM ecology_observer_entries").fetchone()
        assert (
            db.execute("SELECT result FROM jobs WHERE id=%s", (result["observer"]["job_id"],)).fetchone()["result"][
                "status"
            ]
            == "superseded"
        )
    other = database.create_project({"id": LOCAL_USER}, "Other observer scope")["id"]
    with pytest.raises(NotFound):
        configure(database, other, campaign["id"], LOCAL_USER, enabled, 0)


def test_observer_transaction_failure_can_retry_without_partial_entries(database, monkeypatch):
    project, campaign, worker = setup(database)
    assert worker.once()
    result = configure(
        database, project, campaign["id"], LOCAL_USER, ObserverConfig(enabled=True, start_from="beginning"), 0
    )
    job = database.claim(worker.name, capabilities=worker.capabilities)
    assert job["id"] == result["observer"]["job_id"]
    from threemind_lab import ecology_observers

    original = ecology_observers.evaluate_rules

    def fail(*args):
        raise ValueError("observer fixture failure")

    monkeypatch.setattr(ecology_observers, "evaluate_rules", fail)
    with pytest.raises(ValueError, match="fixture failure"):
        execute(database, job)
    with database.tx(project) as db:
        assert not db.execute("SELECT 1 FROM ecology_observer_entries").fetchone()
        assert detail(db, campaign["id"])["observer"]["next_checkpoint_revision"] == 1
    monkeypatch.setattr(ecology_observers, "evaluate_rules", original)
    execute(database, job)
    drain(database, worker, campaign["id"])


def test_large_checkpoint_cursor_failure_recovery_and_dormant_wakeup(database, monkeypatch):
    from threemind_lab import ecology_observers, scheduling
    from threemind_lab.ecology_store import PopulationWriter
    from threemind_lab.ecology_worker import open_population
    from threemind_runtime.capabilities import probe_worker

    project, campaign, worker = setup(database)
    # Own the simulation lease without advancing this test population yet.
    caps = probe_worker(worker.backend)
    caps["features"]["worker.ecology_v1"] = {"state": "available"}
    simulation = database.claim("population-fixture", capabilities=caps)
    assert simulation["id"] == campaign["job_id"]
    writer = PopulationWriter(database, project, campaign, job=simulation)
    config = configure(
        database, project, campaign["id"], LOCAL_USER, ObserverConfig(enabled=True, start_from="beginning"), 0
    )
    assert worker.once()  # No checkpoint yet: suspend without an endless lease loop.
    assert not worker.once()
    with database.tx(project) as db:
        assignment_count = db.execute(
            "SELECT count(*) AS n FROM job_assignments WHERE job_id=%s", (config["observer"]["job_id"],)
        ).fetchone()["n"]
        assert assignment_count == 1
    # Scheduling also describes dormant jobs honestly instead of 'ready'.
    from threemind_lab import execution_limits

    execution_limits.initialize(database, Settings(database_url=database.test_url))
    assert (
        next(j for j in scheduling.jobs(database, project)["rows"] if j["id"] == config["observer"]["job_id"])["reason"]
        == "waiting_evidence"
    )
    with open_population(worker, campaign, writer) as runtime:
        # Explicit transport stress evidence, never inserted into an existing CP.
        for index in range(225):
            writer.record({"kind": "fixture_measurement", "time_us": "0", "sample": index})
        writer.commit(runtime, status="completed", finish=True)
    database.finish(simulation, result={})
    assert worker.once()  # INSERT of the committed checkpoint wakes this job.
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM ecology_observer_entries").fetchone()["n"] == 100
        assert detail(db, campaign["id"])["observer"]["next_checkpoint_revision"] == 1
        db.execute("UPDATE jobs SET available_at=clock_timestamp() WHERE id=%s", (config["observer"]["job_id"],))
    lease = database.claim(worker.name, capabilities=worker.capabilities)
    original = ecology_observers.describe_event
    calls = 0

    def fail_mid_chunk(*args):
        nonlocal calls
        calls += 1
        if calls == 20:
            raise ValueError("partial event chunk")
        return original(*args)

    monkeypatch.setattr(ecology_observers, "describe_event", fail_mid_chunk)
    with pytest.raises(ValueError, match="partial event chunk"):
        execute(database, lease)
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM ecology_observer_entries").fetchone()["n"] == 100
    monkeypatch.setattr(ecology_observers, "describe_event", original)
    execute(database, lease)
    drain(database, worker, campaign["id"])
    with database.tx(project) as db:
        raw_ids = {str(r["id"]) for r in db.execute("SELECT id FROM ecology_events").fetchall()}
        narrated = db.execute("SELECT body FROM ecology_observer_entries WHERE kind='event'").fetchall()
        assert len(raw_ids) > 225 and len(raw_ids) == len(narrated)
        assert {r["body"]["source"]["event_id"] for r in narrated} == raw_ids
        assert detail(db, campaign["id"])["observer"]["job_status"] == "done"
    for table in ("ecology_observer_entries", "ecology_observer_revisions"):
        with pytest.raises(psycopg.Error, match="immutable"), database.tx(project) as db:
            db.execute(f"DELETE FROM {table}")
    other = database.create_project({"id": LOCAL_USER}, "Other observer boundary")["id"]
    with database.tx(other) as db:
        for table in ("ecology_observer_entries", "ecology_observer_revisions", "ecology_observers"):
            assert db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0
