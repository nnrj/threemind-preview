"""Real route and fine-action contracts across the new platform entrances."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_ai_catalogue import PASSWORD, host
from test_research_operations import fixture

from threemind_lab import auth, permissions
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER
from threemind_lab.worker import Worker

pytestmark = pytest.mark.session_auth


def test_public_document_reader_and_private_research_boundary(database):
    with TestClient(create_app(Settings(database_url=database.test_url, authentication="session"), database)) as client:
        for url in ("/api/v2/documents", "/api/v2/history"):
            response = client.get(url)
            assert response.status_code == 200, response.text
        response = client.get("/api/v2/documents/content", params={"path": "docs/zh/platform-workbench.md"})
        assert response.status_code == 200, response.text
        assert client.get("/api/v2/research-experiments").status_code == 401
        assert client.get("/api/v2/configuration/templates").status_code == 401


def test_fine_action_research_plan_admission_and_fresh_step_authorization(database):
    with host(database) as (client, _settings):
        project, run_id, _, _ = fixture(database, client)
        root = permissions.enrich(database, {"id": LOCAL_USER})
        grants = [
            {"action": action, "scope": "member_projects"}
            for action in (
                "research.write",
                "runs.read",
                "runs.resume",
                "runs.observe",
                "runs.stimulate",
            )
        ]
        role = permissions.save_role(database, root, key="specific-plan", name="Specific plan", grants=grants)
        user = auth.create_user(database, "specific-plan", PASSWORD, actor=root, role_ids=[role["id"]])
        with database.tx(project) as db:
            db.execute("INSERT INTO members VALUES(%s,%s,'researcher')", (project, user["id"]))
        credential = client.post(
            "/api/v2/auth/token", json={"username": "specific-plan", "password": PASSWORD, "source": "ai"}
        ).json()
        client.headers["Authorization"] = "Bearer " + credential["access_token"]
        base = f"/api/v2/projects/{project}/runs/{run_id}"
        plan_base = base + "/research/plans"

        def start_plan():
            revision = client.get(base).json()["revision"]
            result = client.post(
                plan_base,
                json={
                    "name": "Concrete actions",
                    "request_id": str(uuid4()),
                    "expected_revision": revision,
                    "protocol": {
                        "steps": [
                            {"command": "stimulus.send", "parameters": {"text": "蓝色圆形"}},
                            {"command": "runtime.wait", "parameters": {"duration_us": 1000}},
                            {"command": "observe.summary", "parameters": {}},
                        ]
                    },
                },
            )
            assert result.status_code == 201, result.text
            plan = result.json()
            result = client.post(
                plan_base + f"/{plan['id']}/control",
                json={
                    "action": "start",
                    "request_id": str(uuid4()),
                    "expected_step": plan["next_step"],
                    "expected_revision": plan["expected_revision"],
                },
            )
            assert result.status_code == 200, result.text
            return plan

        plan = start_plan()
        assert Worker(database, backend="reference").once()
        assert client.get(plan_base + f"/{plan['id']}").json()["status"] == "completed"
        # The same narrow role has no blanket control or global configuration tools.
        assert client.get("/api/v2/configuration/templates").status_code == 403
        admitted = start_plan()
        with database.tx(project) as db:
            before = db.execute("SELECT count(*) AS n FROM input_envelopes WHERE run_id=%s", (run_id,)).fetchone()["n"]
            cp = db.execute("SELECT state_hash FROM runs WHERE id=%s", (run_id,)).fetchone()["state_hash"]
            db.execute(
                "UPDATE platform_roles SET permissions=%s,revision=revision+1 WHERE id=%s",
                (Jsonb([g for g in grants if g["action"] != "runs.stimulate"]), role["id"]),
            )
        assert Worker(database, backend="reference").once()
        with database.tx(project) as db:
            assert (
                db.execute("SELECT status FROM research_plans WHERE id=%s", (admitted["id"],)).fetchone()["status"]
                == "failed"
            )
            assert (
                db.execute("SELECT count(*) AS n FROM input_envelopes WHERE run_id=%s", (run_id,)).fetchone()["n"]
                == before
            )
            assert db.execute("SELECT state_hash FROM runs WHERE id=%s", (run_id,)).fetchone()["state_hash"] == cp


def test_creation_provenance_is_authorized_versioned_and_independent_of_destination(database):
    with host(database) as (client, _settings):
        source = client.post("/api/v2/projects", json={"name": "Preset source"}).json()["id"]
        destination = client.post("/api/v2/projects", json={"name": "Actual ownership"}).json()["id"]
        spec = client.get("/api/v2/configuration/defaults").json()["spec"] | {
            "environment": "manual",
            "clock": "unbounded",
            "duration_s": 1,
        }
        preset_url = f"/api/v2/projects/{source}/configuration/defaults"
        saved = client.put(preset_url, json={"spec": spec, "expected_revision": 0})
        assert saved.status_code == 200, saved.text
        origin = {"kind": "project-preset", "project_id": source, "revision": saved.json()["revision"]}
        edited = spec | {"sample_us": 200000}
        body = {"name": "Copied then edited", "spec": edited, "start_immediately": False, "creation_source": origin}
        target = f"/api/v2/projects/{destination}/runs"
        created = client.post(target, json=body)
        assert created.status_code == 201, created.text
        individual = created.json()
        assert individual["project_id"] == destination and individual["spec"]["sample_us"] == 200000
        assert individual["creation_source"]["project_id"] == source
        assert individual["creation_source"]["source_spec"] == saved.json()["spec"]
        assert (
            client.put(preset_url, json={"spec": edited, "expected_revision": saved.json()["revision"]}).status_code
            == 200
        )
        assert client.get(target + "/" + individual["id"]).json()["creation_source"] == individual["creation_source"]
        for kind, revision, status in (("system", 999, 404), ("factory", 1, 422)):
            result = client.post(
                target,
                json=body
                | {
                    "creation_source": {
                        "kind": kind,
                        "kernel_id": spec["kernel_id"],
                        "revision": revision,
                    }
                },
            )
            assert result.status_code == status, result.text
        root = permissions.enrich(database, {"id": LOCAL_USER})
        role = permissions.save_role(
            database,
            root,
            key="destination-only",
            name="Destination only",
            grants=[{"action": a, "scope": "member_projects"} for a in ("runs.create", "projects.read")],
        )
        user = auth.create_user(database, "destination-only", PASSWORD, actor=root, role_ids=[role["id"]])
        with database.tx(destination) as db:
            db.execute("INSERT INTO members VALUES(%s,%s,'researcher')", (destination, user["id"]))
        credential = client.post(
            "/api/v2/auth/token", json={"username": "destination-only", "password": PASSWORD}
        ).json()
        client.headers["Authorization"] = "Bearer " + credential["access_token"]
        result = client.post(
            target, json=body | {"creation_source": origin | {"revision": saved.json()["revision"] + 1}}
        )
        assert result.status_code in (403, 404), result.text
        with database.tx(destination) as db:
            assert db.execute("SELECT count(*) AS n FROM runs WHERE project_id=%s", (destination,)).fetchone()["n"] == 1
            assert (
                db.execute("SELECT count(*) AS n FROM checkpoints WHERE project_id=%s", (destination,)).fetchone()["n"]
                == 0
            )
        # A source reader need not be a source member. Apply its read domain to
        # the source transaction, rather than reusing the destination create action.
        source_reader = permissions.save_role(
            database,
            root,
            key="source-reader",
            name="Source reader",
            grants=[
                {"action": "runs.create", "scope": "member_projects"},
                {"action": "projects.read", "scope": "all_projects"},
            ],
        )
        permissions.assign_roles(database, root, user["id"], [source_reader["id"]])
        # Role replacement invalidates old sessions; obtain the new authority.
        credential = client.post(
            "/api/v2/auth/token", json={"username": "destination-only", "password": PASSWORD}
        ).json()
        client.headers["Authorization"] = "Bearer " + credential["access_token"]
        copied = client.post(
            target, json=body | {"creation_source": origin | {"revision": saved.json()["revision"] + 1}}
        )
        assert copied.status_code == 201, copied.text
        assert copied.json()["creation_source"]["source_spec"] == edited
