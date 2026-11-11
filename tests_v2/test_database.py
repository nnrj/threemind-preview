import pytest
from lease_helpers import claim_as

from threemind_core import Engine, Stimulus
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker


def project(db):
    return db.create_project({"id": LOCAL_USER}, "Test project")


def test_checkpoint_projection_and_isolation(database):
    p, q = project(database), project(database)
    run = database.create_run(p["id"], "Test", RunSpec().model_dump())
    e = Engine()
    e.inject(Stimulus(0, ((1, 0.7), (2, 0.5))))
    e.advance_to(50000)
    image = e.capture_state()
    cp = database.save_checkpoint(p["id"], run["id"], image, expected_revision=0)
    assert database.load_checkpoint(p["id"], run["id"])[1] == image
    assert len(database.query_graph(p["id"], run["id"])["rows"]) == 2
    assert database.save_checkpoint(p["id"], run["id"], image, expected_revision=0)["id"] == cp["id"]
    with database.tx(q["id"]) as conn:
        assert conn.execute("SELECT count(*) AS n FROM nodes").fetchone()["n"] == 0
    with database.tx(p["id"]) as conn:
        assert conn.execute("SELECT count(*) AS n FROM nodes").fetchone()["n"] == 2
    with database.tx() as conn:
        assert conn.execute("SELECT count(*) AS n FROM nodes").fetchone()["n"] == 0
    e.advance_to(100000)
    database.save_checkpoint(p["id"], run["id"], e.capture_state(), expected_revision=1)
    with pytest.raises(Conflict):
        database.query_graph(p["id"], run["id"], revision=1)


def test_stale_lease_cannot_commit(database):
    p = project(database)
    run = database.create_run(p["id"], "Lease", RunSpec().model_dump())
    database.enqueue(p["id"], "run", run_id=run["id"])
    old = claim_as(database, "first")
    with database.tx() as conn:
        conn.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (old["id"],))
    new = claim_as(database, "second")
    assert new["generation"] == old["generation"] + 1
    with pytest.raises(Conflict):
        database.save_checkpoint(p["id"], run["id"], Engine().capture_state(), expected_revision=0, job=old)
    database.save_checkpoint(p["id"], run["id"], Engine().capture_state(), expected_revision=0, job=new)


def test_worker_complete_export_and_resume(database):
    p = project(database)
    spec = RunSpec(
        environment="replay",
        clock="unbounded",
        duration_s=0.1,
        replay=[{"time_us": "0", "channels": [[1, 0.6], [2, 0.8]], "intensity": 1.0}],
    )
    run = database.create_run(p["id"], "Replay", spec.model_dump())
    database.enqueue(p["id"], "run", run_id=run["id"])
    worker = Worker(database)
    assert worker.once()
    row = database.get_run(p["id"], run["id"])
    assert row["status"] == "completed", row.get("error")
    database.enqueue(p["id"], "export", {"format": "tmind"}, run["id"])
    assert worker.once()
    with database.tx(p["id"]) as conn:
        assert conn.execute("SELECT count(*) AS n FROM artifacts").fetchone()["n"] == 1
