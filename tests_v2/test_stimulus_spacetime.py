import copy
import importlib.util
import json
from dataclasses import replace
from pathlib import Path

import pytest

from threemind_core import Stimulus
from threemind_lab.configuration import catalogue, default_spec, require_valid, validate_configuration
from threemind_lab.protocols import RunSpec
from threemind_runtime import create_engine
from threemind_runtime.profile import profile_from_spec, validate_profile
from threemind_runtime.random_stimuli import RandomStimuli, RandomStimulusConfig
from threemind_runtime.sensory import TextSensor, TextSensorConfig, carrier_frames
from threemind_runtime.stimulus_presets import research_presets, resolve_intensity
from threemind_runtime.stimulus_units import unit_frames
from threemind_runtime.telemetry import HostTelemetryConfig, TelemetryEncoder
from threemind_runtime.world import PhysicalWorld
from threemind_runtime.world_schema import parse_world
from threemind_runtime.world_templates import physical_templates


def test_frozen_stimulus_witnesses():
    path = Path(__file__).parents[1] / "scripts/freeze-stimulus-baseline.py"
    spec = importlib.util.spec_from_file_location("frozen_stimulus", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baseline = json.loads((Path(__file__).parent / "fixtures/stimulus-6241016.json").read_text(encoding="utf-8"))
    assert module.witnesses() == baseline["witnesses"]


def test_strength_and_research_presets_preserve_encoding():
    for preset, intensity in (("normal", 1), ("strong", 4)):
        frames = list(carrier_frames("text-sensor", {"text": "甲是松子。", "preset": preset}, 7, {}))
        expected = list(TextSensor(7, TextSensorConfig()).frames("甲是松子。", intensity))
        assert frames == expected
    assert resolve_intensity(0.5, "strong") == 0.5
    for bad in (True, -1, 101, float("nan")):
        with pytest.raises(ValueError):
            resolve_intensity(bad)
    ordinary = default_spec()
    assert ordinary["config"]["stp_facilitation_tau_s"] == 0
    assert ordinary["config"]["novelty_mode"] == "arrival-window"
    preset = research_presets()[0]
    create_engine(preset["config"], kernel_id=preset["kernel_id"], backend="reference")
    assert catalogue()["text_intensity_presets"] == {"normal": 1, "strong": 4}


def test_optional_diagnostics_are_hash_neutral_and_separate_saturation_cost():
    from threemind_lab.stimulus_diagnostics import diagnose

    core = create_engine(kernel_id="threemind.continuous-memory/2", backend="reference")
    initial = core.capture_state()
    result = diagnose(initial, [Stimulus(0, ((1, 1.0), (2, 0.5)), 4), Stimulus(0, ((1, 1.0), (2, 0.5)), 4)], 100000)
    assert result["hash_verified"] and core.capture_state().digest == initial.digest
    assert any(r["kind"] == "consolidation" and r["extra_intensity"] > 0 for r in result["records"])
    assert any(r["kind"] == "touch" and r["received"] > r["activation_increment"] for r in result["records"])


def test_creation_and_legacy_telemetry_are_distinct():
    assert RunSpec(environment="host").host_telemetry.intensity == 1
    new = require_valid(validate_configuration({"environment": "host"}))
    assert new["host_telemetry"]["intensity"] == 0.2
    assert new["host_telemetry"]["enabled"]
    cfg = HostTelemetryConfig(enabled=True)
    raw = {"cpu_load": {"available": True, "normalized_level": 0.8}}
    legacy = TelemetryEncoder(4, cfg)
    frame, _ = legacy.encode(raw, monotonic_s=1, delivery_us=0)
    state = legacy.capture()
    state["version"] = "physical-telemetry/2"
    state["config"].pop("intensity")
    restored = TelemetryEncoder(4, cfg, state)
    assert restored.capture() == state
    assert frame.intensity == 1
    scaled, _ = TelemetryEncoder(4, replace(cfg, intensity=0.2)).encode(raw, monotonic_s=1, delivery_us=0)
    assert scaled.channels == frame.channels and scaled.intensity == 0.2
    profile = profile_from_spec({"seed": 4})
    assert validate_profile(profile) == profile
    old = copy.deepcopy(profile)
    old["schema"] = "threemind.runtime-profile/5"
    for key in ("host_telemetry", "process_telemetry", "runtime_telemetry"):
        old[key].pop("intensity")
    assert validate_profile(old) == old


@pytest.mark.parametrize("mode", ["fresh-single", "fresh-group", "fixed-amplitude"])
def test_random_recovery_and_declared_correlation(mode):
    source = RandomStimuli(RandomStimulusConfig(mode=mode))
    first = source.sample()
    restored = RandomStimuli(source.config, source.capture())
    second = source.sample()
    assert second == restored.sample()
    one, two = ({e["channel"] for e in sample["elements"]} for sample in (first, second))
    assert bool(one & two) == (mode == "fixed-amplitude")
    assert len(list(unit_frames({"units": [first, second]}))) == 2


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_metadata_does_not_change_core_and_groups_are_not_merged(backend):
    source = RandomStimuli(RandomStimulusConfig(mode="fresh-single"))
    units = [source.sample(), source.sample()]
    units[1]["time_us"] = "0"
    other = copy.deepcopy(units)
    for unit in other:
        unit.update(
            source="observer-renamed", coordinate_frame="arbitrary label", measurements=[{"meaning": "unknown"}]
        )
    a, b = [create_engine(kernel_id="threemind.continuous-memory/2", backend=backend) for _ in range(2)]
    for engine, rows in ((a, units), (b, other)):
        for frame in unit_frames({"units": rows}):
            engine.inject(frame["stimulus"])
        engine.advance_to(100000)
    assert a.capture_state().digest == b.capture_state().digest
    assert not a.capture_state().to_dict()["edges"]


def imu_world(*, free=False, quaternion=(1.0, 0.0, 0.0, 0.0)):
    return parse_world(
        {
            "schema_id": "threemind.world/2",
            "bodies": [{"id": "body", "free": free}],
            "joints": [] if free else [{"id": "horizontal_rail", "body_id": "body", "damping": 0}],
            "geometries": [{"id": "ball", "body_id": "body"}],
            "sensors": [
                {"kind": "accelerometer", "body_id": "body", "id": "acc", "port": 0, "quaternion": quaternion},
                {"kind": "gyroscope", "body_id": "body", "id": "gyro", "port": 1},
            ],
        }
    )


def test_imu_measures_support_freefall_and_local_rotation():
    with PhysicalWorld(imu_world(), 8) as fixed:
        fixed.sample(0)
        assert fixed.last_measurements[0]["values"] == pytest.approx([0, 0, 9.81])
        assert fixed.last_measurements[1]["values"] == pytest.approx([0, 0, 0])
    with PhysicalWorld(imu_world(free=True), 8) as falling:
        falling.data.qvel[0] = 3.0  # uniform horizontal motion contributes no proper acceleration
        falling.data.qvel[5] = 2.0
        falling.sample(0)
        assert falling.last_measurements[0]["values"] == pytest.approx([0, 0, 0], abs=1e-10)
        assert falling.last_measurements[1]["values"] == pytest.approx([0, 0, 2], abs=1e-10)
    with PhysicalWorld(imu_world(quaternion=(0.0, 1.0, 0.0, 0.0)), 8) as inverted:
        inverted.sample(0)
        assert inverted.last_measurements[0]["values"] == pytest.approx([0, 0, -9.81])


@pytest.mark.parametrize("template", ["inertial-cart", "gravity-pendulum"])
def test_world2_recovery_and_carrier_boundary(template):
    spec = physical_templates()[template]
    with PhysicalWorld(spec, 4) as original:
        frame = original.sample(0)
        carrier = original.stimulus_unit(frame, capture_us=20000)
        assert next(iter(unit_frames({"units": [carrier]})))["stimulus"] == frame
        state = original.capture()
        assert state["schema"] == "threemind.world-state/2"
        with PhysicalWorld(spec, 4, state) as restored:
            assert original.sample(20000) == restored.sample(20000)
            assert original.capture() == restored.capture()
    legacy = spec.model_dump(mode="json") | {"schema_id": "threemind.world/1"}
    with pytest.raises(ValueError, match="world/2"):
        parse_world(legacy)


def test_units_api_admission_and_copy_diagnostics(database):
    from uuid import uuid4

    from test_api import client_for

    from threemind_lab.worker import Worker

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Stimulus units acceptance"}).json()["id"]
        random_url = f"/api/v2/projects/{project}/input-fixtures/random"
        generated = client.post(random_url, json={"config": {"seed": 42}, "count": 2})
        assert generated.status_code == 200 and generated.json()["submitted"] is False
        assert len(generated.json()["units"]) == 2
        invalid = client.post(random_url, json={"config": {"unknown_parameter": 1}})
        assert invalid.status_code == 422, invalid.text
        state = generated.json()["state"]
        del state["index"]
        invalid = client.post(random_url, json={"config": {"seed": 42}, "state": state})
        assert invalid.status_code == 422, invalid.text
        base = f"/api/v2/projects/{project}/runs"
        run = client.post(
            base,
            json={
                "name": "Copy diagnostic",
                "spec": {"environment": "manual", "clock": "unbounded", "duration_s": 0.2},
            },
        )
        assert run.status_code == 201, run.text
        run_id = run.json()["id"]
        unit = RandomStimuli().sample()
        response = client.post(
            f"{base}/{run_id}/inputs",
            json={"adapter_id": "stimulus-units", "payload": {"units": [unit]}, "request_id": str(uuid4())},
        )
        assert response.status_code == 202, response.text
        worker = Worker(database, backend="native")
        worker.once()
        _, before = database.load_checkpoint(project, run_id)
        response = client.post(
            f"{base}/{run_id}/input-diagnostics",
            json={"adapter_id": "text-sensor", "payload": {"text": "甲", "preset": "strong"}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["hash_verified"]
        _, after = database.load_checkpoint(project, run_id)
        assert before.digest == after.digest


def test_independent_cli_presets_and_units(tmp_path):
    import subprocess
    import sys

    from threemind_runtime.codec import ArtifactCodec

    text = tmp_path / "carrier.txt"
    text.write_text("甲是松子。", encoding="utf-8")
    outputs = []
    for index, args in enumerate(
        (
            ["--text-input", str(text), "--text-preset", "strong"],
            ["--text-input", str(text), "--text-intensity", "4"],
        )
    ):
        output = tmp_path / f"model{index}.json"
        subprocess.run(
            [sys.executable, "-m", "threemind_runtime.cli", "--clock", "unbounded", "--export", str(output), *args],
            check=True,
            capture_output=True,
            timeout=30,
        )
        outputs.append(ArtifactCodec.decode(output.read_bytes()).digest)
    assert outputs[0] == outputs[1]
    unit = RandomStimuli().sample()
    raw = tmp_path / "units.jsonl"
    raw.write_text(json.dumps(unit) + "\n", encoding="utf-8")
    output = tmp_path / "units-model.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "threemind_runtime.cli",
            "--clock",
            "unbounded",
            "--stimulus-units",
            str(raw),
            "--export",
            str(output),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    expected = create_engine()
    expected.inject(next(iter(unit_frames({"units": [unit]})))["stimulus"])
    expected.advance_to(1000000)
    assert ArtifactCodec.decode(output.read_bytes()).digest == expected.capture_state().digest
