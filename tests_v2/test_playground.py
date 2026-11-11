import copy
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.protocols import RunSpec
from threemind_runtime.robot_protocol import parse_robot, playground_template
from threemind_runtime.robot_templates import custom_arm


def test_protocol_preserves_old_serialization_and_does_not_load_optional_physics():
    old = custom_arm().model_dump(mode="json")
    assert "playground" not in old
    assert parse_robot(old).model_dump(mode="json") == old
    task = playground_template().model_dump(mode="json")
    spec = RunSpec(environment="robot", robot_protocol=task)
    assert spec.model_dump(mode="json")["robot_protocol"] == task
    from threemind_runtime.registry import default_adapter_registry

    contract = default_adapter_registry().describe("robot-task", spec.model_dump(mode="json"))
    assert contract["version"] == "robot-task/2"
    assert default_adapter_registry().describe("robot-task", {"robot_protocol": None})["version"] == "robot-task/1"
    assert "jax" not in sys.modules
    for field, value in (
        ("world", dict(task["world"], label="changed")),
        ("target", [1.0, 0.0, 0.0]),
        ("control", dict(task["control"], mode="torque")),
    ):
        altered = copy.deepcopy(task)
        altered[field] = value
        with pytest.raises(ValueError):
            parse_robot(altered)
    changed = copy.deepcopy(task)
    changed["playground"]["implementation"] = "warp"
    with pytest.raises(ValueError, match="CUDA"):
        parse_robot(changed)


def test_scene_transport_is_exact_and_rejects_corruption_and_expansion():
    from threemind_runtime.playground_scene import pack_scene, unpack_scene

    value = {"meshes": {"1": {"vertices": [0.0, 1.0, -0.25] * 10000}}, "name": "只读场景"}
    archive = pack_scene(value)
    assert len(archive["zlib"]) < archive["bytes"] / 10
    assert unpack_scene(archive) == value
    changed = archive | {"sha256": "0" * 64}
    with pytest.raises(ValueError, match="checksum"):
        unpack_scene(changed)
    with pytest.raises(ValueError, match="budget"):
        unpack_scene(archive | {"bytes": 65 * 2**20})


def test_official_task_library_and_compute_requirements_without_local_jax(database):
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Playground acceptance"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        task = client.get(base + "/robots/catalogue").json()["templates"]["playground-panda"]
        checked = client.post(base + "/robots/validate", json={"protocol": task})
        assert checked.status_code == 200, checked.text
        assert checked.json()["required_capabilities"] == ["worker.playground_jax_cpu"]
        assert checked.json()["layout"] is None
        assert checked.json()["validation_scope"].startswith("protocol-only")
        saved = client.post(base + "/worlds", json={"operation_id": str(uuid4()), "protocol": task})
        assert saved.status_code == 201, saved.text
        assert len(client.get(base + "/worlds?kind=robot").json()["rows"]) == 1
        assert not client.get(base + "/worlds").json()["rows"]
        created = client.post(
            base + "/runs",
            json={
                "name": "Official task",
                "spec": {"environment": "robot", "robot_protocol": task, "clock": "unbounded"},
            },
        )
        assert created.status_code == 201, created.text
        run = created.json()
        assert run["spec"]["robot_protocol"]["playground"] == task["playground"]
        with database.tx(project) as db:
            features = db.execute("SELECT required_features FROM jobs WHERE run_id=%s", (run["id"],)).fetchone()[
                "required_features"
            ]
        assert "worker.playground_jax_cpu" in features
        # A native MuJoCo worker cannot accidentally claim a JAX task.
        assert (
            database.claim(
                "wrong-physics",
                capabilities={"features": {key: {"state": "available"} for key in ("worker.core", "worker.robot_v1")}},
            )
            is None
        )
        ordinary = client.post(
            base + "/runs",
            json={"name": "Ordinary consciousness", "spec": {"environment": "manual", "clock": "unbounded"}},
        ).json()
        with database.tx(project) as db:
            other = db.execute("SELECT required_features FROM jobs WHERE run_id=%s", (ordinary["id"],)).fetchone()[
                "required_features"
            ]
        report = {
            "task_family": "playground",
            "features": {key: {"state": "available"} for key in set(features) | set(other)},
        }
        claimed = database.claim("dedicated-playground", capabilities=report)
        assert str(claimed["run_id"]) == run["id"]
        assert database.claim("dedicated-playground", capabilities=report) is None
