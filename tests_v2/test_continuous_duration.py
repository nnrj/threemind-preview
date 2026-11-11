"""Exercise real persistence and workers: null means no experiment endpoint."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_api import client_for
from test_assessments import protocol as assessment_protocol
from test_evolution_protocol import protocol as evolution_protocol

from threemind_lab import research_operations, run_cycle
from threemind_lab.assessment_protocol import AssessmentProtocol
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_lab.database import LOCAL_USER
from threemind_lab.evolution_protocol import EvolutionProtocol
from threemind_lab.protocols import RunSpec, StudySpec
from threemind_lab.worker import Worker
from threemind_runtime import create_engine


def test_optional_duration_and_explicit_finite_experiments():
    assert RunSpec().duration_s is None
    assert RunSpec().deadline_us(123) is None
    assert RunSpec(duration_s=0.25).deadline_us(123) == 250123
    spec = default_spec()
    assert spec["duration_s"] is None
    field = next(f for f in catalogue()["fields"] if f["path"] == "duration_s")
    assert field["nullable"] and field["default"] is None
    assert validate_configuration(spec, maximum_duration=1)["valid"]
    for bad in (0, -1, "infinity", "60", float("inf"), 0.0000001):
        assert not validate_configuration(spec | {"duration_s": bad})["valid"]
    assert not validate_configuration(spec | {"duration_s": 2}, maximum_duration=1)["valid"]
    assert validate_configuration(spec, current=spec | {"duration_s": 60}, elapsed_us=61_000_000)["valid"]
    assert not validate_configuration(spec | {"duration_s": 60}, current=spec, elapsed_us=61_000_000)["valid"]
    with pytest.raises(ValidationError, match="有限"):
        RunSpec(phases=[{"name": "input", "duration_s": 1}])
    with pytest.raises(ValidationError, match="有限"):
        StudySpec(name="Endpoint study", base=RunSpec())
    for stage in ("development", "evaluation"):
        value = evolution_protocol()
        value[stage]["duration_s"] = None
        with pytest.raises(ValidationError, match="有限"):
            EvolutionProtocol(**value)
    value = assessment_protocol(str(uuid4()))
    value["evaluation"]["duration_s"] = None
    with pytest.raises(ValidationError, match="有限"):
        AssessmentProtocol(**value)


def test_default_passes_sixty_seconds_checkpoint_resume_pause_cancel(database, monkeypatch):
    backend = "native"
    project = database.create_project({"id": LOCAL_USER}, "Continuous duration regression")["id"]
    spec = default_spec() | {
        "environment": "manual",
        "clock": "unbounded",
        "sample_us": 10_000_000,
        "checkpoint_us": 10_000_000,
    }
    run = database.create_run(project, "No time limit", spec)
    database.enqueue(project, "run", run_id=run["id"])
    worker = Worker(database, backend=backend)
    original = run_cycle.create_engine

    def stop_after_old_limit(*args, **kwargs):
        engine = original(*args, **kwargs)
        advance = engine.advance_to

        def advance_and_stop(target, *args, **kwargs):
            result = advance(target, *args, **kwargs)
            if engine.time_us >= 61_000_000:
                worker.stopping = True  # Emulate graceful worker shutdown, after the old deadline.
            return result

        engine.advance_to = advance_and_stop
        return engine

    with monkeypatch.context() as patch:
        patch.setattr(run_cycle, "create_engine", stop_after_old_limit)
        assert worker.once()
    cp, image = database.load_checkpoint(project, run["id"])
    assert database.get_run(project, run["id"])["status"] == "paused" and int(cp["time_us"]) >= 61_000_000
    assert cp["context"]["end_us"] is None
    worker.stopping = False
    research_operations.submit_advance(
        database,
        project,
        run["id"],
        LOCAL_USER,
        request_id=uuid4(),
        expected_revision=cp["revision"],
        duration_us=12345,
    )
    assert worker.once()
    resumed, result = database.load_checkpoint(project, run["id"])
    reference = create_engine(state=image, backend=backend)
    reference.advance_to(int(cp["time_us"]) + 12345)
    assert result.digest == reference.capture_state().digest
    assert database.get_run(project, run["id"])["status"] == "paused" and resumed["context"]["end_us"] is None
    database.command(project, run["id"], "resume", {})
    database.command(project, run["id"], "pause", {})
    assert worker.once()
    assert database.get_run(project, run["id"])["status"] == "paused"
    database.command(project, run["id"], "resume", {})
    database.command(project, run["id"], "cancel", {})
    assert worker.once()
    assert database.get_run(project, run["id"])["status"] == "cancelled"


def test_remove_deadline_keeps_model_and_history_and_fork_is_unlimited(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Remove deadline"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        spec = default_spec() | {"environment": "manual", "clock": "unbounded", "duration_s": 0.06}
        run = database.create_run(project, "Finite subject", spec)
        engine = create_engine()
        engine.advance_to(10000)
        original = engine.capture_state()
        cp = database.save_checkpoint(
            project,
            run["id"],
            original,
            expected_revision=0,
            status="paused",
            context={"start_us": "0", "end_us": "60000", "protocol": spec},
        )
        response = client.put(
            f"{base}/runs/{run['id']}/configuration",
            json={
                "name": "Continuous subject",
                "expected_revision": 1,
                "spec": spec | {"duration_s": None},
            },
        )
        assert response.status_code == 200, response.text
        current, image = database.load_checkpoint(project, run["id"])
        assert image.digest == original.digest and current["context"]["end_us"] is None
        historical, _ = database.load_checkpoint(project, run["id"], cp["id"])
        assert historical["context"]["end_us"] == "60000"
        research_operations.submit_advance(
            database,
            project,
            run["id"],
            LOCAL_USER,
            request_id=uuid4(),
            expected_revision=current["revision"],
            duration_us=100000,
        )
        assert Worker(database).once()
        assert database.get_run(project, run["id"])["time_us"] == "110000"
        fork = client.post(f"{base}/runs/{run['id']}/forks", json={"name": "Continuous fork"})
        assert fork.status_code == 201, fork.text
        fork_cp, _ = database.load_checkpoint(project, fork.json()["id"])
        assert fork.json()["spec"]["duration_s"] is None and fork_cp["context"]["end_us"] is None


def test_ecology_null_duration_can_pause_and_resume_beyond_a_finite_fixture(database, monkeypatch):
    from test_ecology_store import setup

    from threemind_lab.ecology_store import campaign, control
    from threemind_runtime.ecology import EcologyCoordinator

    project, row, worker = setup(database, duration_s=None)
    original = EcologyCoordinator.advance_to
    stop_time = 120000

    def advance_then_stop(runtime, target):
        result = original(runtime, target)
        if runtime.time_us >= stop_time:
            worker.stopping = True
        return result

    monkeypatch.setattr(EcologyCoordinator, "advance_to", advance_then_stop)
    for expected in (120000, 180000):
        stop_time = expected
        assert worker.once()
        with database.tx(project) as db:
            current = campaign(db, row["id"])
        assert current["status"] == "paused" and int(current["time_us"]) >= expected
        assert current["protocol"]["base"]["duration_s"] is None
        if expected == 120000:
            control(database, project, row["id"], LOCAL_USER, "resume", current["control_revision"])
            worker.stopping = False
    control(database, project, row["id"], LOCAL_USER, "cancel", current["control_revision"])
