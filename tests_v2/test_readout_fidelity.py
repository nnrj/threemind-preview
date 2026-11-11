"""Observer neutrality and faithful storage; synthetic nodes are test fixtures."""

import copy
import csv
import io
from dataclasses import replace
from uuid import uuid4

import pytest
from test_api import client_for
from test_readouts import delivery, node, temporal

from threemind_core import Config, Engine, Stimulus
from threemind_lab.protocols import RunSpec
from threemind_lab.readouts import ReadoutHost, nodes_csv
from threemind_lab.worker import Worker
from threemind_runtime.bus import InputBus
from threemind_runtime.host import NativeEngine
from threemind_runtime.readout_config import StructuralReadoutConfig
from threemind_runtime.readouts import StructuralReader


@pytest.mark.parametrize("engine_class", [Engine, NativeEngine])
def test_envelope_labels_and_reader_options_cannot_change_core_dynamics(engine_class):
    trajectories, observations, provenance = [], [], []
    for variant in range(3):
        engine = engine_class(Config(step_us=10000))
        bus = InputBus(engine)
        records = []
        spec = RunSpec(
            environment="manual",
            clock="unbounded",
            structural_readout=StructuralReadoutConfig(
                enabled=variant != 2,
                max_nodes=3 if variant == 0 else 7,
                activation_threshold=0.055 if variant == 0 else 0.99,
                display_limit=1 if variant == 0 else 20,
            ),
            temporal_readout=temporal(enabled=variant != 2, candidate_scope="associative-only"),
        )
        host = ReadoutHost(spec, str(uuid4()), 0, record=records.append)
        # Connections arise through the same stimulation history in every
        # variant. No semantic paths or edges are inserted by this test.
        for index, at in enumerate((0, 75123, 200456, 310789)):
            channels = ((1, 0.8), (2, 0.6), (3, 0.4)) if index < 3 else ((1, 0.8),)
            metadata = delivery(
                id="shared-observer-carrier" if variant == 1 else f"observer-{variant}-{index}",
                at=at,
                index=index if variant == 1 else 0,
                count=4 if variant == 1 else 1,
            )
            metadata["labels"] = {"1": ["honey" if variant == 0 else "unrelated annotation"], "2": [str(variant)]}
            bus.schedule(Stimulus(at, channels), metadata)
        provenance.append(bus.capture())
        hashes, frames = [], []
        for at in (0, 50001, 75123, 150371, 200456, 310789, 400000):
            engine.advance_to(
                at, lambda event, host=host, bus=bus: host.delivered(bus.observe(event)), inputs_only=True
            )
            before = engine.capture_state().digest
            host.observe(engine, force=True)
            assert engine.capture_state().digest == before
            hashes.append(before)
            frames.append(engine.observation_nodes())
        assert engine.capture_state().to_dict()["edges"]
        trajectories.append(hashes)
        observations.append(frames)
        if variant != 2:
            snapshots = [r["payload"] for r in records if r["kind"] == "structural_readout"]
            assert [r["raw_nodes"] for r in snapshots] == frames
        else:
            assert not records
    assert provenance[0] != provenance[1]
    assert trajectories[0] == trajectories[1] == trajectories[2]
    assert observations[0] == observations[1] == observations[2]


def test_unfiltered_snapshot_keeps_weak_untraced_and_non_candidate_nodes():
    nodes = [node(i, 0.8) for i in range(1, 9)] + [
        dict(node(9, 0.001), direct=0, associative=0),
        dict(node(10, 0.0), direct=0, associative=0),
        dict(node(11, 0.5), direct=0, associative=0),
    ]
    original = copy.deepcopy(nodes)
    cfg = StructuralReadoutConfig(max_nodes=3)
    for threshold in (0.055, 0.99):
        record = StructuralReader(replace(cfg, activation_threshold=threshold)).consume(
            123456,
            7,
            nodes,
            [],
            annotations={"9": ["externally considered unrelated"]},
        )
        assert record["raw_nodes"] == original and record["source_node_count"] == len(nodes)
        assert record["raw_observation"]["complete"] and record["raw_observation"]["node_count"] == len(nodes)
        assert record["raw_observation"]["causal_attribution"] == "not-established"
        assert record["structure"] is None
        assert len(record["activity_nodes"]) == (8 if threshold == 0.055 else 0)
        rows = list(csv.DictReader(io.StringIO(nodes_csv(record).decode("utf-8-sig"))))
        assert {int(row["id"]) for row in rows} == {n["id"] for n in original}
        assert all(row["observation_scope"] == "all-source-nodes" for row in rows)
        record["raw_nodes"][-1]["activation"] = -1
        assert nodes == original
    empty = StructuralReader(cfg).consume(0, 0, [], [])
    assert empty["raw_nodes"] == [] and empty["raw_observation"]["complete"]
    assert StructuralReader(replace(cfg, read_touched_activity=False)).consume(0, 0, nodes, []) is None
    partial = StructuralReader(replace(cfg, read_touched_activity=False)).consume(
        0,
        0,
        nodes,
        [
            {"source": 1, "target": 2, "weight": 0.5, "stability": 0.1},
            {"source": 2, "target": 3, "weight": 0.5, "stability": 0.1},
        ],
    )
    assert partial["structure"] and partial["raw_nodes"] == []
    assert partial["raw_observation"] == {
        "schema": "threemind.raw-node-observation/1",
        "complete": False,
        "node_count": 0,
        "scope": "recording-disabled",
        "causal_attribution": "not-established",
    }


def test_default_raw_paging_exports_and_historical_missingness(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Raw observation fixtures"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        run = client.post(f"{root}/runs", json={"name": "Fidelity", "spec": {"environment": "manual"}}).json()["id"]
        url = f"{root}/runs/{run}"
        nodes = [node(1, 0.7), dict(node(2, 0.001), direct=0, associative=0), node(3, 0.0)]
        raw = StructuralReader(StructuralReadoutConfig()).consume(0, 0, nodes, [])
        historical = {k: copy.deepcopy(v) for k, v in raw.items() if k not in ("raw_nodes", "raw_observation")}
        disabled = dict(
            historical,
            raw_nodes=[],
            raw_observation={"complete": False, "scope": "recording-disabled", "node_count": 0},
        )
        image = Engine().capture_state()
        database.save_checkpoint(
            project,
            run,
            image,
            expected_revision=0,
            status="paused",
            events=[
                {"key": key, "kind": "structural_readout", "time_us": "0", "payload": value}
                for key, value in (("raw", raw), ("historical", historical), ("disabled", disabled))
            ],
        )
        before = database.load_checkpoint(project, run)[1].digest
        history = client.get(f"{url}/readouts").json()["rows"]
        assert len(history) == 3
        from threemind_lab.conversation_api import page

        feed = page(database, project, run, environment=True, triggering=True, background=True, kind=None)
        summaries = {r["event_id"]: r["readout"] for r in feed["rows"]}
        assert all("raw_nodes" not in r["payload"] and "activity_nodes" not in r["payload"] for r in history)
        for summary in history:
            record_url = f"{url}/readouts/{summary['id']}"
            exported = client.get(f"{record_url}/export").json()["payload"]
            complete = exported.get("raw_observation", {}).get("complete", False)
            message = summaries[str(summary["id"])]
            assert message["node_count"] == (3 if complete else 1)
            assert message["node_scope"] == ("all-source-nodes" if complete else "derived-nodes-only")
            detail = client.get(record_url, params={"limit": 1, "order": "id"}).json()
            assert detail["section"] == "raw_nodes" and detail["section_available"] is complete
            assert "raw_nodes" not in detail["record"]["payload"]
            csvrows = list(
                csv.DictReader(io.StringIO(client.get(f"{record_url}/export?format=csv").text.lstrip("\ufeff")))
            )
            if complete:
                assert detail["total"] == 3 and detail["more"]
                assert detail["rows"][0]["item"] == nodes[0]
                last = client.get(record_url, params={"offset": 1, "limit": 2, "order": "id"}).json()
                assert [r["item"] for r in last["rows"]] == nodes[1:] and not last["more"]
                assert len(csvrows) == 3 and exported["raw_nodes"] == nodes
                derived = client.get(record_url, params={"section": "nodes"}).json()
                assert len(derived["rows"]) == 1
            else:
                assert detail["rows"] == [] and len(csvrows) == 1
                assert csvrows[0]["observation_scope"] == "derived-nodes-only"
                assert len(client.get(record_url, params={"section": "nodes"}).json()["rows"]) == 1
        assert database.load_checkpoint(project, run)[1].digest == before == image.digest


def test_complete_recording_requires_capable_worker_and_disabled_recording_does_not(database):
    from psycopg.types.json import Jsonb

    from threemind_lab.database import LOCAL_USER

    worker = Worker(database)
    assert not worker.once()
    old = copy.deepcopy(worker.capabilities)
    del old["features"]["worker.raw_readout_v1"]
    database.announce_worker("legacy-filtered-reader", old)
    project = database.create_project({"id": LOCAL_USER}, "Readout capability")["id"]
    spec = RunSpec(environment="manual", clock="unbounded", duration_s=0.01).model_dump(mode="json")
    run = database.create_run(project, "Complete snapshot", spec)
    job = database.enqueue(project, "run", run_id=run["id"])
    assert "worker.raw_readout_v1" in job["required_features"]
    assert database.claim("legacy-filtered-reader", capabilities=old) is None
    with database.tx(project) as db:
        for kind, identity, params in (("research_plan", run["id"], {}), ("study", None, {"protocol": {"base": spec}})):
            required = db.execute(
                "SELECT required_job_features(%s,%s,%s) AS features", (kind, identity, Jsonb(params))
            ).fetchone()["features"]
            assert "worker.raw_readout_v1" in required
        off = copy.deepcopy(spec)
        off["structural_readout"]["read_touched_activity"] = False
        required = db.execute(
            "SELECT required_job_features('study',NULL,%s) AS features", (Jsonb({"protocol": {"base": off}}),)
        ).fetchone()["features"]
        assert "worker.raw_readout_v1" not in required
    assert worker.once() and database.get_run(project, run["id"])["status"] == "completed"


def test_upgrade_refreshes_waiting_jobs_in_each_project_without_touching_models(database):
    import psycopg

    from threemind_lab.database import LOCAL_USER, migrate

    created = []
    for index in range(2):
        project = database.create_project({"id": LOCAL_USER}, f"Upgrade project {index}")["id"]
        run = database.create_run(project, "Waiting legacy protocol", {"environment": "manual"})
        job = database.enqueue(project, "run", run_id=run["id"])
        created.append((project, run["id"], job["id"]))
    with psycopg.connect(database.test_migration_url) as db:
        assert db.info.dbname.startswith("tm2_test_db_")
        from migration_helpers import remove_observer_schema

        remove_observer_schema(db)
        db.execute("DROP TRIGGER device_wiring_immutable ON tm2.device_bindings")
        db.execute("DROP FUNCTION tm2.preserve_device_wiring()")
        db.execute("ALTER TABLE tm2.device_bindings DROP COLUMN wiring_id")
        db.execute("ALTER TABLE tm2.report_source_requests DROP COLUMN ecology_id, DROP COLUMN ecology_checkpoint_id")
        db.execute("DROP FUNCTION tm2.required_job_features_v39(text,uuid,jsonb)")
        db.execute(
            "DROP TABLE tm2.ecology_events,tm2.ecology_checkpoint_members,tm2.ecology_members,tm2.ecology_checkpoints,tm2.ecology_campaigns"
        )
        db.execute("DROP FUNCTION tm2.preserve_ecology_record(),tm2.required_job_features_v38(text,uuid,jsonb)")
        db.execute("SET search_path TO tm2,pg_catalog")
        db.execute("DROP TABLE tm2.world_versions,tm2.world_documents")
        db.execute("DROP FUNCTION tm2.required_job_features_v37(text,uuid,jsonb)")
        db.execute("DROP FUNCTION tm2.preserve_world_version(),tm2.required_job_features_v36(text,uuid,jsonb)")
        db.execute("ALTER TABLE report_source_requests DROP COLUMN evolution_id")
        db.execute("ALTER TABLE report_source_requests DROP CONSTRAINT report_source_requests_kind_check")
        db.execute(
            "ALTER TABLE report_source_requests ADD CHECK(kind IN ('trajectory','nodes','edges','analysis','events'))"
        )
        db.execute(
            "DROP TABLE tm2.evolution_events,tm2.evolution_selections,tm2.evolution_members,tm2.evolution_campaigns"
        )
        db.execute("DROP FUNCTION tm2.required_job_features_v34(text,uuid,jsonb)")
        db.execute("DROP FUNCTION tm2.required_job_features_v35(text,uuid,jsonb)")
        db.execute("DROP FUNCTION tm2.preserve_evolution_record(),tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v33(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version>=34")
        db.execute("DROP FUNCTION tm2.required_job_features(text,uuid,jsonb)")
        db.execute("ALTER FUNCTION tm2.required_job_features_v32(text,uuid,jsonb) RENAME TO required_job_features")
        db.execute("DELETE FROM tm2.schema_version WHERE version=33")
        for project, _run, job in created:
            db.execute("SELECT set_config('tm.project_id',%s,true)", (str(project),))
            db.execute("UPDATE tm2.jobs SET params=params WHERE id=%s", (job,))
    migrate(database.test_migration_url)
    for project, run, job in created:
        with database.tx(project) as db:
            row = db.execute("SELECT required_features FROM jobs WHERE id=%s", (job,)).fetchone()
            assert "worker.raw_readout_v1" in row["required_features"]
        current = database.get_run(project, run)
        assert current["revision"] == 0 and current["spec"] == {"environment": "manual"}
