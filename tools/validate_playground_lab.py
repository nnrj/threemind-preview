"""Disposable-container API/worker acceptance; never reads the workstation .env."""

import json
import time
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from threemind_lab.api import create_app
from threemind_lab.bootstrap import provision
from threemind_lab.config import Settings
from threemind_lab.database import Database
from threemind_lab.worker import Worker
from threemind_runtime.robot_protocol import playground_template


def main():
    start = time.monotonic()
    _, url = provision(
        {"host": "threemind-playground-pg", "port": 5432, "dbname": "postgres", "user": "postgres"},
        database="tm_playground_gate_" + uuid4().hex[:8],
        owner="tm_gate_owner_" + uuid4().hex[:8],
        app="tm_gate_app_" + uuid4().hex[:8],
    )
    db = Database(url)
    try:
        with TestClient(create_app(Settings(database_url=url), db)) as client:
            project = client.post("/api/v2/projects", json={"name": "Disposable official task acceptance"}).json()["id"]
            root = f"/api/v2/projects/{project}"
            task = playground_template().model_dump(mode="json")
            created = client.post(
                root + "/runs",
                json={
                    "name": "Panda episode",
                    "spec": {
                        "environment": "robot",
                        "robot_protocol": task,
                        "clock": "unbounded",
                        "checkpoint_us": 1000000,
                    },
                },
            )
            assert created.status_code == 201, created.text
            run = created.json()["id"]
            worker = Worker(db, name="isolated-playground", max_active=1, task_family="playground")
            print("executing complete official episode through worker", flush=True)
            worker.once()
            result = db.get_run(project, run)
            assert result["status"] == "paused", (result["status"], result.get("error"))
            cp, image = db.load_checkpoint(project, run)
            world = cp["context"]["environment"]
            assert world["terminated"]
            assert int(result["time_us"]) == int(world["last_delivery_us"])
            assert int(result["time_us"]) <= 3000000
            with patch(
                "threemind_runtime.robot.RobotWorld", side_effect=AssertionError("API must not reconstruct physics")
            ):
                scene = client.get(root + f"/runs/{run}/world/protocol")
                assert scene.status_code == 200, scene.text
                assert scene.json()["protocol"]["meshes"]
                observed = client.get(root + f"/runs/{run}/world/observation")
                assert observed.status_code == 200, observed.text
            assert db.load_checkpoint(project, run)[1].digest == image.digest
            # Restarting a terminated episode is an explicit world-only action.
            command = client.post(
                root + f"/runs/{run}/research/actions",
                json={
                    "kind": "runtime.advance",
                    "request_id": str(uuid4()),
                    "expected_revision": result["revision"],
                    "duration_us": 20000,
                },
            )
            assert command.status_code < 300, command.text
            worker.once()
            resumed = db.get_run(project, run)
            assert resumed["time_us"] == result["time_us"], "terminal episode must not silently restart"
            reset = client.post(root + f"/runs/{run}/commands", json={"kind": "robot_control", "payload": {"action": "reset_world"}})
            assert reset.status_code < 300, reset.text
            request = client.post(root + f"/runs/{run}/research/actions", json={"kind": "runtime.advance",
                "request_id": str(uuid4()), "expected_revision": resumed["revision"], "duration_us": 20000})
            assert request.status_code < 300, request.text
            worker.once()
            after_reset = db.get_run(project, run)
            assert after_reset["status"] == "paused", after_reset.get("error")
            assert int(after_reset["time_us"]) == int(result["time_us"]) + 20000
            restored = db.load_checkpoint(project, run)[0]["context"]["environment"]
            assert restored["steps"] == 1 and not restored["terminated"]
            print(
                json.dumps(
                    {
                        "passed": True,
                        "seconds": time.monotonic() - start,
                        "status": result["status"],
                        "steps": world["steps"],
                        "time_us": result["time_us"],
                        "core_hash": image.digest,
                        "scene_geometries": len(scene.json()["protocol"]["geometries"]),
                        "versions": world["versions"],
                        "world_only_reset": True,
                        "scene_uncompressed_bytes": world["scene_archive"]["bytes"],
                        "scene_base64_bytes": len(world["scene_archive"]["zlib"]),
                    }
                ),
                flush=True,
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
