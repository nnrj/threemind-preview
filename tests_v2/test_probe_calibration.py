import io
import json
import zipfile
from dataclasses import replace
from uuid import uuid4

import pytest

from threemind_core import Config
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.bus import InputBus
from threemind_runtime.calibration import CalibrationProtocol, calibrate, template
from threemind_runtime.sensory import TextSensor, TextSensorConfig


def trained(backend="native"):
    sensor = TextSensor(41301, TextSensorConfig(encoding="literal-character"))
    engine = create_engine(Config(), backend=backend)
    bus = InputBus(engine)
    for i in range(12):
        for j, text in enumerate(["甲是松子", "乙是铃铛"]):
            at = (i * 2 + j) * 800000
            for frame in sensor.frames(text):
                bus.schedule(replace(frame["stimulus"], time_us=at), {"source": "manual-cli-text"})
            engine.advance_to(at + 800000, bus.observe, inputs_only=True)
    return engine.capture_state(), sensor.config


@pytest.mark.parametrize("backend", ["native", "reference"])
def test_complete_isolated_trace_and_observer_neutrality(backend):
    image, sensor = trained(backend)
    original = image.digest
    protocol = CalibrationProtocol(intensities=[1.0])
    result, raw = calibrate(image, seed=41301, sensor_config=sensor, protocol=protocol, backend=backend)
    assert result["source_unchanged"] and image.digest == original
    row = result["rows"][1]
    assert row["transport"]["sent"] > 0 and row["delivered_signal_amount"] > 0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert json.loads(z.read("result.json")) == json.loads(json.dumps(result))
        assert ArtifactCodec.decode(z.read("source.tmind")).digest == original
        trace = json.loads(z.read("probes/1/trace.json"))
        final = ArtifactCodec.decode(z.read("probes/1/final.tmind"))
        assert len(trace["all_node_activations"]) == 51
        assert any(v == 0 for _, nodes in trace["all_node_activations"] for _, v in nodes)
    from threemind_runtime.inheritance import birth

    engine = create_engine(state=birth(image), backend=backend)
    engine.reconfigure(Config(**(engine.config.to_dict() | {"plasticity": False})))
    bus = InputBus(engine)
    for frame in TextSensor(41301, sensor).frames("甲"):
        bus.schedule(frame["stimulus"], {"source": "manual-cli-text"})
    engine.advance_to(protocol.window_us, bus.observe, inputs_only=True)
    assert engine.capture_state().digest == final.digest


@pytest.mark.parametrize("sensor", [TextSensorConfig(gain=0), TextSensorConfig(enabled=False)])
def test_unmeasurable_is_not_zero(sensor):
    result, _ = calibrate(
        create_engine(Config()).capture_state(), seed=1, sensor_config=sensor, protocol=CalibrationProtocol(intensities=[0.0])
    )
    assert all(not c["scorable"] for c in result["mapping"]["coverage"].values())
    assert all(v is None for r in result["rows"] for v in r["endpoint"].values())


def test_all_frames_and_invalid_sampling_budget():
    sensor = TextSensor(1, TextSensorConfig(encoding="literal-character", frame_characters=1))
    assert len(template(sensor, "甲乙丙")) == 3
    assert sum(template(sensor, "甲甲").values()) == 1.44
    with pytest.raises(ValueError):
        CalibrationProtocol(sample_us=30000)
    with pytest.raises(ValueError):
        CalibrationProtocol(intensities=[float("nan")])


def test_lab_frozen_source_idempotency_and_readonly_audit(database):
    from test_api import client_for

    from threemind_lab import storage_audit
    from threemind_lab.database import LOCAL_USER
    from threemind_lab.protocols import RunSpec
    from threemind_lab.worker import Worker

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Calibration test"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        image, sensor = trained()
        spec = RunSpec(environment="manual", text_sensor=sensor, seed=41301)
        run = database.create_run(project, "Fixed parent", spec.model_dump())
        cp = database.save_checkpoint(
            project, run["id"], image, expected_revision=0, status="completed", context={"protocol": spec.model_dump()}
        )
        url = f"{base}/runs/{run['id']}/calibrations"
        body = {"operation_id": str(uuid4()), "protocol": {"intensities": [1.0]}}
        response = client.post(url, json=body)
        assert response.status_code == 202, response.text
        ident = response.json()["id"]
        assert client.post(url, json=body).json()["id"] == ident
        assert client.post(url, json=body | {"protocol": {"intensities": [2.0]}}).status_code == 409
        assert Worker(database).once()
        job = client.get(f"{base}/calibrations/{ident}").json()
        assert job["status"] == "done", job.get("error")
        measured = client.get(f"{base}/calibrations/{ident}/result").json()
        assert measured["source_hash"] == image.digest and measured["source_unchanged"]
        assert str(cp["id"]) == str(job["checkpoint_id"])
        assert database.load_checkpoint(project, run["id"])[1].digest == image.digest
        empty = database.create_run(project, "Empty", {})
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='cancelled' WHERE id=%s", (empty["id"],))
        result = storage_audit.scan(database, project, LOCAL_USER)
        rows = {str(r["id"]): r for r in result["rows"]}
        assert rows[str(run["id"])]["classification"] == "keep"
        assert rows[str(empty["id"])]["classification"] == "candidate"
        assert result["read_only"] and all(not r["deletion_authorized"] for r in result["rows"])
        import psycopg

        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction), database.tx(project, read_only=True) as db:
            db.execute("UPDATE runs SET name='must not happen' WHERE id=%s", (empty["id"],))
