from copy import deepcopy
from uuid import uuid4

from fastapi.testclient import TestClient
from test_ecology_store import setup

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.ecology_store import PopulationWriter
from threemind_lab.ecology_worker import open_population
from threemind_lab.protocols import Phase


def test_catalogue_strict_defaults_immutable_protocol_scope_and_group_controls(database):
    project, row, worker = setup(database)
    root = f"/api/v2/projects/{project}/ecologies"
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        catalogue = client.get(root + "/catalogue").json()
        assert catalogue["defaults"]["ecology"]["senses"]["enabled"]
        value = catalogue["defaults"]
        value["ecology"]["senses"]["damage_enabled"] = False
        checked = client.post(root + "/validate", json=value)
        assert checked.status_code == 200, checked.text
        assert checked.json()["protocol"]["ecology"]["senses"]["reserve_enabled"]
        broken = deepcopy(value)
        broken["ecology"]["senses"]["enabled"] = "false"
        assert client.post(root + "/validate", json=broken).status_code == 422
        assert client.get(root).json()["rows"][0]["id"] == str(row["id"])
        assert (
            client.post(root + f"/{row['id']}/controls", json={"action": "pause", "expected_revision": 0}).status_code
            == 422
        )
        paused = client.post(
            root + f"/{row['id']}/controls", json={"action": "pause", "expected_revision": row["revision"]}
        ).json()
        assert paused["status"] == "paused"
        assert not worker.once()
        resumed = client.post(
            root + f"/{row['id']}/controls", json={"action": "resume", "expected_revision": paused["revision"]}
        )
        assert resumed.status_code == 200, resumed.text
        assert worker.once()
        detail = client.get(root + f"/{row['id']}").json()
        assert detail["campaign"]["status"] == "completed"
        cp = detail["checkpoint"]
        assert len(detail["members"]) == 6 and "accounts" not in cp["ledger"] and "pools" not in cp["ledger"]
        assert cp["ledger"]["pool_count"] == 1
        pools = client.get(root + f"/{row['id']}/resource-pools", params={"checkpoint_id": cp["id"]}).json()
        assert pools["rows"][0]["habitat"] == "shared" and not pools["more"]
        assert client.get(root + f"/{row['id']}/events").json()["rows"]
        selected_events = client.get(root + f"/{row['id']}/events?individual=n0").json()["rows"]
        assert any(e["kind"] == "resource_transfer" and "n0" in e["payload"]["amounts"] for e in selected_events)
        assert any(e["kind"] == "individual_born" and e["payload"]["parent"] == "n0" for e in selected_events)
        for event in selected_events:
            assert (
                event["individual"] == "n0"
                or event["payload"].get("parent") == "n0"
                or "n0" in event["payload"].get("amounts", {})
            )
        trajectory = client.get(root + f"/{row['id']}/trajectory").json()
        assert trajectory["rows"][-1]["metrics"]["births"] == 4
        exported = client.post(
            root + f"/{row['id']}/exports",
            json={"operation_id": str(uuid4()), "checkpoint_id": cp["id"], "include_models": True},
        )
        assert exported.status_code == 202, exported.text
        assert worker.once()
        export_job = client.get(root + f"/{row['id']}/exports").json()[0]
        assert export_job["status"] == "done", export_job["error"]
        import io
        import json
        import zipfile

        from threemind_runtime import ArtifactCodec

        artifact = client.get(f"/api/v2/projects/{project}/artifacts/{export_job['result']['artifact_id']}")
        with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
            assert {
                "population.csv",
                "population.svg",
                "population.png",
                "individuals.jsonl",
                "events.jsonl",
                "population-state.json",
            } <= set(archive.namelist())
            assert len([name for name in archive.namelist() if name.startswith("models/")]) == 6
            meta = json.loads(archive.read("manifest.json"))
            assert meta["checkpoint_id"] == cp["id"]
            model = ArtifactCodec.decode(archive.read("models/n0.tmind"))
            assert model.digest == next(m["state_hash"] for m in detail["members"] if m["individual"] == "n0")
        other = client.post("/api/v2/projects", json={"name": "Separate project"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/ecologies/{row['id']}").status_code == 404
        assert client.get(root + f"/{row['id']}?checkpoint_id={uuid4()}").status_code == 404
        subject = detail["members"][0]["run_id"]
        assert (
            client.post(
                f"/api/v2/projects/{project}/runs/{subject}/forks", json={"name": "Cannot split a physical world"}
            ).status_code
            == 409
        )
        fork = client.post(
            f"/api/v2/projects/{project}/runs/{subject}/forks",
            json={"name": "Independent birth", "inherit": True, "paused": True},
        )
        assert fork.status_code == 201, fork.text


def test_lab_recovery_and_readout_phase_hooks_keep_actual_input_evidence(database):
    project, row, worker = setup(
        database,
        phases=[
            Phase(name="input", duration_s=0.04),
            Phase(name="closed", duration_s=0.06, input_enabled=False, close_sources=True),
        ],
        structural_readout={"enabled": True},
        temporal_readout={"enabled": True},
    )
    writer = PopulationWriter(database, project, row)
    with open_population(worker, row, writer) as uninterrupted:
        writer.commit(uninterrupted)
        uninterrupted.advance_to(17000)
        writer.commit(uninterrupted)
        restored_writer = PopulationWriter(database, project, writer.row)
        with open_population(worker, writer.row, restored_writer) as restored:
            for end in (20000, 40000, 60000, 80000, 100000):
                uninterrupted.advance_to(end)
                restored.advance_to(end)
                assert uninterrupted.checkpoint() == restored.checkpoint()
                writer.commit(uninterrupted)
        assert not uninterrupted.participants["n0"].source_enabled
        with database.tx(project) as db:
            phases = db.execute("SELECT payload FROM events WHERE kind='phase'").fetchall()
            assert any(p["payload"]["close_sources"] for p in phases)
            assert db.execute("SELECT 1 FROM events WHERE kind='structural_readout'").fetchone()


def test_optional_external_inputs_and_lifecycle_lock_share_existing_bus(database):
    project, row, worker = setup(database, external_inputs=True)
    writer = PopulationWriter(database, project, row)
    with open_population(worker, row, writer) as runtime:
        writer.commit(runtime)
        with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
            subject = runtime.participants["n0"].run_id
            root = f"/api/v2/projects/{project}/runs/{subject}"
            for kind in ("pause", "cancel", "resume", "close_inputs", "intervention"):
                assert client.post(root + "/commands", json={"kind": kind}).status_code == 409
            result = client.post(
                root + "/inputs",
                json={"adapter_id": "text-sensor", "payload": {"text": "ecological probe"}, "request_id": str(uuid4())},
            )
            assert result.status_code == 202, result.text
            assert client.post(root + "/commands", json={"kind": "checkpoint"}).status_code == 200
            runtime.advance_to(20000)
            writer.commit(runtime)
            history = client.get(root + "/inputs").json()
            assert any(r["adapter_id"] == "text-sensor" for r in history["rows"])
        assert runtime.participants["n0"].last_command > 0


def test_quiescence_deadline_and_phase_closure_precede_same_boundary_reproduction(database):
    from threemind_core import Stimulus

    project, row, worker = setup(
        database,
        config={"activation_tau": 0.001, "quiescence_death_us": 10000},
        phases=[
            Phase(name="initial", duration_s=0.01),
            Phase(name="silent", duration_s=0.01, input_enabled=False),
            Phase(name="closed", duration_s=0.08, input_enabled=False, close_sources=True),
        ],
    )
    writer = PopulationWriter(database, project, row)
    with open_population(worker, row, writer) as runtime:
        writer.commit(runtime)
        # Waiting brains have never been activated and are not dead. Give each
        # founder a real initial stimulus, then allow its activity to decay.
        for agent in runtime.participants.values():
            agent.inputs.automatic("initial-probe", "manual-anonymous", Stimulus(1000, ((101, 1.0),)))
        runtime.advance_to(20000)
        assert len(runtime.participants) == 2
        assert all(
            agent.engine.life == "dead" and agent.engine.time_us == 20000 for agent in runtime.participants.values()
        )
        assert all(account.alive for account in runtime.ledger.accounts.values())
        writer.commit(runtime)
        with database.tx(project) as db:
            from threemind_lab.ecology_store import campaign

            latest = campaign(db, row["id"])
            assert latest["control_revision"] == 1 and latest["revision"] > 1
        from threemind_lab.database import LOCAL_USER
        from threemind_lab.ecology_store import control

        # Ordinary observation commits do not make a previously seen pause stale.
        paused = control(database, project, row["id"], LOCAL_USER, "pause", latest["control_revision"])
        assert paused["status"] == "paused"
