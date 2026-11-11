from uuid import uuid4

from fastapi.testclient import TestClient

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.worker import Worker


def test_language_session_jobs_bus_checkpoint_and_operation_parity(database):
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Language acceptance"}).json()["id"]
        base = f"/api/v2/projects/{project}/language"
        body = {"request_id": str(uuid4()), "name": "Language subject", "protocol": {"response_us": 100000}}
        response = client.post(base + "/sessions", json=body)
        assert response.status_code == 202, response.text
        run = response.json()["run_id"]
        assert client.post(base + "/sessions", json=body).json()["replayed"]
        worker = Worker(database, name="language-test")
        assert worker.once()
        state = database.get_run(project, run)
        assert state["revision"] == 1, state
        request = {"request_id": str(uuid4()), "expected_revision": 1, "text": "甲是松子。", "intensity": 1.0}
        sent = client.post(base + f"/sessions/{run}/turns", json=request)
        assert sent.status_code == 202, sent.text
        assert worker.once()
        turns = client.get(base + f"/sessions/{run}/turns").json()["rows"]
        assert turns[0]["status"] == "done", turns[0]["error"]
        result = turns[0]["result"]
        assert result["revision"] == 2
        assert result["process"]["has_activity"]
        assert result["interpretation"]["text"] is None
        assert client.post(base + f"/sessions/{run}/turns", json=request).json()["replayed"]
        assert database.get_run(project, run)["revision"] == 2
        assert (
            client.post(base + f"/sessions/{run}/turns", json=request | {"request_id": str(uuid4())}).status_code == 409
        )
        fork = client.post(base + "/sessions", json=body | {"request_id": str(uuid4()), "source_run_id": run})
        assert fork.status_code == 202, fork.text
        assert worker.once()
        assert (
            database.load_checkpoint(project, fork.json()["run_id"])[1].digest
            == database.load_checkpoint(project, run)[1].digest
        )
        other = client.post("/api/v2/projects", json={"name": "Other language project"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/language/sessions/{run}/turns").status_code == 404
        operations = {r["id"] for r in client.get("/api/v2/operations/catalog").json()["operations"]}
        assert {"language.create", "language.send", "language.train_scratch", "language.train_head"} <= operations
        exported = client.get(base + f"/sessions/{run}/bundle?revision=2")
        assert exported.status_code == 200
        identity = str(uuid4())
        restored = client.post(
            base + f"/imports?request_id={identity}",
            content=exported.content,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert restored.status_code == 201, restored.text
        assert database.load_checkpoint(project, identity)[1].digest == database.load_checkpoint(project, run)[1].digest
        assert client.post(base + f"/imports?request_id={identity}", content=exported.content).json()["replayed"]
        assert (
            client.post(
                base + f"/sessions/{identity}/turns",
                json=request | {"request_id": str(uuid4()), "expected_revision": 1},
            ).status_code
            == 202
        )
        assert worker.once()
        assert client.get(base + f"/sessions/{identity}/turns").json()["rows"][0]["status"] == "done"


def test_scratch_language_training_and_bound_artifact(database):
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Scratch training acceptance"}).json()["id"]
        base = f"/api/v2/projects/{project}/language"
        p = {
            "input_model": "scratch",
            "scratch_width": 32,
            "scratch_layers": 1,
            "embedding_dimensions": 32,
            "response_us": 100000,
        }
        response = client.post(
            base + "/scratch-training",
            json={
                "request_id": str(uuid4()),
                "training": {"protocol": p, "texts": ["甲是松子。", "乙是铃铛。"], "steps": 2},
            },
        )
        assert response.status_code == 202, response.text
        worker = Worker(database, name="language-training-test")
        assert worker.once()
        view = client.get(base).json()
        job = view["jobs"][0]
        assert job["status"] == "done", job
        model = view["models"][0]
        body = {
            "request_id": str(uuid4()),
            "protocol": p | {"input_checkpoint_sha256": model["sha256"]},
            "assets": {"input": model["id"]},
        }
        response = client.post(base + "/sessions", json=body)
        assert response.status_code == 202, response.text
        assert worker.once()
        run = response.json()["run_id"]
        response = client.post(
            base + f"/sessions/{run}/turns",
            json={"request_id": str(uuid4()), "expected_revision": 1, "text": "甲是松子。"},
        )
        assert response.status_code == 202, response.text
        assert worker.once()
        row = client.get(base + f"/sessions/{run}/turns").json()["rows"][0]
        assert row["status"] == "done", row["error"]
        assert row["result"]["process"]["has_activity"]
