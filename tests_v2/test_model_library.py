from uuid import uuid4

import pytest
from test_api import client_for

from threemind_core import Stimulus
from threemind_lab import auth, model_library
from threemind_lab.configuration import default_spec
from threemind_lab.worker import Worker
from threemind_runtime import create_engine


def fixture(client, database):
    project = client.post("/api/v2/projects", json={"name": "Model archive validation"}).json()["id"]
    spec = default_spec() | {"environment": "manual", "clock": "unbounded", "duration_s": 0.03}
    run = database.create_run(project, "原始意识", spec)
    engine = create_engine()
    engine.inject(Stimulus(0, ((1, 0.8), (2, 0.7), (3, 0.4))))
    engine.advance_to(1)
    state = engine.capture_state()
    previous = None
    for revision in range(3):
        cp = database.save_checkpoint(
            project,
            run["id"],
            state,
            expected_revision=revision,
            context={"protocol": spec},
            previous=previous,
            status="completed",
        )
        previous = (cp, state.to_dict())
    assert cp["storage_format"] == "row-delta/1"
    return project, str(run["id"]), f"/api/v2/projects/{project}/runs/{run['id']}", cp, state


def annotate(client, url, **changes):
    row = client.get(url).json()
    return client.patch(
        url + "/metadata",
        json={
            "name": row["name"],
            "description": row["description"],
            "tags": row["tags"],
            "archived": bool(row["archived_at"]),
            "expected_metadata_revision": row["metadata_revision"],
            **changes,
        },
    )


def test_annotations_are_separate_from_core_state_and_searchable_with_history(database):
    with client_for(database) as client:
        project, run, url, cp, state = fixture(client, database)
        root = f"/api/v2/projects/{project}"
        saved = annotate(client, url, name="触觉条件 甲", description="需要研究的对照对象", tags=["触觉", "对照"])
        assert saved.status_code == 200, saved.text
        assert saved.json()["metadata_revision"] == 1 and saved.json()["revision"] == 3
        assert database.load_checkpoint(project, run)[1].digest == state.digest
        rows = client.get(root + "/model-library?q=条件&tag=对照&status=completed").json()["rows"]
        assert len(rows) == 1 and rows[0]["name"] == "触觉条件 甲"
        assert "spec" not in rows[0]  # No complete runtime/configuration snapshots in library summaries.
        body = {
            "label": "稳定的触觉基线",
            "notes": "使用这个状态做后续比较。",
            "tags": ["基线"],
            "pinned": True,
            "expected_metadata_revision": 0,
        }
        response = client.patch(url + f"/versions/{cp['id']}/metadata", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["metadata_revision"] == 1
        assert client.patch(url + f"/versions/{cp['id']}/metadata", json=body).status_code == 409
        versions = client.get(url + "/versions?q=触觉&tag=基线&pinned=true&limit=1").json()
        assert versions["rows"][0]["id"] == str(cp["id"])
        assert database.load_checkpoint(project, run)[1].digest == state.digest
        history = client.get(url + "/metadata-history?limit=1").json()
        assert history["more"] and history["rows"][0]["after_value"]["pinned"]
        assert len(client.get(url + f"/metadata-history?before={history['next']}").json()["rows"]) == 1
        import io
        import json
        import zipfile

        annotations = [json.loads(line) for line in client.get(url + "/metadata-export").text.splitlines()]
        assert annotations[0]["run"]["name"] == "触觉条件 甲"
        assert len([r for r in annotations[1:] if r["kind"] == "checkpoint"]) == 3
        exported = client.post(url + "/exports", json={"format": "evidence", "checkpoint_id": str(cp["id"])}).json()
        assert any("未完成任务" in reason for reason in client.get(url + "/cleanup-preview").json()["reasons"])
        assert Worker(database).once()
        job = next(j for j in client.get(root + "/jobs").json() if j["id"] == exported["id"])
        assert job["status"] == "done", job.get("error")
        with zipfile.ZipFile(
            io.BytesIO(client.get(root + "/artifacts/" + job["result"]["artifact_id"]).content)
        ) as archive:
            annotations = json.loads(archive.read("annotations.json"))
            assert annotations["checkpoint"]["label"] == "稳定的触觉基线"
            assert annotations["checkpoint"]["state_hash"] == state.digest
        assert annotate(client, url, tags=["重复", "重复"]).status_code == 422
        assert annotate(client, url, expected_metadata_revision=0).status_code == 409
        assert annotate(client, url, archived=True).status_code == 200
        assert client.get(root + "/runs").json() == []
        assert len(client.get(root + "/runs?include_archived=true").json()) == 1
        assert client.get(root + "/model-library?archived=archived").json()["rows"][0]["id"] == run
        plan = client.get(url + "/cleanup-preview").json()
        assert not plan["allowed"] and any("已保留" in reason for reason in plan["reasons"])
        assert annotate(client, url, archived=False).status_code == 200
        assert len(client.get(root + "/runs").json()) == 1


def test_metadata_conflicts_with_stale_configuration_title_and_tracks_exact_fork_origin(database):
    with client_for(database) as client:
        project, run, url, cp, state = fixture(client, database)
        child = client.post(
            url + "/forks", json={"name": "历史状态分支", "checkpoint_id": str(cp["id"]), "inherit": False}
        )
        assert child.status_code == 201, child.text
        assert child.json()["origin_checkpoint_id"] == str(cp["id"])
        child_url = f"/api/v2/projects/{project}/runs/{child.json()['id']}"
        client.post(child_url + "/commands", json={"kind": "pause"})
        assert Worker(database).once()
        baseline = client.get(child_url).json()
        assert baseline["status"] == "paused"
        assert annotate(client, child_url, name="已经重新命名").status_code == 200
        config = {
            "name": "过期标题",
            "spec": baseline["spec"],
            "expected_revision": baseline["revision"],
            "expected_metadata_revision": 0,
        }
        assert client.put(child_url + "/configuration", json=config).status_code == 409
        assert client.get(child_url).json()["name"] == "已经重新命名"
        accepted = client.put(
            child_url + "/configuration", json=config | {"name": "配置编辑中的名称", "expected_metadata_revision": 1}
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["metadata_revision"] == 2
        assert client.get(child_url + "/lineage").json()["ancestors"][0]["origin_revision"] == 3
        children = client.get(url + "/lineage").json()["children"]
        assert len(children) == 1 and children[0]["origin_kind"] == "fork"
        assert database.load_checkpoint(project, run)[1].digest == state.digest
        assert annotate(client, url, archived=True).status_code == 200
        plan = client.get(url + "/cleanup-preview").json()
        assert not plan["allowed"] and any("后代" in reason for reason in plan["reasons"])
        # Old hash-only origins remain explicitly unknown rather than guessing a checkpoint.
        old = database.create_run(project, "早期分支", baseline["spec"], parent_id=run, origin_hash=state.digest)
        chain = client.get(f"/api/v2/projects/{project}/runs/{old['id']}/lineage").json()["ancestors"][0]
        assert chain["origin_kind"] is None and chain["origin_checkpoint_id"] is None


def test_cleanup_is_reviewed_atomic_and_preserves_shared_carrier_assets(database, monkeypatch):
    from test_media_v2 import png, protocol

    from threemind_lab.media_store import accept

    with client_for(database) as client:
        project, run, url, _cp, state = fixture(client, database)
        actor = {"id": "00000000-0000-4000-8000-000000000001"}
        other = database.create_run(project, "共享同一原件", protocol())
        # Same prepared carrier in two separate subjects; only one binary original is stored.
        carriers = []
        raw = png()
        for subject in (run, str(other["id"])):
            with database.tx(project) as db:
                db.execute(
                    "UPDATE runs SET status='paused',spec=%s WHERE id=%s", (model_library.Jsonb(protocol()), subject)
                )
            item = accept(
                database, project, subject, actor, raw, kind="image", filename="shared.png", request_id=uuid4()
            )
            carriers.append(item)
            with database.tx(project) as db:
                db.execute("UPDATE runs SET status='completed' WHERE id=%s", (subject,))
        assert annotate(client, url, archived=True).status_code == 200
        plan = client.get(url + "/cleanup-preview").json()
        assert plan["allowed"] and plan["unshared_media"]["n"] == 0
        body = {"token": plan["token"], "confirm_name": plan["name"]}
        assert client.post(url + "/cleanup", json=body | {"confirm_name": "错误名称"}).status_code == 409
        assert annotate(client, url, description="预览后的修改").status_code == 200
        assert client.post(url + "/cleanup", json=body).status_code == 409
        plan = client.get(url + "/cleanup-preview").json()
        body = {"token": plan["token"], "confirm_name": plan["name"]}
        original_jsonb = model_library.Jsonb

        def fail_receipt(value):
            if "reclaimed_media_bytes" in value:
                raise RuntimeError("injected cleanup receipt failure")
            return original_jsonb(value)

        with monkeypatch.context() as patch:
            patch.setattr(model_library, "Jsonb", fail_receipt)
            with pytest.raises(RuntimeError, match="receipt failure"):
                client.post(url + "/cleanup", json=body)
        assert database.load_checkpoint(project, run)[1].digest == state.digest
        assert client.get(url + "/inputs/" + str(carriers[0]["id"])).status_code == 200
        result = client.post(url + "/cleanup", json=body)
        assert result.status_code == 200, result.text
        assert result.json()["reclaimed_media_bytes"] == 0
        assert client.get(url).status_code == 404
        other_url = f"/api/v2/projects/{project}/runs/{other['id']}"
        assert client.get(other_url + "/inputs/" + str(carriers[1]["id"])).status_code == 200
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM media_assets").fetchone()["n"] == 1
            assert db.execute("SELECT count(*) AS n FROM checkpoints WHERE run_id=%s", (run,)).fetchone()["n"] == 0
        assert annotate(client, other_url, archived=True).status_code == 200
        plan = client.get(other_url + "/cleanup-preview").json()
        assert plan["unshared_media"]["n"] == 1
        result = client.post(other_url + "/cleanup", json={"token": plan["token"], "confirm_name": plan["name"]})
        assert result.status_code == 200, result.text
        assert result.json()["reclaimed_media_bytes"] == len(raw)
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM media_assets").fetchone()["n"] == 0
        history = client.get(f"/api/v2/projects/{project}/cleanup-history").json()
        assert len(history["rows"]) == 2


def test_archive_guards_project_isolation_and_viewer_permissions(database):
    with client_for(database) as client:
        project, run, url, cp, _ = fixture(client, database)
        foreign = client.post("/api/v2/projects", json={"name": "Foreign archive"}).json()["id"]
        assert client.get(url.replace(project, foreign) + "/versions").status_code == 404
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='paused' WHERE id=%s", (run,))
        assert annotate(client, url, archived=True).status_code == 409
        with database.tx(project) as db:
            db.execute(
                "UPDATE runs SET status='completed',spec=spec||%s WHERE id=%s",
                (model_library.Jsonb({"study_id": str(uuid4())}), run),
            )
        assert annotate(client, url, archived=True).status_code == 200
        assert any("冻结实验" in reason for reason in client.get(url + "/cleanup-preview").json()["reasons"])
        assert (
            len(
                client.get(
                    f"/api/v2/projects/{project}/runs?study_id=" + client.get(url).json()["spec"]["study_id"]
                ).json()
            )
            == 1
        )
    viewer = auth.create_user(database, "archive-viewer", "isolated archive viewer password")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        login = client.post(
            "/api/v2/login", json={"username": "archive-viewer", "password": "isolated archive viewer password"}
        )
        headers = {"X-CSRF-Token": login.json()["csrf"]}
        assert client.get(url + "/versions").status_code == 200
        assert client.get(url.replace(project, foreign) + "/lineage").status_code == 403
        assert (
            client.patch(
                url + "/metadata", json={"name": "Denied", "expected_metadata_revision": 1}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.patch(
                url + f"/versions/{cp['id']}/metadata", json={"expected_metadata_revision": 0}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.post(
                url + "/cleanup", json={"token": "0" * 64, "confirm_name": "原始意识"}, headers=headers
            ).status_code
            == 403
        )
