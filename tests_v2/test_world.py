import copy
import json

import pytest

from threemind_core import Config, StateImage
from threemind_runtime import create_engine
from threemind_runtime.world import PhysicalWorld, compile_xml
from threemind_runtime.world_schema import CameraSensor, default_world, parse_world


def test_world_protocol_strict_references_units_and_no_script_surface():
    value = default_world().model_dump(mode="json")
    assert parse_world(value).digest == default_world().digest
    for patch in (
        {"script": "print(1)"},
        {"physics": {"step_us": True}},
        {"physics": {"sample_us": 21000}},
        {"physics": {"gravity": [0, 0, float("nan")]}},
        {"bodies": [{"id": "a", "parent_id": "b"}, {"id": "b", "parent_id": "a"}]},
        {"geometries": [{"id": "floor", "shape": "box", "size": [1]}]},
        {"joints": [{"id": "j", "body_id": "body", "axis": [0, 0, 0]}]},
        {"sensors": [{"id": "a", "port": 2, "kind": "touch", "geometry_id": "missing"}]},
    ):
        with pytest.raises(ValueError):
            parse_world(value | patch)
    with pytest.raises(ValueError, match="duplicate"):
        parse_world('{"schema_id":"threemind.world/1","schema_id":"threemind.world/1"}')
    with pytest.raises(ValueError, match="4 MiB"):
        parse_world(" " * (4 * 1024 * 1024 + 1))
    bad = copy.deepcopy(value)
    bad["sensors"][1]["port"] = bad["sensors"][0]["port"]
    with pytest.raises(ValueError, match="port"):
        parse_world(bad)
    with pytest.raises(ValueError, match="unit"):
        parse_world(value | {"bodies": [{"id": "body", "quaternion": [1, 1, 0, 0]}]})


def test_world_observer_labels_editor_order_and_channels_do_not_change_physics():
    spec = default_world()
    changed = spec.model_dump(mode="json")
    changed["label"] = "观察者的新解释"
    for key in ("bodies", "geometries", "joints", "motors", "sensors", "forces"):
        changed[key].reverse()
        for item in changed[key]:
            item["label"] = "仅供观察的标签"
    renamed = parse_world(changed)
    assert renamed.digest != spec.digest and renamed.physical_digest == spec.physical_digest
    assert compile_xml(renamed) == compile_xml(spec)
    with PhysicalWorld(spec, 11) as a, PhysicalWorld(renamed, 11) as b:
        for now in range(0, 200000, 20000):
            before = a.capture()["integration"]
            for _ in range(3):
                a.observation()
            assert before == a.capture()["integration"]
            assert a.sample(now, [(7, 0.3), (8, 0.6)]) == b.sample(now, [(8, 0.6), (7, 0.3)])
        assert a.capture()["integration"] == b.capture()["integration"]
        channels = a.sample(200000).channels
        assert len({c for c, _ in channels}) == len(channels)


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_world_independent_runtime_learning_and_mid_interval_exact_resume(backend):
    spec = default_world()
    a = create_engine(Config(), backend=backend)
    with PhysicalWorld(spec, 23, environment_seed=47) as world:
        for now in range(0, 80000, 20000):
            a.inject(world.sample(now, a.activations()))
            a.advance_to(now + 20000)
        a.inject(world.sample(80000, a.activations()))
        a.advance_to(87000)
        physics = json.loads(json.dumps(world.capture()))
        b = create_engine(state=StateImage.from_dict(a.capture_state().to_dict()), backend=backend)
        with PhysicalWorld(spec, 23, physics, environment_seed=47) as resumed:
            assert resumed.capture()["integration"] == physics["integration"]
            for now in range(100000, 260000, 20000):
                a.advance_to(now)
                b.advance_to(now)
                left = world.sample(now, a.activations())
                right = resumed.sample(now, b.activations())
                assert left == right
                a.inject(left)
                b.inject(right)
                assert a.capture_state().digest == b.capture_state().digest
            assert a.metrics()["nodes"] > 0
            assert world.capture()["integration"] == resumed.capture()["integration"]
            # Physics can be one sensory interval ahead; observations state both clocks.
            assert resumed.observation()["delivery_time_us"] == "260000"
            assert b.time_us == 240000
        with pytest.raises(ValueError, match="continuation"):
            PhysicalWorld(spec, 24, physics, environment_seed=47)
        with pytest.raises(ValueError, match="continuation"):
            PhysicalWorld(spec, 23, physics, environment_seed=48)


def test_world_camera_is_real_headless_sensor_and_closes_its_context():
    spec = default_world()
    spec.sensors.append(CameraSensor(id="eye", port=8, body_id="body", position=(0.0, 0.0, 1.0)))
    with PhysicalWorld(spec, 11) as world:
        first = world.sample(0)
        saved = json.loads(json.dumps(world.capture()))
        image = next(v for v in saved["measurements"] if v["kind"] == "camera_rgb")["values"]
        assert len(image) == 8 * 8 * 3 and max(image) > min(image)
        assert len(first.channels) > 4
        with PhysicalWorld(spec, 11, saved) as continued:
            assert world.sample(20000) == continued.sample(20000)
            assert world.capture()["integration"] == continued.capture()["integration"]
    assert not world.renderers
    changed = spec.model_dump(mode="json")
    changed["geometries"][0]["rgba"] = [1, 0, 0, 1]
    with PhysicalWorld(parse_world(changed), 11) as red:
        red.sample(0)
        assert red.last_measurements[-1]["values"] != image
    assert all("world" not in k for k in create_engine(backend="reference").capture_state().to_dict())
