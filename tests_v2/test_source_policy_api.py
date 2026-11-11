import json
from uuid import uuid4

from test_api import client_for

from threemind_lab import auth
from threemind_lab.worker import Worker


def test_admission_rechecks_unscheduled_carriers_but_preserves_core_promises(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Source policy evidence"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        worker = Worker(database)
        cases = []
        for scheduled in (False, True):
            spec = {
                "environment": "manual",
                "clock": "unbounded",
                "duration_s": 0.03,
                "config": {"attention_competition_enabled": True, "attention_budget": 1},
                "source_policies": {"ui_text_enabled": False, "cli_text_bypass_attention": True},
            }
            response = client.post(root + "/runs", json={"name": "Frozen" if scheduled else "Admission", "spec": spec})
            assert response.status_code == 201, response.text
            run = response.json()["id"]
            url = f"{root}/runs/{run}"
            client.post(url + "/commands", json={"kind": "pause"})
            assert worker.once()
            carrier = {
                "adapter_id": "text-sensor",
                "payload": {"text": "AB汉"},
                "request_id": str(uuid4()),
                "delay_us": 5000,
            }
            assert client.post(url + "/inputs", json=carrier).status_code == 409
            carrier["source_id"] = "cli-text"
            admitted = client.post(url + "/inputs", json=carrier)
            assert admitted.status_code == 202, admitted.text
            assert client.post(url + "/inputs", json=carrier | {"source_id": "ui-text"}).status_code == 409
            assert client.post(url + "/inputs", json=carrier | {"source_id": "ai-debug"}).status_code == 422
            if scheduled:
                client.post(url + "/commands", json={"kind": "pause"})
                client.post(url + "/commands", json={"kind": "resume"})
                assert worker.once()
            current = client.get(url).json()
            assert current["status"] == "paused", current.get("error")
            _, before = database.load_checkpoint(project, run)
            changed = current["spec"]
            changed["source_policies"]["cli_text_enabled"] = False
            changed["source_policies"]["cli_text_bypass_attention"] = False
            updated = client.put(
                url + "/configuration",
                json={
                    "name": current["name"],
                    "spec": changed,
                    "expected_revision": current["revision"],
                },
            )
            assert updated.status_code == 200, updated.text
            _, after = database.load_checkpoint(project, run)
            assert after.to_dict()["queue"] == before.to_dict()["queue"]
            if scheduled:
                assert before.to_dict()["queue"][0]["payload"]["bypass_attention"] is True
            # Idempotent acknowledgement is still retrievable after its source is disabled.
            assert client.post(url + "/inputs", json=carrier).json()["id"] == admitted.json()["id"]
            assert client.post(url + "/inputs", json=carrier | {"request_id": str(uuid4())}).status_code == 409
            client.post(url + "/commands", json={"kind": "resume"})
            assert worker.once()
            final = client.get(url).json()
            assert final["status"] == "completed", final.get("error")
            detail = client.get(url + "/inputs/" + carrier["request_id"]).json()
            frame = detail["frames"][0]
            assert frame["source_policy"]["key"] == "cli_text"
            assert frame["source_policy"]["enabled"] is scheduled
            assert frame["source_policy"]["resolved_at_us"] == "0"
            assert detail["envelope"]["payload"] == carrier["payload"]
            assert detail["envelope"]["configuration"]["source_policy_at_admission"]["enabled"] is True
            if scheduled:
                assert frame["status"] == "delivered" and frame["input_gate"]["competition_bypassed"]
                assert frame["input_gate"]["passed_channels"] > 1
            else:
                assert frame["status"] == "filtered" and frame["reason"] == "source_disabled"
                assert not database.load_checkpoint(project, run)[1].to_dict()["nodes"]
            exported = [
                json.loads(line) for line in client.get(url + "/inputs/export?records=frames").text.splitlines()
            ]
            assert exported[1]["source_policy"] == frame["source_policy"]
            assert client.get(url + "/source-policies").json()["configuration"]["cli_text_enabled"] is False
            cases.append(url)
        foreign = client.post("/api/v2/projects", json={"name": "Foreign policies"}).json()["id"]
        assert client.get(cases[0].replace(project, foreign) + "/source-policies").status_code == 404
    viewer = auth.create_user(database, "source-viewer", "isolated source viewer password")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        login = client.post(
            "/api/v2/login", json={"username": "source-viewer", "password": "isolated source viewer password"}
        )
        assert client.get(cases[0] + "/source-policies").status_code == 200
        assert client.get(cases[0].replace(project, foreign) + "/source-policies").status_code == 403
        assert (
            client.put(
                cases[0] + "/configuration",
                json={"name": "Denied", "spec": changed, "expected_revision": 0},
                headers={"X-CSRF-Token": login.json()["csrf"]},
            ).status_code
            == 403
        )


def test_sources_block_media_and_capture_before_processing_and_leave_device_output_independent(database):
    from test_devices import connect, packet, setup

    with client_for(database) as client:
        spec = {
            "environment": "manual",
            "clock": "realtime",
            "duration_s": 1,
            "auditory_sensor": {"enabled": True},
            "visual_sensor": {"enabled": True},
            "live_capture": {"microphone_enabled": True, "camera_enabled": True},
            "source_policies": {"manual_enabled": False, "background_enabled": False},
        }
        project, run, url, network, device = setup(client, spec=spec)
        for kind in ("audio", "image", "video"):
            response = client.post(
                url + "/media-uploads",
                json={
                    "request_id": str(uuid4()),
                    "filename": "disabled",
                    "kind": kind,
                    "byte_length": 999,
                },
            )
            assert response.status_code == 409, response.text
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM media_uploads WHERE run_id=%s", (run,)).fetchone()["n"] == 0
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
        for kind in ("audio", "video", "av"):
            response = client.post(
                url + "/capture",
                json={
                    "session_id": str(uuid4()),
                    "kind": kind,
                    "source_clock": {"physical_hardware": False},
                },
            )
            assert response.status_code == 409, response.text
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM capture_sessions WHERE run_id=%s", (run,)).fetchone()["n"] == 0
        hello = connect(client, network, device["token"])
        assert hello.status_code == 201, hello.text
        session = network + "/sessions/" + hello.json()["session"]["id"]
        headers = {"Authorization": "Bearer " + device["token"]}
        result = client.post(session + "/packets", headers=headers, json=packet())
        assert result.status_code == 409, result.text
        assert "source_category_disabled" in result.text
        output = client.get(session + "/output", headers=headers)
        assert output.status_code == 200, output.text


def test_source_gate_keeps_simulated_environment_time_and_explicit_filtered_evidence(database):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "Afferent isolation"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        response = client.post(
            root + "/runs",
            json={
                "name": "World without afferents",
                "spec": {
                    "environment": "ambient",
                    "clock": "unbounded",
                    "duration_s": 0.06,
                    "ambient_field": {"sample_us": 10000},
                    "source_policies": {"background_enabled": False},
                },
            },
        )
        assert response.status_code == 201, response.text
        run = response.json()["id"]
        assert Worker(database).once()
        final = client.get(f"{root}/runs/{run}").json()
        assert final["status"] == "completed", final.get("error")
        _, state = database.load_checkpoint(project, run)
        assert state.to_dict()["time_us"] == "60000" and not state.to_dict()["nodes"]
        rows = [
            json.loads(line) for line in client.get(f"{root}/runs/{run}/inputs/export?records=frames").text.splitlines()
        ]
        rows = rows[1:]
        assert len(rows) > 1 and max(int(row["scheduled_time_us"]) for row in rows) > 0
        assert all(row["status"] == "filtered" and row["reason"] == "source_category_disabled" for row in rows)
