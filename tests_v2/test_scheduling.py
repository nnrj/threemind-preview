import pytest

from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.protocols import RunSpec


def test_worker_kernel_features_preserve_minor_versions_and_match_sql_contract():
    from threemind_kernels.registry import kernel_catalog
    from threemind_runtime.capabilities import kernel_feature

    features = [kernel_feature(item["kernel_id"]) for item in kernel_catalog()]
    assert len(features) == len(set(features))
    assert kernel_feature("threemind.continuous-memory/3.1") == "worker.kernel_continuous-memory3.1"
    assert kernel_feature("threemind.continuous-memory/5.1") == "worker.kernel_continuous-memory5.1"
    for version in ("2", "5"):
        assert kernel_feature(f"threemind.continuous-memory/{version}") == f"worker.kernel_continuous-memory{version}"


def report(*features, queue="runtime", backend="reference"):
    # These scheduling tests vary compute/source support, not protocol versions.
    if queue == "runtime":
        features = (*features, "worker.environment_seed_v1", "worker.raw_readout_v1")
    return {"queue": queue, "backend": backend, "features": {name: {"state": "available"} for name in features}}


def subject(database, environment="mujoco", **kwargs):
    project = database.create_project({"id": LOCAL_USER}, "Scheduling probes")["id"]
    run = database.create_run(
        project, "Subject", RunSpec(environment=environment, duration_s=0.02, **kwargs).model_dump()
    )
    job = database.enqueue(project, "run", run_id=run["id"])
    return project, run, job


def test_unreported_or_incapable_workers_skip_without_consuming_attempts(database):
    project, run, physical = subject(database)
    manual = database.create_run(project, "Manual", RunSpec(environment="manual", duration_s=0.02).model_dump())
    later = database.enqueue(project, "run", run_id=manual["id"])
    assert database.claim("unreported") is None
    basic = report("worker.core")
    database.announce_worker("basic", basic)
    assert database.claim("basic")["id"] == later["id"]
    with database.tx(project) as db:
        waiting = db.execute(
            "SELECT status,attempts,required_features FROM jobs WHERE id=%s", (physical["id"],)
        ).fetchone()
        assert set(waiting.pop("required_features")) == {
            "worker.core", "worker.mujoco", "worker.environment_seed_v1", "worker.raw_readout_v1",
        }
        assert waiting == {
            "status": "pending",
            "attempts": 0,
        }
    assert database.get_run(project, run["id"])["status"] == "queued"
    ready = report("worker.core", "worker.mujoco")
    database.announce_worker("physics", ready)
    assert database.claim("physics")["id"] == physical["id"]


def test_local_capability_snapshot_not_overwritten_registry_controls_claim(database):
    project, _run, job = subject(database)
    database.announce_worker("same-name", report("worker.core", "worker.mujoco"))
    assert database.claim("same-name", capabilities=report("worker.core")) is None
    actual = report("worker.core", "worker.mujoco", backend="native")
    leased = database.claim("same-name", capabilities=actual)
    with database.tx(project) as db:
        saved = db.execute("SELECT * FROM job_assignments WHERE job_id=%s", (job["id"],)).fetchone()
        assert saved["capabilities"]["backend"] == "native"
        assert saved["generation"] == leased["generation"]
    database.announce_worker("same-name", report("worker.core"))
    with database.tx(project) as db:
        assert (
            db.execute("SELECT capabilities FROM job_assignments WHERE job_id=%s", (job["id"],)).fetchone()[
                "capabilities"
            ]
            == actual
        )
    with database.tx() as db:
        assert db.execute("SELECT count(*) AS n FROM job_assignments").fetchone()["n"] == 0


def test_partial_telemetry_supported_and_pending_spec_requirements_refreshed(database):
    project, run, _job = subject(
        database, environment="host", process_telemetry={"enabled": True}, runtime_telemetry={"enabled": True}
    )
    partial = report("worker.core", "worker.telemetry_runtime")
    partial["features"].update(
        {"worker.telemetry_host": {"state": "partial"}, "worker.telemetry_process": {"state": "partial"}}
    )
    database.announce_worker("partial", partial)
    claimed = database.claim("partial")
    assert set(claimed["required_features"]) == set(partial["features"])
    database.finish(claimed, result={})
    second = database.enqueue(project, "run", run_id=run["id"])
    with database.tx(project) as db:
        db.execute("UPDATE runs SET spec=jsonb_set(spec,'{environment}','\"mujoco\"') WHERE id=%s", (run["id"],))
        assert (
            "worker.mujoco"
            in db.execute("SELECT required_features FROM jobs WHERE id=%s", (second["id"],)).fetchone()[
                "required_features"
            ]
        )
    assert database.claim("partial") is None


def test_receipt_failure_rolls_back_lease_and_recovery_retains_each_attempt(database, monkeypatch):
    from threemind_lab import scheduling

    project, _run, job = subject(database, environment="manual")
    caps = report("worker.core")
    database.announce_worker("receipt-worker", caps)
    original = scheduling.public_assignment
    monkeypatch.setattr(scheduling, "public_assignment", lambda _: {"cannot_serialize": object()})
    with pytest.raises(TypeError):
        database.claim("receipt-worker")
    with database.tx(project) as db:
        assert db.execute("SELECT status,attempts FROM jobs WHERE id=%s", (job["id"],)).fetchone() == {
            "status": "pending",
            "attempts": 0,
        }
    monkeypatch.setattr(scheduling, "public_assignment", original)
    first = database.claim("receipt-worker")
    with database.tx() as db:
        db.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (job["id"],))
    database.announce_worker("replacement", caps)
    second = database.claim("replacement")
    assert second["generation"] == first["generation"] + 1
    with pytest.raises(Conflict):
        database.renew(first)
    with database.tx(project) as db:
        rows = db.execute(
            "SELECT worker_id,generation FROM job_assignments WHERE job_id=%s ORDER BY generation", (job["id"],)
        ).fetchall()
    assert rows == [{"worker_id": "receipt-worker", "generation": 1}, {"worker_id": "replacement", "generation": 2}]


def test_waiting_reasons_match_admission_and_preserve_project_metadata_boundary(database):
    from threemind_lab import execution_limits, scheduling
    from threemind_lab.config import Settings

    execution_limits.initialize(database, Settings(database_url=database.test_url, max_active_jobs=1))
    project, _run, job = subject(database)

    def state():
        return scheduling.jobs(database, project)["rows"][0]

    assert state()["reason"] == "no_eligible_worker"
    database.announce_worker("physics", report("worker.core", "worker.mujoco"))
    assert state()["reason"] == "waiting_turn"
    with database.tx() as db:
        db.execute("UPDATE workers SET enabled=false WHERE id='physics'")
    assert state()["reason"] == "no_eligible_worker"
    with database.tx() as db:
        db.execute("UPDATE workers SET enabled=true,heartbeat=now()-interval '91 seconds' WHERE id='physics'")
    assert state()["reason"] == "no_eligible_worker"
    database.announce_worker("physics", report("worker.core", "worker.mujoco"))
    execution_limits.save(database, LOCAL_USER, {"runtime": 0}, 0, project)
    assert state()["reason"] == "admission_paused"
    execution_limits.save(database, LOCAL_USER, {"runtime": None}, 1, project)
    other, _, _ = subject(database, environment="manual")
    database.announce_worker("manual", report("worker.core"))
    claimed = database.claim("manual")
    assert claimed["project_id"] == other
    assert state()["reason"] == "capacity"
    assert "params" not in state() and "spec" not in state() and "global_usage" not in state()
    database.finish(claimed, result={})
    with database.tx(project) as db:
        db.execute("UPDATE jobs SET params=jsonb_build_object('barrier_id','test') WHERE id=%s", (job["id"],))
    assert state()["reason"] == "waiting_checkpoint"
    with database.tx(project) as db:
        db.execute("UPDATE jobs SET params='{}' WHERE id=%s", (job["id"],))
    claimed = database.claim("physics")
    assert state()["reason"] == "running"
    with database.tx() as db:
        db.execute("UPDATE jobs SET lease_until=now()-interval '1 second' WHERE id=%s", (job["id"],))
    assert state()["reason"] == "awaiting_recovery"


def test_queue_api_permissions_receipts_and_stable_pagination(database):
    from test_api import client_for

    from threemind_lab import auth

    owner = auth.create_user(database, "scheduling-admin", "isolated scheduling admin secret", admin=True)
    viewer = auth.create_user(database, "scheduling-viewer", "isolated scheduling viewer secret")
    project = database.create_project(owner, "Visible")["id"]
    outside, _, job = subject(database, environment="manual")
    for _ in range(54):
        database.enqueue(project, "analysis", params={"private": "do not expose"})
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    database.announce_worker("receipt", report("worker.core"))
    database.claim("receipt")
    with client_for(database, "server") as client:
        base = f"/api/v2/projects/{project}/execution/jobs"
        assert client.get(base).status_code == 401
        login = client.post(
            "/api/v2/login", json={"username": "scheduling-viewer", "password": "isolated scheduling viewer secret"}
        ).json()
        first = client.get(base).json()
        second = client.get(base, params=first["next"]).json()
        assert len(first["rows"]) == 50 and len(second["rows"]) == 4 and second["next"] is None
        assert not {r["id"] for r in first["rows"]} & {r["id"] for r in second["rows"]}
        assert "do not expose" not in client.get(base).text
        assert client.get(base, params={"before_time": first["next"]["before_time"]}).status_code == 422
        assert client.get(base, params={**first["next"], "before_time": "2026-01-01T00:00:00"}).status_code == 422
        assert client.get(f"{base}/{job['id']}/assignments").status_code == 404
        assert client.get(f"/api/v2/projects/{outside}/execution/jobs").status_code == 403
        assert client.get(f"/api/v2/admin/execution/projects/{outside}/jobs").status_code == 403
        assert client.get("/api/v2/admin/execution").status_code == 403
        assert client.get("/api/v2/admin/execution/projects").status_code == 403
        assert client.get(f"/api/v2/admin/execution/projects/{outside}").status_code == 403
        assert client.get(f"/api/v2/admin/execution/projects/{outside}/jobs/{job['id']}/assignments").status_code == 403
        client.post("/api/v2/logout", json={}, headers={"X-CSRF-Token": login["csrf"]})
        client.post(
            "/api/v2/login", json={"username": "scheduling-admin", "password": "isolated scheduling admin secret"}
        )
        admin_base = f"/api/v2/admin/execution/projects/{outside}/jobs"
        assert client.get(admin_base).status_code == 200
        assert client.get(f"/api/v2/projects/{outside}/runs").status_code == 403
        receipts = client.get(f"{admin_base}/{job['id']}/assignments").json()
        assert receipts[0]["worker_id"] == "receipt" and receipts[0]["capabilities"]["backend"] == "reference"


@pytest.mark.parametrize("monitor_grant", [False, True])
def test_host_monitor_requires_its_own_action_and_does_not_grant_project_access(database, monitor_grant):
    from test_api import client_for

    from threemind_lab import auth, permissions

    root = permissions.enrich(database, {"id": LOCAL_USER})
    role = permissions.save_role(database, root, key="scheduling-monitor" if monitor_grant else "settings-reader",
                                 name="Isolated monitor grant",
                                 grants=[{"action": "system.read", "scope": "platform"}] +
                                 ([{"action": "execution.read", "scope": "platform"}] if monitor_grant else []))
    user = auth.create_user(database, "custom-monitor", "isolated monitor password", role_ids=[role["id"]])
    assert not user["admin"]
    project, _, job = subject(database, environment="manual")
    with client_for(database, "server") as client:
        login = client.post("/api/v2/login", json={"username": "custom-monitor", "password": "isolated monitor password"}).json()
        expected = 200 if monitor_grant else 403
        for path in ("/api/v2/admin/execution", "/api/v2/admin/execution/projects",
                     f"/api/v2/admin/execution/projects/{project}",
                     f"/api/v2/admin/execution/projects/{project}/jobs",
                     f"/api/v2/admin/execution/projects/{project}/jobs/{job['id']}/assignments"):
            response = client.get(path)
            assert response.status_code == expected, (path, response.text)
        assert client.post("/api/v2/admin/execution/validate", json={"limits": {"runtime": 1, "ai": 1, "notification": 1}},
                           headers={"X-CSRF-Token": login["csrf"]}).status_code == expected
        # Host metadata visibility neither opens the original research project
        # nor confers the ability to change global execution policy.
        assert client.get(f"/api/v2/projects/{project}/execution/jobs").status_code == 403
        assert client.get(f"/api/v2/projects/{project}/runs").status_code == 403
        assert client.post("/api/v2/admin/execution/limits", json={"limits": {}, "expected_revision": 0},
                           headers={"X-CSRF-Token": login["csrf"]}).status_code == 403


def test_host_monitor_action_mapping_is_specific():
    from starlette.requests import Request

    from threemind_lab.permissions import request_action

    def action(path, method="GET"):
        return request_action(Request({"type": "http", "method": method, "scheme": "http", "server": ("local",80),
                                       "path": path, "headers": [], "query_string": b""}))

    assert action("/api/v2/admin/execution") == "execution.read"
    assert action("/api/v2/admin/execution/projects/project/jobs") == "execution.read"
    assert action("/api/v2/admin/execution/validate", "POST") == "execution.read"
    assert action("/api/v2/admin/execution/limits", "POST") == "system.write"
    assert action("/api/v2/admin/execution/projects/project/limits", "POST") == "system.write"
    assert action("/api/v2/system/defaults") == "system.read"
    assert action("/api/v2/projects/project/execution/jobs") == "research.read"


def test_actual_runtime_skips_unavailable_physics_without_backend_fallback(database, monkeypatch):
    from threemind_lab.worker import Worker
    from threemind_runtime import capabilities

    project, physical, job = subject(database)
    manual = database.create_run(
        project, "Executable", RunSpec(environment="manual", duration_s=0.002, clock="unbounded").model_dump()
    )
    database.enqueue(project, "run", run_id=manual["id"])
    monkeypatch.setattr(capabilities, "probe_worker", lambda backend: report("worker.core", backend=backend))
    worker = Worker(database, backend="reference", name="basic-runtime")
    assert worker.once()
    assert database.get_run(project, manual["id"])["status"] == "completed"
    assert database.get_run(project, physical["id"])["status"] == "queued"
    assert not worker.once()
    with database.tx(project) as db:
        assert db.execute("SELECT attempts FROM jobs WHERE id=%s", (job["id"],)).fetchone()["attempts"] == 0
        assert (
            db.execute("SELECT capabilities->>'backend' AS backend FROM job_assignments").fetchone()["backend"]
            == "reference"
        )


def test_lease_starts_after_admission_lock_wait(database):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta

    _project, _, _ = subject(database, environment="manual")
    database.announce_worker("waiting-lock", report("worker.core"))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with database.tx() as locked:
            locked.execute("SELECT pg_advisory_xact_lock(738349202)")
            future = pool.submit(database.claim, "waiting-lock")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with database.tx() as observer:
                    waiting = observer.execute(
                        "SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND wait_event='advisory'"
                    ).fetchone()["n"]
                if waiting:
                    break
                time.sleep(0.01)
            assert waiting
            released_at = locked.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        claimed = future.result(timeout=5)
    assert claimed["lease_until"] >= released_at + timedelta(seconds=60)


@pytest.mark.parametrize("scope", ["host", "process", "runtime"])
def test_disabled_sources_do_not_require_unused_telemetry(database, scope):
    from psycopg.types.json import Jsonb

    project, run, _job = subject(
        database,
        environment="manual",
        **{scope + "_telemetry": {"enabled": True}},
        source_policies={scope + "_enabled": False},
    )
    database.announce_worker("core-only", report("worker.core"))
    first = database.claim("core-only")
    assert first["required_features"] == ["worker.core", "worker.environment_seed_v1", "worker.raw_readout_v1"]
    database.finish(first, result={})
    second = database.enqueue(project, "run", run_id=run["id"])
    with database.tx(project) as db:
        db.execute(
            "UPDATE runs SET spec=jsonb_set(spec,%s,'true') WHERE id=%s",
            (["source_policies", scope + "_enabled"], run["id"]),
        )
    assert database.claim("core-only") is None
    with database.tx(project) as db:
        db.execute(
            "UPDATE runs SET spec=jsonb_set(spec,'{source_policies,background_enabled}',%s) WHERE id=%s",
            (Jsonb(False), run["id"]),
        )
    assert database.claim("core-only")["id"] == second["id"]
