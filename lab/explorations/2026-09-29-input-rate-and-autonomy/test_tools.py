"""Checks of external physics and wiring, not expectations of a positive result."""

from types import SimpleNamespace

import pytest
from world import SPEC, Body, motor

from threemind_runtime.world_ports import WorldPorts


def test_body_exact_integration_is_independent_of_observation_subdivision():
    a, b = Body(0.9, -0.17), Body(0.9, -0.17)
    a.move(0.6, 3.7)
    for _ in range(37):
        b.move(0.6, 0.1)
    assert a.x == pytest.approx(b.x, abs=1e-12)
    assert a.v == pytest.approx(b.v, abs=1e-12)


def test_region_swap_changes_channels_without_changing_dose():
    a, b = Body(0.2, 0), Body(0.2, 0, 0.5)
    x, y = a.sense(19, 0), b.sense(19, 0)
    assert x.intensity == y.intensity
    assert sum(v for _, v in x.channels) == sum(v for _, v in y.channels) == 4
    assert not {i for i, _ in x.channels} & {i for i, _ in y.channels}


def test_projection_matches_existing_world_ports_for_all_nodes():
    actuator = SimpleNamespace(ctrl=[0.0])
    old = WorldPorts.__new__(WorldPorts)
    old.seed = 9293201
    old.prefix = ""
    old._projection = {}
    old.spec = SimpleNamespace(
        wiring_namespace="ring-study-v1",
        motors=[SimpleNamespace(id="move", port=0, control_limit=1, projection_gain=SPEC["projection_gain"])],
    )
    old.data = SimpleNamespace(actuator=lambda name: actuator)
    nodes = [{"id": i, "activation": (i % 5) * 0.13} for i in range(1, 29)]
    old._control([(n["id"], n["activation"]) for n in reversed(nodes)])
    assert motor(old.seed, nodes) == actuator.ctrl[0]
    assert motor(old.seed, list(reversed(nodes))) == actuator.ctrl[0]


def test_fixed_motion_and_rest_have_no_region_preference_across_swapped_layouts():
    for control in (-0.5, 0, 0.5):
        a, b = Body(0.1875), Body(0.1875, phase=0.5)
        for _ in range(600):
            assert a.region + b.region == 1
            a.move(control, 0.1)
            b.move(control, 0.1)
