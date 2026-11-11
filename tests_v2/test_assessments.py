import io
import json
from uuid import uuid4

import psycopg
import pytest
from pydantic import ValidationError
from test_api import client_for
from test_development import select, start

from threemind_lab.assessment_protocol import AssessmentProtocol, Criterion, summarize
from threemind_lab.configuration import default_spec
from threemind_lab.worker import Worker


def protocol(source):
    return {
        "source_version_id": source,
        "evaluation": default_spec()
        | {
            "environment": "ambient",
            "clock": "unbounded",
            "duration_s": 0.04,
            "checkpoint_us": 10000,
            "sample_us": 10000,
        },
        "environment_seeds": [1101, 1102],
        "criteria": [
            {"id": "alive", "metric": "not_dead_at_end", "threshold": 1},
            {"id": "scale", "metric": "nodes", "operator": "gte", "threshold": 100000},
        ],
    }


def prepared(client, database):
    project = client.post("/api/v2/projects", json={"name": "Independent assessment QA"}).json()["id"]
    base = f"/api/v2/projects/{project}"
    parent, _ = start(client, base)
    worker = Worker(database)
    assert worker.once()
    cp, image = database.load_checkpoint(project, parent["run_id"])
    version, _ = select(client, base, parent["run_id"], cp)
    request = {
        "operation_id": str(uuid4()),
        "name": "出生后独立评估",
        "objective": "功能验收，不是意识科学结论",
        "protocol": protocol(version["id"]),
    }
    response = client.post(base + "/assessments", json=request)
    assert response.status_code == 201, response.text
    return project, base, parent, image, request, response.json(), worker


def test_assessment_missing_failed_and_partial_bounds_are_not_success_rates():
    rule = Criterion(id="value", metric="nodes", threshold=2, required_fraction=0.75)
    trials = [
        {"values": {"nodes": 3}, "complete": True},
        {"values": {"nodes": 4}, "complete": False},
        {"values": {}, "complete": True},
        {"values": {"nodes": 1}, "complete": True},
    ]
    result = summarize(trials, [rule])[0]
    assert result["status"] == "undetermined" and result["undetermined"] == 2
    assert result["fraction_lower_bound"] == 0.25 and result["fraction_upper_bound"] == 0.75
    assert not result["bound_is_confidence_interval"]
    assert summarize(trials, [rule.model_copy(update={"required_fraction": 1})])[0]["status"] == "not_satisfied"
    assert summarize([], [rule])[0]["status"] == "undetermined"
    raw = protocol(str(uuid4()))
    for changes in (
        {"environment_seeds": [1, 1]},
        {"excluded_environment_seeds": [1101]},
        {"evaluation": raw["evaluation"] | {"duration_s": "1"}},
        {"evaluation": raw["evaluation"] | {"clock": "realtime"}},
        {"criteria": [{"id": "bad", "metric": "intelligence", "threshold": 1}]},
    ):
        with pytest.raises(ValidationError):
            AssessmentProtocol(**(raw | changes))


def test_independent_birth_capture_fixed_partial_sources_and_reports(database):
    with client_for(database) as client:
        project, base, parent, image, request, created, worker = prepared(client, database)
        root = base + "/assessments/" + created["id"]
        assert client.post(base + "/assessments", json=request).json()["id"] == created["id"]
        assert client.post(base + "/assessments", json=request | {"name": "changed"}).status_code == 409
        state = client.get(root).json()
        assert len(state["trials"]) == 2 and not state["all_trials_complete"]
        assert all(r["status"] == "undetermined" for r in state["criteria"])
        run_id = state["trials"][0]["run_id"]
        assert client.post(base + f"/runs/{run_id}/commands", json={"kind": "pause"}).status_code == 409
        assert (
            client.post(
                base + f"/runs/{run_id}/commands", json={"kind": "stimulus", "payload": {"channels": [[1, 1]]}}
            ).status_code
            == 409
        )
        partial_request = {"operation_id": str(uuid4()), "kind": "assessment", "assessment_id": created["id"]}
        partial = client.post(base + "/report-sources", json=partial_request)
        assert partial.status_code == 202, partial.text
        assert worker.once() and worker.once() and worker.once()
        fixed = client.get(base + "/report-sources/" + partial.json()["id"]).json()
        assert fixed["status"] == "done", fixed["error"]
        assert fixed["manifest"]["coverage"]["trials_complete"] == 0
        assert fixed["manifest"]["assessment"]["criteria"][0]["status"] == "undetermined"
        after = client.get(root).json()
        assert after["all_trials_complete"], after
        assert [r["status"] for r in after["criteria"]] == ["satisfied", "not_satisfied"]
        assert all(r["lifetime_right_censored"] for r in after["trials"])
        assert image.digest == database.load_checkpoint(project, parent["run_id"])[1].digest
        for trial in after["trials"]:
            with database.tx(project) as db:
                born = db.execute(
                    "SELECT payload FROM events WHERE run_id=%s AND kind='development_birth'", (trial["run_id"],)
                ).fetchone()
                assert born["payload"]["source_hash"] == image.digest
                assert (
                    db.execute(
                        "SELECT count(*) AS n FROM innate_versions WHERE run_id=%s", (trial["run_id"],)
                    ).fetchone()["n"]
                    == 0
                )
        complete_request = partial_request | {"operation_id": str(uuid4())}
        complete = client.post(base + "/report-sources", json=complete_request).json()
        assert worker.once()
        captured = client.get(base + "/report-sources/" + complete["id"]).json()
        assert captured["manifest"]["assessment"]["criteria"][1]["status"] == "not_satisfied"
        assert captured["manifest"]["coverage"]["trials_complete"] == 2
        template = client.get(base + f"/report-sources/{complete['id']}/template").json()
        assert "blocks" in template, template
        preview = client.post(base + "/research-documents/preview", json=template)
        assert preview.status_code == 200, preview.text
        assert client.post(base + "/report-sources", json=partial_request).json()["id"] == partial.json()["id"]
        second = client.post("/api/v2/projects", json={"name": "Foreign assessment QA"}).json()["id"]
        assert client.get(f"/api/v2/projects/{second}/assessments/{created['id']}").status_code == 404
        with database.tx(second) as db:
            assert db.execute("SELECT count(*) AS n FROM assessment_batches").fetchone()["n"] == 0
        with pytest.raises(psycopg.Error), database.tx(project) as db:
            db.execute("UPDATE assessment_members SET environment_seed=999 WHERE batch_id=%s", (created["id"],))
        with pytest.raises(psycopg.Error), database.tx(project) as db:
            db.execute("UPDATE assessment_batches SET objective='changed' WHERE id=%s", (created["id"],))


def test_assessment_pause_resume_cancellation_and_inherited_identity_validation(database):
    with client_for(database) as client:
        project, base, parent, image, request, created, worker = prepared(client, database)
        root = base + "/assessments/" + created["id"]
        bad = request["protocol"] | {"evaluation": request["protocol"]["evaluation"] | {"seed": 999}}
        assert client.post(base + "/assessments/validate", json=bad).status_code == 422
        action = {"operation_id": str(uuid4()), "expected_revision": 1, "action": "pause"}
        assert client.post(root + "/controls", json=action).status_code == 200
        assert client.post(root + "/controls", json=action).status_code == 200
        assert worker.once() and worker.once()
        state = client.get(root).json()
        assert state["statuses"] == {"paused": 2}
        assert (
            client.post(
                root + "/controls", json={"operation_id": str(uuid4()), "expected_revision": 1, "action": "resume"}
            ).status_code
            == 409
        )
        resumed = {"operation_id": str(uuid4()), "expected_revision": 2, "action": "resume"}
        assert client.post(root + "/controls", json=resumed).status_code == 200
        # Cancel immediately, before resumed children execute another stimulus.
        cancelled = {"operation_id": str(uuid4()), "expected_revision": 3, "action": "cancel"}
        assert client.post(root + "/controls", json=cancelled).status_code == 200
        assert worker.once() and worker.once()
        state = client.get(root).json()
        assert state["statuses"] == {"cancelled": 2}
        assert all(result["status"] == "undetermined" for result in state["criteria"])
        assert image.digest == database.load_checkpoint(project, parent["run_id"])[1].digest


def test_assessment_summary_exports_and_ai_cannot_supply_or_omit_decisions(database, tmp_path):
    from cryptography.fernet import Fernet
    from docx import Document
    from pypdf import PdfReader
    from test_ai_providers import create as provider_create
    from test_ai_providers import get_call
    from test_report_exports import artifact
    from test_research_ai import ask, reply
    from test_research_documents import save_body

    from threemind_lab import report_exports, research_documents
    from threemind_lab.config import Settings
    from threemind_lab.database import LOCAL_USER

    with client_for(database) as client:
        project, base, parent, image, _request, created, worker = prepared(client, database)
        assert worker.once() and worker.once()
        source = client.post(
            base + "/report-sources",
            json={"operation_id": str(uuid4()), "kind": "assessment", "assessment_id": created["id"]},
        ).json()
        assert worker.once()
        template = client.get(base + f"/report-sources/{source['id']}/template").json()
        template["blocks"][-1]["markdown"] = "功能验收；不证明意识质量，不能预测未知环境。"
        summary = next(b for b in template["blocks"] if b["type"] == "assessment_summary")
        fabricated = json.loads(json.dumps(template))
        next(b for b in fabricated["blocks"] if b["type"] == "assessment_summary")["status"] = "satisfied"
        assert client.post(base + "/research-documents/preview", json=fabricated).status_code == 422
        identity = uuid4()
        research_documents.save(database, project, LOCAL_USER, identity, save_body(template))
        for fmt in ("markdown", "html", "docx", "pdf"):
            requested = report_exports.request(
                database,
                project,
                LOCAL_USER,
                identity,
                {"operation_id": str(uuid4()), "revision": 1, "format": fmt, "include_data": True},
            )
            assert worker.once()
            with database.tx(project) as db:
                job = db.execute("SELECT * FROM jobs WHERE id=%s", (requested["job_id"],)).fetchone()
            assert job["status"] == "done", job["error"]
            raw = artifact(database, project, job["result"]["artifact_id"])
            (tmp_path / ("assessment." + ("md" if fmt == "markdown" else fmt))).write_bytes(raw)
            if fmt == "docx":
                document = Document(io.BytesIO(raw))
                text = "\n".join(p.text for p in document.paragraphs)
            elif fmt == "pdf":
                text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(raw)).pages)
            else:
                text = raw.decode()
            assert "固定规则判定" in text and "not_dead_at_end" in text and "不符合" in text
        settings = Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),))
        provider = provider_create(database, settings, project)
        scope = {"kind": "record", "sources": [source["id"]]}
        call, _, preview = ask(database, settings, project, provider, scope)
        facts = preview["evidence"]["sources"][0]
        assert facts["assessment"]["criteria"][1]["status"] == "not_satisfied"
        no_decisions = template | {"blocks": [b for b in template["blocks"] if b is not summary]}
        assert reply(database, settings, json.dumps(no_decisions)).once()
        assert get_call(database, project, call)["result"]["application_status"] == "rejected"
        call, _, _ = ask(database, settings, project, provider, scope)
        assert reply(database, settings, json.dumps(template)).once()
        assert get_call(database, project, call)["result"]["application_status"] == "recorded"
        assert image.digest == database.load_checkpoint(project, parent["run_id"])[1].digest


def test_api_refuses_unmigrated_schema_before_serving_requests(database):
    database.require_current_schema()
    with psycopg.connect(database.test_migration_url) as db:
        assert db.info.dbname.startswith("tm2_test_db_")
        db.execute("DELETE FROM tm2.schema_version WHERE version=43")
    try:
        with pytest.raises(ValueError, match="cli migrate"), client_for(database):
            pass
    finally:
        with psycopg.connect(database.test_migration_url) as db:
            db.execute("INSERT INTO tm2.schema_version(version) VALUES(43)")
    database.require_current_schema()
