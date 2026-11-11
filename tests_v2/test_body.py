import json
import math
from dataclasses import asdict, replace

import pytest

from threemind_core import Config, Stimulus
from threemind_lab.protocols import RunSpec
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.body import (
    AmbientConfig,
    AmbientField,
    BodyFilter,
    BodyFilterConfig,
    EnvironmentHost,
    InteroceptionConfig,
)


def test_body_sampling_same_time_frames_baseline_time_constant_and_raw_integrity():
    cfg = BodyFilterConfig(enabled=True, noise=0, adaptation=0.5, threshold=0, sample_us=100000, channel_count=2)
    body = BodyFilter(cfg, 11)
    raw = Stimulus(0, ((3, 0.8), (2, 0.8), (1, 0.6)))
    result, evidence = body.process(raw)
    assert result.channels == ((2, 0.4), (3, 0.4)) and raw.channels[0] == (3, 0.8)
    assert evidence["raw_channels"] == 3 and evidence["passed_channels"] == 2
    assert body.process(Stimulus(0, ((9, 0.9),)))[0].channels == ((9, 0.45),)
    before = body.capture()
    assert body.process(Stimulus(99999, ((1, 1),)))[1]["reason"] == "body_sampling"
    assert body.capture()["baseline"] == before["baseline"]
    assert body.capture()["rng"] == before["rng"]
    body.process(Stimulus(100000, ((1, 1),)))
    expected = 0.6 + (1 - math.exp(-0.1 / cfg.baseline_tau_s)) * 0.4
    assert body.baseline[1][0] == pytest.approx(expected)
    with pytest.raises(ValueError, match="backwards"):
        body.process(Stimulus(1, ((1, 0.5),)))
    # Bypass is transparent and consumes no noise or baseline updates.
    bypass = BodyFilter(replace(cfg, enabled=False), 11, body.capture())
    saved = bypass.capture()
    assert bypass.process(raw)[0] is raw and bypass.capture() == saved


def test_body_noise_restores_in_json_and_baselines_are_bounded():
    cfg = BodyFilterConfig(enabled=True, baseline_capacity=64, sample_us=1000)
    a = BodyFilter(cfg, 23)
    a.process(Stimulus(0, tuple((i, 0.5) for i in range(64))))
    saved = json.loads(json.dumps(a.capture()))
    b = BodyFilter(cfg, 23, saved)
    later = Stimulus(1000, ((65, 0.5), (66, 0.5)))
    assert a.process(later) == b.process(later)
    assert len(b.baseline) == 64 and b.counters["baseline_evicted"] == 2
    assert 0 not in b.baseline and 1 not in b.baseline
    captured = b.capture()
    captured["baseline"][65][0] = -99
    assert b.baseline[65][0] >= 0
    with pytest.raises(ValueError, match="incompatible"):
        BodyFilter(cfg, 24, saved)


def test_explicit_ambient_state_lifetime_budget_and_validation():
    cfg = AmbientConfig(
        transient_rate_per_s=10000, maximum_transients=1, lifetime_min_us=200000, lifetime_max_us=200000
    )
    a = AmbientField(cfg, 11)
    first = a.sample(0)
    assert [kind for kind, _ in first] == ["ambient-fixture", "ambient-disturbance"]
    assert first[0][1].time_us == 100000
    a.sample(100000)
    assert a.rejected_transients == 1
    b = AmbientField(cfg, 11, json.loads(json.dumps(a.capture())))
    later = a.sample(200000)
    assert later == b.sample(200000) and len(a.transients) == 1
    assert later[1][1].channels != first[1][1].channels
    assert AmbientField(cfg, 23).sample(0) != first
    for cls, values in (
        (AmbientConfig, {"lifetime_min_us": 10, "lifetime_max_us": 9}),
        (AmbientConfig, {"sample_us": True}),
        (BodyFilterConfig, {"adaptation": float("nan")}),
        (BodyFilterConfig, {"noise": -0.1}),
        (InteroceptionConfig, {"enabled": 1}),
    ):
        with pytest.raises(ValueError):
            cls(**values)


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_external_host_restore_pending_events_closed_sources_and_portable_model(backend):
    spec = RunSpec(
        environment="ambient", clock="unbounded", body_filter={"enabled": True}, interoception={"enabled": True}
    )
    engine = create_engine(Config(), backend=backend)
    host = EnvironmentHost(spec, 0)

    def emit(engine, records):
        def append(key, source, value, **metadata):
            records.append((key, source, value.to_dict(), metadata))
            if not metadata.get("filter_reason"):
                engine.inject(value)

        return append

    records = []
    host.poll(engine, emit(engine, records))
    assert not engine.activations() and all(q["time_us"] == "100000" for q in engine.capture_state().to_dict()["queue"])
    engine.advance_to(40000)
    state = json.loads(json.dumps(host.capture()))
    restored_engine = create_engine(
        state=ArtifactCodec.decode(ArtifactCodec.encode(engine.capture_state(), "tmind")), backend=backend
    )
    restored = EnvironmentHost(spec, restored_engine.time_us, state=state)
    out_a, out_b = [], []
    for until in (100000, 120000, 200000, 300000):
        host.poll(engine, emit(engine, out_a))
        restored.poll(restored_engine, emit(restored_engine, out_b))
        engine.advance_to(until)
        restored_engine.advance_to(until)
    assert out_a == out_b and engine.capture_state().digest == restored_engine.capture_state().digest
    saved = host.capture()
    host.poll(engine, emit(engine, records), source_enabled=False)
    assert host.capture() == saved and host.deadline(False) is None
    independent = create_engine(state=engine.capture_state(), backend=backend)
    # A model does not contain an automatic external oscillator or fixture.
    assert "body_tools" not in independent.capture_state().to_dict()
    assert asdict(spec.body_filter)["enabled"] and spec.environment == "ambient"
