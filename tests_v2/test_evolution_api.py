import hashlib
import io
import json
import zipfile
from uuid import uuid4

from test_api import client_for
from test_evolution import drain
from test_evolution_protocol import protocol

from threemind_lab import auth, evolution
from threemind_lab.database import LOCAL_USER
from threemind_lab.worker import Worker


def test_graphical_catalogue_validation_creation_and_complete_evidence_export(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Directed selection API"}).json()["id"]
        root = f"/api/v2/projects/{project}/evolutions"
        catalogue = client.get(root + "/catalogue").json()
        assert len(catalogue["metrics"]) == 13 and catalogue["defaults"]["criteria"] == []
        assert client.post(root + "/validate", json=catalogue["defaults"]).status_code == 422
        body = {"generations": 2, "population_size": 2, "evaluation_blocks": 2, "verification_blocks": 2, "seed": 42}
        seeds = client.post(root + "/seeds", json=body)
        assert seeds.status_code == 200 and seeds.json()["development_seeds"] == protocol()["development_seeds"]
        assert client.post(root + "/seeds", json=body | {"seed": "42"}).status_code == 422
        checked = client.post(root + "/validate", json=protocol())
        assert checked.status_code == 200 and checked.json()["valid"], checked.text
        declared = checked.json()["protocol"]
        request = {
            "operation_id": str(uuid4()),
            "name": "Graphical protocol",
            "objective": "Verify raw lineage and selection evidence",
            "protocol": declared,
        }
        response = client.post(root, json=request)
        assert response.status_code == 201, response.text
        campaign = response.json()
        url = root + "/" + campaign["id"]
        assert client.post(root, json=request).json()["id"] == campaign["id"]
        assert client.post(root, json=request | {"objective": "changed"}).status_code == 409
        assert "protocol" not in client.get(root).json()["rows"][0]
        assert client.get(url + "/protocol").json()["protocol_hash"] == campaign["protocol_hash"]
        finished = drain(Worker(database), project, campaign["id"])
        assert finished["status"] == "completed", finished["error"]
        exports = client.post(url + "/exports", json={"operation_id": str(uuid4())})
        assert exports.status_code == 202, exports.text
        job_id = exports.json()["id"]
        worker = Worker(database)
        assert worker.once()
        record = client.get(url + "/exports").json()[0]
        assert record["status"] == "done", record["error"]
        artifact_id = record["result"]["artifact_id"]
        downloaded = client.get(f"/api/v2/projects/{project}/artifacts/{artifact_id}")
        assert downloaded.status_code == 200
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as bundle:
            manifest = json.loads(bundle.read("manifest.json"))
            assert manifest["snapshot_revision"] == finished["revision"]
            for name, digest in manifest["files"].items():
                assert hashlib.sha256(bundle.read(name)).hexdigest() == digest
            members = [json.loads(row) for row in bundle.read("members.jsonl").splitlines()]
            assert len(members) == 16 and all(m["outcome"]["metrics"] for m in members)
            assert len(bundle.read("selections.jsonl").splitlines()) == 4
            assert len(bundle.read("scores.csv").splitlines()) == 5
            assert json.loads(bundle.read("campaign.json"))["protocol_hash"] == campaign["protocol_hash"]
            assert len(bundle.read("checkpoint-provenance.jsonl").splitlines()) == 16
            assert bundle.read("figures/nodes.png").startswith(b"\x89PNG")
            assert b"<svg" in bundle.read("figures/nodes.svg")
            assert len(json.loads(bundle.read("descriptive-series.json"))) == 2
        with database.tx(project) as db:
            # A lost finish acknowledgement reuses the successfully captured
            # artifact instead of producing a different snapshot on retry.
            db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (job_id,))
        assert worker.once()
        assert client.get(url + "/exports").json()[0]["result"]["artifact_id"] == artifact_id
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM artifacts WHERE job_id=%s", (job_id,)).fetchone()["n"] == 1


def test_evolution_api_respects_project_roles_and_control_revisions(database):
    owner = auth.create_user(database, "evolution-owner", "test password for evolution owner")
    viewer = auth.create_user(database, "evolution-viewer", "test password for evolution viewer")
    project = database.create_project(owner, "Private lineage")["id"]
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        root = f"/api/v2/projects/{project}/evolutions"
        assert client.get(root).status_code == 401
        login = client.post(
            "/api/v2/login", json={"username": "evolution-viewer", "password": "test password for evolution viewer"}
        ).json()
        client.headers["X-CSRF-Token"] = login["csrf"]
        assert client.get(root + "/catalogue").status_code == 200
        request = {
            "operation_id": str(uuid4()),
            "name": "No write",
            "objective": "Permission fixture",
            "protocol": protocol(),
        }
        assert client.post(root, json=request).status_code == 403
        login = client.post(
            "/api/v2/login", json={"username": "evolution-owner", "password": "test password for evolution owner"}
        ).json()
        client.headers["X-CSRF-Token"] = login["csrf"]
        response = client.post(root, json=request)
        assert response.status_code == 201, response.text
        created = response.json()
        url = root + "/" + created["id"]
        assert (
            client.post(
                url + "/controls", json={"action": "pause", "expected_revision": created["revision"]}
            ).status_code
            == 200
        )
        assert (
            client.post(
                url + "/controls", json={"action": "resume", "expected_revision": created["revision"]}
            ).status_code
            == 409
        )
        other = database.create_project({"id": LOCAL_USER}, "Other identity")["id"]
        assert evolution.listing(database, other)["rows"] == []
