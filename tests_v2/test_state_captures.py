import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from lease_helpers import claim_as
from test_api import client_for

from threemind_lab import model_library, state_captures
from threemind_lab.database import LOCAL_USER
from threemind_lab.state_captures import CaptureRequest
from threemind_lab.worker import Worker
from threemind_runtime import create_engine


def setup(client):
    project = client.post("/api/v2/projects", json={"name": "命名捕获验证"}).json()["id"]
    root = f"/api/v2/projects/{project}"
    spec = {
        "environment": "replay",
        "clock": "unbounded",
        "duration_s": 0.02,
        "replay": [{"time_us": "0", "channels": [[1, 0.6], [2, 0.4]]}],
    }
    run = client.post(root + "/runs", json={"name": "实际意识", "spec": spec}).json()
    return project, root, run, root + "/runs/" + run["id"]


def body(**changes):
    return {"request_id": str(uuid4()), "label": "", "auto_name": "timestamp", "pinned": False, **changes}


def test_named_capture_real_worker_exact_receipt_no_core_change_and_retry(database):
    with client_for(database) as client:
        project, root, run, url = setup(client)
        assert Worker(database).once()
        baseline = database.load_checkpoint(project, run["id"])[1].digest
        other = client.post(root + "/runs", json={"name": run["name"], "spec": run["spec"]}).json()
        url = root + "/runs/" + other["id"]
        request = body(label="刺激撤除前的状态", pinned=True)
        received = client.post(url + "/state-captures", json=request)
        assert received.status_code == 202, received.text
        assert received.json()["status"] == "pending" and received.json()["checkpoint_id"] is None
        assert client.post(url + "/state-captures", json=request).json()["id"] == received.json()["id"]
        assert client.post(url + "/state-captures", json=body(label="second")).status_code == 409
        assert client.post(url + "/state-captures", json=request | {"label": "different"}).status_code == 409
        assert client.post(url + "/state-captures", json=body(pinned="false")).status_code == 422
        assert Worker(database).once()
        receipt = client.get(url + "/state-captures").json()["rows"][0]
        assert receipt["status"] == "completed", receipt
        cp, captured = database.load_checkpoint(project, other["id"], receipt["checkpoint_id"])
        assert cp["label"] == request["label"] and cp["pinned"] and cp["metadata_revision"] == 1
        assert cp["revision"] == receipt["result"]["revision"] and captured.digest == receipt["result"]["state_hash"]
        assert database.load_checkpoint(project, other["id"])[1].digest == baseline
        assert client.post(url + "/state-captures", json=request).json()["id"] == receipt["id"]
        assert client.post(url + "/state-captures", json=body()).status_code == 409
        assert client.get(url + "/versions?pinned=true").json()["rows"][0]["id"] == receipt["checkpoint_id"]
        stream = [json.loads(line) for line in client.get(url + "/metadata-export").text.splitlines()]
        assert any(r.get("kind") == "state_capture" and r["record"]["id"] == receipt["id"] for r in stream)
        other_project = client.post("/api/v2/projects", json={"name": "Other capture project"}).json()["id"]
        assert client.get(url.replace(project, other_project) + "/state-captures").status_code == 404
        assert (
            client.patch(
                url + "/metadata", json={"name": other["name"], "archived": True, "expected_metadata_revision": 0}
            ).status_code
            == 200
        )
        assert not client.get(url + "/cleanup-preview").json()["allowed"]
        assert (
            client.patch(
                url + f"/versions/{cp['id']}/metadata",
                json={"label": cp["label"], "pinned": False, "expected_metadata_revision": 1},
            ).status_code
            == 200
        )
        preview = client.get(url + "/cleanup-preview").json()
        assert preview["allowed"] and preview["counts"]["state_captures"] == 1
        assert (
            client.post(url + "/cleanup", json={"token": preview["token"], "confirm_name": other["name"]}).status_code
            == 200
        )
        with database.tx(project) as db:
            assert not db.execute("SELECT 1 FROM state_captures WHERE run_id=%s", (other["id"],)).fetchone()


def test_capture_atomic_annotation_rollback_precise_boundary_and_concurrent_idempotence(database, monkeypatch):
    with client_for(database) as client:
        project, _root, run, url = setup(client)
        request = CaptureRequest(**body(auto_name="revision"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(
                pool.map(lambda _: state_captures.submit(database, project, run["id"], LOCAL_USER, request), range(2))
            )
        assert receipts[0]["id"] == receipts[1]["id"]
        command = receipts[0]["command_id"]
        state = create_engine().capture_state()
        first = database.save_checkpoint(project, run["id"], state, expected_revision=0, last_command=0)
        assert first["label"] == ""
        original = model_library.update_metadata

        def fault(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("failure after annotation, before capture receipt")

        monkeypatch.setattr(model_library, "update_metadata", fault)
        kwargs = {"expected_revision": 1, "last_command": command}
        with pytest.raises(RuntimeError, match="after annotation"):
            database.save_checkpoint(project, run["id"], state, **kwargs)
        assert database.get_run(project, run["id"])["revision"] == 1
        assert client.get(url + "/state-captures").json()["rows"][0]["status"] == "pending"
        assert client.get(url + "/metadata-history").json()["rows"] == []
        monkeypatch.setattr(model_library, "update_metadata", original)
        cp = database.save_checkpoint(project, run["id"], state, **kwargs)
        assert cp["label"] == "实际意识 · r2" and cp["metadata_revision"] == 1
        assert database.save_checkpoint(project, run["id"], state, **kwargs)["id"] == cp["id"]
        receipt = client.get(url + "/state-captures").json()["rows"][0]
        assert receipt["result"]["label"] == "实际意识 · r2"
        assert len(client.get(url + "/metadata-history").json()["rows"]) == 1
        assert client.post(url + "/state-captures", json=body()).status_code == 202
        assert client.get(url + "/state-captures?limit=1").json()["next"] is not None
        assert (
            len(client.get(url + "/state-captures?limit=1&before=" + str(receipt["ordinal"] + 1)).json()["rows"]) == 1
        )
        pending = client.get(url + "/state-captures").json()["rows"][0]
        with database.tx(project) as db:
            db.execute("UPDATE runs SET name=%s WHERE id=%s", ("意识" * 60, run["id"]))
        dated = database.save_checkpoint(
            project, run["id"], state, expected_revision=2, last_command=pending["command_id"]
        )
        assert len(dated["label"]) == 120 and " · r3 · " in dated["label"] and dated["label"].endswith("Z")
        assert client.get(url + "/state-captures").json()["rows"][0]["result"]["label"] == dated["label"]


@pytest.mark.parametrize("reason", ["permission", "ended", "failure", "exhausted"])
def test_capture_failure_is_explicit_and_never_labels_an_old_checkpoint(database, reason):
    with client_for(database) as client:
        project, _root, run, url = setup(client)
        request = body(label="Do not attach to an old state")
        pending = client.post(url + "/state-captures", json=request).json()
        if reason == "permission":
            with database.tx(project) as db:
                db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (project, LOCAL_USER))
        if reason in ("failure", "exhausted"):
            job = claim_as(database, "capture-failure-worker")
            if reason == "failure":
                database.finish(job, error="known isolated failure")
            else:
                with database.tx() as db:
                    db.execute(
                        "UPDATE jobs SET attempts=5,lease_until=now()-interval '1 second' WHERE id=%s", (job["id"],)
                    )
                assert claim_as(database, "capture-recovery-worker") is None
        else:
            cp = database.save_checkpoint(
                project,
                run["id"],
                create_engine().capture_state(),
                expected_revision=0,
                last_command=pending["command_id"] if reason == "permission" else 0,
                status="completed",
            )
            assert database.load_checkpoint(project, run["id"], cp["id"])[0]["label"] == ""
        receipt = client.get(url + "/state-captures").json()["rows"][0]
        assert receipt["status"] == "failed" and receipt["checkpoint_id"] is None and receipt["error"]
        assert client.get(url + "/metadata-history").json()["rows"] == []
        if reason == "permission":
            assert client.post(url + "/state-captures", json=body()).status_code == 403
