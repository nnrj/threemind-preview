import itertools

import pytest

from lab.tools.state_exchange import GROUPS, exchange
from threemind_core import StateImage, Stimulus
from threemind_runtime import create_engine


@pytest.fixture(scope="module")
def parents():
    images = []
    for order in ((1, 2), (2, 1)):
        engine = create_engine(kernel_id="threemind.continuous-memory/2", backend="native")
        for t in range(0, 30_000_000, 500000):
            engine.inject(Stimulus(t, ((5, 1.0),), 0.2))
        for i in range(12):
            for j, channel in enumerate(order):
                engine.inject(Stimulus(i * 550000 + j * 50000, ((channel, 1.0), (3, 1.0)), 0.4))
        engine.advance_to(30_000_000)
        images.append(engine.capture_state())
    return images


def test_sham_and_identity_preserve_exact_hash(parents):
    a, b = parents
    assert exchange(a, b)[0].digest == a.digest
    result, receipt = exchange(a, a, GROUPS)
    assert result.digest == a.digest and receipt["changes"] == []


def test_weights_follow_channels_not_creation_id(parents):
    a, b = parents
    before = a.payload
    result, receipt = exchange(a, b, ("W",))
    assert a.payload == before and result.digest != a.digest
    assert all(row["location"][0] == "edge" and row["location"][-1] == "weight" for row in receipt["changes"])
    assert result.to_dict()["nodes"] == a.to_dict()["nodes"]
    assert result.to_dict()["operator_state"] == a.to_dict()["operator_state"]

    def weights(image):
        state = image.to_dict()
        channels = {n["id"]: n["channel"] for n in state["nodes"]}
        return {(channels[e["source"]], channels[e["target"]]): e["weight"] for e in state["edges"]}

    assert weights(result) == weights(b)


def test_all_combinations_roundtrip_in_both_backends(parents):
    a, b = parents
    for bits in itertools.product((False, True), repeat=4):
        groups = tuple(g for g, on in zip(GROUPS, bits) if on)
        image, _ = exchange(a, b, groups)
        assert create_engine(state=image, backend="reference").capture_state().digest == image.digest


def test_reject_clock_config_topology_and_inflight(parents):
    a, b = parents
    for key, value in (("time_us", "30000001"), ("traversed", [[1, 2]]), ("queue", [{"invalid": True}])):
        bad = b.to_dict()
        bad[key] = value
        with pytest.raises(ValueError):
            exchange(a, StateImage.from_dict(bad), ("W",))
    bad = b.to_dict()
    bad["config"]["intensity_gain"] = 0.0
    with pytest.raises(ValueError):
        exchange(a, StateImage.from_dict(bad), ("W",))
    with pytest.raises(ValueError):
        exchange(a, b, ("W", "W"))
