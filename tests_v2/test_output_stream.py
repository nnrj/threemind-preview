import json
from dataclasses import replace

import pytest
from test_api import client_for

from threemind_core import Stimulus
from threemind_lab.configuration import default_spec
from threemind_lab.organs import latest
from threemind_lab.worker import Worker
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.media import AcousticConfig, ProjectorConfig, organ_output
from threemind_runtime.output_organs import OutputOrgans
from threemind_runtime.profile import LEGACY_OUTPUT_FIELDS, profile_from_spec, validate_profile


@pytest.mark.parametrize("backend", ["native", "reference"])
def test_independent_output_cadence_restores_and_does_not_change_core(backend):
    engine = create_engine(backend=backend)
    engine.inject(Stimulus(0, ((1, 0.7), (2, 0.8))))
    engine.inject(Stimulus(173333, ((2, 0.4),)))
    baseline = create_engine(state=engine.capture_state(), backend=backend)
    baseline.advance_to(1000000)
    acoustic = AcousticConfig(enabled=True, output_interval_us=70001)
    projector = ProjectorConfig(enabled=True, output_interval_us=110003, width=8, height=8)
    output = OutputOrgans(acoustic, projector)
    delivered = []
    output.output.subscribe("device", delivered.append)
    rows = []
    while output.next_us <= 200000:
        engine.advance_to(output.next_us)
        rows.append(output.observe(engine))
    engine.advance_to(200000)
    copy = OutputOrgans(acoustic, projector, 200000, state=json.loads(json.dumps(output.capture())))
    frozen = copy.capture()
    frozen["configuration"]["acoustic_output"]["gain"] = 999
    assert copy.capture()["configuration"]["acoustic_output"]["gain"] == 1
    while output.next_us <= 1000000:
        engine.advance_to(output.next_us)
        row = output.observe(engine)
        assert copy.observe(engine) == row
        rows.append(row)
    engine.advance_to(1000000)
    final = output.observe(engine, final=True)
    assert final["terminal"] and copy.observe(engine, final=True) == final
    assert output.observe(engine, final=True) is None
    assert delivered == rows + [final]
    assert engine.capture_state().digest == baseline.capture_state().digest
    assert [int(r["time_us"]) for r in rows if "voices" in r] == list(range(0, 1000001, 70001))
    assert [int(r["time_us"]) for r in rows if "image" in r] == list(range(0, 1000001, 110003))


def test_output_reconfiguration_and_frequency_bounds_are_explicit():
    engine = create_engine()
    output = OutputOrgans(AcousticConfig(enabled=True), ProjectorConfig())
    engine.advance_to(12345)
    with pytest.raises(ValueError, match="skipped"):
        output.observe(engine)
    changed = OutputOrgans(replace(output.acoustic, gain=2), ProjectorConfig(), 12345, state=output.capture())
    assert changed.next_us == 12345 and changed.observe(engine)["time_us"] == "12345"
    with pytest.raises(ValueError):
        AcousticConfig(minimum_frequency=500, maximum_frequency=200)
    sample = organ_output(
        0,
        [(47, 0.8)],
        AcousticConfig(enabled=True, gain=2, minimum_frequency=200, maximum_frequency=3200),
        ProjectorConfig(enabled=True, width=8, height=8, gain=2),
    )
    assert sample["voices"][0]["amplitude"] == 1
    assert 200 <= sample["voices"][0]["frequency_hz"] < 3200
    assert "ff" in sample["image"]["gray8_hex"]


def test_legacy_profile_shape_and_hash_are_preserved():
    current = profile_from_spec(default_spec())
    assert current["schema"] == "threemind.runtime-profile/6"
    v4 = json.loads(json.dumps(current))
    v4.pop("source_policies")
    for root in ("host_telemetry", "process_telemetry", "runtime_telemetry"):
        v4[root].pop("intensity")
    v4["schema"] = "threemind.runtime-profile/4"
    assert validate_profile(v4) == v4
    old = json.loads(json.dumps(v4))
    old["schema"] = "threemind.runtime-profile/3"
    for root, keys in LEGACY_OUTPUT_FIELDS.items():
        old[root] = {key: value for key, value in old[root].items() if key in keys}
    assert validate_profile(old) == old
    engine = create_engine()
    for profile in (old, v4, current):
        raw = ArtifactCodec.encode(engine.capture_state(), "json", profile=profile)
        assert ArtifactCodec.decode(raw, with_profile=True)[1] == profile


def test_monitor_keeps_latest_per_organ_with_complete_evidence_and_project_permissions(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "output monitor verification"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = default_spec() | {
            "environment": "replay",
            "clock": "unbounded",
            "duration_s": 0.51,
            "sample_us": 200000,
            "replay": [Stimulus(0, ((1, 0.9), (2, 0.7))).to_dict()],
            "acoustic_output": {"enabled": True, "output_interval_us": 70000},
            "activation_projector": {"enabled": True, "output_interval_us": 110000, "width": 8, "height": 8},
            "structural_readout": {"enabled": False},
            "temporal_readout": {"enabled": False},
        }
        run = client.post(f"{root}/runs", json={"name": "independent outputs", "spec": spec}).json()["id"]
        assert Worker(database).once()
        url = f"{root}/runs/{run}"
        assert client.get(url).json()["status"] == "completed"
        rows = [json.loads(line) for line in client.get(f"{url}/organs/export").text.splitlines()]
        audio = [int(r["time_us"]) for r in rows if "voices" in r["payload"]]
        images = [int(r["time_us"]) for r in rows if "image" in r["payload"]]
        assert audio == list(range(0, 510000, 70000)) + [510000]
        assert images == list(range(0, 510000, 110000)) + [510000]
        # The final combined record must not erase the independently sampled histories.
        value = latest(database, project, run, rows[0]["sample_id"])
        assert value["skipped_samples"] == len(rows) - 2 and len(value["frames"]) == 1
        streamed = client.get(f"{url}/organs/monitor")
        assert streamed.status_code == 200 and "event: ended" in streamed.text
        assert "latest-committed-organ-samples" in streamed.text
        assert len(client.get(f"{url}/organs/export").text.splitlines()) == len(rows)
        assert client.get(f"{url}/organs/monitor", headers={"Origin": "https://untrusted.example"}).status_code == 403
        foreign = client.post("/api/v2/projects", json={"name": "foreign monitor"}).json()["id"]
        assert client.get(f"/api/v2/projects/{foreign}/runs/{run}/organs/monitor").status_code == 404
