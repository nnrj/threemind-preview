import copy
import csv
import io
import json
import math
from collections import namedtuple
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from test_api import client_for

from threemind_core import Engine
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.protocols import RunSpec, StudySpec
from threemind_lab.telemetry import RuntimeTelemetry
from threemind_lab.worker import Worker
from threemind_runtime.profile import profile_from_spec, validate_profile
from threemind_runtime.telemetry import (
    METRICS,
    TELEMETRY_CONFIGS,
    ExecutionMeter,
    HostTelemetryConfig,
    RuntimeTelemetryConfig,
    SignalConfig,
    TelemetryEncoder,
    telemetry_parameters,
)
from threemind_runtime.telemetry_probe import MetricReading, SystemTelemetryProbe, _cpu_totals


def reading(value):
    return MetricReading.ratio(value).to_dict()


def test_encoding_real_time_smoothing_discontinuity_and_disjoint_wiring():
    config = HostTelemetryConfig(enabled=True, smoothing_tau_s=1)
    encoder = TelemetryEncoder(47, config)
    first, a = encoder.encode({"memory_pressure": reading(0.2)}, monotonic_s=1.0, delivery_us=100)
    snapshot = encoder.capture()
    second, b = encoder.encode({"memory_pressure": reading(0.6)}, monotonic_s=3.0, delivery_us=200)
    expected = math.exp(-2) * 0.2 + (1 - math.exp(-2)) * 0.6
    assert b["memory_pressure"]["smoothed_level"] == pytest.approx(expected)
    assert len(first.channels) == 1 and len(second.channels) == 2
    assert not a["memory_pressure"]["baseline_established"]
    assert snapshot["previous"]["memory_pressure"] == 0.2  # capture cannot alias future mutations
    resumed = TelemetryEncoder(47, config, snapshot)
    assert resumed.encode({"memory_pressure": reading(0.6)}, monotonic_s=3.0, delivery_us=200) == (second, b)
    missing, audit = encoder.encode({}, monotonic_s=4.0, delivery_us=300)
    assert missing is None and not audit["memory_pressure"]["raw"]["available"]
    reappeared, audit = encoder.encode({"memory_pressure": reading(0.9)}, monotonic_s=5.0, delivery_us=400)
    assert len(reappeared.channels) == 1 and not audit["memory_pressure"]["baseline_established"]
    with pytest.raises(ValueError, match="increasing"):
        encoder.encode({}, monotonic_s=5.0, delivery_us=500)
    disabled = TelemetryEncoder(47, replace(config, enabled=False))
    assert disabled.encode({"memory_pressure": reading(0.9)}, monotonic_s=1.0, delivery_us=0)[0] is None
    identities = set()
    for cls in TELEMETRY_CONFIGS.values():
        e = TelemetryEncoder(47, cls(enabled=True, smoothing_tau_s=0))
        values = {name: reading(0.5) for name in METRICS[cls.scope]}
        pulses = []
        for t, level in enumerate((0.5, 1.0, 0.0), 1):
            frame, _ = e.encode({name: reading(level) for name in values}, monotonic_s=float(t), delivery_us=t)
            pulses.extend(n for n, _ in frame.channels)
        ids = set(pulses)
        assert not ids & identities and len(ids) == len(values) * 3
        identities |= ids
    assert len(identities) == 105


def test_manual_scale_uses_raw_measurement_and_does_not_invent_missing_values():
    cfg = HostTelemetryConfig(
        enabled=True, signals={"cpu_frequency": SignalConfig(reference_override=True, reference=4e9)}
    )
    value = MetricReading.scaled(2e9, unit="Hz", reference=0, reference_source="missing maximum").to_dict()
    assert value["raw_value"] == 2e9 and value["normalized_level"] is None
    e = TelemetryEncoder(7, cfg)
    frame, audit = e.encode({"cpu_frequency": value}, monotonic_s=1.0, delivery_us=1)
    assert len(frame.channels) == 1 and frame.channels[0][1] == 0.5
    assert audit["cpu_frequency"]["reference_source"] == "explicit adapter reference"
    bad = MetricReading.unavailable("Hz", "no counter").to_dict()
    assert e.encode({"cpu_frequency": bad}, monotonic_s=2.0, delivery_us=2)[0] is None
    probe = SystemTelemetryProbe(psutil_module=None)
    assert probe._rate("x", 50, 1.0) is None
    assert probe._rate("x", 100, 3.0) == 25
    assert probe._rate("x", None, 4.0) is None
    assert probe._rate("x", 9000, 5.0) is None
    assert probe._rate("x", 1, 6.0) is None
    CPU = namedtuple("CPU", "user system idle guest guest_nice interrupt dpc")
    assert _cpu_totals(CPU(10, 8, 7, 2, 1, 1, 1)) == (25, 7)


def test_configuration_coverage_and_strict_portable_profiles():
    fields = {f["path"]: f for f in catalogue()["fields"]}
    contract = {}
    for root, path, field, default, _ in telemetry_parameters():
        assert fields[f"{root}.{path}"]["default"] == default
        contract.setdefault(root, {})[path] = {**field.metadata, "type": type(default).__name__}
    actual = json.loads(
        Path("crates/threemind-runtime/src/telemetry-profile-contract.json").read_text(encoding="utf-8")
    )
    assert actual == json.loads(json.dumps(contract))
    assert len([p for p in fields if "_telemetry." in p]) == 193
    spec = default_spec()
    spec["process_telemetry"]["enabled"] = True
    spec["process_telemetry"]["signals"]["cpu_load"]["gain"] = 0.7
    validated = validate_configuration(spec, current=default_spec())
    assert validated["valid"] and validated["spec"]["process_telemetry"]["signals"]["cpu_load"]["gain"] == 0.7
    invalid = copy.deepcopy(spec)
    invalid["runtime_telemetry"]["signals"]["thread_cpu_load"]["gain"] = "1"
    assert not validate_configuration(invalid)["valid"]
    with pytest.raises(ValueError):
        RunSpec(**(spec | {"clock": "unbounded"}))
    with pytest.raises(ValueError):
        StudySpec(base=RunSpec(**spec))
    profile = profile_from_spec(spec)
    assert profile["schema"] == "threemind.runtime-profile/6" and validate_profile(profile) == profile
    broken = copy.deepcopy(profile)
    del broken["host_telemetry"]["signals"]["memory_pressure"]
    with pytest.raises(ValueError):
        validate_profile(broken)
    v2 = {k: v for k, v in profile.items() if k not in TELEMETRY_CONFIGS and k != "source_policies"}
    v2["schema"] = "threemind.runtime-profile/2"
    from threemind_runtime.profile import LEGACY_OUTPUT_FIELDS

    for root, keys in LEGACY_OUTPUT_FIELDS.items():
        v2[root] = {key: value for key, value in v2[root].items() if key in keys}
    assert validate_profile(v2) == v2


class FakeProbe:
    backend = "deterministic-test-probe"

    def reset_rate_baselines(self, scopes):
        self.reset_scopes = scopes

    def collect(self, now, scopes=("host", "process")):
        return (
            {"memory_pressure": MetricReading.ratio(0.25)} if "host" in scopes else {},
            {"thread_count": MetricReading.scaled(4, unit="threads", reference=512, reference_source="test")}
            if "process" in scopes
            else {},
        )


def test_instance_feedback_measures_only_previous_core_calls_and_delays_delivery():
    meter = ExecutionMeter(0.0)
    meter.add(0.2, 0.1, 0.05)
    values, context = meter.close(1.0)
    assert values["thread_cpu_load"]["raw_value"] == 0.1
    assert values["epoch_busy_ratio"]["raw_value"] == 0.2
    assert values["epoch_execution_time_ms"]["raw_value"] == 200
    assert context["core_calls"] == 1
    assert meter.close(2.0)[0]["epoch_execution_time_ms"]["available"] is False
    now = [0.0]
    spec = RunSpec(environment="manual", runtime_telemetry=RuntimeTelemetryConfig(enabled=True, sample_interval_ms=100))
    engine = Engine()
    run = str(uuid4())
    inputs = RuntimeInputs(None, str(uuid4()), run, engine, spec, {}, 0)
    t = RuntimeTelemetry(spec, run, clock=lambda: now[0], probe=FakeProbe())
    events = []
    t.measured(0.01, 0.005, 0.002)
    now[0] = 0.09
    t.poll(inputs, events.append, source_enabled=True)
    assert not events
    now[0] = 0.1
    engine.advance_to(100000)
    t.poll(inputs, events.append, source_enabled=True)
    assert events[0]["payload"]["context"]["runtime"]["thread_cpu_s"] == 0.005
    frame = inputs.changes["frames"][0]
    assert frame["scheduled_time_us"] == "200000" and not engine.graph()["nodes"]
    engine.advance_to(200000)
    assert engine.graph()["nodes"]
    restarted = RuntimeTelemetry(spec, run, clock=lambda: now[0], probe=FakeProbe())
    assert restarted.session_id != t.session_id and not restarted.encoders["runtime"].previous
    now[0] = 0.3
    restarted.poll(inputs, events.append, source_enabled=False)
    assert len(events) == 1


def test_telemetry_database_atomicity_paging_export_and_worker_resume(database, monkeypatch):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "telemetry restoration"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = RunSpec(
            environment="manual",
            duration_s=0.65,
            checkpoint_us=100000,
            host_telemetry=HostTelemetryConfig(enabled=True, sample_interval_ms=100),
        )
        created = client.post(f"{root}/runs", json={"name": "OS sampling", "spec": spec.model_dump()})
        assert created.status_code == 201, created.text
        run = created.json()["id"]
        url = f"{root}/runs/{run}"
        engine = Engine()
        inputs = RuntimeInputs(database, project, run, engine, spec, {}, 0)
        now = [0.0]
        sampler = RuntimeTelemetry(spec, run, clock=lambda: now[0], probe=FakeProbe())
        now[0] = 0.1
        events = []
        sampler.poll(inputs, events.append, source_enabled=True)
        from threemind_lab import inputs as storage

        original = storage.commit_inputs

        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("injected commit failure")

        with monkeypatch.context() as patch:
            patch.setattr(storage, "commit_inputs", fail)
            with pytest.raises(ValueError, match="injected"):
                database.save_checkpoint(
                    project,
                    run,
                    engine.capture_state(),
                    expected_revision=0,
                    events=events,
                    input_changes=inputs.changes,
                )
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM events WHERE kind='telemetry_sample'").fetchone()["n"] == 0
            assert db.execute("SELECT count(*) AS n FROM input_envelopes").fetchone()["n"] == 0
        monkeypatch.setattr("threemind_runtime.telemetry_probe.SystemTelemetryProbe", FakeProbe)
        poll = RuntimeTelemetry.poll
        requested = []

        def pause_after_sampling(sampler, inputs, emit, **kwargs):
            poll(sampler, inputs, emit, **kwargs)
            if sampler.last and not requested:
                requested.append(True)
                assert client.post(f"{url}/commands", json={"kind": "pause"}).status_code == 200

        with monkeypatch.context() as patch:
            patch.setattr(RuntimeTelemetry, "poll", pause_after_sampling)
            assert Worker(database).once()
        paused = client.get(url).json()
        assert paused["status"] == "paused", paused.get("error")
        assert client.post(f"{url}/commands", json={"kind": "resume"}).status_code == 200
        assert Worker(database).once()
        finished = client.get(url).json()
        assert finished["status"] == "completed", finished.get("error")
        rows, cursor = [], None
        while True:
            page = client.get(
                f"{url}/telemetry", params={"limit": 1, **({"before_id": cursor} if cursor else {})}
            ).json()
            rows += page["rows"]
            if not page["more"]:
                break
            cursor = page["next"]
        assert len(rows) >= 2 and len({r["id"] for r in rows}) == len(rows)
        assert len({r["payload"]["session_id"] for r in rows}) == 2
        earliest = {}
        for row in reversed(rows):
            earliest.setdefault(row["payload"]["session_id"], row)
        assert all(
            not r["payload"]["scopes"]["host"]["measurements"]["memory_pressure"]["baseline_established"]
            for r in earliest.values()
        )
        for row in rows:
            evidence = row["payload"]["scopes"]["host"]
            detail = client.get(f"{url}/inputs/{evidence['envelope_id']}").json()
            assert detail["envelope"]["payload"]["sample_id"] == row["payload"]["sample_id"]
            assert int(evidence["scheduled_time_us"]) >= int(row["time_us"]) + 100000
        assert not any(e["kind"] == "telemetry_sample" for e in client.get(f"{url}/events").json())
        assert len(client.get(f"{url}/events?kind=telemetry_sample").json()) == len(rows)
        assert len(client.get(f"{url}/telemetry/export").text.splitlines()) == len(rows)
        records = list(
            csv.DictReader(io.StringIO(client.get(f"{url}/telemetry/export?format=csv").text.lstrip("\ufeff")))
        )
        assert len(records) == len(rows) * 21
        missing = [r for r in records if r["metric"] == "cpu_frequency"]
        assert all(r["available"] == "False" and r["raw_value"] == "" for r in missing)
        other = client.post("/api/v2/projects", json={"name": "other"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/runs/{run}/telemetry").status_code == 404
        assert client.get(f"{url}/telemetry?scope=missing").status_code == 422
        assert client.get(f"{url}/telemetry/export?format=missing").status_code == 422
