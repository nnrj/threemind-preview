"""Host/UI metadata must not initialize or reconfigure a living individual."""

from copy import deepcopy
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from threemind_lab import auth, permissions
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER
from threemind_lab.operation_receipts import HEADER
from threemind_lab.worker import Worker


@pytest.mark.parametrize("kernel_id", [None, "threemind.continuous-memory/3.1", "threemind.continuous-memory/5.1"])
def test_prepare_defaults_template_edit_and_start_once(database, kernel_id):
    with TestClient(create_app(Settings(database_url=database.test_url, backend="reference"), database)) as client:
        # All creation/configuration tools work before any project exists.
        default = client.get("/api/v2/configuration/defaults", params={"kernel_id": kernel_id} if kernel_id else {}).json()
        assert default["revision"] == 0
        assert client.get("/api/v2/projects").json() == []
        spec = default["spec"] | {
            "environment": "replay",
            "duration_s": 0.05,
            "clock": "unbounded",
            "replay": [{"time_us": "0", "channels": [[11, 0.5], [12, 0.4]]}],
        }
        spec["host_telemetry"]["enabled"] = False
        spec["process_telemetry"]["enabled"] = False
        spec["runtime_telemetry"]["enabled"] = False
        checked = client.post("/api/v2/configuration/validate", json={"spec": spec})
        assert checked.status_code == 200 and checked.json()["valid"], checked.text
        saved = client.put("/api/v2/configuration/defaults", json={"spec": spec, "expected_revision": 0})
        assert saved.status_code == 200, saved.text
        assert (
            client.put("/api/v2/configuration/defaults", json={"spec": spec, "expected_revision": 0}).status_code == 409
        )
        template = client.post("/api/v2/configuration/templates", json={"name": "A", "spec": spec}).json()
        assert client.get("/api/v2/configuration/templates").json()["items"][0]["id"] == template["id"]
        project = client.post("/api/v2/projects", json={"name": "Prepared acceptance"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        response = client.post(
            root + "/runs",
            json={
                "name": "Prepared",
                "spec": spec,
                "start_immediately": False,
                "creation_source": {"kind": "template", "id": template["id"], "revision": 1},
            },
        )
        assert response.status_code == 201, response.text
        run = response.json()
        assert (run["status"], run["revision"], run["time_us"]) == ("paused", 0, "0")
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM jobs").fetchone()["n"] == 0
            assert db.execute("SELECT count(*) AS n FROM checkpoints").fetchone()["n"] == 0
        # Opening and inspecting do not create a checkpoint or execution task.
        assert client.get(root + "/runs/" + run["id"]).json()["revision"] == 0
        changed = spec | {"sample_us": 200000}
        body = {
            "name": "Edited",
            "spec": changed,
            "expected_revision": 0,
            "expected_metadata_revision": run["metadata_revision"],
        }
        edited = client.put(root + "/runs/" + run["id"] + "/configuration", json=body)
        assert edited.status_code == 200, edited.text
        assert edited.json()["revision"] == 0 and edited.json()["metadata_revision"] == run["metadata_revision"] + 1
        assert client.put(root + "/runs/" + run["id"] + "/configuration", json=body).status_code == 409
        assert (
            client.put(
                "/api/v2/configuration/templates/" + template["id"],
                json={"name": "B", "spec": spec, "expected_revision": 1},
            ).status_code
            == 200
        )
        assert client.get(root + "/runs/" + run["id"]).json()["spec"] == edited.json()["spec"]
        resume = root + "/runs/" + run["id"] + "/commands"
        assert client.post(resume, json={"kind": "resume"}).status_code == 200
        assert client.post(resume, json={"kind": "resume"}).status_code == 409
        assert client.put(root + "/runs/" + run["id"] + "/configuration", json=body).status_code == 409
        assert Worker(database, backend="reference").once()
        done = client.get(root + "/runs/" + run["id"]).json()
        assert done["revision"] > 0 and done["status"] in ("completed", "dead")
        assert done["creation_source"] == run["creation_source"]


def test_mail_transports_rules_and_global_inbox(database):
    settings = Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),))
    with TestClient(create_app(settings, database)) as client:
        project = client.post("/api/v2/projects", json={"name": "Mail rules"}).json()["id"]
        response = client.post(
            "/api/v2/services/notifications",
            json={
                "name": "Mail",
                "config": {"transport": "smtp", "smtp_host": "localhost", "smtp_security": "none"},
                "project_ids": [project],
            },
        )
        assert response.status_code == 201, response.text
        service = response.json()
        assert set(service["config"]).isdisjoint({"recipients", "events", "enabled"})
        root = f"/api/v2/projects/{project}/notifications"
        rules = client.put(
            root + "/settings", json={"service_id": service["id"], "config": {"enabled": True}, "expected_revision": 0}
        )
        assert rules.status_code == 200, rules.text
        assert rules.json()["service_id"] == service["id"]
        assert len(client.get(root + "/services").json()["items"]) == 1
        with database.tx(project) as db:
            notice = db.execute(
                "SELECT emit_notification(%s,NULL,'acceptance','run_completed','{}') AS id", (project,)
            ).fetchone()["id"]
        assert client.get("/api/v2/notifications/unread").json()["unread"] == 1
        listed = client.get("/api/v2/notifications").json()["items"]
        assert listed[0]["id"] == str(notice)
        assert client.post("/api/v2/notifications/read", json={"ids": [str(notice)]}).status_code == 200
        assert client.get("/api/v2/notifications/unread").json()["unread"] == 0
        assert (
            client.put(
                "/api/v2/services/notifications/" + service["id"],
                json={"name": "Updated", "config": service["config"], "expected_revision": 1, "project_ids": [project]},
            ).status_code
            == 200
        )
        # Changing transport does not rewrite the old frozen policy or enqueue mail.
        assert client.get(root + "/settings").json()["service_revision"] == 1
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM jobs WHERE kind='notification'").fetchone()["n"] == 0


def test_template_kernel_filter_fixed_revisions_and_source_checks(database):
    with TestClient(create_app(Settings(database_url=database.test_url, backend="reference"), database)) as client:
        kernels = ("threemind.continuous-memory/2", "threemind.continuous-memory/3", "threemind.continuous-memory/4")
        specs = {kernel: client.get("/api/v2/configuration/defaults", params={"kernel_id": kernel}).json()["spec"]
                 for kernel in kernels}
        templates = []
        for name, kernel in (("first /2", kernels[0]), ("second /2", kernels[0]), ("first /3", kernels[1])):
            result = client.post("/api/v2/configuration/templates", json={"name": name, "spec": specs[kernel]})
            assert result.status_code == 201, result.text
            assert result.json()["kernel_id"] == kernel
            templates.append(result.json())
        all_templates = client.get("/api/v2/configuration/templates").json()
        assert len(all_templates["items"]) == 3
        filtered = client.get("/api/v2/configuration/templates", params={"kernel_id": kernels[0]}).json()
        assert {item["id"] for item in filtered["items"]} == {item["id"] for item in templates[:2]}
        assert len(filtered["builtins"]) == 1
        builtin = filtered["builtins"][0]
        assert builtin["spec"]["config"]["stp_facilitation_tau_s"] == 1.0
        assert builtin["kernel_id"] == builtin["spec"]["kernel_id"] == kernels[0]
        assert client.get("/api/v2/configuration/templates", params={"kernel_id": kernels[2]}).json()["builtins"] == []
        historical = client.get("/api/v2/configuration/templates", params={"kernel_id": "unified-associative"}).json()["builtins"]
        assert {item["id"] for item in historical} == {
            "labeled-feature-v1", "anonymous-sensory-v2", "anonymous-spatial-v3"}
        assert all(item["kernel_id"] == "unified-associative" for item in historical)
        labeled = next(item for item in historical if item["id"] == "labeled-feature-v1")
        assert labeled["spec"]["config"]["sensory_encoding"] == "legacy-labeled"
        assert labeled["original_preset"] == "labeled-feature-v1" and labeled["source_provenance"]["revision"]
        assert client.get("/api/v2/configuration/templates", params={"kernel_id": "unknown/1"}).status_code == 422
        cross_kernel = client.put("/api/v2/configuration/templates/" + templates[0]["id"], json={
            "name": "illegal changed kernel", "spec": specs[kernels[2]], "expected_revision": 1,
        })
        assert cross_kernel.status_code == 422
        versions_url = "/api/v2/configuration/templates/" + templates[0]["id"] + "/versions"
        assert len(client.get(versions_url).json()["items"]) == 1

        project = client.post("/api/v2/projects", json={"name": "source consistency"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        preset = client.put(root + "/configuration/defaults", json={"spec": specs[kernels[0]], "expected_revision": 0})
        assert preset.status_code == 200, preset.text
        wrong_sources = [
            {"kind": "factory", "kernel_id": kernels[1], "revision": 0},
            {"kind": "template", "id": templates[0]["id"], "revision": 1},
            {"kind": "project-preset", "project_id": project, "revision": preset.json()["revision"]},
            builtin["source"],
            {"kind": "explicit", "kernel_id": kernels[0]},
        ]
        for source in wrong_sources:
            denied = client.post(root + "/runs", json={"name": "wrong kernel", "spec": specs[kernels[2]],
                                                       "start_immediately": False, "creation_source": source})
            assert denied.status_code == 422 and "kernel differs" in denied.text, denied.text
        assert client.get(root + "/runs").json() == []
        # Provenance identifies a starting template, not a ban on same-kernel edits.
        modified = deepcopy(builtin["spec"])
        modified["config"]["stp_facilitation_tau_s"] = 2.0
        accepted = client.post(root + "/runs", json={"name": "edited builtin", "spec": modified,
            "start_immediately": False, "creation_source": builtin["source"]})
        assert accepted.status_code == 201, accepted.text
        assert accepted.json()["spec"]["config"]["stp_facilitation_tau_s"] == 2.0
        assert accepted.json()["creation_source"]["source_spec"]["config"]["stp_facilitation_tau_s"] == 1.0

        # Old cross-kernel revisions remain original evidence; new edits bind to
        # the current revision's kernel rather than rewriting either version.
        template_id = templates[0]["id"]
        with database.tx() as db:
            db.execute("UPDATE creation_templates SET spec=%s,revision=2 WHERE id=%s",
                       (Jsonb(specs[kernels[1]]), template_id))
            db.execute("INSERT INTO creation_template_versions(template_id,revision,name,spec,actor_id) "
                       "VALUES(%s,2,'historical cross-kernel revision',%s,%s)",
                       (template_id, Jsonb(specs[kernels[1]]), LOCAL_USER))
        result = client.put("/api/v2/configuration/templates/" + template_id,
                            json={"name": "same /3 kernel", "spec": specs[kernels[1]], "expected_revision": 2})
        assert result.status_code == 200, result.text
        versions = client.get(versions_url).json()["items"]
        assert [(item["revision"], item["kernel_id"]) for item in versions] == [
            (3, kernels[1]), (2, kernels[1]), (1, kernels[0])]
        accepted = client.post(root + "/runs", json={"name": "old revision source", "spec": specs[kernels[0]],
            "start_immediately": False, "creation_source": {"kind": "template", "id": template_id, "revision": 1}})
        assert accepted.status_code == 201, accepted.text


def test_template_from_saved_run_is_static_conflict_checked_and_receiptable(database, monkeypatch):
    import threemind_runtime

    def no_engine(*args, **kwargs):
        raise AssertionError("template operations must not initialize a consciousness")

    with TestClient(create_app(Settings(database_url=database.test_url, backend="reference"), database)) as client:
        project = client.post("/api/v2/projects", json={"name": "copy static configuration"}).json()["id"]
        spec = client.get("/api/v2/configuration/defaults").json()["spec"]
        spec |= {"study_id": str(uuid4()), "condition": "declared control", "block_seed": 38}
        run = database.create_run(project, "existing individual", spec)
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='running',metadata_revision=7,time_us=12345 WHERE id=%s", (run["id"],))
        run_url = f"/api/v2/projects/{project}/runs/{run['id']}"
        before = client.get(run_url).json()
        monkeypatch.setattr(threemind_runtime, "create_engine", no_engine)
        assert client.post(run_url + "/configuration-template", json={"name": "stale", "expected_metadata_revision": 6}).status_code == 409
        identity = str(uuid4())
        body = {"name": "source parameters", "expected_metadata_revision": 7}
        first = client.post(run_url + "/configuration-template", headers={HEADER: identity}, json=body)
        assert first.status_code == 201, first.text
        template = first.json()
        assert all(template["spec"][field] is None for field in ("study_id", "condition", "block_seed"))
        assert template["spec"]["config"] == before["spec"]["config"]
        assert template["source"] == {"kind": "run-configuration", "project_id": project,
                                      "run_id": str(run["id"]), "metadata_revision": 7}
        replay = client.post(run_url + "/configuration-template", headers={HEADER: identity}, json=body)
        assert replay.status_code == 201 and replay.json()["id"] == template["id"]
        assert replay.headers["X-ThreeMind-Replayed"] == "true"
        conflict = client.post(run_url + "/configuration-template", headers={HEADER: identity}, json=body | {"name": "different"})
        assert conflict.status_code == 409
        assert client.get(run_url).json() == before
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM jobs").fetchone()["n"] == 0
            assert db.execute("SELECT count(*) AS n FROM checkpoints").fetchone()["n"] == 0
        catalogue = {item["id"]: item for item in client.get("/api/v2/operations/catalog").json()["operations"]}
        assert catalogue["configuration.template_from_run"]["request_receipt"]
        assert not catalogue["configuration.template_from_run"]["human_confirmation"]


def test_template_copy_needs_platform_write_and_run_read_but_no_run_control(database):
    password = "isolated template reader password"
    administrator = permissions.enrich(database, {"id": LOCAL_USER})
    permissions.actor_context.set(administrator)
    project = database.create_project(administrator, "not a member")
    from threemind_lab.platform_configuration import factory
    run = database.create_run(project["id"], "readable source", factory())
    reader = permissions.save_role(database, administrator, key="template-source-reader", name="source reader",
        grants=[{"action": "runs.read", "scope": "all_projects"},
                {"action": "system.write", "scope": "platform"}])
    user = auth.create_user(database, "template-copy-reader", password, role_ids=[reader["id"]])
    read_only = permissions.save_role(database, administrator, key="template-read-without-save", name="read only",
        grants=[{"action": "runs.read", "scope": "all_projects"}])
    write_only = permissions.save_role(database, administrator, key="template-save-without-source", name="write only",
        grants=[{"action": "system.write", "scope": "platform"}])
    permissions.actor_context.set(None)
    with TestClient(create_app(Settings(database_url=database.test_url, authentication="session", backend="reference"), database)) as client:
        login = client.post("/api/v2/login", json={"username": user["username"], "password": password})
        assert login.status_code == 200, login.text
        headers = {"X-CSRF-Token": login.json()["csrf"], HEADER: str(uuid4())}
        url = f"/api/v2/projects/{project['id']}/runs/{run['id']}/configuration-template"
        body = {"name": "shared copied configuration", "expected_metadata_revision": 0}
        allowed = client.post(url, json=body, headers=headers)
        assert allowed.status_code == 201, allowed.text
        # Revocation is checked before an old success can be replayed.
        permissions.actor_context.set(administrator)
        permissions.assign_roles(database, administrator, user["id"], [read_only["id"]])
        assert client.post(url, json=body, headers=headers).status_code in (401, 403)
        login = client.post("/api/v2/login", json={"username": user["username"], "password": password})
        headers["X-CSRF-Token"] = login.json()["csrf"]
        assert client.post(url, json=body, headers=headers).status_code == 403
        permissions.actor_context.set(administrator)
        permissions.assign_roles(database, administrator, user["id"], [write_only["id"]])
        login = client.post("/api/v2/login", json={"username": user["username"], "password": password})
        headers["X-CSRF-Token"] = login.json()["csrf"]
        denied = client.post(url, json=body, headers={**headers, HEADER: str(uuid4())})
        assert denied.status_code == 403
