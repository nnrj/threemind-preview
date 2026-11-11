from dataclasses import fields

import pytest

from threemind_core import Stimulus
from threemind_kernels.definition import KernelDefinition
from threemind_kernels.lif import KERNEL_ID, LifConfig
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.inheritance import birth


@pytest.mark.parametrize("backend", ["reference", "native"])
@pytest.mark.parametrize("format", ["json", "tmind"])
def test_lif_model_birth_and_definition(backend, format):
    e = create_engine({"input_gain_na": 5.0}, kernel_id=KERNEL_ID, backend=backend)
    e.inject(Stimulus(0, ((1, 0.8), (2, 0.6))))
    e.advance_to(3317)
    image = e.capture_state()
    restored = ArtifactCodec.decode(ArtifactCodec.encode(image, format))
    assert image.digest == restored.digest
    assert KernelDefinition.parse(restored.to_dict()["definition"]).digest == restored.to_dict()["definition_hash"]
    fresh = birth(image)
    assert fresh.to_dict()["queue"] == fresh.to_dict()["short_term"] == []
    assert [s["weight"] for s in fresh.to_dict()["synapses"]] == [s["weight"] for s in image.to_dict()["synapses"]]
    offspring = create_engine(state=fresh, backend=backend)
    assert offspring.life == "waiting" and offspring.metrics()["spikes"] == 0
    assert offspring.capture_state().digest == fresh.digest
    assert e.capture_state().digest == image.digest


def test_catalogue_contains_only_real_lif_fields_and_immutable_checks():
    from threemind_lab.configuration import catalogue, validate_configuration
    from threemind_lab.protocols import Arm, RunSpec, StudySpec

    cat = catalogue()
    visible = [f for f in cat["fields"] if not f.get("kernels") or KERNEL_ID in f["kernels"]]
    keys = [f["path"][7:] for f in visible if f["path"].startswith("config.")]
    assert set(keys) == {f.name for f in fields(LifConfig)} and len(keys) == len(set(keys))
    original = {"kernel_id": KERNEL_ID, "environment": "manual", "config": {}}
    assert validate_configuration(original)["valid"]
    assert not validate_configuration(original | {"config": {"threshold_mv": -49.0}}, current=original)["valid"]
    assert not validate_configuration(original | {"energy_supply": {"enabled": True}})["valid"]
    with pytest.raises(ValueError):
        StudySpec(
            name="wrong continuation",
            base=RunSpec(**original, duration_s=1),
            arms=[Arm(name="a"), Arm(name="b", config_patch={"rest_mv": -66})],
        )


def test_readout_marks_physical_quantity_and_is_nonintrusive():
    from threemind_runtime.readout_session import ReadoutSession

    e = create_engine({"input_gain_na": 5.0}, kernel_id=KERNEL_ID)
    rows = []
    session = ReadoutSession(e, record=rows.append)
    session.schedule([{"stimulus": Stimulus(0, ((1, 0.8), (2, 0.6)))}])
    session.advance_to(250000)
    assert rows
    assert all(r["payload"]["observation_quantity"] == "normalized-depolarization" for r in rows)
    before = e.capture_state().digest
    session.host.observe(e, force=True)
    assert e.capture_state().digest == before


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_spike_recording_can_be_disabled_without_changing_physics(backend):
    from threemind_runtime.event_observation import advance_observed

    final = []
    for enabled in (True, False):
        engine = create_engine({"input_gain_na": 5.0}, kernel_id=KERNEL_ID, backend=backend)
        engine.inject(Stimulus(0, ((1, 0.8), (2, 0.6))))
        rows = []
        advance_observed(engine, 10000, rows.append, record_spikes=enabled)
        assert any(r["kind"] == "spikes" for r in rows) == enabled
        assert all(r["kind"] in ("stimulus", "spikes") for r in rows)
        final.append(engine.capture_state().digest)
    assert final[0] == final[1]


def test_lab_lif_checkpoint_export_import_birth_and_physical_readout(database):
    from test_api import client_for

    from threemind_lab.worker import Worker

    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "LIF integration"}).json()["id"]
        base = f"/api/v2/projects/{p}"
        spec = {
            "kernel_id": KERNEL_ID,
            "config": {"input_gain_na": 5.0},
            "environment": "replay",
            "clock": "unbounded",
            "duration_s": 0.21,
            "checkpoint_us": 100000,
            "replay": [{"time_us": "0", "channels": [[1, 0.8], [2, 0.7]]}],
        }
        response = client.post(f"{base}/runs", json={"name": "spiking", "spec": spec})
        assert response.status_code == 201, response.text
        run = response.json()
        worker = Worker(database)
        assert worker.once()
        saved = database.get_run(p, run["id"])
        assert saved["status"] == "completed", saved
        with database.tx(p) as db:
            spikes = db.execute("SELECT payload FROM events WHERE run_id=%s AND kind='spikes'", (run["id"],)).fetchall()
        assert spikes and all(row["payload"]["nodes"] for row in spikes)
        page = client.get(f"{base}/runs/{run['id']}/spikes?limit=1").json()
        assert page["items"][0]["payload"]["nodes"] and page["recording_enabled"]
        _, image = database.load_checkpoint(p, run["id"])
        assert image.to_dict()["dynamics"] == KERNEL_ID
        raw = client.get(f"{base}/runs/{run['id']}/physical-state?limit=1").json()
        assert raw["supported"] and raw["nodes"][0]["spikes"] > 0 and raw["next_after_id"]
        assert client.get(f"{base}/runs/{run['id']}/spatial").json()["supported"] is False
        exported = client.post(f"{base}/runs/{run['id']}/exports", json={"format": "tmind"})
        assert exported.status_code == 202 and worker.once()
        job = next(j for j in client.get(f"{base}/jobs").json() if j["id"] == exported.json()["id"])
        assert job["status"] == "done", job
        data = client.get(f"{base}/artifacts/{job['result']['artifact_id']}").content
        assert ArtifactCodec.decode(data).digest == image.digest
        imported = client.post(f"{base}/imports", files={"file": ("lif.tmind", data)}, data={"name": "imported"})
        assert imported.status_code == 201, imported.text
        assert imported.json()["spec"]["kernel_id"] == KERNEL_ID
        fork = client.post(f"{base}/runs/{run['id']}/forks", json={"name": "offspring", "inherit": True})
        assert fork.status_code == 201, fork.text
        child = database.load_checkpoint(p, fork.json()["id"])[1]
        assert create_engine(state=child).metrics()["spikes"] == 0
