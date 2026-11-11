import json
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from test_ai_providers import chat_response, create, get_call
from test_research_documents import capture, save_body, setup

from threemind_lab import ai_tools, report_sources, research_ai, research_documents
from threemind_lab.ai_worker import AIWorker
from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Conflict, NotFound
from threemind_lab.worker import Worker


def fixture(database):
    project, run, cp, engine = setup(database)
    source, _ = capture(database, project, run)
    settings = Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),))
    provider = create(database, settings, project)
    scope = {"kind": "record", "sources": [str(source["id"])], "objective": "比较刺激撤除前后的现象"}
    spec = research_documents.defaults(database, project, source["id"])
    spec["blocks"][-1]["markdown"] = "工程夹具；存在缺失，时间样本不是独立重复，不能据此断定意识。"
    return settings, project, run["id"], cp, engine.capture_state(), source, provider, scope, spec


def ask(database, settings, project, provider, scope):
    preview = research_ai.preview(database, project, LOCAL_USER, scope)
    body = scope | {
        "operation_id": str(uuid4()),
        "provider_id": str(provider["id"]),
        "evidence_hash": preview["evidence_hash"],
    }
    return research_ai.request(database, settings, project, LOCAL_USER, body), body, preview


def reply(database, settings, text, received=None):
    def respond(request):
        if received is not None:
            received.append(json.loads(request.content))
        return chat_response(text)

    return AIWorker(database, settings, transport=httpx.MockTransport(respond))


def test_generation_complete_evidence_idempotency_and_unreviewed_independent_document(database):
    settings, project, run, _cp, image, source, provider, scope, spec = fixture(database)
    call, body, preview = ask(database, settings, project, provider, scope)
    snapshot = preview["evidence"]["sources"][0]
    assert snapshot["statistics"]["activation"]["count"] == 78
    assert snapshot["statistics"]["activation"]["missing"] == 1
    assert snapshot["coverage"]["row_count"] == 79
    assert snapshot["coverage"]["legacy_commit_unknown_omitted"] == 1
    assert "protocol" not in snapshot["provenance"] and "replay" not in snapshot["provenance"]
    assert research_ai.request(database, settings, project, LOCAL_USER, body)["id"] == call["id"]
    with pytest.raises(Conflict):
        research_ai.request(database, settings, project, LOCAL_USER, body | {"objective": "改了范围"})
    with pytest.raises(Conflict):
        report_sources.release(database, project, LOCAL_USER, source["id"])
    old = {"queue": "ai", "features": {"worker.ai": {"state": "available"}}}
    assert database.claim("old-ai-worker", queue="ai", capabilities=old) is None
    received = []
    worker = reply(database, settings, json.dumps(spec), received)
    assert worker.once()
    done = get_call(database, project, call)
    result = done["result"]
    assert result["application_status"] == "recorded", result
    saved = research_documents.get(database, project, result["document_id"])
    assert saved["review"] == "draft" and saved["ai_call_id"] == call["id"]
    assert saved["content_revision"] == 1
    assert research_documents.render(database, project, result["document_id"])["ai_call_id"] == str(call["id"])
    from threemind_lab.report_publication import content_nodes

    nodes, _, _ = content_nodes(saved, {"blocks": [], "sources": {}}, {"language": "zh-CN", "include_data": False})
    assert any("AI 辅助生成" in node.get("text", "") for node in nodes)
    assert len(received) == 1
    assert database.load_checkpoint(project, run)[1].digest == image.digest
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM input_envelopes WHERE run_id=%s", (run,)).fetchone()["n"] == 0
        db.execute("UPDATE jobs SET status='pending' WHERE id=%s", (done["job_id"],))
    assert worker.once() and len(received) == 1
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM research_documents").fetchone()["n"] == 1
    second, _, _ = ask(database, settings, project, provider, scope)
    assert worker.once()
    assert get_call(database, project, second)["result"]["document_id"] != result["document_id"]


def test_generation_rejects_fabrication_scope_changes_omissions_and_stale_preview(database, monkeypatch):
    settings, project, _run, _cp, _image, _source, provider, scope, spec = fixture(database)
    _, body, _ = ask(database, settings, project, provider, scope)
    assert reply(database, settings, '{"kind":"record","kind":"report"}').once()
    invalid = [
        spec | {"sources": []},
        spec | {"kind": "report"},
        spec | {"sources": [str(uuid4())]},
        spec
        | {
            "blocks": [
                {
                    "id": "fake",
                    "type": "table",
                    "source": scope["sources"][0],
                    "metrics": ["activation"],
                    "values": [10],
                }
            ]
        },
        spec | {"blocks": spec["blocks"][:-1]},
    ]
    for proposed in invalid:
        call, _, _ = ask(database, settings, project, provider, scope)
        assert reply(database, settings, json.dumps(proposed)).once()
        assert get_call(database, project, call)["result"]["application_status"] == "rejected"
    with database.tx(project) as db:
        assert db.execute("SELECT count(*) AS n FROM research_documents").fetchone()["n"] == 0
    with pytest.raises(Conflict, match="预览不一致"):
        research_ai.request(
            database, settings, project, LOCAL_USER, body | {"operation_id": str(uuid4()), "evidence_hash": "0" * 64}
        )
    monkeypatch.setattr(research_ai, "MAX_EVIDENCE_BYTES", 1)
    with pytest.raises(ValueError, match="摘要超过"):
        research_ai.preview(database, project, LOCAL_USER, scope)


def test_report_generation_pins_selected_record_revision_and_rejects_unprovided_blocks(database):
    settings, project, _run, _cp, _image, source, provider, _scope, spec = fixture(database)
    record = uuid4()
    research_documents.save(database, project, LOCAL_USER, record, save_body(spec))
    data = next(b for b in spec["blocks"] if b["type"] == "table")
    scope = {"kind": "report", "records": [{"record_id": str(record), "revision": 1, "block_ids": [data["id"]]}]}
    call, _, preview = ask(database, settings, project, provider, scope)
    original_hash = preview["evidence"]["records"][0]["content_hash"]
    research_documents.save(database, project, LOCAL_USER, record, save_body(spec | {"title": "之后改名"}, 1))
    proposal = {
        "kind": "report",
        "title": "报告",
        "sources": [str(source["id"])],
        "blocks": [
            {
                "id": "from-record",
                "type": "record_block",
                "record_id": str(record),
                "revision": 1,
                "block_id": data["id"],
            },
            {"id": "limits", "type": "commentary", "section": "limitations", "markdown": "有缺失，需要复核。"},
        ],
    }
    assert reply(database, settings, json.dumps(proposal)).once()
    done = get_call(database, project, call)
    assert done["result"]["application_status"] == "recorded", done["result"]
    rendered = research_documents.render(database, project, done["result"]["document_id"])
    assert rendered["blocks"][0]["record_hash"] == original_hash
    second, _, _ = ask(database, settings, project, provider, scope)
    proposal["blocks"][0]["block_id"] = spec["blocks"][0]["id"]
    assert reply(database, settings, json.dumps(proposal)).once()
    assert get_call(database, project, second)["result"]["application_status"] == "rejected"


def test_analysis_generation_keeps_all_endpoints_and_censored_pairs(database):
    from lease_helpers import claim_as

    from threemind_lab.statistics import compare_pairs

    settings, project, _run, _cp, _image, _source, provider, _scope, _spec = fixture(database)
    analysis = compare_pairs(
        [
            {
                "seed": i,
                "control": {"value": i, "unknown": None},
                "treatment": {"value": i - 0.5, "unknown": None},
                "phase_evidence": {"control": [{"complete": False, "settling": {"right_censored": True}}]},
            }
            for i in range(3)
        ],
        resamples=100,
    )
    database.enqueue(project, "analysis", {"study_id": str(uuid4())})
    job = claim_as(database, "analysis-fixture")
    artifact = database.put_artifact(job, "paired.json", "application/json", json.dumps(analysis).encode())
    database.finish(job, result={"artifact_id": str(artifact["id"])})
    capture_request = report_sources.request(
        database,
        project,
        LOCAL_USER,
        {"operation_id": str(uuid4()), "kind": "analysis", "analysis_artifact_id": str(artifact["id"])},
    )
    assert Worker(database).once()
    scope = {"kind": "record", "sources": [str(capture_request["id"])]}
    call, _, preview = ask(database, settings, project, provider, scope)
    summary = preview["evidence"]["sources"][0]
    assert summary["pair_evidence_coverage"]["pairs_with_right_censoring"] == 3
    assert summary["pair_evidence_coverage"]["pairs_with_incomplete_markers"] == 3
    assert summary["analysis"]["metrics"] == analysis["metrics"]
    assert "pairs" not in summary["analysis"] and summary["analysis"]["pair_count"] == 3
    spec = research_documents.defaults(database, project, capture_request["id"])
    spec["blocks"][-1]["markdown"] = "缺失终点不能补零，阶段有删失。"
    assert reply(database, settings, json.dumps(spec)).once()
    assert get_call(database, project, call)["result"]["application_status"] == "recorded"
    call, _, _ = ask(database, settings, project, provider, scope)
    spec["blocks"][1]["metrics"] = spec["blocks"][1]["metrics"][:1]
    assert reply(database, settings, json.dumps(spec)).once()
    assert "全部统计终点" in get_call(database, project, call)["result"]["error"]


def test_generation_api_authorization_cancellation_and_atomic_rollback(database, monkeypatch):

    settings, project, _run, _cp, _image, _source, provider, scope, spec = fixture(database)
    other = database.create_project({"id": LOCAL_USER}, "Other project")["id"]
    with pytest.raises(NotFound):
        research_ai.preview(database, other, LOCAL_USER, scope)
    with TestClient(create_app(settings, database)) as client:
        call, _, _ = ask(database, settings, project, provider, scope)
        worker = reply(database, settings, json.dumps(spec))
        capabilities = {
            "queue": "ai",
            "features": {
                name: {"state": "available"}
                for name in ("worker.ai", "worker.research_ai_v1", "worker.research_events_v1")
            },
        }
        job = database.claim("cancel-race", queue="ai", capabilities=capabilities)
        assert worker.run(job)["status"] == "completed"
        response = client.post(f"/api/v2/projects/{project}/ai/calls/{call['id']}/cancel")
        assert response.status_code == 200
        assert ai_tools.apply_completed(database, job)["application_status"] == "rejected"
        database.finish(job, result={"status": "completed"})
        next_call, _, _ = ask(database, settings, project, provider, scope)
        original = research_documents.save

        def broken(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("fault after document insert")

        monkeypatch.setattr(research_documents, "save", broken)
        assert worker.once()
        assert get_call(database, project, next_call)["result"]["application_status"] == "rejected"
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM research_documents").fetchone()["n"] == 0
        assert client.post(f"/api/v2/projects/{project}/research-generation/preview", json=scope).status_code == 200
    with TestClient(create_app(replace(settings, mode="server"), database)) as client:
        assert client.post(f"/api/v2/projects/{project}/research-generation/preview", json=scope).status_code == 401
