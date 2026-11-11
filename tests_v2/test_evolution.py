import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from test_evolution_protocol import protocol

from threemind_lab import evolution
from threemind_lab.database import LOCAL_USER, Conflict, NotFound
from threemind_lab.evolution_protocol import EvolutionRequest
from threemind_lab.worker import Worker


def campaign(database, **changes):
    project = database.create_project({"id": LOCAL_USER}, "Evolution integration")["id"]
    request = EvolutionRequest(
        operation_id=uuid4(),
        name="Two generations",
        objective="Engineering lineage verification",
        protocol=protocol(**changes),
    )
    created = evolution.create(database, project, LOCAL_USER, request, 600)
    return project, created, request


def drain(worker, project, identity, maximum=90):
    for _ in range(maximum):
        value = evolution.detail(worker.db, project, identity)
        if value["status"] != "active":
            return value
        assert worker.once(), value
    pytest.fail("coordinator did not terminate within its declared test budget")


def test_one_worker_completes_generations_with_pinned_parent_and_separate_verification(database):
    project, created, request = campaign(database)
    assert evolution.create(database, project, LOCAL_USER, request, 600)["id"] == created["id"]
    with database.tx() as db:
        db.execute("UPDATE execution_limits SET limits=jsonb_set(limits,'{runtime}','1')")
    worker = Worker(database, max_active=1)
    assert worker.once()
    initial = evolution.detail(database, project, created["id"])
    assert initial["phase"] == "development" and len(initial["members"]) == 2
    with database.tx(project) as db:
        parent_job = db.execute("SELECT * FROM jobs WHERE id=%s", (created["job_id"],)).fetchone()
        assert parent_job["status"] == "pending" and parent_job["params"]["barrier_ready"] is False
        assert db.execute("SELECT count(*) AS n FROM jobs WHERE status='leased'").fetchone()["n"] == 0
    result = drain(worker, project, created["id"])
    assert result["status"] == "completed", result["error"]
    assert result["generation"] == 1 and result["phase"] == "complete"
    assert "protocol" not in result and result["progress_range"] == [0, 1]
    with database.tx(project) as db:
        members = db.execute(
            "SELECT * FROM evolution_members WHERE campaign_id=%s ORDER BY generation,stage,slot,block_index",
            (created["id"],),
        ).fetchall()
        selections = db.execute(
            "SELECT * FROM evolution_selections WHERE campaign_id=%s ORDER BY generation,rank", (created["id"],)
        ).fetchall()
        assert len(members) == 16 and len(selections) == 4
        assert all(member["outcome"]["metrics"]["nodes"] > 0 for member in members)
        assert db.execute("SELECT count(*) AS n FROM innate_versions").fetchone()["n"] == 4
        development = {(m["generation"], m["slot"]): m for m in members if m["stage"] == "development"}
        for member in members:
            cp = db.execute(
                "SELECT run_id,state_hash FROM checkpoints WHERE id=%s", (member["checkpoint_id"],)
            ).fetchone()
            assert cp["run_id"] == member["run_id"] and cp["state_hash"] == member["state_hash"]
            if member["stage"] != "development":
                parent = development[(member["generation"], member["slot"])]
                assert member["source_version_id"] == parent["candidate_version_id"]
                version = db.execute(
                    "SELECT checkpoint_id FROM innate_versions WHERE id=%s", (member["source_version_id"],)
                ).fetchone()
                assert version["checkpoint_id"] == parent["checkpoint_id"] != member["checkpoint_id"]
        parent_ids = {r["candidate_version_id"] for r in selections if r["generation"] == 0 and r["selected"]}
        assert {
            m["source_version_id"] for m in members if m["generation"] == 1 and m["stage"] == "development"
        } == parent_ids
        assert all(len(r["evidence"]["blocks"]) == 2 for r in selections)
        events = db.execute(
            "SELECT kind,payload FROM evolution_events WHERE campaign_id=%s ORDER BY revision", (created["id"],)
        ).fetchall()
        assert events[-1]["kind"] == "completed" and events[-1]["payload"]["verification_used_for_selection"] is False
        assert sum(e["kind"] == "parents_selected" for e in events) == 2
    with pytest.raises(Conflict, match="冻结"):
        database.command(project, members[0]["run_id"], "resume", {})
    with pytest.raises(Conflict):
        evolution.control(database, project, created["id"], LOCAL_USER, "resume", result["revision"])


def test_simultaneous_last_children_cannot_lose_the_coordinator_wakeup(database, monkeypatch):
    project, created, _ = campaign(database)
    driver = Worker(database, name="wave-driver")
    assert driver.once()
    jobs = []
    for index in range(2):
        name = f"parallel-child-{index}"
        database.announce_worker(name, driver.capabilities)
        job = database.claim(name, max_active=2, capabilities=driver.capabilities)
        assert job and job["kind"] == "run"
        Worker(database).run(job)
        jobs.append(job)
    gate = threading.Barrier(2)
    original = evolution.child_finished

    def synchronized(db, job):
        gate.wait(timeout=10)
        original(db, job)

    with monkeypatch.context() as patch:
        patch.setattr(evolution, "child_finished", synchronized)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(database.finish, job, result={"status": "completed"}) for job in jobs]
            for result in results:
                result.result(timeout=20)
    with database.tx(project) as db:
        assert (
            db.execute(
                "SELECT params->>'barrier_ready' AS ready FROM jobs WHERE id=%s", (created["job_id"],)
            ).fetchone()["ready"]
            == "true"
        )
    assert driver.once()
    assert evolution.detail(database, project, created["id"])["phase"] == "evaluation"


def test_failure_is_not_a_score_and_explicit_retry_uses_the_same_individual(database, monkeypatch):
    project, created, _ = campaign(database)
    worker = Worker(database)
    assert worker.once()
    original = worker.run

    def failing(job):
        raise ValueError("declared fixture failure, never a zero score")

    with monkeypatch.context() as patch:
        patch.setattr(worker, "run", failing)
        assert worker.once()
    assert worker.once() and worker.once()
    blocked = evolution.detail(database, project, created["id"])
    assert blocked["status"] == "blocked" and not blocked["selections"]
    failed = next(m for m in blocked["members"] if m["run_status"] == "failed")
    assert failed["checkpoint_id"] is None
    with pytest.raises(Conflict):
        evolution.control(database, project, created["id"], LOCAL_USER, "resume", blocked["revision"])
    evolution.control(database, project, created["id"], LOCAL_USER, "retry", blocked["revision"])
    assert worker.run == original
    final = drain(worker, project, created["id"])
    assert final["status"] == "completed", final["error"]
    with database.tx(project) as db:
        assert (
            db.execute("SELECT count(*) AS n FROM evolution_members WHERE run_id=%s", (failed["run_id"],)).fetchone()[
                "n"
            ]
            == 1
        )
        assert (
            db.execute("SELECT count(*) AS n FROM jobs WHERE run_id=%s AND kind='run'", (failed["run_id"],)).fetchone()[
                "n"
            ]
            == 2
        )


def test_pause_resume_and_cancel_settle_member_states(database):
    project, created, _ = campaign(database)
    worker = Worker(database)
    assert worker.once()
    current = evolution.detail(database, project, created["id"])
    evolution.control(database, project, created["id"], LOCAL_USER, "pause", current["revision"])
    paused = evolution.detail(database, project, created["id"])
    with pytest.raises(Conflict, match="提交停止"):
        evolution.control(database, project, created["id"], LOCAL_USER, "resume", paused["revision"])
    assert worker.once() and worker.once()
    assert {m["run_status"] for m in evolution.detail(database, project, created["id"])["members"]} == {"paused"}
    evolution.control(database, project, created["id"], LOCAL_USER, "resume", paused["revision"])
    resumed = evolution.detail(database, project, created["id"])
    evolution.control(database, project, created["id"], LOCAL_USER, "pause", resumed["revision"])
    assert worker.once() and worker.once()
    stopped = evolution.detail(database, project, created["id"])
    evolution.control(database, project, created["id"], LOCAL_USER, "cancel", stopped["revision"])
    result = evolution.detail(database, project, created["id"])
    assert result["status"] == "cancelled" and {m["run_status"] for m in result["members"]} == {"cancelled"}
    assert not worker.once()


def test_campaign_protocol_and_final_evidence_are_project_scoped_and_immutable(database):
    project, created, request = campaign(database)
    other = database.create_project({"id": LOCAL_USER}, "Other evolution")["id"]
    with pytest.raises(NotFound):
        evolution.detail(database, other, created["id"])
    with pytest.raises(Conflict):
        evolution.create(database, project, LOCAL_USER, request.model_copy(update={"name": "different"}), 600)
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), database.tx(project) as db:
        db.execute("UPDATE evolution_campaigns SET objective='different' WHERE id=%s", (created["id"],))
    assert evolution.detail(database, project, created["id"])["objective"] == request.objective
    original = copy.deepcopy(created["protocol"])
    assert original["selection_mode"] == "directed"


def test_partial_wave_creation_rolls_back_and_retries_without_duplicate_births(database, monkeypatch):
    project, created, _ = campaign(database)
    worker = Worker(database)
    original = evolution.development.create_in
    calls = 0

    def reject_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("second child rejected in test transaction")
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(evolution.development, "create_in", reject_second)
        assert worker.once()
    stopped = evolution.detail(database, project, created["id"])
    assert stopped["status"] == "blocked" and stopped["members"] == []
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM runs").fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM development_sessions").fetchone()["n"] == 0
    evolution.control(database, project, created["id"], LOCAL_USER, "retry", stopped["revision"])
    assert worker.once()
    assert len(evolution.detail(database, project, created["id"])["members"]) == 2


@pytest.mark.parametrize("failure", ["exception", "lease_exhausted"])
def test_coordinator_failure_becomes_diagnosable_and_can_be_retried(database, monkeypatch, failure):
    worker = Worker(database)
    assert not worker.once()
    project, created, _ = campaign(database)
    if failure == "exception":

        def crash(*args):
            raise RuntimeError("coordinator crash fixture")

        with monkeypatch.context() as patch:
            patch.setattr(evolution, "_drive", crash)
            assert worker.once()
    else:
        job = database.claim(worker.name, capabilities=worker.capabilities)
        assert job["kind"] == "evolution"
        with database.tx(project) as db:
            db.execute("UPDATE jobs SET attempts=5,lease_until=now()-interval '1 second' WHERE id=%s", (job["id"],))
        assert not worker.once()
    stopped = evolution.detail(database, project, created["id"])
    assert stopped["status"] == "blocked" and stopped["error"]
    assert stopped["events"][0]["kind"] == "coordinator_failed"
    evolution.control(database, project, created["id"], LOCAL_USER, "retry", stopped["revision"])
    assert worker.once() and evolution.detail(database, project, created["id"])["phase"] == "development"


def test_cancel_during_child_pause_finalization_is_not_lost(database):
    project, created, _ = campaign(database)
    worker = Worker(database)
    assert worker.once()
    job = database.claim(worker.name, capabilities=worker.capabilities)
    stopper = Worker(database)
    stopper.stopping = True
    stopper.run(job)
    assert database.get_run(project, job["run_id"])["status"] == "paused"
    current = evolution.detail(database, project, created["id"])
    evolution.control(database, project, created["id"], LOCAL_USER, "cancel", current["revision"])
    database.finish(job, result={"status": "paused"})
    assert database.get_run(project, job["run_id"])["status"] == "cancelled"
    assert worker.once() and not worker.once()
    assert {r["run_status"] for r in evolution.detail(database, project, created["id"])["members"]} == {"cancelled"}


def test_repeated_protocol_reproduces_all_generation_hashes_and_selected_slots(database):
    captured = []
    worker = Worker(database)
    for _ in range(2):
        project, created, _ = campaign(database)
        result = drain(worker, project, created["id"])
        assert result["status"] == "completed", result["error"]
        with database.tx(project) as db:
            hashes = db.execute(
                "SELECT generation,stage,slot,block_index,environment_seed,state_hash FROM evolution_members WHERE campaign_id=%s ORDER BY generation,stage,slot,block_index",
                (created["id"],),
            ).fetchall()
            scores = db.execute(
                "SELECT generation,slot,rank,selected,scores FROM evolution_selections WHERE campaign_id=%s ORDER BY generation,slot",
                (created["id"],),
            ).fetchall()
        assert len({row["state_hash"] for row in hashes}) > 4
        captured.append((hashes, scores))
    assert captured[0] == captured[1]


def test_exhausted_child_lease_wakes_coordinator_into_blocked_state(database):
    project, created, _ = campaign(database)
    worker = Worker(database)
    assert worker.once()
    job = database.claim(worker.name, capabilities=worker.capabilities)
    assert job["kind"] == "run"
    with database.tx(project) as db:
        db.execute("UPDATE jobs SET attempts=5,lease_until=now()-interval '1 second' WHERE id=%s", (job["id"],))
    assert worker.once()  # marks the exhausted child and executes its sibling
    assert worker.once()  # coordinator observes a failure, never a score
    result = evolution.detail(database, project, created["id"])
    assert result["status"] == "blocked" and result["selections"] == []
    assert any(m["run_status"] == "blocked" and m["outcome"] is None for m in result["members"])
    with database.tx(project) as db:
        assert db.execute("SELECT status FROM jobs WHERE id=%s", (job["id"],)).fetchone()["status"] == "failed"


def test_old_worker_cannot_claim_coordinator_children_or_campaign_export(database):
    from threemind_lab import evolution_export

    current = Worker(database)
    assert not current.once()
    project, created, _ = campaign(database)
    old = copy.deepcopy(current.capabilities)
    old["features"].pop("worker.evolution_v1")
    database.announce_worker("before-evolution", old)
    assert database.claim("before-evolution", capabilities=old) is None
    assert current.once()
    exported = evolution_export.enqueue(database, project, created["id"], LOCAL_USER, uuid4())
    assert database.claim("before-evolution", capabilities=old) is None
    with database.tx(project) as db:
        waiting = db.execute(
            "SELECT required_features,status,attempts FROM jobs WHERE id=%s", (exported["id"],)
        ).fetchone()
        assert waiting["status"] == "pending" and waiting["attempts"] == 0
        assert "worker.evolution_v1" in waiting["required_features"]
