import itertools

import pytest

from lab.tools.state_exchange_cut import GROUPS, exchange_cut
from threemind_core import StateImage, Stimulus
from threemind_runtime import create_engine


@pytest.fixture(scope="module")
def parents():
    images = []
    for order in ((1, 2), (2, 1)):
        engine = create_engine(kernel_id="threemind.continuous-memory/2", backend="native")
        for i in range(12):
            for j, channel in enumerate(order):
                engine.inject(Stimulus(i * 550000 + j * 50000, ((channel, 1.0), (3, 1.0)), 0.4))
        engine.inject(Stimulus(7_100_000, ((3, 1.0),), 0.3))
        engine.advance_to(7_000_000)
        images.append(engine.capture_state())
    return images


def test_cut_retains_all_inflight_and_fast_state(parents):
    a, b = parents
    before = a.to_dict()
    assert before["queue"]
    for bits in itertools.product((0, 1), repeat=3):
        groups = tuple(g for g, yes in zip(GROUPS, bits) if yes)
        image, receipt = exchange_cut(a, b, groups)
        after = image.to_dict()
        assert all(after[k] == before[k] for k in before if k not in ("nodes", "edges"))
        assert create_engine(state=image, backend="reference").capture_state().digest == image.digest
        assert receipt["retained_queue_events"] == len(before["queue"])
        assert all(x["location"][-1] not in ("activation", "inhibition") for x in receipt["changes"])


def test_sham_identity_and_rejections(parents):
    a, b = parents
    assert exchange_cut(a, b)[0].digest == a.digest
    assert exchange_cut(a, a, GROUPS)[0].digest == a.digest
    with pytest.raises(ValueError):
        exchange_cut(a, b, ("D",))
    with pytest.raises(ValueError):
        exchange_cut(a, b, ("W", "W"))


def test_cut_uses_channel_identity(parents):
    a, b = parents
    image, receipt = exchange_cut(a, b, ("W",))
    assert receipt["changes"]
    assert image.to_dict()["nodes"] == a.to_dict()["nodes"]

    def weights(im):
        s = im.to_dict()
        channels = {n["id"]: n["channel"] for n in s["nodes"]}
        return {(channels[e["source"]], channels[e["target"]]): e["weight"] for e in s["edges"]}

    assert weights(image) == weights(b)


def test_cut_rejects_different_clocks_config_and_unfinished_novelty(parents):
    a, b = parents
    changed = b.to_dict()
    changed["time_us"] = str(int(changed["time_us"]) + 1)
    with pytest.raises(ValueError):
        exchange_cut(a, StateImage.from_dict(changed), ("W",))
    changed = b.to_dict()
    changed["config"]["intensity_gain"] = 0.0
    with pytest.raises(ValueError):
        exchange_cut(a, StateImage.from_dict(changed), ("W",))
    changed = b.to_dict()
    changed["operator_state"]["novelty"]["pending"] = [{"unfinished": True}]
    with pytest.raises(ValueError):
        exchange_cut(a, StateImage.from_dict(changed), ("W",))


def test_transmitted_events_continue_in_both_backends(parents):
    image, _ = exchange_cut(*parents, GROUPS)
    engines = [create_engine(state=image, backend=b) for b in ("native", "reference")]
    for engine in engines:
        engine.advance_to(7_300_000)
    assert engines[0].capture_state().digest == engines[1].capture_state().digest
