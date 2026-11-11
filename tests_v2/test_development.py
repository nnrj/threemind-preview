import io
import json
import zipfile
from uuid import uuid4

import psycopg
import pytest
from test_api import client_for

from threemind_core import Config, Stimulus
from threemind_lab import auth
from threemind_lab.configuration import default_spec
from threemind_lab.database import LOCAL_USER
from threemind_lab.development import DevelopmentRequest, create
from threemind_lab.worker import Worker
from threemind_runtime import BIRTH_RULE, ArtifactCodec, birth, create_engine


def protocol():
    return default_spec() | {
        "environment": "replay",
        "clock": "unbounded",
        "duration_s": 0.04,
        "checkpoint_us": 10000,
        "sample_us": 10000,
        "replay": [{"time_us": "0", "channels": [[1, 0.8], [2, 0.7]]}],
    }


def test_development_json_does_not_coerce_scientific_parameter_types():
    from pydantic import ValidationError

    for patch in ({"seed": "12"}, {"duration_s": "0.1"}, {"trace": "false"}):
        with pytest.raises(ValidationError):
            DevelopmentRequest(operation_id=uuid4(), name="strict", objective="typed protocol", spec=protocol() | patch)


def start(client, base, source=None, spec=None, name="发育一"):
    request = {
        "operation_id": str(uuid4()),
        "name": name,
        "objective": "观察物理刺激塑造结构的过程",
        "source_version_id": source,
        "spec": spec or protocol(),
    }
    response = client.post(base + "/development", json=request)
    assert response.status_code == 201, response.text
    return response.json(), request


def select(client, base, run, cp, name="先天一"):
    request = {
        "operation_id": str(uuid4()),
        "name": name,
        "selection_note": "研究者选择；没有自动适应度筛选",
        "run_id": str(run),
        "checkpoint_id": str(cp["id"]),
        "expected_state_hash": cp["state_hash"],
    }
    response = client.post(base + "/innate-versions", json=request)
    assert response.status_code == 201, response.text
    return response.json(), request


@pytest.mark.parametrize("backend", ["reference", "native"])
def test_storage_free_birth_preserves_learned_structure_and_remains_plastic(backend):
    engine = create_engine(Config(energy_simulation_enabled=True, spatial_embedding=True), backend=backend)
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
    engine.advance_to(10000)
    original = engine.capture_state()
    image = birth(original)
    state, before = image.to_dict(), original.to_dict()
    assert image.digest == birth(image).digest and original.to_dict() == before
    assert image.digest != original.digest and state["time_us"] == "0" and state["queue"] == []
    assert state["life"] == "waiting" and state["sources_open"]
    for old, new in zip(before["nodes"], state["nodes"], strict=True):
        for key in ("id", "channel", "support", "stability", "touches"):
            assert new[key] == old[key]
        assert new["activation"] == new["inhibition"] == new["trace"] == 0
    assert [e["weight"] for e in state["edges"]] == [e["weight"] for e in before["edges"]]
    for fmt in ("tmind", "json"):
        assert ArtifactCodec.decode(ArtifactCodec.encode(image, fmt)).digest == image.digest
    child = create_engine(state=image, backend=backend)
    child.inject(Stimulus(0, ((1, 0.8), (3, 0.7))))
    child.advance_to(10000)
    assert 3 in {n["channel"] for n in child.capture_state().to_dict()["nodes"]}
    assert original.digest == engine.capture_state().digest


def test_development_registration_lineage_birth_recovery_and_exports(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Development"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        session, request = start(client, base)
        assert client.post(base + "/development", json=request).json()["id"] == session["id"]
        assert client.post(base + "/development", json=request | {"name": "changed"}).status_code == 409
        worker = Worker(database)
        assert worker.once()
        run = database.get_run(project, session["run_id"])
        assert run["status"] == "completed", run["error"]
        cp, parent_image = database.load_checkpoint(project, run["id"])
        version, selection = select(client, base, run["id"], cp)
        assert client.post(base + "/innate-versions", json=selection).json()["id"] == version["id"]
        assert version["generation"] == 0 and version["birth_rule"] == BIRTH_RULE
        child, _ = start(client, base, version["id"], name="继承后发育")
        # An actual worker shutdown checkpoint, then a fresh worker continues it.
        worker.stopping = True
        assert worker.once()
        child_cp, child_image = database.load_checkpoint(project, child["run_id"])
        assert database.get_run(project, child["run_id"])["status"] == "paused"
        # The stopped worker has already queued the declared replay input, but
        # has delivered none; inherited learned structure is still unchanged.
        assert child_image.to_dict()["time_us"] == "0"
        for table in ("nodes", "edges"):
            assert child_image.to_dict()[table] == birth(parent_image).to_dict()[table]
        database.command(project, child["run_id"], "resume", {})
        assert Worker(database).once()
        child_cp, child_image = database.load_checkpoint(project, child["run_id"])
        assert database.get_run(project, child["run_id"])["status"] == "completed"
        assert child_image.digest != birth(parent_image).digest
        uninterrupted, _ = start(client, base, version["id"], name="相同初态不中断")
        assert Worker(database).once()
        assert database.load_checkpoint(project, uninterrupted["run_id"])[1].digest == child_image.digest
        with database.tx(project) as db:
            assert (
                db.execute(
                    "SELECT count(*) AS n FROM events WHERE run_id=%s AND kind='development_birth'", (child["run_id"],)
                ).fetchone()["n"]
                == 1
            )
            required = db.execute("SELECT required_features FROM jobs WHERE run_id=%s", (child["run_id"],)).fetchall()
            assert all("worker.development_v1" in j["required_features"] for j in required)
        next_version, _ = select(client, base, child["run_id"], child_cp, name="先天二")
        detail = client.get(base + f"/innate-versions/{next_version['id']}").json()
        assert detail["generation"] == 1 and detail["parent_version_id"] == version["id"]
        assert [row["id"] for row in detail["lineage"]] == [next_version["id"], version["id"]]
        assert detail["development"]["id"] == child["id"]
        for fmt in ("tmind", "json", "bundle"):
            job = client.post(base + f"/innate-versions/{version['id']}/exports", json={"format": fmt}).json()
            assert Worker(database).once()
            with database.tx(project) as db:
                result = db.execute("SELECT * FROM jobs WHERE id=%s", (job["id"],)).fetchone()
            assert result["status"] == "done", result["error"]
            raw = client.get(base + f"/artifacts/{result['result']['artifact_id']}").content
            if fmt == "bundle":
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    manifest = json.loads(archive.read("manifest.json"))
                    assert not manifest["raw_evidence_included"]
                    assert "children" not in manifest["version"]
                    assert manifest["model"]["source_hash"] == parent_image.digest
                    raw = archive.read("model.tmind")
            image, profile = ArtifactCodec.decode(raw, with_profile=True)
            assert image.digest == birth(parent_image).digest
            assert profile["sensory_seed"] == protocol()["seed"]
        assert database.load_checkpoint(project, run["id"], cp["id"])[1].digest == parent_image.digest
        assert len(client.get(base + "/development").json()["rows"]) == 3
        assert len(client.get(base + "/innate-versions?q=先天二").json()["rows"]) == 1
        assert "protocol" not in client.get(base + "/development").json()["rows"][0]
        reasons = client.get(base + f"/runs/{run['id']}/cleanup-preview").json()["reasons"]
        assert any("先天版本" in reason for reason in reasons)


def test_registration_pins_historical_protocol_and_rejects_identity_changes(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Historical identity"}).json()["id"]
        base = f"/api/v2/projects/{project}"
        spec = protocol()
        run = database.create_run(project, "Historical source", spec)
        engine = create_engine(Config(**spec["config"]))
        engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7))))
        engine.advance_to(10000)
        cp = database.save_checkpoint(
            project, run["id"], engine.capture_state(), context={"protocol": spec}, expected_revision=0, status="paused"
        )
        with database.tx(project) as db:
            db.execute("UPDATE runs SET spec=jsonb_set(spec,'{seed}','12') WHERE id=%s", (run["id"],))
        version, selection = select(client, base, run["id"], cp)
        assert version["protocol"]["seed"] == spec["seed"]
        for changes in (
            {"seed": 12},
            {"config": spec["config"] | {"plasticity": False}},
            {"text_sensor": spec["text_sensor"] | {"channel_count": 4}},
        ):
            response = client.post(
                base + "/development",
                json={
                    "operation_id": str(uuid4()),
                    "name": "Invalid",
                    "objective": "invalid identity",
                    "source_version_id": version["id"],
                    "spec": spec | changes,
                },
            )
            assert response.status_code in (400, 422), response.text
        assert (
            client.post(
                base + "/innate-versions",
                json=selection | {"operation_id": str(uuid4()), "expected_state_hash": "0" * 64},
            ).status_code
            == 409
        )
        for table, identity in (("innate_versions", version["id"]),):
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState), database.tx(project) as db:
                db.execute(f"DELETE FROM {table} WHERE id=%s", (identity,))
        with database.tx() as db:
            assert db.execute("SELECT * FROM innate_versions").fetchall() == []


def test_creation_rolls_back_without_orphan_run_and_old_workers_cannot_claim(database):
    project = database.create_project({"id": LOCAL_USER}, "Atomic training")["id"]
    request = DevelopmentRequest(operation_id=uuid4(), name="Atomic", objective="Atomic boundary", spec=protocol())
    with psycopg.connect(database.test_migration_url) as db:
        assert db.info.dbname.startswith("tm2_test_db_")
        db.execute(
            "CREATE FUNCTION tm2.reject_test_development() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.params ? 'development_id' THEN RAISE EXCEPTION 'test interruption'; END IF; RETURN NEW; END $$"
        )
        db.execute(
            "CREATE TRIGGER reject_test_development BEFORE INSERT ON tm2.jobs FOR EACH ROW EXECUTE FUNCTION tm2.reject_test_development()"
        )
    with pytest.raises(psycopg.errors.RaiseException):
        create(database, project, LOCAL_USER, request, 600)
    with database.tx(project) as db:
        assert db.execute("SELECT id FROM runs").fetchall() == []
        assert db.execute("SELECT id FROM development_sessions").fetchall() == []
    with psycopg.connect(database.test_migration_url) as db:
        db.execute("DROP TRIGGER reject_test_development ON tm2.jobs")
        db.execute("DROP FUNCTION tm2.reject_test_development()")
    create(database, project, LOCAL_USER, request, 600)
    from threemind_runtime.capabilities import probe_worker

    caps = probe_worker("native")
    database.announce_worker("old-worker", caps)
    assert database.claim("old-worker", capabilities=caps) is None
    assert Worker(database).once()


def test_development_project_role_and_nonce_boundaries(database):
    owner = auth.create_user(database, "development-owner", "a long test secret for owner")
    viewer = auth.create_user(database, "development-viewer", "a long test secret for viewer")
    project = database.create_project(owner, "Private training")["id"]
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        base = f"/api/v2/projects/{project}"
        assert client.get(base + "/development").status_code == 401
        login = client.post(
            "/api/v2/login", json={"username": "development-viewer", "password": "a long test secret for viewer"}
        ).json()
        assert client.get(base + "/development").status_code == 200
        body = {"operation_id": str(uuid4()), "name": "denied", "objective": "denied", "spec": protocol()}
        assert client.post(base + "/development", json=body, headers={"X-CSRF-Token": login["csrf"]}).status_code == 403
        assert client.get(f"/api/v2/projects/{uuid4()}/innate-versions").status_code == 403
