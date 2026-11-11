from copy import deepcopy
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.configuration import validate_configuration
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime.world_schema import CameraSensor, default_world


def test_world_library_revisions_and_real_run_evidence_are_project_scoped(database):
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "World engineering acceptance"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        spec = default_world().model_dump(mode="json")
        result = client.post(base + "/worlds/validate", json={"protocol": spec})
        assert result.status_code == 200, result.text
        assert result.json()["model"]["motors"] == 2 and result.json()["layout"]["delivery_time_us"] is None
        request = {"operation_id": str(uuid4()), "protocol": spec}
        first = client.post(base + "/worlds", json=request)
        assert first.status_code == 201, first.text
        first = first.json()
        identity = first["document_id"]
        assert client.post(base + "/worlds", json=request).json()["revision"] == 1
        spec2 = deepcopy(spec)
        spec2["label"] = "Only observer label changed"
        second = client.post(
            base + "/worlds",
            json={"operation_id": str(uuid4()), "document_id": identity, "expected_revision": 1, "protocol": spec2},
        ).json()
        assert second["revision"] == 2 and second["physical_hash"] == first["physical_hash"]
        assert second["protocol_hash"] != first["protocol_hash"]
        assert client.post(base + "/worlds", json=request).json()["revision"] == 1
        assert client.post(base + "/worlds", json=request | {"protocol": spec2}).status_code == 409
        assert client.get(base + f"/worlds/{identity}/export?revision=1").json() == spec
        assert len(client.get(base + f"/worlds/{identity}/revisions").json()["rows"]) == 2
        run_spec = RunSpec(environment="world", world_protocol=spec, clock="unbounded", duration_s=0.087).model_dump(
            mode="json"
        )
        created = client.post(base + "/runs", json={"name": "Declared world subject", "spec": run_spec})
        assert created.status_code == 201, created.text
        run = created.json()
        worker = Worker(database, name="world-engineering")
        worker.once()  # Runs without a browser or render observer.
        final = database.get_run(project, run["id"])
        assert final["status"] == "completed"
        cp, image = database.load_checkpoint(project, run["id"])
        assert len(image.to_dict()["nodes"]) > 0
        observed = client.get(base + f"/runs/{run['id']}/world/observation").json()
        assert observed["id"] == str(cp["id"])
        assert observed["time_us"] == "87000"
        assert observed["observation"]["physical_time_us"] == "100000"
        assert observed["world_hash"] == first["protocol_hash"]
        assert client.get(base + f"/runs/{run['id']}/world/protocol").json()["protocol"] == spec
        carriers = client.get(base + f"/runs/{run['id']}/body-tools").json()
        assert carriers["has_world"] and len(carriers["rows"]) == 5
        assert all(row["configuration"]["world_hash"] == first["protocol_hash"] for row in carriers["rows"])
        assert any(row["status"] == "scheduled" for row in carriers["rows"])
        before = image.digest
        for _ in range(3):
            client.get(base + f"/runs/{run['id']}/world/observation")
        assert database.load_checkpoint(project, run["id"])[1].digest == before
        assert not validate_configuration(run_spec | {"world_protocol": spec2}, current=run_spec)["valid"]
        other = client.post("/api/v2/projects", json={"name": "Another project"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/worlds/{identity}").status_code == 404
        assert client.get(f"/api/v2/projects/{other}/runs/{run['id']}/world/observation").status_code == 404
        with database.tx(project) as db, pytest.raises(psycopg.Error, match="immutable"):
            db.execute("DELETE FROM world_versions WHERE document_id=%s", (identity,))


def test_world_jobs_require_both_world_and_rgb_worker_capabilities(database):
    from threemind_lab.database import LOCAL_USER

    project = database.create_project({"id": LOCAL_USER}, "World capability isolation")["id"]
    spec = default_world()
    spec.sensors.append(CameraSensor(id="eye", port=10, body_id="body", position=(0.0, 0.0, 1.0)))
    run = database.create_run(
        project,
        "Headless RGB subject",
        RunSpec(environment="world", world_protocol=spec, duration_s=0.04, clock="unbounded").model_dump(mode="json"),
    )
    job = database.enqueue(project, "run", run_id=run["id"])
    with database.tx(project) as db:
        required = db.execute("SELECT required_features FROM jobs WHERE id=%s", (job["id"],)).fetchone()[
            "required_features"
        ]
    assert {"worker.world_v1", "worker.world_rgb_v1"} <= set(required)
    worker = Worker(database, name="rgb-capable")
    worker.once()
    assert database.get_run(project, run["id"])["status"] == "completed"
    cp, _ = database.load_checkpoint(project, run["id"])
    assert len(cp["context"]["environment"]["measurements"][-1]["values"]) == 192
    caps = deepcopy(worker.capabilities)
    caps["features"].pop("worker.world_rgb_v1")
    waiting = database.create_run(project, "Waiting for real RGB support", run["spec"])
    database.enqueue(project, "run", run_id=waiting["id"])
    assert database.claim("old-no-rgb", capabilities=caps) is None


def test_world_development_generations_keep_identity_and_evaluate_in_a_separate_world(database):
    from test_evolution import campaign, drain

    from threemind_lab import evolution

    world = default_world().model_dump(mode="json")
    development = RunSpec(environment="world", world_protocol=world, clock="unbounded", duration_s=0.047).model_dump(
        mode="json"
    )
    evaluation = deepcopy(development)
    evaluation["world_protocol"]["geometries"][-1]["position"][0] = -1.3
    project, created, _ = campaign(database, development=development, evaluation=evaluation)
    worker = Worker(database, name="world-lineage")
    result = drain(worker, project, created["id"])
    assert result["status"] == "completed", result["error"]
    with database.tx(project) as db:
        rows = db.execute(
            "SELECT m.stage,m.source_version_id,m.candidate_version_id,c.context "
            "FROM evolution_members m JOIN checkpoints c ON c.id=m.checkpoint_id WHERE m.campaign_id=%s",
            (created["id"],),
        ).fetchall()
        versions = db.execute("SELECT id FROM innate_versions").fetchall()
    assert len(rows) == 16 and len(versions) == 4
    for row in rows:
        frozen = row["context"]["protocol"]["world_protocol"]
        assert frozen == (world if row["stage"] == "development" else evaluation["world_protocol"])
        assert row["context"]["environment"]["elapsed_us"] == 60000
        assert row["context"]["environment"]["observation"]["bodies"]
    assert {row["candidate_version_id"] for row in rows if row["stage"] == "development"} == {v["id"] for v in versions}
    assert evolution.detail(database, project, created["id"])["phase"] == "complete"


def test_world_paired_conditions_restore_the_same_warmup_physics(database):
    from test_study_editor import protocol

    value = protocol()
    value["base"]["environment"] = "world"
    value["base"]["world_protocol"] = default_world().model_dump(mode="json")
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "World paired conditions"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        created = client.post(base + "/studies", json=value)
        assert created.status_code == 202, created.text
        job = created.json()
        assert "worker.world_v1" in job["required_features"]
        worker = Worker(database)
        assert worker.once()
        runs = client.get(base + f"/runs?study_id={job['params']['study_id']}").json()
        assert len(runs) == 4
        for seed in value["seeds"]:
            left, right = [
                database.load_checkpoint(project, run["id"])[0] for run in runs if run["spec"]["seed"] == seed
            ]
            assert left["context"]["environment"]["integration"] == right["context"]["environment"]["integration"]
        for run in runs:
            assert (
                client.get(base + f"/runs/{run['id']}/world/protocol").json()["protocol"]
                == value["base"]["world_protocol"]
            )
        for _ in runs:
            assert worker.once()
        assert all(database.get_run(project, r["id"])["status"] == "completed" for r in runs)


def test_world_library_server_viewers_can_inspect_but_cannot_write(database):
    from test_api import client_for

    from threemind_lab import auth
    from threemind_lab.world_api import WorldEdit
    from threemind_lab.worlds import save

    owner = auth.create_user(database, "world-owner", "isolated world owner password")
    viewer = auth.create_user(database, "world-viewer", "isolated world viewer password")
    project = database.create_project(owner, "World role isolation")["id"]
    spec = default_world().model_dump(mode="json")
    row = save(database, project, owner["id"], WorldEdit(operation_id=uuid4(), protocol=spec))
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        base = f"/api/v2/projects/{project}/worlds"
        assert client.get(base).status_code == 401
        login = client.post(
            "/api/v2/login", json={"username": "world-viewer", "password": "isolated world viewer password"}
        ).json()
        client.headers["X-CSRF-Token"] = login["csrf"]
        assert client.get(base + f"/{row['document_id']}").status_code == 200
        assert client.post(base + "/validate", json={"protocol": spec}).status_code == 200
        assert client.post(base, json={"operation_id": str(uuid4()), "protocol": spec}).status_code == 403
        assert (
            client.put(
                base + f"/{row['document_id']}/archive", json={"expected_revision": 1, "archived": True}
            ).status_code
            == 403
        )
