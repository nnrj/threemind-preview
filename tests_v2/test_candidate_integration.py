"""Candidate identity/state must survive real Runtime and Lab boundaries."""

from dataclasses import fields

import pytest

from threemind_core import Stimulus
from threemind_kernels.continuous import KERNEL_ID, ContinuousConfig
from threemind_kernels.definition import KernelDefinition
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.inheritance import birth
from threemind_runtime.store import SQLiteStore


def populated(backend="native"):
    engine = create_engine(kernel_id=KERNEL_ID, backend=backend)
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    engine.advance_to(103_379)
    return engine


@pytest.mark.parametrize("format", ["json", "tmind"])
@pytest.mark.parametrize("backend", ["reference", "native"])
def test_complete_artifact_roundtrip_and_definition_binding(format, backend):
    engine = populated(backend)
    image = engine.capture_state()
    assert image.to_dict()["operator_state"]["short_term"]
    encoded = ArtifactCodec.encode(image, format)
    restored = ArtifactCodec.decode(encoded)
    assert restored.digest == image.digest
    assert KernelDefinition.parse(restored.to_dict()["definition"]).digest == restored.to_dict()["definition_hash"]
    resumed = create_engine(state=restored, backend=backend)
    engine.advance_to(501_379)
    resumed.advance_to(501_379)
    assert resumed.capture_state().digest == engine.capture_state().digest


def test_device_checkpoint_and_structural_birth(tmp_path):
    engine = populated()
    image = engine.capture_state()
    store = SQLiteStore(tmp_path / "candidate.sqlite")
    assert store.save("candidate", image) == 1
    _, loaded = store.load("candidate")
    assert loaded.digest == image.digest
    newborn = birth(image)
    state = newborn.to_dict()
    assert state["operator_state"] == {"short_term": [], "fast": []}
    assert state["queue"] == [] and state["life"] == "waiting"
    assert state["dynamics"] == KERNEL_ID
    assert [e["weight"] for e in state["edges"]] == [e["weight"] for e in image.to_dict()["edges"]]
    assert create_engine(state=newborn).capture_state().digest == newborn.digest
    assert loaded.digest == image.digest


def test_candidate_catalogue_defaults_and_immutable_kernel_selection():
    from threemind_lab.configuration import catalogue, validate_configuration
    from threemind_lab.protocols import Arm, RunSpec, StudySpec

    catalog = catalogue()
    visible = [f for f in catalog["fields"] if not f.get("kernels") or KERNEL_ID in f["kernels"]]
    assert {f["path"][7:] for f in visible if f["path"].startswith("config.")} == {
        f.name for f in fields(ContinuousConfig)
    }
    assert catalog["kernel_defaults"][KERNEL_ID] == ContinuousConfig().to_dict()
    base = {"kernel_id": KERNEL_ID, "environment": "manual", "config": {"fast_gain": 0.2}}
    assert validate_configuration(base)["valid"]
    changed = base | {"kernel_id": "threemind.causal/9", "config": {}}
    assert not validate_configuration(changed, current=base)["valid"]
    study = StudySpec(
        name="Continuous operator ablation",
        base=RunSpec(kernel_id=KERNEL_ID, environment="ambient", clock="unbounded", duration_s=0.2),
        arms=[Arm(name="baseline"), Arm(name="short-term off", config_patch={"stp_enabled": False})],
    )
    assert study.base.kernel_id == KERNEL_ID


def test_temporal_probe_uses_selected_kernel_and_keeps_source():
    from threemind_runtime.sensory import TextSensorConfig
    from threemind_runtime.temporal_probe import TemporalProbeProtocol, calibrate_temporal

    image = populated().capture_state()
    original = image.digest
    protocol = TemporalProbeProtocol(cues=["甲"], intensities=[0.5], route="birth", learning_during_probe=False)
    result, raw = calibrate_temporal(image, seed=1, sensor_config=TextSensorConfig(), protocol=protocol)
    assert image.digest == original and raw
    assert result["rows"] and result["rows"][0]["classification"] != "not_observed"


def test_lab_candidate_run_checkpoint_export_import_and_fork(database):
    from test_api import client_for

    from threemind_lab.worker import Worker

    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Candidate integration"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        spec = {
            "kernel_id": KERNEL_ID,
            "environment": "replay",
            "clock": "unbounded",
            "duration_s": 0.31,
            "checkpoint_us": 100000,
            "replay": [{"time_us": "0", "channels": [[1, 0.8], [2, 0.7]]}],
        }
        response = client.post(f"{base}/runs", json={"name": "candidate", "spec": spec})
        assert response.status_code == 201, response.text
        run = response.json()
        worker = Worker(database)
        assert worker.once()
        saved = database.get_run(project, run["id"])
        assert saved["status"] == "completed", saved
        _, image = database.load_checkpoint(project, run["id"])
        assert image.to_dict()["dynamics"] == KERNEL_ID and image.to_dict()["operator_state"]["short_term"]
        exported = client.post(f"{base}/runs/{run['id']}/exports", json={"format": "tmind"})
        assert exported.status_code == 202, exported.text
        assert worker.once()
        job = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == exported.json()["id"])
        assert job["status"] == "done", job
        raw = client.get(f"{base}/artifacts/{job['result']['artifact_id']}").content
        assert ArtifactCodec.decode(raw).digest == image.digest
        imported = client.post(f"{base}/imports", files={"file": ("candidate.tmind", raw)}, data={"name": "imported"})
        assert imported.status_code == 201, imported.text
        assert imported.json()["spec"]["kernel_id"] == KERNEL_ID
        fork = client.post(f"{base}/runs/{run['id']}/forks", json={"name": "offspring", "inherit": True})
        assert fork.status_code == 201, fork.text
        child = database.load_checkpoint(project, fork.json()["id"])[1]
        assert child.to_dict()["operator_state"] == {"short_term": [], "fast": []}
