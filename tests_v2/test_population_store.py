import json

import pytest
from test_ecology_runtime import configuration

from threemind_runtime.cold_state import StateReference
from threemind_runtime.ecology_job import EcologyJob, parse_job
from threemind_runtime.population_store import PopulationStore


def test_standalone_population_mid_delivery_restore_and_all_evidence(tmp_path):
    job = EcologyJob(ecology=configuration())
    store = PopulationStore(tmp_path / "population.sqlite")
    events = []
    with job.open(record=events.append) as runtime:
        revision = store.save("example", job, runtime.checkpoint(), expected_revision=0, events=events)
        events.clear()
        runtime.advance_to(17000)
        revision = store.save("example", job, runtime.checkpoint(), expected_revision=revision, events=events)
        loaded_revision, saved_job, checkpoint = store.load("example")
        assert loaded_revision == revision
        assert checkpoint[0]["pending_end_us"] == 20000
        with saved_job.open(checkpoint=checkpoint) as restored:
            assert restored.checkpoint() == runtime.checkpoint()
            for end in (20000, 47000, 100000):
                runtime.advance_to(end)
                restored.advance_to(end)
                assert runtime.checkpoint() == restored.checkpoint()
        assert len(list(store.evidence("example", revision))) == 2
        _, _, original = store.load("example", revision=1)
        assert original[0]["time_us"] == 0 and len(original[1]) == 2


def test_local_population_rollback_cas_and_protocol_identity(tmp_path):
    job = EcologyJob(ecology=configuration())
    store = PopulationStore(tmp_path / "population.sqlite")
    with job.open() as runtime:
        store.save("example", job, runtime.checkpoint(), expected_revision=0)
        runtime.advance_to(20000)
        metadata, images = runtime.checkpoint()
        broken = dict(images)

        def failure():
            raise ValueError("second model read failed")

        broken["n1"] = StateReference(images["n1"].digest, failure)
        with pytest.raises(ValueError, match="second model"):
            store.save("example", job, (metadata, broken), expected_revision=1, events=[{"kind": "not committed"}])
        revision, _, saved = store.load("example")
        assert revision == 1 and saved[0]["time_us"] == 0
        with store.connect() as db:
            assert db.execute("SELECT count(*) FROM population_checkpoints").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM population_members").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM population_evidence").fetchone()[0] == 0
        store.save("example", job, (metadata, images), expected_revision=1)
        with pytest.raises(ValueError, match="writer"):
            store.save("example", job, (metadata, images), expected_revision=1)
        different = parse_job(job.model_dump_json())
        different.environment_seed += 1
        with pytest.raises(ValueError, match="frozen protocol"):
            store.save("example", different, (metadata, images), expected_revision=2)


def test_store_detects_corrupt_brain_and_protocol_duplicate_fields(tmp_path):
    job = EcologyJob(ecology=configuration())
    store = PopulationStore(tmp_path / "population.sqlite")
    with job.open() as runtime:
        store.save("example", job, runtime.checkpoint(), expected_revision=0)
    with store.connect() as db:
        row = db.execute("SELECT hash,ordinal,body FROM population_chunks LIMIT 1").fetchone()
        altered = bytearray(row[2])
        altered[-1] ^= 1
        db.execute("UPDATE population_chunks SET body=? WHERE hash=? AND ordinal=?", (altered, row[0], row[1]))
    _, saved_job, checkpoint = store.load("example")
    with pytest.raises(ValueError):
        saved_job.open(checkpoint=checkpoint)
    with pytest.raises(ValueError, match="duplicate"):
        parse_job('{"sensory_seed":1,"sensory_seed":2}')
    value = job.model_dump(mode="json")
    value["participant"]["actuator_feedback"] = "false"
    with pytest.raises(ValueError):
        parse_job(json.dumps(value))
