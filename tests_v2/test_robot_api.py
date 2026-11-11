from uuid import uuid4

from fastapi.testclient import TestClient

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.configuration import validate_configuration
from threemind_lab.worker import Worker


def test_robot_protocol_library_actual_execution_observation_and_operation_parity(database):
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Robot acceptance"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        catalogue = client.get(base + "/robots/catalogue").json()
        task = catalogue["templates"]["custom-arm-reach"]
        checked = client.post(base + "/robots/validate", json={"protocol": task})
        assert checked.status_code == 200, checked.text
        assert checked.json()["model"]["motors"] == 4
        saved = client.post(base + "/worlds", json={"operation_id": str(uuid4()), "protocol": task})
        assert saved.status_code == 201, saved.text
        assert len(client.get(base + "/worlds?kind=robot").json()["rows"]) == 1
        assert not client.get(base + "/worlds").json()["rows"]
        result = client.post(
            base + "/runs",
            json={
                "name": "Robot subject",
                "spec": {"environment": "robot", "robot_protocol": task, "clock": "unbounded", "duration_s": 0.087},
            },
        )
        assert result.status_code == 201, result.text
        run = result.json()
        with database.tx(project) as db:
            features = db.execute("SELECT required_features FROM jobs WHERE run_id=%s", (run["id"],)).fetchone()
        assert "worker.robot_v1" in features["required_features"]
        worker = Worker(database, name="robot-acceptance")
        worker.once()
        final = database.get_run(project, run["id"])
        assert final["status"] == "completed", final.get("error")
        assert "task_distance" in final["metrics"]
        cp, image = database.load_checkpoint(project, run["id"])
        assert cp["context"]["environment"]["kind"] == "robot"
        observed = client.get(base + f"/runs/{run['id']}/world/observation")
        assert observed.status_code == 200, observed.text
        assert observed.json()["observation"]["control_mode"] == "torque"
        protocol = client.get(base + f"/runs/{run['id']}/world/protocol").json()
        assert protocol["robot_protocol"] == task
        assert database.load_checkpoint(project, run["id"])[1].digest == image.digest
        current = final["spec"]
        changed = dict(current, robot_protocol=dict(task, control=dict(task["control"], mode="position")))
        assert not validate_configuration(changed, current=current)["valid"]
        rows = {r["id"]: r for r in client.get("/api/v2/operations/catalog").json()["operations"]}
        assert "robot.validate" in rows and "world.observe" in rows
        other = client.post("/api/v2/projects", json={"name": "other"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/runs/{run['id']}/world/observation").status_code == 404
