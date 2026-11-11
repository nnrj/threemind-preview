import copy
import io
import json
import zipfile
from uuid import uuid4

from test_api import client_for
from test_ecology_runtime import configuration
from test_ecology_store import setup

from threemind_lab import research_ai
from threemind_lab.database import LOCAL_USER
from threemind_lab.ecology_store import PopulationWriter, control
from threemind_lab.ecology_worker import open_population
from threemind_runtime.ecology_rules import Hazard


def capture(client, base, worker, **selection):
    body = {"operation_id": str(uuid4()), **selection}
    response = client.post(base + "/report-sources", json=body)
    assert response.status_code == 202, response.text
    identity = response.json()["id"]
    assert client.post(base + "/report-sources", json=body).json()["id"] == identity
    assert worker.once()
    source = client.get(base + f"/report-sources/{identity}").json()
    assert source["status"] == "done", source["error"]
    return identity, source


def test_population_sources_freeze_before_later_births_and_keep_physical_time(database):
    project, row, worker = setup(database)
    base = f"/api/v2/projects/{project}"
    writer = PopulationWriter(database, project, row)
    with client_for(database) as client, open_population(worker, row, writer) as runtime:
        common = {"operation_id": str(uuid4()), "kind": "ecology_members", "ecology_id": str(row["id"])}
        assert client.post(base + "/report-sources", json=common).status_code == 409
        writer.commit(runtime)
        runtime.advance_to(17000)
        writer.commit(runtime)
        early = str(writer.row["checkpoint_id"])
        pending = client.post(base + "/report-sources", json=common)
        assert pending.status_code == 202, pending.text
        for boundary in (20000, 40000, 60000, 80000, 100000):
            runtime.advance_to(boundary)
            writer.commit(runtime)
        frozen = runtime.checkpoint()
        control(
            database,
            project,
            row["id"],
            LOCAL_USER,
            "pause",
            writer.row["revision"] - writer.row["checkpoint_revision"],
        )
        assert worker.once()
        old = client.get(base + f"/report-sources/{pending.json()['id']}").json()
        assert old["row_count"] == 2 and old["provenance"]["checkpoint"]["id"] == early
        assert old["provenance"]["checkpoint"]["population"]["physical_time_us"] == "20000"
        assert client.post(base + "/report-sources", json=common).json()["id"] == pending.json()["id"]
        for invalid in ({"run_id": str(uuid4())}, {"from_us": "0"}, {"evolution_generation": 0}):
            assert client.post(base + "/report-sources", json=common | invalid).status_code == 422
        other = client.post("/api/v2/projects", json={"name": "Other scope"}).json()["id"]
        assert client.post(f"/api/v2/projects/{other}/report-sources", json=common).status_code == 404
        selected, latest = capture(client, base, worker, kind="ecology_members", ecology_id=str(row["id"]))
        assert latest["row_count"] == 6
        members = client.get(base + f"/report-sources/{selected}/rows").json()["rows"]
        assert {r["label"] for r in members} == {f"n{i}" for i in range(6)}
        assert {r["values"]["offspring_count"] for r in members} == {0, 1}
        assert all(r["time_us"] is None and r["provenance"]["state_hash"] for r in members)
        assert latest["manifest"]["coverage"]["rows_are_independent_replicates"] is False
        trajectory, series = capture(
            client,
            base,
            worker,
            kind="ecology_trajectory",
            ecology_id=str(row["id"]),
            ecology_checkpoint_id=early,
        )
        assert series["row_count"] == 2
        points = client.get(base + f"/report-sources/{trajectory}/rows").json()["rows"]
        assert points[-1]["time_us"] == "17000"
        assert points[-1]["values"]["physical_time_s"] == 0.02
        assert points[-1]["provenance"]["pending_delivery_us"] == "20000"
        assert all(r["values"]["births"] == 0 for r in points)
        assert runtime.checkpoint() == frozen
        for source, chart in ((selected, "histogram"), (trajectory, "line")):
            template = client.get(base + f"/report-sources/{source}/template").json()
            rendered = client.post(base + "/research-documents/preview", json=template)
            assert rendered.status_code == 200, rendered.text
            assert any(b.get("chart") == chart for b in rendered.json()["blocks"])
        bad = common | {"operation_id": str(uuid4()), "kind": "ecology_trajectory", "through_us": "100001"}
        assert client.post(base + "/report-sources", json=bad).status_code == 422


def test_dead_population_reports_exports_ai_and_capability_boundaries(database):
    rules = configuration()
    rules.rules.hazards = [Hazard(id="fatal", radius=100, damage_per_s=1e6)]
    project, row, worker = setup(database, ecology=rules)
    assert worker.once()
    base = f"/api/v2/projects/{project}"
    with client_for(database) as client:
        request = {"operation_id": str(uuid4()), "kind": "ecology_members", "ecology_id": str(row["id"])}
        queued = client.post(base + "/report-sources", json=request)
        assert queued.status_code == 202, queued.text
        old = copy.deepcopy(worker.capabilities)
        del old["features"]["worker.ecology_evidence_v1"]
        assert database.claim("old-ecology-reader", capabilities=old) is None
        assert worker.once()
        source = queued.json()["id"]
        data = client.get(base + f"/report-sources/{source}").json()
        assert data["status"] == "done", data["error"]
        assert data["row_count"] == 2
        rows = client.get(base + f"/report-sources/{source}/rows").json()["rows"]
        assert all(r["values"]["body_alive"] == 0 and r["values"]["offspring_count"] == 0 for r in rows)
        assert all(r["provenance"]["body_survival_right_censored"] is False for r in rows)
        template = client.get(base + f"/report-sources/{source}/template").json()
        invalid = copy.deepcopy(template)
        invalid["blocks"][1]["chart"] = "line"
        assert client.post(base + "/research-documents/preview", json=invalid).status_code == 422
        with database.tx(project) as db:
            evidence = research_ai.prepare(
                db, {"kind": "record", "sources": [source], "objective": "Describe the complete population"}
            )
            assert "Body failure, Core death" in evidence["evidence"]["sources"][0]["provenance"]["inference_boundary"]
            assert "NOT lifetime" in evidence["prompt"]["system"]
        record = str(uuid4())
        saved = client.put(
            base + f"/research-documents/{record}",
            json={"operation_id": str(uuid4()), "expected_revision": 0, "spec": template},
        )
        assert saved.status_code == 200, saved.text
        for fmt in ("markdown", "html", "docx", "pdf"):
            response = client.post(
                base + f"/research-documents/{record}/exports",
                json={"operation_id": str(uuid4()), "revision": 1, "format": fmt, "include_data": True},
            )
            assert response.status_code == 202, response.text
            assert database.claim("old-ecology-publisher", capabilities=old) is None
            assert worker.once()
            exported = client.get(base + f"/research-documents/{record}/exports").json()["rows"][0]
            assert exported["status"] == "done", exported.get("error")
            artifact = client.get(base + f"/artifacts/{exported['result']['bundle_artifact_id']}")
            with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
                assert any(name.endswith(".jsonl") for name in archive.namelist())
        from cryptography.fernet import Fernet
        from test_ai_providers import create, get_call
        from test_research_ai import ask, reply

        from threemind_lab.config import Settings

        settings = Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),))
        provider = create(database, settings, project)
        call, _, _ = ask(
            database,
            settings,
            project,
            provider,
            {
                "kind": "record",
                "sources": [source],
                "objective": "Describe recorded body failure without claiming consciousness",
            },
        )
        old_ai = {
            "queue": "ai",
            "features": {
                name: {"state": "available"}
                for name in ("worker.ai", "worker.research_events_v1", "worker.research_ai_v1", "worker.ecology_v1")
            },
        }
        assert database.claim("old-ecology-author", queue="ai", capabilities=old_ai) is None
        template["blocks"][-1]["markdown"] = (
            "Engineering fixture. Body failure is not Core death, and these individuals are not independent evolutionary replicates."
        )
        assert reply(database, settings, json.dumps(template)).once()
        assert get_call(database, project, call)["result"]["application_status"] == "recorded"


def test_resource_pool_pages_include_inactive_habitats_and_fixed_scope(database):
    rules = configuration("independent")
    rules.founder_count = 31
    rules.rules.reproduction.population_limit = 31
    rules.rules.reproduction.enabled = False
    rules.rules.hazards = [Hazard(id="fatal", radius=100, damage_per_s=1e6)]
    project, row, worker = setup(database, ecology=rules)
    assert worker.once()
    with client_for(database) as client:
        root = f"/api/v2/projects/{project}/ecologies/{row['id']}"
        detail = client.get(root).json()
        assert detail["checkpoint"]["ledger"]["pool_count"] == 31
        assert "pools" not in detail["checkpoint"]["ledger"]
        assert detail["checkpoint"]["observation"]["population"]["living_bodies"] == 0
        params = {"checkpoint_id": detail["checkpoint"]["id"]}
        first = client.get(root + "/resource-pools", params=params).json()
        assert first["more"] and len(first["rows"]) == 30
        last = client.get(root + "/resource-pools", params=params | {"after": first["rows"][-1]["habitat"]}).json()
        assert not last["more"] and [r["habitat"] for r in last["rows"]] == ["n30"]
        assert {r["habitat"] for r in first["rows"] + last["rows"]} == {f"n{i}" for i in range(31)}
        assert all("food" in r["resources"] for r in first["rows"] + last["rows"])
        other = client.post("/api/v2/projects", json={"name": "Other pool scope"}).json()["id"]
        assert (
            client.get(f"/api/v2/projects/{other}/ecologies/{row['id']}/resource-pools", params=params).status_code
            == 404
        )
        assert client.get(root + "/resource-pools", params={"checkpoint_id": str(uuid4())}).status_code == 404
