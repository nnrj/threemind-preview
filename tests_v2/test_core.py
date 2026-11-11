import math

import pytest

from threemind_core import Config, Engine, Stimulus
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.store import SQLiteStore


def populated(config=None):
    e = Engine(config)
    for t in (0, 13500, 50000, 110000):
        e.inject(Stimulus(t, ((7, 0.6), (8, 0.8))))
    return e


def test_calls_do_not_define_simulation_time():
    whole, divided = populated(), populated()
    whole.advance_to(257431)
    for t in (0, 1234, 11001, 15000, 39876, 90000, 121212, 257431):
        divided.advance_to(t)
        divided.graph()
        divided.capture_state()
    assert whole.capture_state() == divided.capture_state()


def test_event_boundaries_do_not_create_artificial_coactivation():
    separate = Engine()
    separate.inject(Stimulus(0, ((7, 0.6),)))
    separate.inject(Stimulus(0, ((8, 0.6),)))
    separate.advance_to(0)
    together = Engine()
    together.inject(Stimulus(0, ((7, 0.6), (8, 0.6))))
    together.advance_to(0)
    assert not separate.edges
    assert len(together.edges) == 2


def test_immutable_capture_and_full_resume():
    original = populated()
    original.advance_to(27431)
    checkpoint = original.capture_state()
    before = checkpoint.payload
    restored = Engine(state=checkpoint)
    original.advance_to(200000)
    restored.advance_to(200000)
    assert checkpoint.payload == before
    assert original.capture_state() == restored.capture_state()


@pytest.mark.parametrize("format", ["json", "tmind"])
def test_model_roundtrip(format):
    e = populated()
    e.advance_to(123456)
    state = e.capture_state()
    assert ArtifactCodec.decode(ArtifactCodec.encode(state, format)) == state


def test_death_waits_for_activity_and_is_not_pause():
    e = Engine(Config(propagation_rate=0))
    e.advance_to(10**22)
    assert e.life == "waiting"
    e.inject(Stimulus(e.time_us, ((1, 0.8),)))
    e.advance_to(e.time_us)
    e.close_inputs()
    assert e.life == "active"
    snapshot = e.capture_state()
    assert e.capture_state() == snapshot
    e.advance_to(e.time_us + 5_000_000)
    assert e.life == "dead"
    with pytest.raises(ValueError):
        e.inject(Stimulus(e.time_us, ((1, 0.8),)))


def test_analytic_decay_and_delayed_propagation():
    c = Config(plasticity=False, inhibition=False)
    e = Engine(c)
    e.inject(Stimulus(0, ((1, 0.8),)))
    e.advance_to(0)
    a = e.nodes[1].activation
    e.advance_to(123456)
    assert e.graph()["nodes"][0]["activation"] == pytest.approx(a * math.exp(-0.123456 / c.activation_tau))


def test_device_store_compare_and_swap(tmp_path):
    store = SQLiteStore(tmp_path / "device.sqlite3")
    e = populated()
    e.advance_to(10000)
    image = e.capture_state()
    assert store.save("robot", image, expected_revision=0) == 1
    assert store.load("robot") == (1, image)
    with pytest.raises(ValueError):
        store.save("robot", image, expected_revision=0)


def test_reject_late_and_nonfinite_inputs():
    e = Engine()
    e.advance_to(100)
    with pytest.raises(ValueError):
        e.inject(Stimulus(99, ((1, 0.8),)))
    with pytest.raises(ValueError):
        Stimulus(100, ((1, float("nan")),))
    with pytest.raises(ValueError):
        Config(step_us=0)


def test_first_future_input_preserves_global_lattice():
    e = Engine()
    e.inject(Stimulus(20000, ((1, 0.5), (2, 0.6))))
    e.advance_to(20000)
    assert e.next_step_us == 30000
    assert e.next_propagation_us == 100000
    assert not any(q["kind"] == "signal" for q in e.capture_state().to_dict()["queue"])
    e.advance_to(100000)
    assert any(q["kind"] == "signal" and q["time_us"] == "110000" for q in e.capture_state().to_dict()["queue"])
