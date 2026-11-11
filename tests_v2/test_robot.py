import copy
import json

import pytest

from threemind_runtime.robot import RobotWorld
from threemind_runtime.robot_protocol import parse_robot
from threemind_runtime.robot_templates import robot_templates


@pytest.mark.parametrize("identity", ["custom-arm-reach", "custom-arm-push", "custom-mobile"])
@pytest.mark.parametrize("mode", ["torque", "position", "velocity", "skill"])
def test_body_control_sensors_metrics_and_exact_resume(identity, mode):
    protocol = robot_templates()[identity].model_dump(mode="json")
    protocol["control"]["mode"] = mode
    with RobotWorld(protocol, 11, environment_seed=7) as a:
        for now in range(0, 100000, 10000):
            a.sample(now, [(2, 0.1), (10, 0.8)])
        state = json.loads(json.dumps(a.capture()))
        with RobotWorld(protocol, 11, state, environment_seed=7) as b:
            for now in range(100000, 200000, 10000):
                assert a.sample(now, [(2, 0.2), (10, 0.9)]) == b.sample(now, [(2, 0.2), (10, 0.9)])
            assert a.capture() == b.capture()
        before = a.capture()
        for _ in range(3):
            a.observation()
            a.task_metrics()
            a.scene_protocol()
        assert before == a.capture()
        assert all(c["mode"] == mode for c in a.last_controls)
        assert a.last_measurements[-1]["kind"] == "ideal-optical-beacon/1"
        assert all("success" not in m["id"] for m in a.last_measurements)
        assert a.task_metrics()["task_mechanical_work_j"] >= 0


def test_task_controls_do_not_modify_old_worlds_or_allow_silent_fallback():
    protocol = robot_templates()["custom-arm-reach"].model_dump(mode="json")
    with RobotWorld(protocol, 11) as a:
        a.sample(0, action=[1.0] * 4)
        assert all(r["control"] > 0 for r in a.last_controls)
        state = a.capture()
        with pytest.raises(ValueError, match="normalized"):
            a.sample(10000, action=[float("nan")] * 4)
        changed = copy.deepcopy(protocol)
        changed["control"]["mode"] = "position"
        with pytest.raises(ValueError, match="continuation"):
            RobotWorld(changed, 11, state)
        with pytest.raises(ValueError, match="consecutive"):
            a.sample(0)
        assert a.capture() == state
    protocol["control"]["mode"] = "automatic_magic"
    with pytest.raises(ValueError):
        parse_robot(protocol)


def test_identical_target_and_input_without_labels():
    protocol = robot_templates()["custom-arm-reach"].model_dump(mode="json")
    changed = copy.deepcopy(protocol)
    changed["name"] = "another interpretation"
    with RobotWorld(protocol, 41, environment_seed=9) as a, RobotWorld(changed, 41, environment_seed=9) as b:
        assert a.sample(0, [(2, 0.8)]) == b.sample(0, [(2, 0.8)])
        assert a.capture()["world"]["integration"] == b.capture()["world"]["integration"]


def test_intervention_has_explicit_expiry_and_survives_snapshot():
    task = robot_templates()["custom-arm-reach"]
    with RobotWorld(task, 11) as a:
        a.sample(0)
        receipt = a.intervene(5000, {"action": "actuators", "commands": [0.2] * 4, "duration_us": 20000})
        assert receipt["effective_time_us"] == "10000"
        a.intervene(5000, {"action": "force", "body_id": "tool", "force": [0.1, 0.0, 0.0], "duration_us": 20000})
        with RobotWorld(task, 11, a.capture()) as b:
            for now in (10000, 20000, 30000):
                assert a.sample(now) == b.sample(now)
                assert a.capture() == b.capture()
                assert a.last_action_source == ("research_intervention" if now < 30000 else "core_projection")
            assert a.external_force is None and a.external_action is None
        before = a.capture()
        with pytest.raises(ValueError, match="whole"):
            a.intervene(40000, {"action": "actuators", "commands": [0.2] * 4, "duration_us": 15000})
        assert a.capture() == before


def test_robot_import_preserves_explicit_old_kernel_identity():
    from threemind_kernels.registry import BASELINE_KERNEL
    from threemind_runtime.host import create_engine
    from threemind_runtime.robot_session import RobotSession

    image = create_engine(kernel_id=BASELINE_KERNEL).capture_state()
    with RobotSession(robot_templates()["custom-arm-reach"], image=image) as session:
        assert session.kernel_id == BASELINE_KERNEL
        session.advance(20000)
        assert session.engine.capture_state().to_dict()["dynamics"] == BASELINE_KERNEL


def test_robot_protocol_rejects_duplicate_keys_and_ambiguous_variant():
    value = robot_templates()["custom-arm-reach"].model_dump(mode="json")
    raw = json.dumps(value)
    with pytest.raises(ValueError, match="duplicate"):
        parse_robot('{"name":"duplicate",' + raw[1:])
    value["control"].update(mode="position", actuator_variant="ideal-torque")
    with pytest.raises(ValueError, match="requires torque"):
        parse_robot(value)


@pytest.mark.parametrize("backend", ["native", "reference"])
def test_robot_session_restores_brain_and_inflight_sensory_input(backend):
    from threemind_core import StateImage
    from threemind_runtime.robot_session import RobotSession

    task = robot_templates()["custom-arm-reach"]
    with RobotSession(task, backend=backend) as a:
        a.advance(87000)
        image = StateImage.from_dict(a.engine.capture_state().to_dict())
        context = json.loads(json.dumps(a.context()))
        with RobotSession(task, backend=backend, image=image, context=context) as b:
            a.advance(190000)
            b.advance(110000)
            b.advance(190000)
            assert a.engine.capture_state().digest == b.engine.capture_state().digest
            assert a.context() == b.context()


@pytest.mark.parametrize("identity", ["g1", "piper", "so101"])
def test_installed_real_assets_have_actual_dofs_and_restore(identity):
    from threemind_runtime.robot_assets import installed, task_for_asset

    if not installed(identity):
        pytest.skip("pinned optional asset not installed")
    task = task_for_asset(identity)
    with RobotWorld(task, 11) as a:
        a.sample(0)
        state = a.capture()
        with RobotWorld(task, 11, state) as b:
            assert a.sample(10000, [(2, 0.6)]) == b.sample(10000, [(2, 0.6)])
            assert a.capture() == b.capture()
        assert a.model.nu == {"g1": 29, "piper": 7, "so101": 6}[identity]
        assert "meshes" in a.scene_protocol()
    if identity == "so101":
        task.control.mode = "torque"
        with pytest.raises(ValueError, match="not supported"):
            RobotWorld(task, 11)
        task.control.actuator_variant = "ideal-torque"
        with RobotWorld(task, 11) as a:
            a.sample(0, action=[0.1] * 6)
            state = a.capture()
            with RobotWorld(task, 11, state) as b:
                assert a.sample(10000) == b.sample(10000)
                assert a.capture() == b.capture()
            assert a.last_controls[0]["mode"] == "torque"
