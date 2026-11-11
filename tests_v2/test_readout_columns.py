"""Exact scalar/column agreement, including recoverable intermediate state."""

import copy
import json
import random
from types import MethodType

import pytest

from threemind_runtime.bus import OutputBus
from threemind_runtime.readout_config import TemporalReadoutConfig
from threemind_runtime.readouts import TemporalReader


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@pytest.mark.parametrize("scope", ["all-active", "associative-only", "associative-or-persistent"])
@pytest.mark.parametrize("origin", [0, 2**75 + 19])
def test_column_observer_exact_irregular_samples_growth_disappearance_resume(scope, origin):
    config = TemporalReadoutConfig(baseline_us=400000, max_response_us=12000000, candidate_scope=scope)
    fast, scalar = TemporalReader(config), TemporalReader(config)
    scalar._observe = MethodType(TemporalReader._observe_reference, scalar)
    rng = random.Random(523)
    stamp = origin
    resumed = None
    for step in range(14):
        stamp += rng.choice([0, 7001, 45123, 100000, 150013])
        nodes = [
            {
                "id": i + 2**55,
                "channel": i,
                "activation": rng.choice([-0.0, 0.04, 0.13, 0.81]),
                "inhibition": rng.choice([-0.0, 0.03]),
                "direct": rng.choice([0.0, 0.2]),
                "associative": rng.choice([0.0, 0.1]),
                "stability": rng.choice([0.0, 0.7]),
            }
            for i in range(320 + step * 7)
            if i % 13 != step % 13
        ]
        rng.shuffle(nodes)
        original = copy.deepcopy(nodes)
        deliveries = (
            [
                {
                    "envelope_id": "one",
                    "delivered_time_us": str(stamp),
                    "frame_index": step - 2,
                    "frame_count": 10,
                    "source": "manual-test",
                }
            ]
            if step in (2, 11)
            else []
        )
        actual = fast.consume(stamp, step, nodes, deliveries)
        expected = scalar.consume(stamp, step, nodes, deliveries)
        assert encoded(actual) == encoded(expected)
        assert encoded(fast.capture()) == encoded(scalar.capture())
        assert nodes == original
        if resumed:
            assert encoded(resumed.consume(stamp, step, nodes, deliveries)) == encoded(actual)
            assert encoded(resumed.capture()) == encoded(fast.capture())
        resumed = TemporalReader(config, fast.capture())
    assert fast._columns
    assert encoded(fast.close(stamp, "run_ended")) == encoded(scalar.close(stamp, "run_ended"))
    assert not fast._columns


def test_column_budget_and_wide_gap_fall_back_without_integer_narrowing():
    config = TemporalReadoutConfig(baseline_us=0, max_node_entries=320)
    fast, scalar = TemporalReader(config), TemporalReader(config)
    scalar._observe = MethodType(TemporalReader._observe_reference, scalar)
    nodes = [
        {"id": i, "activation": 0.5, "inhibition": 0.1, "direct": 0.1, "associative": 0.3, "stability": 0.2}
        for i in range(300)
    ]
    delivery = {
        "envelope_id": "one",
        "delivered_time_us": "0",
        "frame_index": 0,
        "frame_count": 10,
        "source": "manual-test",
    }
    for stamp, sample, deliveries in [
        (0, nodes, [delivery]),
        (100000, nodes[:150], []),
        (200000, nodes + [dict(n, id=n["id"] + 400) for n in nodes[:30]], []),
    ]:
        assert encoded(fast.consume(stamp, stamp, sample, deliveries)) == encoded(
            scalar.consume(stamp, stamp, sample, deliveries)
        )
        assert encoded(fast.capture()) == encoded(scalar.capture())
    assert not fast._columns
    fast, scalar = TemporalReader(config), TemporalReader(config)
    scalar._observe = MethodType(TemporalReader._observe_reference, scalar)
    for stamp, deliveries in [(0, [delivery]), (2**70, [])]:
        assert encoded(fast.consume(stamp, stamp, nodes, deliveries)) == encoded(
            scalar.consume(stamp, stamp, nodes, deliveries)
        )
    assert not fast._columns


def test_output_bus_exclusive_ownership_retains_default_and_multi_consumer_isolation():
    bus, received = OutputBus(), []

    def mutate(frame):
        frame["values"].append(9)
        received.append(frame)

    bus.subscribe("first", mutate)
    frame = {"values": [1]}
    bus.publish(frame)
    assert frame == {"values": [1]} and received[-1] == {"values": [1, 9]}
    exclusive = {"values": [2]}
    bus.publish(exclusive, owned=True)
    assert received[-1] is exclusive
    second = []
    bus.subscribe("second", second.append)
    shared = {"values": [3]}
    bus.publish(shared, owned=True)
    assert shared == second[0] == {"values": [3]}
    assert received[-1] == {"values": [3, 9]}


def test_integer_observations_do_not_change_types_when_later_samples_are_floats():
    config = TemporalReadoutConfig(baseline_us=0)
    fast, scalar = TemporalReader(config), TemporalReader(config)
    scalar._observe = MethodType(TemporalReader._observe_reference, scalar)
    delivery = {
        "envelope_id": "one",
        "delivered_time_us": "0",
        "frame_index": 0,
        "frame_count": 10,
        "source": "manual-test",
    }
    for step in range(4):
        nodes = [
            {
                "id": i,
                "activation": 1 if step == 0 else 0.5,
                "inhibition": 0.0,
                "direct": 0.0,
                "associative": 0.3,
                "stability": 0.2,
            }
            for i in range(300)
        ]
        at = step * 100000
        deliveries = [delivery] if step == 0 else []
        assert encoded(fast.consume(at, step, nodes, deliveries)) == encoded(
            scalar.consume(at, step, nodes, deliveries)
        )
        assert encoded(fast.capture()) == encoded(scalar.capture())
    assert not fast._columns
