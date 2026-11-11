from fastapi.testclient import TestClient

from threemind_lab import auth
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.worker import Worker


def client_for(db, mode="workstation"):
    return TestClient(create_app(Settings(database_url=db.test_url, mode=mode), db))


def test_server_auth_project_isolation_and_session_revocation(database):
    owner = auth.create_user(database, "research-owner", "a long secret for tests", admin=True)
    viewer = auth.create_user(database, "research-viewer", "another long test secret")
    project = database.create_project(owner, "Private")
    run = database.create_run(project["id"], "Private model", {})
    with client_for(database, "server") as client:
        assert client.get("/api/v2/projects").status_code == 401
        login = client.post(
            "/api/v2/login", json={"username": "research-viewer", "password": "another long test secret"}
        )
        assert login.status_code == 200
        assert "httponly" in login.headers["set-cookie"].lower()
        csrf = login.json()["csrf"]
        assert client.get(f"/api/v2/projects/{project['id']}/runs/{run['id']}").status_code == 403
        with database.tx() as db:
            db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project["id"], viewer["id"]))
        url = f"/api/v2/projects/{project['id']}/runs"
        assert client.get(url).status_code == 200
        assert client.post(url, json={"name": "Denied"}, headers={"X-CSRF-Token": csrf}).status_code == 403
        assert client.post("/api/v2/projects", json={"name": "Denied"}).status_code == 403
        assert client.get("/api/v2/admin").status_code == 403
        assert client.post("/api/v2/logout", json={}, headers={"X-CSRF-Token": csrf}).status_code == 200
        assert client.get(url).status_code == 401
        assert (
            client.post(
                "/api/v2/login",
                json={"username": "research-owner", "password": "a long secret for tests"},
                headers={"Origin": "https://untrusted.invalid"},
            ).status_code
            == 403
        )


def test_live_export_barrier_and_paused_cancel(database):
    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "Export barriers"}).json()["id"]
        base = f"/api/v2/projects/{p}"
        r = client.post(
            f"{base}/runs",
            json={
                "name": "Short",
                "spec": {
                    "environment": "replay",
                    "clock": "unbounded",
                    "duration_s": 0.05,
                    "replay": [{"time_us": "0", "channels": [[1, 0.8], [2, 0.7]]}],
                },
            },
        )
        assert r.status_code == 201, r.text
        rid = r.json()["id"]
        job = client.post(f"{base}/runs/{rid}/exports", json={"format": "tmind"})
        assert job.status_code == 202 and "barrier_id" in job.json()["params"]
        worker = Worker(database)
        assert worker.once()
        assert worker.once()
        jobs = client.get(f"{base}/jobs").json()
        export = next(j for j in jobs if j["id"] == job.json()["id"])
        assert export["status"] == "done", export.get("error")
        assert export["params"]["barrier_ready"]
        artifact = export["result"]["artifact_id"]
        raw = client.get(f"{base}/artifacts/{artifact}")
        assert raw.status_code == 200 and raw.headers["content-disposition"].startswith("attachment")
        from threemind_runtime import ArtifactCodec

        image = ArtifactCodec.decode(raw.content)
        assert image.digest == export["result"]["state_hash"]
        assert int(image.to_dict()["time_us"]) <= 50000
        graph = client.get(f"{base}/runs/{rid}/graph").json()
        assert client.get(f"{base}/runs/{rid}/graph?since={graph['revision']}").status_code == 304
        assert client.get("/api/v2/not-an-api").status_code == 404
        cp = client.get(f"{base}/runs/{rid}/checkpoints").json()[0]
        changes = client.get(f"{base}/runs/{rid}/data/changes?checkpoint_id={cp['id']}")
        assert changes.status_code == 200 and changes.json()["checkpoint_id"] == cp["id"]
        selection = client.post(
            f"{base}/runs/{rid}/data-exports",
            json={"table": "edges", "format": "parquet", "checkpoint_id": cp["id"], "minimum": 1},
        )
        assert selection.status_code == 202, selection.text
        assert worker.once()
        query_job = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == selection.json()["id"])
        assert query_job["status"] == "done", query_job.get("error")
        assert query_job["result"]["rows"] == 0
        assert client.get(f"{base}/runs/{rid}").json()["status"] == "completed"
        imported = client.post(f"{base}/imports", files={"file": ("model.tmind", raw.content, "application/zip")})
        assert imported.status_code == 201, imported.text
        paused = imported.json()["id"]
        assert client.post(f"{base}/runs/{paused}/commands", json={"kind": "cancel"}).status_code == 200
        assert client.get(f"{base}/runs/{paused}").json()["status"] == "cancelled"


def test_paired_study_physics_and_analysis(database):
    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "Paired"}).json()["id"]
        base = f"/api/v2/projects/{p}"
        study = client.post(
            f"{base}/studies",
            json={
                "name": "Physics pairs",
                "warmup_s": 0.1,
                "base": {"environment": "mujoco", "clock": "unbounded", "duration_s": 0.2},
                "seeds": [11, 23],
            },
        )
        assert study.status_code == 202, study.text
        sid = study.json()["params"]["study_id"]
        worker = Worker(database)
        for _ in range(5):
            assert worker.once()
        runs = client.get(f"{base}/runs").json()
        branches = [r for r in runs if r["spec"].get("study_id") == sid]
        assert len(branches) == 4
        assert all(r["status"] == "completed" for r in branches), [(r["status"], r["error"]) for r in branches]
        for seed in (11, 23):
            pair = [r for r in branches if r["spec"]["block_seed"] == seed]
            assert pair[0]["origin_hash"] == pair[1]["origin_hash"]
            assert pair[0]["parent_id"] == pair[1]["parent_id"]
        analysis = client.post(
            f"{base}/analyses", json={"study_id": sid, "control": "完整可塑性", "treatment": "关闭可塑性"}
        )
        assert analysis.status_code == 202
        assert worker.once()
        job = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == analysis.json()["id"])
        assert job["status"] == "done", job.get("error")
        assert all(m["n"] == 2 for m in job["result"]["analysis"]["metrics"])
        # Retrying study orchestration must not create new branches.
        database.enqueue(p, "study", study.json()["params"])
        assert worker.once()
        assert len(client.get(f"{base}/runs").json()) == 6
