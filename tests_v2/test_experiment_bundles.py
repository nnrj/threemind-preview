import hashlib
from uuid import uuid4

import pytest
from test_api import client_for
from test_research_operations import advance, fixture
from test_research_plans import start

from threemind_lab import research_plans
from threemind_lab.database import LOCAL_USER
from threemind_lab.research_commands import StageProtocol
from threemind_lab.worker import Worker


def completed(database, worker, project, response):
    assert response.status_code in (201, 202), response.text
    assert worker.once()
    with database.tx(project) as db:
        job = db.execute("SELECT * FROM jobs WHERE id=%s", (response.json()["id"],)).fetchone()
    assert job["status"] == "done", job.get("error")
    return job["result"]


@pytest.mark.parametrize("kernel_id", [None, "threemind.continuous-memory/5.1"])
def test_bundle_restores_pending_delivery_and_stage_cursor_without_fork_reset(database, kernel_id):
    with client_for(database) as client:
        project, run_id, _, _ = fixture(database, client, kernel_id=kernel_id)
        base = f"/api/v2/projects/{project}"
        worker = Worker(database)
        advance(database, project, run_id, 1, duration_us=2000)
        assert worker.once()
        row = database.get_run(project, run_id)
        protocol = StageProtocol(
            mode="manual",
            stages=[
                {
                    "name": "retained clock",
                    "repeat": 3,
                    "steps": [{"command": "runtime.wait", "parameters": {"duration_us": 1000}}],
                }
            ],
        )
        plan = research_plans.create(
            database,
            project,
            run_id,
            LOCAL_USER,
            name="cursor",
            protocol=protocol.model_dump(),
            request_id=uuid4(),
            expected_revision=row["revision"],
        )
        start(database, project, run_id, plan)
        assert worker.once()
        row = database.get_run(project, run_id)
        result = completed(
            database,
            worker,
            project,
            client.post(
                f"{base}/runs/{run_id}/bundles", json={"name": "pending signal", "expected_revision": row["revision"]}
            ),
        )
        bundle_id = result["bundle_id"]
        detail = client.get(f"{base}/bundles/{bundle_id}").json()
        assert detail["compatibility"]["can_resume"], detail["compatibility"]
        raw = client.get(f"{base}/bundles/{bundle_id}/download").content
        assert hashlib.sha256(raw).hexdigest() == detail["sha256"]
        before = client.get(f"{base}/bundles/{bundle_id}/entry", params={"name": "plans.json"}).json()
        assert before["value"][0]["next_step"] == 1
        # A real upload/verification roundtrip remains read-only until an explicit resume.
        request_id = str(uuid4())
        upload = client.post(
            f"{base}/bundle-uploads",
            json={"request_id": request_id, "name": "import", "bytes": len(raw), "sha256": detail["sha256"]},
        )
        assert upload.status_code == 201, upload.text
        uid = upload.json()["id"]
        chunk = client.put(
            f"{base}/bundle-uploads/{uid}/chunks/0", content=raw, headers={"Content-Type": "application/octet-stream"}
        )
        assert chunk.status_code == 200, chunk.text
        assert client.put(f"{base}/bundle-uploads/{uid}/chunks/0", content=raw).json()["replayed"]
        imported = completed(database, worker, project, client.post(f"{base}/bundle-uploads/{uid}/complete"))
        assert imported["mode"] == "read_only"
        resumed = completed(
            database,
            worker,
            project,
            client.post(
                f"{base}/bundles/{imported['bundle_id']}/resumes",
                json={"name": "continued new identity", "request_id": str(uuid4())},
            ),
        )
        other = resumed["run_id"]
        assert str(other) != str(run_id)
        cp_a, a = database.load_checkpoint(project, run_id)
        cp_b, b = database.load_checkpoint(project, other)
        assert a.digest == b.digest
        assert cp_a["context"]["next_observation_us"] == cp_b["context"]["next_observation_us"]
        for subject, pid in ((run_id, plan["id"]), (other, resumed["plan_ids"][0])):
            for _ in range(2):
                with database.tx(project) as db:
                    current = research_plans.get(db, subject, pid)
                start(database, project, subject, current)
                assert worker.once()
            with database.tx(project) as db:
                current = research_plans.get(db, subject, pid)
                delivered = db.execute(
                    "SELECT count(*) n FROM input_frames WHERE run_id=%s AND status='delivered'", (subject,)
                ).fetchone()["n"]
            assert current["status"] == "completed" and current["next_step"] == 3
            assert delivered == 2
        _, a = database.load_checkpoint(project, run_id)
        _, b = database.load_checkpoint(project, other)
        assert a.digest == b.digest
        assert int(a.to_dict()["time_us"]) == 5000


def test_bundle_missing_context_is_read_only_and_upload_hash_mismatch_cannot_resume(database):
    with client_for(database) as client:
        project, run_id, _, _ = fixture(database, client)
        base, worker = f"/api/v2/projects/{project}", Worker(database)
        result = completed(
            database, worker, project, client.post(f"{base}/runs/{run_id}/bundles", json={"expected_revision": 1})
        )
        bundle = client.get(f"{base}/bundles/{result['bundle_id']}").json()
        assert not bundle["compatibility"]["can_resume"]
        assert (
            client.post(
                f"{base}/bundles/{result['bundle_id']}/resumes", json={"name": "refused", "request_id": str(uuid4())}
            ).status_code
            == 409
        )
        upload = client.post(
            f"{base}/bundle-uploads", json={"request_id": str(uuid4()), "name": "bad", "bytes": 3, "sha256": "0" * 64}
        ).json()
        assert client.put(f"{base}/bundle-uploads/{upload['id']}/chunks/0", content=b"bad").status_code == 200
        response = client.post(f"{base}/bundle-uploads/{upload['id']}/complete")
        assert worker.once()
        with database.tx(project) as db:
            row = db.execute("SELECT * FROM jobs WHERE id=%s", (response.json()["id"],)).fetchone()
        assert row["status"] == "failed" and "校验失败" in row["error"]


def test_pending_media_and_text_keep_carriers_and_result_after_resume(database):
    from test_media_v2 import png, protocol

    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "pending media bundle"}).json()["id"]
        base = f"/api/v2/projects/{p}"
        run = client.post(base + "/runs", json={"name": "source", "spec": protocol()}).json()
        url, worker = base + f"/runs/{run['id']}", Worker(database)
        assert client.post(url + "/commands", json={"kind": "pause"}).status_code == 200
        assert worker.once()
        original = database.get_run(p, run["id"])
        assert original["status"] == "paused"
        media = client.post(
            url + "/media",
            params={"kind": "image", "filename": "retina.png", "request_id": str(uuid4())},
            content=png(),
        )
        assert media.status_code == 202, media.text
        text = client.post(
            url + "/inputs",
            json={"request_id": str(uuid4()), "adapter_id": "text-sensor", "payload": {"text": "原样。"}},
        )
        assert text.status_code == 202, text.text
        saved = completed(
            database, worker, p, client.post(url + "/bundles", json={"expected_revision": original["revision"]})
        )
        clone = completed(
            database,
            worker,
            p,
            client.post(
                base + f"/bundles/{saved['bundle_id']}/resumes", json={"name": "clone", "request_id": str(uuid4())}
            ),
        )
        for subject in (run["id"], clone["run_id"]):
            assert client.post(base + f"/runs/{subject}/commands", json={"kind": "resume"}).status_code == 200
            assert worker.once()
            with database.tx(p) as db:
                carriers = db.execute(
                    "SELECT payload,status FROM input_envelopes WHERE run_id=%s ORDER BY adapter_id", (subject,)
                ).fetchall()
            assert all(c["status"] == "completed" for c in carriers)
        _, first = database.load_checkpoint(p, run["id"])
        _, second = database.load_checkpoint(p, clone["run_id"])
        assert first.digest == second.digest
