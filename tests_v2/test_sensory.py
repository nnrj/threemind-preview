import io
import json
import subprocess
import zipfile
from dataclasses import asdict, replace
from uuid import uuid4

import pytest
from test_api import client_for
from test_runtime_interop import RUNTIME

from threemind_core import Config, Engine, Stimulus
from threemind_lab.configuration import default_spec, validate_configuration
from threemind_lab.inputs import evidence_rows
from threemind_lab.worker import Worker
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.adapters import channel_id
from threemind_runtime.bus import InputBus, LatestOutput, OutputBus
from threemind_runtime.profile import profile_from_spec
from threemind_runtime.sensory import TextSensor, TextSensorConfig, carrier_frames
from threemind_runtime.store import SQLiteStore


def test_text_modes_preserve_carriers_and_labels_are_observation_only():
    config = TextSensorConfig(frame_characters=2)
    anonymous = TextSensor(11, config)
    labeled = TextSensor(11, replace(config, encoding="labeled-observation"))
    text = "Ａ\n汉字 👁 "
    a, b = list(anonymous.frames(text)), list(labeled.frames(text))
    assert [f["stimulus"] for f in a] == [f["stimulus"] for f in b]
    assert all(not f["labels"] for f in a) and any(f["labels"] for f in b)
    assert anonymous.normalize(text) == "A\n汉字 👁 "
    assert [f["stimulus"].time_us for f in a] == list(range(0, len(a) * 20000, 20000))
    assert next(anonymous.frames(" "))["stimulus"].channels  # whitespace is a carrier
    engines = [Engine(), Engine()]
    for engine, frames in zip(engines, (a, b)):
        for f in frames:
            engine.inject(f["stimulus"])
        engine.advance_to(100000)
    assert engines[0].capture_state().digest == engines[1].capture_state().digest
    literal = TextSensor(11, replace(config, encoding="literal-character", frame_characters=1))
    chars = "Aa汉字👁\n "
    receptors = [f["stimulus"].channels[0][0] for f in literal.frames(chars)]
    assert len(set(receptors)) == len(chars)
    reserved = {
        channel_id(11, ns, i) for ns, size in (("planar-physical-v1", 16), ("host-physical-v1", 4)) for i in range(size)
    }
    assert not reserved.intersection(receptors)
    assert list(TextSensor(12, config).frames(text)) != a
    with pytest.raises(ValueError):
        list(TextSensor(11, replace(config, max_carrier_characters=2)).frames("ABC"))
    with pytest.raises(ValueError):
        list(carrier_frames("anonymous-frames", {"frames": [{}]}, 11, {}))
    with pytest.raises(ValueError):
        list(
            carrier_frames(
                "anonymous-frames",
                {"frames": [{"time_us": "1", "channels": []}, {"time_us": "0", "channels": []}]},
                11,
                {},
            )
        )
    original = default_spec()
    changed = original | {"text_sensor": asdict(replace(TextSensorConfig(), encoding="literal-character"))}
    assert any(e["path"] == "text_sensor.encoding" for e in validate_configuration(changed, current=original)["errors"])


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_input_bus_preserves_independent_events_and_recovers_exactly(backend):
    engine = create_engine(Config(), backend=backend)
    bus = InputBus(engine)
    bus.reserve(2, 2)
    bus.schedule(Stimulus(3000, ((7, 0.7),)), {"envelope_id": "A"})
    bus.schedule(Stimulus(3000, ((9, 0.5),)), {"envelope_id": "B"})
    assert bus.pending_count() == 2 and bus.remaining_channels() == 2
    image = engine.capture_state()
    resumed = create_engine(state=image, backend=backend)
    other = InputBus(resumed, bus.capture())
    other.verify(image.to_dict())
    seen = []
    engine.advance_to(3000, lambda event: seen.append(bus.observe(event)), inputs_only=True)
    resumed.advance_to(3000, other.observe, inputs_only=True)
    assert engine.capture_state().digest == resumed.capture_state().digest
    assert [f["envelope_id"] for f in seen] == ["A", "B"]
    assert len({f["core_event_id"] for f in seen}) == 2
    assert not engine.capture_state().to_dict()["edges"]  # no false AB co-stimulation
    assert other.pending_count() == bus.pending_count() == 0 and other.remaining_channels() == 0
    merged = create_engine(backend=backend)
    merged.inject(Stimulus(3000, ((7, 0.7), (9, 0.5))))
    merged.advance_to(3000)
    assert merged.capture_state().to_dict()["edges"]


def test_output_consumers_do_not_mutate_each_other_and_evidence_failure_is_visible():
    bus, view, evidence = OutputBus(), LatestOutput(), []
    bus.subscribe("evidence", evidence.append)
    bus.subscribe("view", view)
    bus.subscribe("mutator", lambda value: value.update(fake=True))
    bus.publish({"sequence": 1})
    bus.publish({"sequence": 2})
    assert evidence == [{"sequence": 1}, {"sequence": 2}]
    assert view.take() == {"frame": {"sequence": 2}, "skipped": 1}

    def fail(value):
        raise RuntimeError("sink unavailable")

    bus.subscribe("failure", fail)
    with pytest.raises(RuntimeError, match="sink unavailable"):
        bus.publish({"sequence": 3})


def test_input_records_are_project_scoped_and_checkpoint_atomic(database):
    with client_for(database) as client:
        projects = [client.post("/api/v2/projects", json={"name": name}).json()["id"] for name in ("A", "B")]
        runs = [
            database.create_run(p, "Input boundaries", default_spec() | {"environment": "manual"}) for p in projects
        ]
        urls = [f"/api/v2/projects/{p}/runs/{r['id']}" for p, r in zip(projects, runs)]
        payload = {"adapter_id": "text-sensor", "request_id": str(uuid4()), "payload": {"text": "=原始文本"}}
        assert client.post(f"{urls[0]}/inputs", json=payload).status_code == 202
        assert client.post(f"{urls[1]}/inputs", json=payload).status_code == 409
        assert client.get(f"{urls[1]}/inputs/{payload['request_id']}").status_code == 404
        assert client.get(f"{urls[1]}/inputs").json()["rows"] == []
        empty = client.get(f"{urls[1]}/inputs/export?records=frames&format=csv")
        assert empty.status_code == 200 and "envelope_id" in empty.text.splitlines()[0]
        bad = {
            "envelope_id": payload["request_id"],
            "frame_index": 0,
            "core_event_id": 1,
            "core_sequence": 1,
            "delivered_time_us": "0",
        }
        with pytest.raises(ValueError, match="no matching scheduled"):
            database.save_checkpoint(
                projects[0],
                runs[0]["id"],
                Engine().capture_state(),
                expected_revision=0,
                input_changes={"delivered": [bad]},
            )
        assert database.get_run(projects[0], runs[0]["id"])["revision"] == 0
        assert client.get(f"{urls[0]}/inputs/{payload['request_id']}").json()["envelope"]["status"] == "accepted"


def test_admission_pause_fork_and_historical_provenance(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Sensory restoration"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = default_spec() | {
            "environment": "manual",
            "clock": "unbounded",
            "duration_s": 0.1,
            "text_sensor": asdict(TextSensorConfig(encoding="literal-character", frame_characters=1)),
            "input_bus": {"max_pending_frames": 3, "max_pending_channels": 10},
        }
        response = client.post(f"{root}/runs", json={"name": "Sensory subject", "spec": spec})
        assert response.status_code == 201, response.text
        run_id = response.json()["id"]
        url = f"{root}/runs/{run_id}"
        client.post(f"{url}/commands", json={"kind": "pause"})
        worker = Worker(database)
        assert worker.once()
        assert client.get(url).json()["status"] == "paused"
        payload = {
            "adapter_id": "text-sensor",
            "request_id": str(uuid4()),
            "payload": {"text": "A汉B"},
            "delay_us": 5000,
        }
        accepted = client.post(f"{url}/inputs", json=payload)
        assert accepted.status_code == 202, accepted.text
        assert accepted.json()["frame_count"] == 3
        assert client.post(f"{url}/inputs", json=payload).json()["id"] == accepted.json()["id"]
        assert client.post(f"{url}/inputs", json=payload | {"payload": {"text": "C"}}).status_code == 409
        assert client.post(f"{url}/inputs", json=payload | {"request_id": str(uuid4())}).status_code == 409
        assert (
            client.post(
                f"{url}/inputs", json=payload | {"request_id": str(uuid4()), "payload": {"text": "ABCD"}}
            ).status_code
            == 422
        )
        before = client.get(url).json()
        low = spec | {"input_bus": {"max_pending_frames": 2, "max_pending_channels": 10}}
        assert (
            client.put(
                f"{url}/configuration", json={"name": "Subject", "spec": low, "expected_revision": before["revision"]}
            ).status_code
            == 409
        )
        assert client.get(f"{url}/inputs").json()["rows"][0]["status"] == "accepted"
        client.post(f"{url}/commands", json={"kind": "pause"})
        client.post(f"{url}/commands", json={"kind": "resume"})
        assert worker.once()
        paused = client.get(url).json()
        assert paused["status"] == "paused", paused.get("error")
        queue = client.get(f"{url}/input-queue").json()
        assert queue["pending_frames"] == 3 and queue["next"]["scheduled_time_us"] == "5000"
        cp, image = database.load_checkpoint(project, run_id)
        expected = create_engine(state=image)
        expected.advance_to(100000)
        detail = client.get(f"{url}/inputs/{payload['request_id']}").json()
        assert [int(f["scheduled_time_us"]) for f in detail["frames"]] == [5000, 25000, 45000]
        assert detail["envelope"]["payload"] == {"text": "A汉B"}
        child = client.post(f"{url}/forks", json={"name": "Independent audit", "inherit": False}).json()["id"]
        assert worker.once()
        child_row = database.get_run(project, child)
        assert child_row["status"] == "completed", child_row["error"]
        assert child_row["state_hash"] == expected.capture_state().digest
        assert client.get(f"{url}/inputs/{payload['request_id']}").json()["envelope"]["delivered_count"] == 0
        client.post(f"{url}/commands", json={"kind": "resume"})
        assert worker.once()
        completed = client.get(url).json()
        assert completed["status"] == "completed", completed.get("error")
        assert completed["state_hash"] == child_row["state_hash"]
        detail = client.get(f"{url}/inputs/{payload['request_id']}").json()
        assert detail["envelope"]["delivered_count"] == 3
        assert all(f["scheduled_time_us"] == f["delivered_time_us"] for f in detail["frames"])
        with database.tx(project) as db:
            historical = list(evidence_rows(db, run_id, cp["revision"]))
        assert all(f["status"] == "scheduled" and f["delivered_time_us"] is None for f in historical)
        raw = client.get(f"{url}/inputs/export?records=envelopes&format=jsonl").text.splitlines()
        assert json.loads(raw[1])["payload"] == {"text": "A汉B"}
        assert "A汉B" in client.get(f"{url}/inputs/export?records=envelopes&format=csv").text
        export = client.post(f"{url}/exports", json={"format": "evidence", "checkpoint_id": str(cp["id"])}).json()
        assert worker.once()
        job = next(j for j in client.get(f"{root}/jobs").json() if j["id"] == export["id"])
        assert job["status"] == "done", job.get("error")
        raw = client.get(f"{root}/artifacts/{job['result']['artifact_id']}").content
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            frames = [json.loads(line) for line in archive.read("input-frames.jsonl").splitlines()]
            assert len(frames) == 3 and all(f["status"] == "scheduled" for f in frames)
            assert not any(
                json.loads(line)["kind"] == "input_delivered" for line in archive.read("events.jsonl").splitlines()
            )
            model = archive.read("model.tmind")
        imported = client.post(f"{root}/imports", files={"file": ("model.tmind", model, "application/zip")})
        assert imported.status_code == 201, imported.text
        assert imported.json()["spec"]["text_sensor"] == spec["text_sensor"]
        assert imported.json()["spec"]["seed"] == spec["seed"]


@pytest.mark.parametrize("format", ["tmind", "json"])
@pytest.mark.parametrize("profile_version", [3, 4, 5, 6])
def test_runtime_profile_survives_rust_python_and_sqlite_round_trip(tmp_path, format, profile_version):
    assert RUNTIME.exists(), "build the Rust runtime to validate portable profiles"
    profile = profile_from_spec(
        default_spec() | {"seed": 23, "text_sensor": asdict(TextSensorConfig(encoding="literal-character", gain=0.5))}
    )
    profile["schema"] = f"threemind.runtime-profile/{profile_version}"
    if profile_version < 6:
        for root in ("host_telemetry", "process_telemetry", "runtime_telemetry"):
            profile[root].pop("intensity")
    if profile_version < 5:
        profile.pop("source_policies")
        profile["schema"] = f"threemind.runtime-profile/{profile_version}"
    if profile_version == 3:
        from threemind_runtime.profile import LEGACY_OUTPUT_FIELDS

        profile["schema"] = "threemind.runtime-profile/3"
        for root, keys in LEGACY_OUTPUT_FIELDS.items():
            profile[root] = {key: value for key, value in profile[root].items() if key in keys}
    initial = Engine().capture_state()
    source, output, dbfile = tmp_path / f"input.{format}", tmp_path / "output.tmind", tmp_path / "device.sqlite"
    source.write_bytes(ArtifactCodec.encode(initial, format, profile=profile))
    result = subprocess.run(
        [
            str(RUNTIME),
            "--model",
            str(source),
            "--clock",
            "unbounded",
            "--until-us",
            "10000",
            "--export",
            str(output),
            "--store",
            str(dbfile),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    image, actual = ArtifactCodec.decode(output.read_bytes(), with_profile=True)
    assert actual == profile
    store = SQLiteStore(dbfile)
    revision, saved, actual = store.load("default", with_profile=True)
    assert actual == profile and image.digest == saved.digest
    store.save("default", image, expected_revision=revision)
    output = tmp_path / "resumed.json"
    result = subprocess.run(
        [
            str(RUNTIME),
            "--resume",
            "--store",
            str(dbfile),
            "--clock",
            "unbounded",
            "--until-us",
            "20000",
            "--export",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert ArtifactCodec.decode(output.read_bytes(), with_profile=True)[1] == profile
    document = json.loads(ArtifactCodec.encode(initial, "json", profile=profile))
    document["runtime_profile"]["sensory_seed"] = 29
    with pytest.raises(ValueError, match="profile checksum"):
        ArtifactCodec.decode(json.dumps(document).encode())
