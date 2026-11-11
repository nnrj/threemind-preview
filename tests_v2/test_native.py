import random

import pytest

from threemind_core import Config, Engine, Stimulus
from threemind_runtime.host import NativeEngine


@pytest.mark.parametrize(
    "config", [Config(), Config(step_us=5000, delay_us=17311), Config(inhibition=False), Config(plasticity=False)]
)
def test_native_reference_equivalence(config):
    a, b = Engine(config), NativeEngine(config)
    rng = random.Random(7791)
    for time in sorted(rng.randrange(0, 400000) for _ in range(40)):
        channels = tuple((channel, rng.uniform(0.1, 0.9)) for channel in rng.sample(range(16), 4))
        stimulus = Stimulus(time, channels, rng.uniform(0.5, 1.5))
        a.inject(stimulus)
        b.inject(stimulus)
    for t in (0, 19371, 100001, 250000, 500000):
        a.advance_to(t)
        b.advance_to(t)
        x, y = a.capture_state().to_dict(), b.capture_state().to_dict()
        assert len(x["nodes"]) == len(y["nodes"])
        assert len(x["edges"]) == len(y["edges"])
        assert [(q["id"], q["time_us"], q["kind"]) for q in x["queue"]] == [
            (q["id"], q["time_us"], q["kind"]) for q in y["queue"]
        ]
        # Different system libm implementations may differ by a few ULPs.
        for left, right in zip(x["nodes"], y["nodes"]):
            for key in left:
                if isinstance(left[key], float):
                    assert right[key] == pytest.approx(left[key], rel=1e-12, abs=1e-14)
                else:
                    assert right[key] == left[key]
        for left, right in zip(x["edges"], y["edges"]):
            for key in left:
                if isinstance(left[key], float):
                    assert right[key] == pytest.approx(left[key], rel=1e-12, abs=1e-14)
                else:
                    assert right[key] == left[key]
        for key in ("time_us", "state_time_us", "sequence", "next_event", "next_node", "life"):
            assert x[key] == y[key]


def test_native_partition_and_resume_are_exact():
    a = NativeEngine()
    a.inject(Stimulus(0, ((1, 0.6), (2, 0.7))))
    a.advance_to(12345)
    b = NativeEngine(state=a.capture_state())
    for t in (23456, 78901, 100000):
        b.advance_to(t)
    a.advance_to(100000)
    assert a.capture_state().digest == b.capture_state().digest


def test_input_recorder_does_not_change_dynamics():
    a = NativeEngine()
    a.inject(Stimulus(0, ((1, 0.4), (2, 0.5))))
    b = NativeEngine(state=a.capture_state())
    rows = []
    a.advance_to(100000, rows.append, inputs_only=True)
    b.advance_to(100000)
    assert [r["kind"] for r in rows] == ["stimulus"]
    assert a.capture_state().digest == b.capture_state().digest


def test_canonical_native_hash_matches_independent_reference():
    import hashlib
    import json

    from _threemind_native import canonical_hash

    from threemind_core.engine import canonical_bytes

    value = {"中文😀": [-0.0, 1.0, 1, 1.25e-103, True, None, {"z": '\u2028\u007f\u0000\r\t\n\b\f\\"', "a": 2**62}]}
    assert canonical_hash(json.dumps(value).encode()) == hashlib.sha256(canonical_bytes(value)).hexdigest()
    with pytest.raises(ValueError, match="duplicate"):
        canonical_hash(b'{"a":1,"a":2}')


@pytest.mark.parametrize("plasticity", [True, False])
def test_complete_readout_projection_matches_reference_without_relaxation(plasticity):
    import math

    a, b = Engine(Config(plasticity=plasticity)), NativeEngine(Config(plasticity=plasticity))
    for engine in (a, b):
        engine.inject(Stimulus(0, ((1, 0.7), (2, 0.8), (3, 0.5))))
        engine.advance_to(13371)
    image = a.capture_state().to_dict()
    dt = (int(image["time_us"]) - int(image["state_time_us"])) / 1e6
    projected = a.observation_nodes()
    # Direct touch is the current physical-period contact record, not activation.
    assert projected[0]["direct"] == image["nodes"][0]["direct"]
    assert projected[0]["activation"] == pytest.approx(
        image["nodes"][0]["activation"] * math.exp(-dt / a.config.activation_tau)
    )
    for left, right in zip(projected, b.observation_nodes()):
        assert set(left) == set(right)
        for key, value in left.items():
            assert right[key] == pytest.approx(value, rel=1e-12, abs=1e-14)
    ids = [n["id"] for n in projected[:2]]
    for left, right in zip(a.induced_edges(ids), b.induced_edges(ids)):
        assert set(left) == set(right)
        for key, value in left.items():
            assert right[key] == pytest.approx(value, rel=1e-12, abs=1e-14)
