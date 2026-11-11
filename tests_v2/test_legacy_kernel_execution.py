"""Engineering compatibility witnesses, never organism training records."""

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from threemind_core import StateImage, Stimulus
from threemind_kernels import kernel_catalog, resolve_kernel
from threemind_kernels.legacy.unified.model import ModelManifest, ModelPackage
from threemind_kernels.legacy.unified.runtime import ConsciousnessRuntime
from threemind_kernels.legacy.unified.sensors import TextSensorAdapter
from threemind_kernels.legacy.unified_adapter import LegacyStimulus, UnifiedConfig, UnifiedEngine, presets
from threemind_runtime import Runtime, birth, create_engine
from threemind_runtime.bus import InputBus

FIXTURES = Path(__file__).parent / "fixtures"


def assert_state_close(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_state_close(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected):
            assert_state_close(left, right)
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-14)
    else:
        assert actual == expected


@pytest.mark.parametrize("version", range(1, 7))
@pytest.mark.parametrize("backend", ["reference", "native"])
def test_frozen_historical_continuation(version, backend):
    witness = json.loads((FIXTURES / f"causal{version}-continuation.json").read_text(encoding="utf-8"))
    image = StateImage.from_dict(witness["before"])
    engine = create_engine(state=image, backend=backend)
    assert engine.capture_state().digest == witness["before_hash"]
    engine.advance_to(int(witness["target_us"]))
    actual = engine.capture_state()
    assert_state_close(actual.to_dict(), witness["after"])
    if backend == "native":
        assert actual.digest == witness["after_hash"]


@pytest.mark.parametrize("version", range(1, 9))
@pytest.mark.parametrize("backend", ["reference", "native"])
def test_historical_birth_bus_delivery_and_same_version_restore(version, backend):
    identity = f"threemind.causal/{version}"
    engine = create_engine(kernel_id=identity, backend=backend)
    runtime = Runtime(engine)
    bus = InputBus(runtime.engine)
    bus.schedule(Stimulus(0, ((7, 0.8), (13, 0.6))), {"source": "manual-text"})
    bus.verify(engine.capture_state().to_dict())
    engine.advance_to(30_000, bus.observe, inputs_only=True)
    assert bus.pending == {}
    assert engine.dynamics == identity
    assert engine.metrics()["nodes"] == 2
    saved = engine.capture_state()
    restored = create_engine(state=saved, kernel_id=identity, backend=backend)
    assert restored.capture_state().digest == saved.digest
    next_stimulus = Stimulus(40_000, ((7, 0.4), (21, 0.3)))
    engine.inject(next_stimulus)
    restored.inject(next_stimulus)
    engine.advance_to(500_000)
    restored.advance_to(500_000)
    assert restored.capture_state().digest == engine.capture_state().digest


@pytest.mark.parametrize("version", range(1, 9))
def test_historical_backend_discrete_and_float_agreement(version):
    identity = f"threemind.causal/{version}"
    engines = [create_engine(kernel_id=identity, backend=backend) for backend in ("reference", "native")]
    for engine in engines:
        for when, channels in ((0, {7: 0.8, 13: 0.6}), (210_000, {7: 0.5, 19: 0.4}), (430_000, {13: 0.7, 19: 0.2})):
            engine.inject(Stimulus(when, tuple(channels.items())))
        engine.advance_to(650_000)
    assert_state_close(engines[0].capture_state().to_dict(), engines[1].capture_state().to_dict())


@pytest.mark.parametrize("version", range(1, 9))
@pytest.mark.parametrize("backend", ["reference", "native"])
def test_historical_structural_birth_matches_original_rule_and_keeps_kernel(version, backend):
    witness = json.loads((FIXTURES / "legacy-birth.json").read_text(encoding="utf-8"))["cases"][version - 1]
    if "parent_fixture" in witness:
        original = json.loads((FIXTURES / witness["parent_fixture"]).read_text(encoding="utf-8"))["before"]
    else:
        original = witness["parent"]
    image = StateImage.from_dict(original)
    assert image.digest == witness["parent_hash"]
    child_image = birth(image)
    child = child_image.to_dict()
    assert child_image.digest == witness["child_hash"]
    assert child_image.digest == birth(child_image).digest
    assert image.to_dict() == original
    assert child.keys() == original.keys()
    assert child["config"] == original["config"]
    assert child["dynamics"] == witness["kernel_id"]
    assert child["time_us"] == child["state_time_us"] == "0"
    assert child["life"] == "waiting" and child["sources_open"] and child["queue"] == []
    assert child["next_node"] == original["next_node"]
    assert child["sequence"] == child["next_event"] == 0
    for old, new in zip(original["nodes"], child["nodes"], strict=True):
        assert new.keys() == old.keys()
        for field in ("id", "channel", "support", "stability", "touches"):
            assert new[field] == old[field]
        assert new["activation"] == new["inhibition"] == new["trace"] == 0.0
    for old, new in zip(original["edges"], child["edges"], strict=True):
        assert new.keys() == old.keys()
        for field in ("source", "target", "weight", "stability", "touches"):
            assert new[field] == old[field]
        assert new["eligibility"] == 0.0
    engine = create_engine(state=child_image, backend=backend)
    assert engine.capture_state().digest == child_image.digest
    resumed = create_engine(state=engine.capture_state(), backend=backend)
    for current in (engine, resumed):
        seen = []
        current.inject(Stimulus(0, ((child["nodes"][0]["channel"], 0.4), (99, 0.5))))
        current.advance_to(250_000, seen.append)
        assert current.dynamics == witness["kernel_id"]
        assert any(event["kind"] == "stimulus" for event in seen)
        capacity = child["config"].get("max_nodes")
        if capacity is None or len(child["nodes"]) < capacity:
            assert 99 in {node["channel"] for node in current.capture_state().to_dict()["nodes"]}
        else:
            # This frozen causal/3 witness intentionally has a full capacity.
            # Structural birth must preserve its original capacity constraint.
            assert current.metrics()["resources"]["node_capacity_rejections"] != "0"
    assert engine.capture_state().digest == resumed.capture_state().digest


def test_registry_has_real_kernels_and_version_owned_fields():
    identities = {item["kernel_id"] for item in kernel_catalog()}
    assert {f"threemind.causal/{n}" for n in range(1, 10)} <= identities
    assert {f"threemind.continuous-memory/{n}" for n in range(1, 5)} <= identities
    assert "unified-associative" in identities
    assert not {p["id"] for p in presets()} & identities
    assert "propagation_limit" not in resolve_kernel("threemind.causal/1").config_fields()
    assert "propagation_limit" in resolve_kernel("threemind.causal/3").config_fields()
    assert resolve_kernel("unified-associative").backends == ("reference",)
    with pytest.raises(ValueError, match="no automatic fallback"):
        create_engine(kernel_id="unified-associative", backend="native")


def test_legacy_config_cannot_silently_promote_or_take_modern_fields():
    with pytest.raises(ValueError):
        create_engine({"energy_simulation_enabled": True}, kernel_id="threemind.causal/2", backend="reference")
    with pytest.raises(ValueError):
        create_engine({"retention_half_life_min_s": 30}, kernel_id="threemind.causal/8", backend="reference")
    engine = create_engine(kernel_id="threemind.causal/6", backend="reference")
    with pytest.raises(ValueError, match="causal/7"):
        engine.inject(Stimulus(0, ((1, 0.3),), bypass_attention=True))
    with pytest.raises(ValueError, match="identity"):
        create_engine(state=engine.capture_state(), kernel_id="threemind.causal/7", backend="reference")


def unified(config=None):
    return UnifiedEngine(config or UnifiedConfig(), consciousness_id="f21c5bb4-b1d6-42b4-a3d6-56f4f84aaf89")


def test_unified_uses_original_seed_and_literal_uint64_through_input_bus():
    engine = unified(UnifiedConfig(sensory_encoding="literal-character"))
    expected_seed = int.from_bytes(
        hashlib.blake2b(engine._engine.consciousness_id.encode(), digest_size=8).digest(), "big"
    )
    assert engine._engine.sensory_seed == expected_seed
    adapter = TextSensorAdapter(expected_seed, encoding="literal-character")
    frame = adapter.encode("测试")
    assert max(frame.channels) > 2**32
    item = LegacyStimulus(0, frame.channels, source="manual")
    assert replace(item, bypass_attention=True).channels == item.channels
    assert LegacyStimulus.from_dict(item.to_dict()) == item
    bus = InputBus(engine)
    bus.schedule(item, {"source": "manual-text"})
    bus.verify(engine.capture_state().to_dict())
    deliveries = []

    def observe(event):
        deliveries.append(event)
        bus.observe(event)

    engine.advance_to(0, observe)
    assert bus.next_time_us is None
    assert engine.metrics()["tick"] == 0
    assert deliveries[0]["delivery_stage"] == "legacy_input_queue"
    engine.advance_to(engine.config.step_us, observe)
    assert engine.metrics()["tick"] == 1
    assert {int(k) for k in engine.capture_state().to_dict()["package"]["state"]["receptor_index"]} == set(
        frame.channels
    )


def test_unified_same_epoch_keeps_sequential_ticks_and_partial_restore():
    engine = unified()
    for channels in ({1: 0.7}, {2: 0.6}):
        engine.inject(LegacyStimulus(0, channels))
    engine.inject(LegacyStimulus(90_000, {3: 0.8}))
    engine.advance_to(50_000)
    saved = engine.capture_state()
    restored = create_engine(state=saved, backend="reference")
    assert restored.capture_state().digest == saved.digest
    with pytest.raises(ValueError, match="identity"):
        UnifiedEngine(state=saved, consciousness_id="new-identity")
    for boundary in (100_000, 220_000, 400_000):
        engine.advance_to(boundary)
    restored.advance_to(400_000)
    assert restored.capture_state().digest == engine.capture_state().digest
    # Three original frames in epoch one produce three old ticks, then three idle ticks.
    assert engine.metrics()["tick"] == 6
    assert engine.metrics()["input_epoch"] == 4


def test_unified_text_epoch_spacing_matches_original_encoder_and_dynamics():
    engine = unified(UnifiedConfig(node_payload="labeled", sensory_encoding="legacy-labeled"))
    initial = engine.capture_state().to_dict()
    original = ConsciousnessRuntime(
        ModelPackage(ModelManifest.from_dict(initial["manifest"]), **copy.deepcopy(initial["package"])),
        config=engine.config.runtime(),
    )
    adapter = TextSensorAdapter(original.sensory_seed, labeled=True, encoding="legacy-labeled")
    frames = adapter.encode_stream("红圆蓝方黄三角", frame_characters=2)
    original.register_channel_labels(adapter.channel_labels)
    original.enqueue_frames(frames, inter_frame_epochs=1)
    engine.enqueue_text("红圆蓝方黄三角", frame_characters=2)
    engine.advance_to(0)
    for epoch in range(1, 7):
        original.step(ticks=1)
        engine.advance_to(epoch * engine.config.step_us)
        saved = engine.capture_state().to_dict()["package"]["state"]
        old = json.loads(json.dumps(original.state_dict()))
        for key in (
            "tick",
            "nodes",
            "edges",
            "receptor_index",
            "channel_labels",
            "sensory_seed",
            "recent",
            "input_epoch",
            "energy_reserve",
        ):
            assert_state_close(saved[key], old[key])


def test_unified_read_only_projections_cannot_mutate_original_dynamics():
    engine = unified()
    engine.inject(LegacyStimulus(0, {1: 0.8, 2: 0.6}))
    engine.advance_to(engine.config.step_us)
    saved = engine.capture_state().to_dict()
    for key, mutate in (("nodes", lambda v: v[0].update(activation=42)), ("life", lambda v: "dead")):
        corrupted = copy.deepcopy(saved)
        value = mutate(corrupted[key])
        if value is not None:
            corrupted[key] = value
        with pytest.raises(ValueError, match="read-only"):
            create_engine(state=StateImage.from_dict(corrupted), backend="reference")
    before = engine.capture_state().digest
    engine.metrics()
    engine.graph()
    engine.observation_nodes()
    engine.induced_edges([1, 2])
    assert engine.capture_state().digest == before


def test_unified_dead_idle_horizon_preserves_pending_evidence():
    engine = unified()
    engine.inject(LegacyStimulus(1_000_000, {1: 0.3}))
    engine._engine.die("engineering-test")
    engine.advance_to(2_000_000)
    image = engine.capture_state()
    restored = create_engine(state=image, backend="reference")
    assert restored.capture_state().digest == image.digest
    assert restored.capture_state().to_dict()["queue"][0]["time_us"] == "1000000"


def test_unified_structural_birth_is_distinct_from_exact_fork():
    engine = unified()
    engine.inject(LegacyStimulus(0, {1: 0.7}))
    engine.advance_to(engine.config.step_us)
    image = engine.capture_state()
    with pytest.raises(ValueError, match="structural inheritance is not defined"):
        birth(image)
    assert engine.capture_state().digest == image.digest
    assert create_engine(state=image, backend="reference").capture_state().digest == image.digest
