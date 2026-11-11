import copy
import json

import pytest

from threemind_runtime.population_world import PopulationWorld, SpawnLayout, body_scope
from threemind_runtime.world import PhysicalWorld
from threemind_runtime.world_schema import CameraSensor, TouchSensor, default_world, parse_world


def specimen():
    world = default_world()
    for joint in world.joints:
        joint.initial_jitter = 0
    return world


def test_shared_bodies_interact_once_while_independent_habitats_are_isolated():
    common = (specimen(), "body", 2, 11, 29)
    with (
        PopulationWorld(*common, layout=SpawnLayout(spacing=0.2)) as shared,
        PopulationWorld(*common, habitat="independent", layout=SpawnLayout(spacing=0.2)) as separate,
    ):
        for world in (shared, separate):
            world.activate("n0")
            world.activate("n1")
            assert {f.time_us for f in world.step({"n0": None, "n1": None}).values()} == {20000}
        assert len(shared.habitats) == 1 and len(separate.habitats) == 2
        assert shared.habitats["shared"].data.time == pytest.approx(0.02)  # Not once per brain.
        assert all(h.data.time == pytest.approx(0.02) for h in separate.habitats.values())
        assert shared.measurements()["n0"]["contact_force"] > 0
        assert separate.measurements()["n0"]["contact_force"] == 0
        assert shared.measurements()["n0"]["position"] != separate.measurements()["n0"]["position"]
        with PopulationWorld(
            *common, habitat="independent", layout=SpawnLayout(spacing=0.2), state=separate.capture()
        ) as control:
            for _ in range(6):
                actual = separate.step({"n0": [(7, 0.8)], "n1": None})
                baseline = control.step({"n0": None, "n1": None})
                assert actual["n1"] == baseline["n1"]
            assert separate.measurements()["n0"] != control.measurements()["n0"]


def test_physical_prefix_is_not_a_change_to_sensory_or_motor_identity():
    world = specimen()
    world.joints[0].initial = 0.2
    world.sensors = [s for s in world.sensors if s.kind.startswith("joint_")]
    with PhysicalWorld(world, 17) as original, PopulationWorld(world, "body", 2, 17, 39) as population:
        population.activate("parent")
        population.activate("child")
        values = [(123, 0.2), (124, 0.7)]
        original._control(values)
        for identity in ("parent", "child"):
            port = population.port(identity)
            assert port.channel_mask == original.channel_mask
            port._control(values)
            assert port.last_controls == original.last_controls
            assert port._senses() == original._senses()
            assert port._senses()  # A nonzero actual measurement crosses the same anonymous port.
        assert population.port("parent").prefix != population.port("child").prefix
        assert {s.port for s in population.port("child").spec.sensors} == {s.port for s in original.spec.sensors}


@pytest.mark.parametrize("habitat", ["shared", "independent"])
def test_whole_population_restores_solver_membership_and_late_births_exactly(habitat):
    common = (default_world(), "body", 3, 23, 47)
    with PopulationWorld(*common, habitat=habitat) as current:
        current.activate("n0")
        current.activate("n1")
        for _ in range(4):
            current.step({"n0": [(1, 0.8)], "n1": [(3, 0.4)]})
        current.remove("n0")
        current.activate("n2")
        current.step({"n1": [(3, 0.4)], "n2": [(1, 0.8)]})
        saved = json.loads(json.dumps(current.capture()))
        with PopulationWorld(*common, habitat=habitat, state=saved) as resumed:
            assert current.capture() == resumed.capture()
            for _ in range(8):
                assert current.step({"n2": [(5, 0.3)], "n1": [(3, 0.4)]}) == resumed.step(
                    {"n1": [(3, 0.4)], "n2": [(5, 0.3)]}
                )
                assert current.capture() == resumed.capture()
                assert current.observation() == resumed.observation()
        if habitat == "independent":
            assert saved["worlds"]["n2"]["start_us"] == 80000
            assert saved["worlds"]["n2"]["integration"][0] == pytest.approx(0.02)
        assert current.members == {"n1", "n2"}
        for identity in list(current.members):
            current.remove(identity)
        current.step({})
        assert not current.members
        with PopulationWorld(*common, habitat=habitat, state=current.capture()) as empty:
            assert current.capture() == empty.capture()


def test_viewer_labels_order_and_queries_cannot_change_shared_physics():
    world = specimen()
    changed = world.model_dump(mode="json")
    changed["label"] = "研究者的观察标签"
    for key in ("bodies", "geometries", "joints", "motors", "sensors", "forces"):
        changed[key].reverse()
        for item in changed[key]:
            item["label"] = "观察解释不是动力学"
    changed = parse_world(changed)
    with PopulationWorld(world, "body", 2, 11, 29) as a, PopulationWorld(changed, "body", 2, 11, 29) as b:
        for h in (a, b):
            h.activate("n0")
            h.activate("n1")
        for _ in range(8):
            saved = a.capture()
            for _ in range(4):
                a.observation()
            assert a.capture() == saved
            assert a.step({"n1": [(3, 0.8)], "n0": [(4, 0.3)]}) == b.step({"n0": [(4, 0.3)], "n1": [(3, 0.8)]})
            assert a.capture() == b.capture()


def test_real_rgb_eyes_share_physics_but_keep_individual_measurements_and_cleanup():
    world = specimen()
    world.sensors.append(CameraSensor(id="eye", port=8, body_id="body", position=(0.0, 0.0, 1.0), width=5, height=4))
    with PopulationWorld(world, "body", 2, 11, 29) as current:
        current.activate("n0")
        current.activate("n1")
        current.step({"n0": None, "n1": None})
        left = current.port("n0").last_measurements[-1]["values"]
        right = current.port("n1").last_measurements[-1]["values"]
        assert len(left) == len(right) == 60 and max(left) > min(left)
        assert left != right
        with PopulationWorld(world, "body", 2, 11, 29, state=current.capture()) as resumed:
            assert current.step({"n0": [(7, 0.5)], "n1": None}) == resumed.step({"n0": [(7, 0.5)], "n1": None})
        port = current.port("n0")
        current.remove("n0")
        assert not port.renderers
        assert not any(g["name"].startswith("p0_") for g in current.observation()["worlds"]["shared"]["geometries"])
    assert not current.habitats


def test_invalid_bindings_clocks_or_membership_never_silently_drop_components():
    world = specimen()
    with pytest.raises(ValueError, match="existing root"):
        body_scope(world, "invented")
    invalid = copy.deepcopy(world)
    invalid.sensors.append(TouchSensor(id="floor_touch", port=8, geometry_id="floor"))
    with pytest.raises(ValueError, match="every configured"):
        PopulationWorld(invalid, "body", 2, 11, 29)
    with PopulationWorld(world, "body", 2, 11, 29) as current:
        current.activate("n0")
        saved = current.capture()
        for actions in ({}, {"n0": [(1, float("nan"))]}, {"n0": None, "made-up": None}):
            with pytest.raises(ValueError):
                current.step(actions)
            assert current.capture() == saved
        for patch in ({"time_us": 20000}, {"capacity": 3}, {"seed": 12}, {"worlds": {}}, {"time_us": 1}):
            with pytest.raises((ValueError, KeyError)):
                PopulationWorld(world, "body", 2, 11, 29, state=saved | patch)
    with pytest.raises(ValueError, match="seed"):
        PopulationWorld(world, "body", 2, True, 29, habitat="independent")


def test_removed_slots_do_not_remain_as_invisible_rangefinder_obstacles():
    with PopulationWorld(specimen(), "body", 2, 11, 29) as world:
        world.activate("n0")
        port = world.port("n0")
        port._senses()
        before = next(s["values"][0] for s in port.last_measurements if s["kind"] == "rangefinder")
        world.activate("n1")
        port._senses()
        occupied = next(s["values"][0] for s in port.last_measurements if s["kind"] == "rangefinder")
        assert 0 < occupied < before
        world.remove("n1")
        port._senses()
        assert next(s["values"][0] for s in port.last_measurements if s["kind"] == "rangefinder") == before


def test_free_joint_body_resets_and_restores_without_inheriting_physical_motion():
    world = specimen()
    world.bodies[0].free = True
    world.bodies[0].position = (0, 0, 0.8)
    world.joints, world.motors = [], []
    world.sensors = [s for s in world.sensors if s.kind in ("touch", "rangefinder")]
    with PopulationWorld(world, "body", 2, 11, 29) as live:
        live.activate("n0")
        for _ in range(4):
            live.step({"n0": None})
        assert live.measurements()["n0"]["position"][2] < 0.8
        with PopulationWorld(world, "body", 2, 11, 29, state=live.capture()) as restored:
            assert live.step({"n0": None}) == restored.step({"n0": None})
            assert live.capture() == restored.capture()
        live.remove("n0")
        live.activate("n1")
        assert live.measurements()["n1"]["position"][2] == 0.8
        assert not live.habitats["shared"].data.joint("p0_f_body").qvel.any()
