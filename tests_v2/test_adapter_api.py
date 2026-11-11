from test_api import client_for

from threemind_lab import auth, permissions
from threemind_lab.database import LOCAL_USER
from threemind_lab.worker import Worker


def test_adapter_bindings_worker_report_parameter_contracts_and_permissions(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Adapter contracts"}).json()["id"]
        run = client.post(
            f"/api/v2/projects/{project}/runs",
            json={
                "name": "Bound tools",
                "spec": {
                    "environment": "manual",
                    "clock": "unbounded",
                    "duration_s": 0.02,
                    "body_filter": {"enabled": True},
                    "interoception": {"enabled": True},
                },
            },
        ).json()["id"]
        url = f"/api/v2/projects/{project}/runs/{run}"
        data = client.get(url + "/adapters").json()
        assert data["worker"] is None
        rows = {r["id"]: r for r in data["adapters"]}
        assert rows["body-filter"]["binding_status"] == "inactive"
        assert rows["simulated-interoception"]["binding_status"] == "configured"
        assert rows["camera"]["binding_status"] == "disabled"
        assert any(p["immutable"] for p in rows["text-sensor"]["parameters"])
        worker = Worker(database)
        assert worker.once()
        data = client.get(url + "/adapters").json()
        assert data["worker"]["id"] == worker.name
        report = data["worker"]["capabilities"]
        assert data["worker"]["online"] and report["scope"] == "worker"
        assert report["features"]["worker.core"]["state"] == "available"
        assert data["api"]["scope"] == "api" and "browser.microphone" not in data["api"]["features"]
        assert client.get("/api/v2/capabilities").json()["all_workers_visible"]
        catalogue = client.get("/api/v2/adapters").json()
        assert {r["id"] for r in catalogue["adapters"]} == set(rows)
        sensory = client.get(url + "/sensory").json()
        assert {r["id"] for r in sensory["adapters"]} == set(rows)
        foreign = client.post("/api/v2/projects", json={"name": "Foreign"}).json()["id"]
        assert client.get(url.replace(project, foreign) + "/adapters").status_code == 404
    # Project-viewer membership and platform role are separate authorities.
    # The built-in user can read host status; this fixture is a project-only reader.
    role = permissions.save_role(
        database,
        permissions.enrich(database, {"id": LOCAL_USER}),
        key="adapter-project-viewer",
        name="Project adapter viewer",
        grants=[{"action": "runs.read", "scope": "member_projects"}],
    )
    viewer = auth.create_user(
        database, "adapter-viewer", "isolated adapter viewer secret", role_ids=[role["id"]]
    )
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        assert client.get("/api/v2/capabilities").status_code == 401
        assert client.get("/api/v2/adapters").status_code == 401
        client.post("/api/v2/login", json={"username": "adapter-viewer", "password": "isolated adapter viewer secret"})
        data = client.get("/api/v2/capabilities").json()
        assert not data["all_workers_visible"] and data["workers"] == []
        assert client.get(url + "/adapters").json()["worker"]["id"] == worker.name
        assert client.get(url.replace(project, foreign) + "/adapters").status_code == 403


def test_incapable_worker_reports_without_claiming_or_switching_backend(database, monkeypatch):
    from threemind_runtime import capabilities

    monkeypatch.setattr(
        capabilities,
        "probe_worker",
        lambda backend: {
            "scope": "worker",
            "backend": backend,
            "features": {"worker.core": {"state": "unavailable", "reason": "native binary missing in isolated test"}},
        },
    )
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Worker capability"}).json()["id"]
        run = client.post(
            f"/api/v2/projects/{project}/runs", json={"name": "Await native", "spec": {"environment": "manual"}}
        ).json()["id"]
        worker = Worker(database, backend="native")
        assert not worker.once()
        with database.tx(project) as db:
            job = db.execute("SELECT status,attempts FROM jobs WHERE run_id=%s", (run,)).fetchone()
            assert job["status"] == "pending" and job["attempts"] == 0
        rows = client.get("/api/v2/capabilities").json()["workers"]
        assert rows[0]["capabilities"]["backend"] == "native" and rows[0]["online"]
