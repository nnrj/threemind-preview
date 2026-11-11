from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from lease_helpers import claim_as
from test_api import client_for

from threemind_lab import auth
from threemind_lab import execution_limits as limits
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Conflict


def setup(database, **values):
    settings = Settings(database_url=database.test_url, **values)
    limits.initialize(database, settings)
    return settings


def project(database):
    return database.create_project({"id": LOCAL_USER}, "Execution budget")["id"]


def test_project_caps_do_not_block_other_projects_or_queues(database):
    setup(database)
    p, q = project(database), project(database)
    limits.save(database, LOCAL_USER, {"runtime": 1}, 0, p)
    first = database.enqueue(p, "analysis")
    database.enqueue(p, "analysis")
    other = database.enqueue(q, "analysis")
    ai = database.enqueue(p, "ai")
    assert claim_as(database, "first")["id"] == first["id"]
    assert claim_as(database, "second")["id"] == other["id"]
    assert claim_as(database, "third") is None
    assert claim_as(database, "ai-only", queue="ai")["id"] == ai["id"]
    state = limits.snapshot(database, p)
    assert state["effective"] == {"runtime": 1, "ai": 2, "notification": 1}
    assert state["usage"]["runtime"]["pending"] == 1
    assert state["usage"]["runtime"]["active"] == 1
    assert limits.snapshot(database, q)["usage"]["ai"]["active"] == 0


def test_simultaneous_claims_lowering_and_expired_recovery(database):
    setup(database, max_active_jobs=3)
    projects = [project(database) for _ in range(5)]
    for p in projects:
        limits.save(database, LOCAL_USER, {"runtime": 1}, 0, p)
        for _ in range(3):
            database.enqueue(p, "analysis")
    with ThreadPoolExecutor(max_workers=8) as pool:
        claimed = [job for job in pool.map(lambda i: claim_as(database, f"concurrent-{i}"), range(8)) if job]
    assert len(claimed) == len({j["project_id"] for j in claimed}) == 3
    limits.save(database, LOCAL_USER, {"runtime": 0, "ai": 2, "notification": 1}, 1)
    assert claim_as(database, "paused") is None
    for job in claimed:
        database.renew(job)
    assert limits.snapshot(database)["usage"]["runtime"]["active"] == 3
    for job in claimed[1:]:
        database.finish(job, result={})
    with database.tx() as db:
        db.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (claimed[0]["id"],))
    limits.save(database, LOCAL_USER, {"runtime": 1, "ai": 2, "notification": 1}, 2)
    recovered = claim_as(database, "recovery")
    assert recovered["id"] == claimed[0]["id"]
    assert recovered["generation"] == claimed[0]["generation"] + 1
    with pytest.raises(Conflict):
        database.renew(claimed[0])
    assert claim_as(database, "at-new-cap") is None


def test_policy_versions_inheritance_restart_and_transaction_rollback(database):
    settings = setup(database)
    p = project(database)
    limits.save(database, LOCAL_USER, {"runtime": 4, "ai": 0, "notification": 1}, 1)
    limits.initialize(database, replace(settings, max_active_jobs=1, max_ai_jobs=10))
    assert limits.snapshot(database)["global"]["limits"]["runtime"] == 4
    with pytest.raises(Conflict):
        limits.save(database, LOCAL_USER, {"runtime": 2, "ai": 2, "notification": 1}, 1)
    limits.save(database, LOCAL_USER, {"runtime": 9, "ai": None}, 0, p)
    assert limits.snapshot(database, p)["effective"]["runtime"] == 4
    assert limits.snapshot(database, p)["effective"]["ai"] == 0
    limits.save(database, LOCAL_USER, {"runtime": None}, 1, p)
    assert limits.snapshot(database, p)["project"]["limits"]["runtime"] is None
    for value in (True, "3", 1.5, -1, 1025):
        with pytest.raises(ValueError):
            limits.save(database, LOCAL_USER, {"runtime": value}, 2, p)
    with database.tx() as db:
        before = db.execute("SELECT count(*) AS n FROM execution_limit_history").fetchone()["n"]
    # A real history write failure must roll back the policy, not leave an unaudited edit.
    from uuid import uuid4

    import psycopg

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        limits.save(database, uuid4(), {"runtime": 0}, 2, p)
    state = limits.snapshot(database, p)
    assert state["project"]["revision"] == 2 and state["project"]["limits"]["runtime"] is None
    with database.tx() as db:
        assert db.execute("SELECT count(*) AS n FROM execution_limit_history").fetchone()["n"] == before


def test_api_permissions_validation_csrf_and_worker_drain_audit(database):
    owner = auth.create_user(database, "limits-admin", "isolated execution admin secret", admin=True)
    viewer = auth.create_user(database, "limits-viewer", "isolated execution viewer secret")
    p = database.create_project(owner, "Visible")["id"]
    q = database.create_project(owner, "Other")["id"]
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (p, viewer["id"]))
    with client_for(database, "server") as client:
        assert client.get("/api/v2/admin/execution").status_code == 401
        login = client.post(
            "/api/v2/login", json={"username": "limits-viewer", "password": "isolated execution viewer secret"}
        ).json()
        headers = {"X-CSRF-Token": login["csrf"]}
        assert client.get("/api/v2/admin/execution").status_code == 403
        assert client.get(f"/api/v2/projects/{p}/execution").status_code == 200
        assert client.get(f"/api/v2/projects/{q}/execution").status_code == 403
        edit = {"limits": {"runtime": 0}, "expected_revision": 0}
        assert (
            client.post(f"/api/v2/admin/execution/projects/{p}/limits", json=edit, headers=headers).status_code == 403
        )
        client.post("/api/v2/logout", json={}, headers=headers)
        login = client.post(
            "/api/v2/login", json={"username": "limits-admin", "password": "isolated execution admin secret"}
        ).json()
        headers = {"X-CSRF-Token": login["csrf"]}
        assert client.post(f"/api/v2/admin/execution/projects/{p}/limits", json=edit).status_code == 403
        outside = project(database)
        assert client.get(f"/api/v2/admin/execution/projects/{outside}").status_code == 200
        assert client.get(f"/api/v2/projects/{outside}/runs").status_code == 403
        invalid = {"limits": {"runtime": True}, "project": True}
        assert client.post("/api/v2/admin/execution/validate", json=invalid).status_code == 422
        assert (
            client.post(f"/api/v2/admin/execution/projects/{p}/limits", json=edit, headers=headers).status_code == 200
        )
        assert (
            client.post(f"/api/v2/admin/execution/projects/{p}/limits", json=edit, headers=headers).status_code == 409
        )
        database.announce_worker("drain-test", {})
        job = database.enqueue(q, "analysis")
        claimed = claim_as(database, "drain-test")
        assert claimed["id"] == job["id"]
        assert (
            client.post("/api/v2/admin/workers/drain-test/enabled?enabled=false", json={}, headers=headers).status_code
            == 200
        )
        database.renew(claimed)
        assert claim_as(database, "drain-test") is None
        assert (
            client.post("/api/v2/admin/workers/missing/enabled?enabled=false", json={}, headers=headers).status_code
            == 404
        )
        administration = client.get("/api/v2/admin").json()
        assert type(administration["max_active_jobs"]) is int
        assert any(r["action"] == "worker.drain" for r in administration["audit"])


def test_lowering_live_admission_preserves_simulation_and_complete_state(database, monkeypatch):
    from threemind_lab.protocols import RunSpec
    from threemind_lab.worker import Worker

    setup(database)
    p = project(database)
    spec = RunSpec(
        environment="replay",
        clock="unbounded",
        duration_s=0.06,
        checkpoint_us=10000,
        replay=[{"time_us": "0", "channels": [[1, 0.7], [2, 0.5]]}],
    ).model_dump()
    baseline = database.create_run(p, "Baseline", spec)
    database.enqueue(p, "run", run_id=baseline["id"])
    worker = Worker(database, backend="reference")
    assert worker.once()
    expected = database.get_run(p, baseline["id"])
    modified = database.create_run(p, "Admission paused while running", spec)
    database.enqueue(p, "run", run_id=modified["id"])
    original = database.save_checkpoint
    changed = False

    def capture(*args, **kwargs):
        nonlocal changed
        result = original(*args, **kwargs)
        if not changed:
            limits.save(database, LOCAL_USER, {"runtime": 0, "ai": 2, "notification": 1}, 1)
            changed = True
        return result

    monkeypatch.setattr(database, "save_checkpoint", capture)
    assert worker.once() and changed
    actual = database.get_run(p, modified["id"])
    assert expected["status"] == actual["status"] == "completed"
    assert expected["state_hash"] == actual["state_hash"]
    assert expected["time_us"] == actual["time_us"] == "60000"
    assert limits.snapshot(database)["global"]["limits"]["runtime"] == 0


def test_project_search_pagination_escapes_wildcards(database):
    setup(database)
    for index in range(53):
        database.create_project({"id": LOCAL_USER}, f"Page {index:03d}")
    literal = database.create_project({"id": LOCAL_USER}, "Literal %_ scope")
    first = limits.project_choices(database, "Page ")
    second = limits.project_choices(database, "Page ", 50)
    assert len(first["rows"]) == 50 and first["more"]
    assert len(second["rows"]) == 3 and not second["more"]
    assert not {p["id"] for p in first["rows"]} & {p["id"] for p in second["rows"]}
    assert limits.project_choices(database, "%_")["rows"] == [{"id": literal["id"], "name": literal["name"]}]
