import copy
import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from test_ai_providers import chat_response, create, get_call, setup

from threemind_lab import world_ai, worlds
from threemind_lab.ai_worker import AIWorker
from threemind_lab.api import create_app
from threemind_lab.database import LOCAL_USER, Conflict, NotFound
from threemind_lab.world_api import WorldEdit
from threemind_runtime.world_schema import default_world


def request(database):
    settings, project = setup(database)
    provider = create(database, settings, project)
    base = default_world().model_dump(mode="json")
    scope = {"objective": "增加一个可离屏工作的低分辨率眼睛，只构造物理条件。", "world_protocol": base}
    preview = world_ai.prepare(scope)
    body = scope | {
        "operation_id": str(uuid4()),
        "provider_id": str(provider["id"]),
        "evidence_hash": preview["evidence_hash"],
    }
    call = world_ai.request(database, settings, project, LOCAL_USER, body)
    proposed = copy.deepcopy(base)
    proposed["sensors"].append(
        {
            "id": "eye",
            "kind": "camera_rgb",
            "port": 6,
            "body_id": "body",
            "position": [0, 0, 1],
            "width": 4,
            "height": 4,
        }
    )
    proposal = {
        "rationale": "用实际物理成像作为外部感官。",
        "limitations": ["低分辨率与本机成像；不能据此推断意识。"],
        "protocol": proposed,
    }
    return settings, project, provider, body, call, preview, proposal


def reply(database, settings, proposal, sent=None):
    def response(message):
        if sent is not None:
            sent.append(json.loads(message.content))
        return chat_response(proposal if isinstance(proposal, str) else json.dumps(proposal))

    return AIWorker(database, settings, transport=httpx.MockTransport(response))


def test_world_ai_freezes_transmitted_scope_and_records_only_a_reviewable_proposal(database):
    settings, project, _provider, body, call, preview, proposed = request(database)
    assert not preview["evidence"]["contains_model_state_or_research_measurements"]
    assert world_ai.request(database, settings, project, LOCAL_USER, body)["id"] == call["id"]
    with pytest.raises(Conflict):
        world_ai.request(database, settings, project, LOCAL_USER, body | {"objective": "不同范围"})
    with pytest.raises(Conflict, match="预览不一致"):
        world_ai.request(
            database, settings, project, LOCAL_USER, body | {"operation_id": str(uuid4()), "evidence_hash": "0" * 64}
        )
    old = {"queue": "ai", "features": {"worker.ai": {"state": "available"}}}
    assert database.claim("old-world-worker", queue="ai", capabilities=old) is None
    sent = []
    worker = reply(database, settings, proposed, sent)
    assert worker.once()
    done = get_call(database, project, call)
    result = done["result"]
    assert result["application_status"] == "proposed", result
    assert result["review_status"] == "unreviewed" and not result["world_created"] and not result["run_created"]
    assert "worker.world_rgb_v1" in result["required_capabilities"]
    assert any(c["path"] == "sensors.eye.kind" and not c["before_present"] for c in result["changes"])
    assert sent[0]["messages"][1]["content"] == preview["prompt"]["user"]
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM world_documents").fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM runs").fetchone()["n"] == 0
        db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (done["job_id"],))
    assert worker.once() and len(sent) == 1  # Lost application acknowledgment cannot resend a paid request.
    adopted = copy.deepcopy(result["protocol"])
    adopted["label"] = "人工审阅后调整的世界"
    edit = WorldEdit(operation_id=uuid4(), protocol=adopted, ai_call_id=call["id"])
    saved = worlds.save(database, project, LOCAL_USER, edit)
    assert saved["ai_call_id"] == call["id"] and saved["ai_protocol_hash"] == result["protocol_hash"]
    assert saved["protocol_hash"] != saved["ai_protocol_hash"]
    assert worlds.save(database, project, LOCAL_USER, edit)["revision"] == 1
    other = database.create_project({"id": LOCAL_USER}, "Isolated adoption")["id"]
    with pytest.raises(NotFound):
        worlds.save(
            database, other, LOCAL_USER, WorldEdit(operation_id=uuid4(), protocol=adopted, ai_call_id=call["id"])
        )
    with database.tx(other) as db:
        assert db.execute("SELECT count(*) AS n FROM world_documents").fetchone()["n"] == 0


@pytest.mark.parametrize("kind", ["script", "duplicate", "reference", "cancel", "truncated"])
def test_invalid_or_cancelled_world_proposals_never_create_worlds_or_runs(database, kind):
    settings, project, _provider, _body, call, _preview, proposal = request(database)
    if kind == "script":
        proposal["protocol"]["script"] = "do not execute"
    elif kind == "duplicate":
        proposal = '{"rationale":"a","rationale":"b"}'
    elif kind == "reference":
        proposal["protocol"]["sensors"][-1]["body_id"] = "missing"
    elif kind == "cancel":
        with TestClient(create_app(settings, database)) as client:
            assert client.post(f"/api/v2/projects/{project}/ai/calls/{call['id']}/cancel").status_code == 200
    if kind == "truncated":
        worker = AIWorker(
            database,
            settings,
            transport=httpx.MockTransport(lambda _: chat_response(json.dumps(proposal), finish="length")),
        )
    else:
        worker = reply(database, settings, proposal)
    assert worker.once()
    done = get_call(database, project, call)
    assert done["status"] in ("failed", "cancelled") or done["result"]["application_status"] == "rejected"
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM world_documents").fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM runs").fetchone()["n"] == 0


def test_world_ai_api_uses_same_preview_hash_and_versioned_diff(database):
    settings, project = setup(database)
    provider = create(database, settings, project)
    scope = {"objective": "仅调整观察名称", "world_protocol": default_world().model_dump(mode="json")}
    with TestClient(create_app(settings, database)) as client:
        base = f"/api/v2/projects/{project}/worlds"
        preview = client.post(base + "/ai/preview", json=scope)
        assert preview.status_code == 200, preview.text
        body = scope | {
            "operation_id": str(uuid4()),
            "provider_id": str(provider["id"]),
            "evidence_hash": preview.json()["evidence_hash"],
        }
        generated = client.post(base + "/ai/requests", json=body)
        assert generated.status_code == 202, generated.text
        assert client.post(base + "/ai/requests", json=body).json()["id"] == generated.json()["id"]
    reordered = copy.deepcopy(scope["world_protocol"])
    for group in ("bodies", "geometries", "joints", "motors", "sensors", "forces"):
        reordered[group].reverse()
    assert world_ai.differences(scope["world_protocol"], reordered) == []
