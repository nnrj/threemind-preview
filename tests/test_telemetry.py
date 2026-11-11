from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from threemind.model import ModelManifest, ModelPackage
from threemind.api import (
    _HostObservedRuntime,
    _migrate_legacy_ambient_setting,
    _project_legacy_source_switches_into_policies,
    _resolve_model_adapters,
    _telemetry_delivery_enabled,
    adapter_runtime_state,
    ui_settings,
)
from threemind_adapters import (
    HostTelemetryAdapter,
    HostTelemetryCollector,
    MetricReading,
    ProcessTelemetryAdapter,
    RuntimeTelemetryAdapter,
    SystemTelemetryProbe,
    TelemetryAuditStore,
    TelemetrySample,
    default_adapter_registry,
    host_signal_names,
    process_signal_names,
    runtime_signal_names,
)


def sample(sample_id: str, level: float, *, available: bool = True) -> TelemetrySample:
    host = {
        name: MetricReading.unavailable("ratio", "test unavailable")
        for name in host_signal_names()
    }
    host["cpu_load"] = MetricReading.ratio(level) if available else MetricReading.unavailable("ratio", "counter absent")
    return TelemetrySample(
        sample_id=sample_id,
        captured_at_utc=datetime.now(timezone.utc).isoformat(),
        monotonic_seconds=float(sample_id.removeprefix("s") or 0),
        backend="fake-probe",
        host=host,
        process={},
        duration_ms=0.2,
    )


def cpu_only_config(**overrides: object) -> dict[str, object]:
    signals = {
        name: {"level": name == "cpu_load", "change": name == "cpu_load", "gain": 1.0}
        for name in host_signal_names()
    }
    return {"smoothing": 0.0, "levels_enabled": True, "changes_enabled": True, "signals": signals, **overrides}


def runtime_sample(
    sample_id: str,
    *,
    owner: str,
    cpu_load: float,
    busy_ratio: float = .2,
    execution_ms: float = 4.0,
    latency_ms: float = 1.0,
    monotonic_seconds: float = 1.0,
    context: dict[str, object] | None = None,
) -> TelemetrySample:
    return TelemetrySample(
        sample_id=sample_id,
        captured_at_utc=datetime.now(timezone.utc).isoformat(),
        monotonic_seconds=monotonic_seconds,
        backend="fake-runtime-clock",
        host={},
        process={},
        duration_ms=.1,
        runtime={
            "thread_cpu_load": MetricReading.ratio(cpu_load),
            "epoch_busy_ratio": MetricReading.ratio(busy_ratio),
            "epoch_execution_time_ms": MetricReading.scaled(execution_ms, unit="ms", reference=250, reference_source="configured reference"),
            "scheduler_latency_ms": MetricReading.scaled(latency_ms, unit="ms", reference=250, reference_source="configured reference"),
        },
        scope="runtime",
        owner_consciousness_id=owner,
        context=context or {},
    )


def test_first_sample_establishes_change_baseline_without_fake_change() -> None:
    adapter = HostTelemetryAdapter(101, config=cpu_only_config())
    first = adapter.encode(sample("s1", .25))
    assert first.frame is not None
    assert len(first.frame.channels) == 1
    measurement = first.audit["measurements"]["cpu_load"]
    assert measurement["rise"] == 0
    assert measurement["fall"] == 0
    assert measurement["change_baseline_established"] is False
    assert first.audit["input_frame"] == {
        "source": first.frame.source,
        "channels": {str(channel): value for channel, value in first.frame.channels.items()},
        "intensity": 1.0,
        "external": True,
        "bypass_filter": False,
    }


def test_level_rise_and_fall_are_distinct_nonnegative_channels() -> None:
    adapter = HostTelemetryAdapter(102, config=cpu_only_config())
    adapter.encode(sample("s1", .20))
    rising = adapter.encode(sample("s2", .70))
    falling = adapter.encode(sample("s3", .10))
    rise = rising.audit["measurements"]["cpu_load"]
    fall = falling.audit["measurements"]["cpu_load"]
    assert rise["rise"] == pytest.approx(.5) and rise["fall"] == 0
    assert fall["fall"] == pytest.approx(.6) and fall["rise"] == 0
    assert set(rise["channels"]) == {"level", "rise"}
    assert set(fall["channels"]) == {"level", "fall"}
    assert all(value >= 0 for value in rising.frame.channels.values())
    assert all(value >= 0 for value in falling.frame.channels.values())


def test_global_and_per_signal_switches_preserve_configuration() -> None:
    config = cpu_only_config(levels_enabled=False, changes_enabled=False)
    adapter = HostTelemetryAdapter(103, config=config)
    assert adapter.encode(sample("s1", .4)).frame is None
    assert adapter.config["signals"]["cpu_load"]["level"] is True
    assert adapter.config["signals"]["cpu_load"]["change"] is True
    adapter.configure({"levels_enabled": True})
    encoded = adapter.encode(sample("s2", .5))
    assert encoded.frame is not None
    assert set(encoded.audit["measurements"]["cpu_load"]["channels"]) == {"level"}


@pytest.mark.parametrize(
    ("levels_enabled", "changes_enabled", "expected"),
    [(False, False, set()), (True, False, {"level"}), (False, True, {"rise"}), (True, True, {"level", "rise"})],
)
def test_every_level_change_master_switch_combination(
    levels_enabled: bool,
    changes_enabled: bool,
    expected: set[str],
) -> None:
    adapter = HostTelemetryAdapter(304, config=cpu_only_config(levels_enabled=levels_enabled, changes_enabled=changes_enabled))
    adapter.encode(sample("s1", .2))
    encoded = adapter.encode(sample("s2", .7))
    channels = set(encoded.audit["measurements"]["cpu_load"]["channels"])
    assert channels == expected
    assert (encoded.frame is not None) is bool(expected)


def test_unavailable_metric_is_audited_but_never_fabricated_as_zero() -> None:
    adapter = HostTelemetryAdapter(104, config=cpu_only_config())
    encoded = adapter.encode(sample("s1", 0, available=False))
    assert encoded.frame is None
    metric = encoded.audit["measurements"]["cpu_load"]
    assert metric["available"] is False
    assert metric["raw_value"] is None
    assert metric["unavailable_reason"] == "counter absent"


def test_reset_baseline_prevents_pause_interval_from_becoming_change_spike() -> None:
    adapter = HostTelemetryAdapter(105, config=cpu_only_config())
    adapter.encode(sample("s1", .1))
    adapter.reset_baseline()
    resumed = adapter.encode(sample("s2", .9))
    metric = resumed.audit["measurements"]["cpu_load"]
    assert metric["rise"] == 0 and metric["fall"] == 0
    assert set(metric["channels"]) == {"level"}


def test_unavailable_interval_reestablishes_metric_change_baseline() -> None:
    adapter = HostTelemetryAdapter(106, config=cpu_only_config())
    adapter.encode(sample("s1", .1))
    adapter.encode(sample("s2", 0, available=False))
    resumed = adapter.encode(sample("s3", .9))
    metric = resumed.audit["measurements"]["cpu_load"]
    assert metric["rise"] == 0 and metric["fall"] == 0
    assert metric["change_baseline_established"] is False
    assert set(metric["channels"]) == {"level"}


def test_host_runtime_marks_even_short_pause_resume_as_sensory_discontinuity() -> None:
    runtime = _HostObservedRuntime(ModelPackage.empty())
    initial = runtime.host_continuity_revision()
    runtime.pause()
    after_pause = runtime.host_continuity_revision()
    runtime.resume()
    assert after_pause == initial + 1
    assert runtime.host_continuity_revision() == after_pause + 1


def test_runtime_physical_measurement_uses_real_clocks_and_resets_its_window() -> None:
    monotonic_values = iter((100.0, 100.10, 100.11, 100.12, 101.0, 102.0, 102.001))
    thread_cpu_values = iter((20.0, 20.004))
    runtime = _HostObservedRuntime(
        ModelPackage.empty(),
        monotonic_clock=lambda: next(monotonic_values),
        thread_cpu_clock=lambda: next(thread_cpu_values),
    )
    runtime._advance_input_epoch()
    measured = runtime.consume_runtime_telemetry(101.0)

    assert measured.scope == "runtime"
    assert measured.owner_consciousness_id == runtime.consciousness_id
    assert measured.runtime["thread_cpu_load"].raw_value == pytest.approx(.004)
    assert measured.runtime["epoch_busy_ratio"].raw_value == pytest.approx(.01)
    assert measured.runtime["epoch_execution_time_ms"].raw_value == pytest.approx(10.0)
    assert measured.context["epoch_count"] == 1
    assert measured.context["tick_start"] == 1
    assert measured.context["tick_end"] == 1

    empty_window = runtime.consume_runtime_telemetry(102.0)
    assert empty_window.context["epoch_count"] == 0
    assert empty_window.runtime["epoch_execution_time_ms"].available is False


def test_runtime_feedback_envelope_is_observed_only_in_the_following_window() -> None:
    runtime = _HostObservedRuntime(ModelPackage.empty())
    first = runtime.consume_runtime_telemetry(runtime._runtime_telemetry_window_started + 1.0)
    assert first.context["input_envelopes"] == []

    adapter = RuntimeTelemetryAdapter(runtime.sensory_seed, config={"smoothing": 0.0})
    encoded = adapter.encode(runtime_sample("feedback-1", owner=runtime.consciousness_id, cpu_load=.2))
    assert encoded.frame is not None
    receipt = runtime.enqueue_frame(
        encoded.frame,
        adapter_id="runtime-telemetry-field",
        metadata={"telemetry_sample_id": "feedback-1"},
    )
    runtime._advance_input_epoch()
    following = runtime.consume_runtime_telemetry(runtime._runtime_telemetry_window_started + 1.0)
    observed = following.context["input_envelopes"]
    assert [row["envelope_id"] for row in observed] == [receipt["envelope_id"]]
    assert observed[0]["adapter_id"] == "runtime-telemetry-field"
    # Transport identifiers remain audit context and never become sensory
    # channels or graph payload.
    assert receipt["envelope_id"] not in {str(channel) for channel in encoded.frame.channels}
    assert receipt["envelope_id"] not in str(runtime.state_dict()["nodes"])


def test_one_shared_sample_maps_to_different_anonymous_channels() -> None:
    shared = sample("s1", .6)
    first = HostTelemetryAdapter(201, config=cpu_only_config()).encode(shared)
    second = HostTelemetryAdapter(202, config=cpu_only_config()).encode(shared)
    assert first.frame is not None and second.frame is not None
    assert set(first.frame.channels) != set(second.frame.channels)
    assert first.audit["sample_id"] == second.audit["sample_id"] == "s1"
    assert all(isinstance(channel, int) for channel in first.frame.channels)
    assert all(0 <= channel < 8192 for channel in first.frame.channels)
    assert all(value >= 0 and value < float("inf") for value in first.frame.channels.values())


def test_all_builtin_telemetry_components_have_distinct_anonymous_channels() -> None:
    host = HostTelemetryAdapter(203)
    process = ProcessTelemetryAdapter(203)
    runtime = RuntimeTelemetryAdapter(203)
    channels = {
        host._channel(name, component)
        for name in host_signal_names()
        for component in ("level", "rise", "fall")
    } | {
        process._channel(name, component)
        for name in process_signal_names()
        for component in ("level", "rise", "fall")
    } | {
        runtime._channel(name, component)
        for name in runtime_signal_names()
        for component in ("level", "rise", "fall")
    }
    assert len(channels) == (len(host_signal_names()) + len(process_signal_names()) + len(runtime_signal_names())) * 3


def test_runtime_measurement_maps_differently_per_consciousness_and_never_negative() -> None:
    measured = runtime_sample("r1", owner="mind-a", cpu_load=.4)
    first = RuntimeTelemetryAdapter(501, config={"smoothing": 0.0}).encode(measured)
    second = RuntimeTelemetryAdapter(502, config={"smoothing": 0.0}).encode(measured)
    assert first.frame is not None and second.frame is not None
    assert first.frame.source == "ambient-runtime-telemetry"
    assert set(first.frame.channels) != set(second.frame.channels)
    assert all(value >= 0 and value < float("inf") for value in first.frame.channels.values())
    assert first.audit["owner_consciousness_id"] == "mind-a"


def test_automatic_probe_reference_wins_until_manual_override_is_explicit() -> None:
    host = {name: MetricReading.unavailable("ratio", "test unavailable") for name in host_signal_names()}
    host["network_receive_rate"] = MetricReading.scaled(
        50,
        unit="bytes/s",
        reference=100,
        reference_source="active interface link speed",
    )
    shared = TelemetrySample("n1", datetime.now(timezone.utc).isoformat(), 1.0, "fake", host, {}, .1)
    automatic = HostTelemetryAdapter(401).encode(shared)
    metric = automatic.audit["measurements"]["network_receive_rate"]
    assert metric["normalized_level"] == pytest.approx(.5)
    assert metric["reference_source"] == "active interface link speed"

    manual = HostTelemetryAdapter(401, config={
        "signals": {"network_receive_rate": {"reference_override": True, "reference": 200}},
    }).encode(shared)
    metric = manual.audit["measurements"]["network_receive_rate"]
    assert metric["normalized_level"] == pytest.approx(.25)
    assert metric["reference_source"] == "adapter configured reference"


def test_process_adapter_is_explicitly_whole_process_and_nonnegative() -> None:
    reading = MetricReading.ratio(.4)
    shared = TelemetrySample("p1", datetime.now(timezone.utc).isoformat(), 1.0, "fake", {}, {"cpu_load": reading}, .1)
    adapter = ProcessTelemetryAdapter(303, config={"smoothing": 0.0})
    encoded = adapter.encode(shared)
    assert encoded.frame is not None
    assert encoded.frame.source == "ambient-process-telemetry"
    assert all(value >= 0 for value in encoded.frame.channels.values())


def test_counter_reset_reestablishes_probe_baseline() -> None:
    probe = SystemTelemetryProbe(psutil_module=None)
    assert probe._rate("counter", 100, 1.0) is None
    assert probe._rate("counter", 140, 2.0) == 40
    assert probe._rate("counter", 5, 3.0) is None
    assert probe._rate("counter", 15, 4.0) == 10


def test_missing_psutil_uses_native_cpu_memory_and_marks_other_metrics_unavailable() -> None:
    probe = SystemTelemetryProbe(psutil_module=None)
    host, process = probe.collect(1.0, {"host"})
    assert set(host_signal_names()).issubset(host)
    assert host["disk_read_rate"].available is False
    assert host["disk_read_rate"].raw_value is None
    assert process["cpu_load"].available is False


class CountingProbe:
    backend = "counting-probe"
    psutil = None

    def __init__(self) -> None:
        self.calls = 0

    def collect(self, monotonic_seconds: float, scopes: set[str] | None = None):
        self.calls += 1
        return sample(f"s{self.calls}", .4).host, {}


class BaselineAwareProbe(CountingProbe):
    def __init__(self) -> None:
        super().__init__()
        self.resets: list[set[str]] = []

    def reset_rate_baselines(self, scopes: set[str] | None = None) -> None:
        self.resets.append({"host", "process"} if scopes is None else set(scopes))


def test_shared_collector_samples_once_for_multiple_consciousness_encoders() -> None:
    probe = CountingProbe()
    collector = HostTelemetryCollector(probe=probe, clock=lambda: 10.0)
    shared = collector.sample({"host"})
    first = HostTelemetryAdapter(1, config=cpu_only_config()).encode(shared)
    second = HostTelemetryAdapter(2, config=cpu_only_config()).encode(shared)
    assert probe.calls == 1
    assert first.audit["sample_id"] == second.audit["sample_id"]
    assert set(first.frame.channels) != set(second.frame.channels)
    assert collector.status()["dependency"] == "partial"


def test_collector_reestablishes_raw_counter_baselines_after_scope_disconnect() -> None:
    probe = BaselineAwareProbe()
    collector = HostTelemetryCollector(probe=probe, clock=lambda: 10.0)
    collector.sample({"host"})
    collector.sample({"host"})
    collector.sample({"host", "process"})
    collector.deactivate({"host"})
    collector.sample({"host", "process"})
    assert probe.resets == [{"host"}, {"process"}, {"host"}]


def test_collector_injects_and_clears_application_host_timing() -> None:
    probe = CountingProbe()
    clock_values = iter((10.0, 10.001, 11.0, 11.001))
    collector = HostTelemetryCollector(probe=probe, clock=lambda: next(clock_values))
    collector.set_scheduler_latency(12.5)
    collector.set_tick_execution_time(3.25)
    measured = collector.sample({"process"})
    assert measured.process["scheduler_latency_ms"].raw_value == pytest.approx(12.5)
    assert measured.process["tick_execution_time_ms"].raw_value == pytest.approx(3.25)
    collector.clear_process_observations()
    cleared = collector.sample({"process"})
    assert "scheduler_latency_ms" not in cleared.process
    assert "tick_execution_time_ms" not in cleared.process


def test_sampling_configuration_uses_real_milliseconds_not_core_ticks() -> None:
    adapter = HostTelemetryAdapter(404, config={"sample_interval_ms": 1750})
    assert adapter.config["sample_interval_ms"] == 1750
    # The adapter accepts a monotonic-time sample directly. It has no Core
    # tick counter and therefore cannot change cadence with simulation speed.
    assert adapter.encode(sample("s1", .3)).audit["monotonic_seconds"] == 1.0


def test_registry_recursively_validates_and_merges_telemetry_config() -> None:
    registry = default_adapter_registry()
    state = {"host-telemetry-field": {"enabled": True, "config": {}}}
    updated = registry.update(state, "host-telemetry-field", enabled=None, config={"signals": {"cpu_load": {"gain": 2.5}}})
    assert updated["config"]["signals"]["cpu_load"]["gain"] == 2.5
    try:
        registry.update(state, "host-telemetry-field", enabled=None, config={"signals": {"cpu_load": {"invented": 1}}})
    except ValueError as error:
        assert "invented" in str(error)
    else:
        raise AssertionError("unknown nested telemetry property was accepted")


def test_model_defaults_make_host_telemetry_explicit_and_random_ambient_opt_in() -> None:
    manifest = ModelManifest.from_dict({})
    bindings = {row["adapter_id"]: row for row in manifest.adapter_bindings}
    assert bindings["host-telemetry-field"]["enabled"] is True
    assert bindings["process-telemetry-field"]["enabled"] is False
    assert bindings["runtime-telemetry-field"]["enabled"] is False
    assert bindings["ambient-field"]["enabled"] is False
    explicit = ModelManifest.from_dict({"adapter_bindings": [{"adapter_id": "host-telemetry-field", "enabled": False}]})
    assert explicit.adapter_bindings[0]["enabled"] is False


def test_partial_model_telemetry_config_is_fully_resolved_before_save() -> None:
    manifest = ModelManifest.from_dict({
        "adapter_bindings": [{
            "adapter_id": "host-telemetry-field",
            "enabled": True,
            "config": {"signals": {"cpu_load": {"gain": 2.0}}},
        }],
    })
    runtime = _HostObservedRuntime(ModelPackage.empty(manifest))
    _resolve_model_adapters(runtime)
    binding = runtime.manifest.adapter_bindings[0]
    assert binding["config"]["signals"]["cpu_load"]["gain"] == 2.0
    assert binding["config"]["signals"]["memory_pressure"]["level"] is True
    assert binding["config"]["sample_interval_ms"] == 1000
    assert runtime.manifest.parameters["homeostasis_enabled"] is False


def test_legacy_global_homeostasis_is_off_unless_explicitly_enabled() -> None:
    default_runtime = _HostObservedRuntime(ModelPackage.empty())
    assert default_runtime.config.homeostasis_enabled is False
    default_runtime.nodes = {
        1: {"activation": 10.0},
        2: {"activation": 10.0},
    }
    default_runtime._homeostasis()
    assert sum(float(node["activation"]) for node in default_runtime.nodes.values()) == pytest.approx(20.0)

    explicit = ModelManifest(parameters={"homeostasis_enabled": True, "target_total_activation": 4.0})
    clamped_runtime = _HostObservedRuntime(ModelPackage.empty(explicit))
    assert clamped_runtime.config.homeostasis_enabled is True
    clamped_runtime.nodes = {
        1: {"activation": 10.0},
        2: {"activation": 10.0},
    }
    clamped_runtime._homeostasis()
    assert sum(float(node["activation"]) for node in clamped_runtime.nodes.values()) == pytest.approx(4.0)


def test_runtime_feedback_requires_background_device_and_model_binding(monkeypatch) -> None:
    manifest = ModelManifest.from_dict({
        "adapter_bindings": [{"adapter_id": "runtime-telemetry-field", "enabled": True}],
    })
    runtime = _HostObservedRuntime(ModelPackage.empty(manifest))
    telemetry_device = adapter_runtime_state["runtime-telemetry-field"]
    stimuli = ui_settings.setdefault("stimuli", {})
    source_policies = stimuli.setdefault("source_policies", {})
    background_policy = source_policies.setdefault("background", {})
    monkeypatch.setitem(telemetry_device, "enabled", True)
    monkeypatch.setitem(stimuli, "background_enabled", True)
    monkeypatch.setitem(background_policy, "enabled", True)
    runtime.set_source("ambient", True)
    assert _telemetry_delivery_enabled(runtime, "runtime-telemetry-field") is True

    runtime.manifest.adapter_bindings[0]["enabled"] = False
    assert _telemetry_delivery_enabled(runtime, "runtime-telemetry-field") is False
    runtime.manifest.adapter_bindings[0]["enabled"] = True
    monkeypatch.setitem(telemetry_device, "enabled", False)
    assert _telemetry_delivery_enabled(runtime, "runtime-telemetry-field") is False
    monkeypatch.setitem(telemetry_device, "enabled", True)
    monkeypatch.setitem(stimuli, "background_enabled", False)
    assert _telemetry_delivery_enabled(runtime, "runtime-telemetry-field") is False


def test_legacy_random_ambient_switch_does_not_disable_background_master() -> None:
    disabled = {"stimuli": {"ambient_enabled": False}}
    assert _migrate_legacy_ambient_setting(disabled) is False
    assert disabled["stimuli"]["background_enabled"] is True
    assert "ambient_enabled" not in disabled["stimuli"]

    enabled = {"stimuli": {"ambient_enabled": True, "background_enabled": False}}
    assert _migrate_legacy_ambient_setting(enabled) is True
    # An explicitly configured new master remains authoritative.
    assert enabled["stimuli"]["background_enabled"] is False


def test_legacy_background_master_patch_updates_exact_source_policy() -> None:
    patch = {
        "stimuli": {
            "background_enabled": False,
            "source_policies": {"background": {"enabled": True, "bypass_attention": True}},
        },
    }
    _project_legacy_source_switches_into_policies(patch)
    assert patch["stimuli"]["source_policies"]["background"] == {
        "enabled": False,
        "bypass_attention": True,
    }


def test_audit_store_deduplicates_raw_sample_and_persists_delivery_links(tmp_path) -> None:
    path = tmp_path / "telemetry.sqlite3"
    shared = sample("s1", .5)
    store = TelemetryAuditStore(path)
    store.record_batch(shared, [
        {"consciousness_id": "mind-a", "adapter_id": "host-telemetry-field", "envelope_id": "a", "audit": {"measurements": {}}},
        {"consciousness_id": "mind-b", "adapter_id": "host-telemetry-field", "envelope_id": "b", "audit": {"measurements": {}}},
    ])
    store.record_sample(shared)
    assert store.list_samples()["total"] == 1
    assert store.list_deliveries()["total"] == 2
    store.close()
    reopened = TelemetryAuditStore(path)
    assert reopened.list_samples()["total"] == 1
    assert reopened.list_deliveries(consciousness_id="mind-a")["total"] == 1
    reopened.close()


def test_runtime_audit_migrates_old_schema_and_filters_by_owner_after_restart(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "telemetry.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE telemetry_samples (sample_id TEXT PRIMARY KEY, captured_at_utc TEXT NOT NULL, monotonic_seconds REAL NOT NULL, backend TEXT NOT NULL, payload_json TEXT NOT NULL)")
    connection.execute("CREATE TABLE telemetry_deliveries (delivery_id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT NOT NULL, consciousness_id TEXT NOT NULL, adapter_id TEXT NOT NULL, envelope_id TEXT, created_at_utc TEXT NOT NULL, audit_json TEXT NOT NULL)")
    legacy_payload = sample("s1", .2).to_dict()
    legacy_payload.pop("scope", None)
    legacy_payload.pop("owner_consciousness_id", None)
    legacy_payload.pop("context", None)
    connection.execute(
        "INSERT INTO telemetry_samples(sample_id,captured_at_utc,monotonic_seconds,backend,payload_json) VALUES (?,?,?,?,?)",
        ("s1", datetime.now(timezone.utc).isoformat(), 1.0, "legacy", json.dumps(legacy_payload)),
    )
    connection.commit()
    connection.close()

    store = TelemetryAuditStore(path)
    legacy = store.list_samples(scope="shared")
    assert legacy["items"][0]["scope"] == "shared"
    assert legacy["items"][0]["context"] == {}
    measured = runtime_sample(
        "runtime-owned",
        owner="mind-a",
        cpu_load=.3,
        context={"tick_start": 10, "tick_end": 14, "input_envelopes": [{"envelope_id": "external-1"}]},
    )
    store.record_batch(measured, [{
        "consciousness_id": "mind-a",
        "adapter_id": "runtime-telemetry-field",
        "envelope_id": "feedback-1",
        "audit": {"sample_context": measured.context, "measurements": {}},
    }])
    store.close()

    reopened = TelemetryAuditStore(path)
    result = reopened.list_samples(scope="runtime", consciousness_id="mind-a")
    assert result["total"] == 1
    assert result["items"][0]["context"]["tick_start"] == 10
    assert reopened.list_samples(scope="runtime", consciousness_id="mind-b")["total"] == 0
    assert reopened.list_deliveries(consciousness_id="mind-a", adapter_id="runtime-telemetry-field")["total"] == 1
    reopened.close()
