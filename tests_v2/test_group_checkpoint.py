from uuid import uuid4

import pytest
from lease_helpers import claim_as

from threemind_core import Engine, Stimulus
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.protocols import RunSpec


def setup(database):
    project = database.create_project({"id": LOCAL_USER}, "Atomic population checkpoint")
    runs = [
        database.create_run(project["id"], f"Member {i}", RunSpec(environment="manual").model_dump()) for i in range(2)
    ]
    engines = [Engine(), Engine()]
    for index, engine in enumerate(engines):
        engine.inject(Stimulus(0, ((index, 0.8), (index + 7, 0.5))))
        engine.advance_to(10000)
    return project["id"], runs, engines


def test_multi_brain_checkpoints_projection_and_parent_record_commit_or_rollback_together(database):
    project, runs, engines = setup(database)
    operation = str(uuid4())
    with pytest.raises(RuntimeError, match="injected"), database.tx(project) as db:
        for run, engine in zip(runs, engines, strict=True):
            database.save_checkpoint(
                project,
                run["id"],
                engine.capture_state(),
                expected_revision=0,
                context={"population_operation": operation},
                transaction=db,
            )
        db.execute(
            "INSERT INTO audit(user_id,action,resource) VALUES(%s,'population.fixture',%s)", (LOCAL_USER, operation)
        )
        raise RuntimeError("injected failure after both brains")
    assert all(database.get_run(project, run["id"])["revision"] == 0 for run in runs)
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM checkpoints").fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM nodes").fetchone()["n"] == 0
        assert not db.execute("SELECT 1 FROM audit WHERE resource=%s", (operation,)).fetchone()
    saved = []
    with database.tx(project) as db:
        for run, engine in zip(runs, engines, strict=True):
            image = engine.capture_state()
            cp = database.save_checkpoint(
                project,
                run["id"],
                image,
                expected_revision=0,
                context={"population_operation": operation},
                transaction=db,
            )
            saved.append((cp, image))
        db.execute(
            "INSERT INTO audit(user_id,action,resource) VALUES(%s,'population.fixture',%s)", (LOCAL_USER, operation)
        )
        # Another transaction cannot observe either member before its parent commit.
        assert all(database.get_run(project, run["id"])["revision"] == 0 for run in runs)
    assert all(database.get_run(project, run["id"])["revision"] == 1 for run in runs)
    with database.tx(project) as db:
        for run, (cp, image) in zip(runs, saved, strict=True):
            retry = database.save_checkpoint(
                project,
                run["id"],
                image,
                expected_revision=0,
                context={"population_operation": operation},
                transaction=db,
            )
            assert retry["id"] == cp["id"]
    with database.tx(project) as db:
        for run, engine, (cp, image) in zip(runs, engines, saved, strict=True):
            engine.advance_to(17000)
            next_cp = database.save_checkpoint(
                project,
                run["id"],
                engine.capture_state(),
                expected_revision=1,
                previous=(cp, image.to_dict()),
                transaction=db,
            )
            assert next_cp["storage_format"] == "row-delta/1"
    for run, engine in zip(runs, engines, strict=True):
        assert database.load_checkpoint(project, run["id"])[1].digest == engine.capture_state().digest
        assert len(database.query_graph(project, run["id"])["rows"]) == 2


def test_group_write_keeps_cas_fencing_and_project_scope(database):
    project, runs, engines = setup(database)
    database.enqueue(project, "run", run_id=runs[0]["id"])
    stale = claim_as(database, "group-old")
    with database.tx() as db:
        db.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (stale["id"],))
    fresh = claim_as(database, "group-new")
    assert fresh["generation"] > stale["generation"]
    with pytest.raises(Conflict), database.tx(project) as db:
        database.save_checkpoint(
            project, runs[0]["id"], engines[0].capture_state(), expected_revision=0, job=fresh, transaction=db
        )
        database.save_checkpoint(
            project, runs[1]["id"], engines[1].capture_state(), expected_revision=0, job=stale, transaction=db
        )
    assert all(database.get_run(project, run["id"])["revision"] == 0 for run in runs)
    with pytest.raises(Conflict), database.tx(project) as db:
        database.save_checkpoint(
            project, runs[0]["id"], engines[0].capture_state(), expected_revision=0, transaction=db
        )
        database.save_checkpoint(
            project, runs[1]["id"], engines[1].capture_state(), expected_revision=9, transaction=db
        )
    assert all(database.get_run(project, run["id"])["revision"] == 0 for run in runs)
    other = database.create_project({"id": LOCAL_USER}, "Other group")
    with database.tx(other["id"]) as db, pytest.raises(ValueError, match="project scope"):
        database.save_checkpoint(
            project, runs[0]["id"], engines[0].capture_state(), expected_revision=0, transaction=db
        )
    with database.pool.connection() as connection, pytest.raises(ValueError, match="active owning"):
        database.save_checkpoint(
            project, runs[0]["id"], engines[0].capture_state(), expected_revision=0, transaction=connection
        )
