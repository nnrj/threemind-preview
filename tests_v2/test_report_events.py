import hashlib
import io
import json
import zipfile
from datetime import UTC
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from test_api import client_for
from test_report_exports import artifact
from test_research_documents import capture, save_body, setup

from threemind_lab import report_exports, report_sources, research_ai, research_documents
from threemind_lab.database import LOCAL_USER, NotFound
from threemind_lab.report_schema import CaptureSource
from threemind_lab.worker import Worker


def event_fixture(database):
    project, run, cp, engine = setup(database)
    with database.tx(project) as db:
        command = db.execute(
            "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,'intervention',%s) RETURNING id,created_at",
            (project, run["id"], Jsonb({"learning": False})),
        ).fetchone()
        # A pending command has no committed event and must never appear as an applied intervention.
        db.execute(
            "INSERT INTO commands(project_id,run_id,kind,payload) VALUES(%s,%s,'pause','{}')", (project, run["id"])
        )
        for i in range(123):
            kind = "input_scheduled" if i == 0 else "input_delivered"
            if i == 1:
                kind = "energy_scheduled"
            key = f"fixture:{i}"
            if i == 2:
                kind, key = "intervention", f"command:{command['id']}"
            if i == 3:
                kind = "configuration_changed"
            db.execute(
                "INSERT INTO events(project_id,run_id,event_key,time_us,kind,payload,commit_revision,provenance) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    project,
                    run["id"],
                    key,
                    "2000000" if i == 122 else str(max(1, i) * 1000),
                    kind,
                    Jsonb(
                        {
                            "carrier": "private event carrier not for AI",
                            "status": "rejected" if i == 1 else "recorded",
                            "index": i,
                            "parameters": {"before": 0.5, "after": 0.7},
                        }
                    ),
                    2 if i == 120 else None if i == 121 else 1,
                    Jsonb({"envelope_id": str(uuid4())}),
                ),
            )
    return project, run, cp, engine, command


def event_source(database, project, run, **changes):
    return capture(database, project, run, kind="events", metrics=["event_count"], **changes)[0]


def test_event_boundary_full_rows_hash_and_two_clocks(database):
    project, run, cp, engine, command = event_fixture(database)
    source = event_source(database, project, run, checkpoint_id=str(cp["id"]))
    assert source["row_count"] == 120
    assert source["manifest"]["coverage"]["legacy_commit_unknown_omitted"] == 1
    preview = report_sources.data_rows(database, project, source["id"], limit=1000)["rows"]
    assert all("payload" not in r["provenance"] and "recorded_provenance" not in r["provenance"] for r in preview)
    assert [r["time_us"] for r in preview[:3]] == ["1000", "1000", "2000"]
    assert int(preview[0]["provenance"]["event_id"]) < int(preview[1]["provenance"]["event_id"])
    assert [r["quality"] for r in preview[:4]] == [
        "scheduled_input",
        "rejected_input",
        "processed_command",
        "configuration_commit",
    ]
    applied = preview[2]
    assert applied["provenance"]["command_id"] == str(command["id"])
    assert applied["provenance"]["admitted_at"] == command["created_at"].astimezone(UTC).isoformat()
    assert all(r["label"] != "pause" for r in preview)
    manifest = dict(source["manifest"])
    coverage = manifest.pop("coverage")
    checksum = hashlib.sha256(report_sources.encode(manifest) + b"\n")
    for row in preview:
        full = report_sources.full_row(database, project, source["id"], row["ordinal"])["row"]
        assert full["provenance"]["payload"]["index"] == row["ordinal"]
        checksum.update(report_sources.encode(full) + b"\n")
    checksum.update(report_sources.encode(coverage))
    assert checksum.hexdigest() == source["content_hash"]
    engine.advance_to(2_000_000)
    database.save_checkpoint(project, run["id"], engine.capture_state(), expected_revision=1)
    assert report_sources.get_source(database, project, source["id"])["content_hash"] == source["content_hash"]
    later = event_source(database, project, run)
    assert later["row_count"] == 122


def test_event_filter_empty_sources_defaults_and_no_fake_numeric_inference(database):
    project, run, _, _, _ = event_fixture(database)
    source = event_source(database, project, run, event_group="interventions")
    assert source["row_count"] == 2
    spec = research_documents.defaults(database, project, source["id"])
    view = research_documents.render(database, project, spec=spec)
    assert next(b for b in view["blocks"] if b["type"] == "fact")["value"] == 2
    bar = next(b for b in view["blocks"] if b["type"] == "chart")
    assert bar["data"]["method"] == "all-events-by-kind-and-phase/1"
    assert {r["label"]: r["value"] for r in bar["data"]["rows"]} == {"configuration_changed": 1, "intervention": 1}
    table = next(b for b in view["blocks"] if b["type"] == "table")
    assert table["source_kind"] == "events" and "payload" not in table["rows"][0]["provenance"]
    for bad in ({"type": "chart", "chart": "line"}, {"type": "fact", "statistic": "mean"}):
        with pytest.raises(ValueError):
            research_documents.render(
                database,
                project,
                spec=spec
                | {"blocks": [{"id": "invalid", "source": str(source["id"]), "metric": "event_count", **bad}]},
            )
    empty = event_source(database, project, run, event_group="interventions", event_kinds=["input_delivered"])
    assert empty["row_count"] == 0
    empty_view = research_documents.render(
        database, project, spec=research_documents.defaults(database, project, empty["id"])
    )
    assert next(b for b in empty_view["blocks"] if b["type"] == "chart")["data"]["rows"] == []
    assert "not proof" in empty["manifest"]["coverage"]["empty_result_means"]
    with pytest.raises(ValueError):
        CaptureSource.model_validate(
            {"operation_id": uuid4(), "run_id": run["id"], "kind": "nodes", "event_group": "inputs"}
        )
    interval = event_source(database, project, run, event_group="inputs", from_us="1000", through_us="1000")
    assert interval["row_count"] == 2


def test_event_ai_summary_complete_without_raw_payloads_or_false_delivery(database):
    project, run, _, _, _ = event_fixture(database)
    source = event_source(database, project, run)
    preview = research_ai.preview(database, project, LOCAL_USER, {"kind": "record", "sources": [str(source["id"])]})
    evidence = preview["evidence"]["sources"][0]
    assert sum(r["count"] for r in evidence["event_counts"]) == 120
    assert next(r for r in evidence["event_counts"] if r["label"] == "energy_scheduled")["phase"] == "rejected_input"
    assert "private event carrier" not in json.dumps(preview)
    assert "parameters" not in evidence
    assert evidence["selection"]["event_group"] == "all" and evidence["content_hash"] == source["content_hash"]


def test_event_api_isolation_and_old_worker_rejection(database):
    project, run, _, _, _ = event_fixture(database)
    request = report_sources.request(
        database, project, LOCAL_USER, {"operation_id": uuid4(), "kind": "events", "run_id": run["id"]}
    )
    assert (
        database.claim(
            "previous-source-worker", capabilities={"features": {"worker.research_documents": {"state": "available"}}}
        )
        is None
    )
    assert Worker(database).once()
    other = database.create_project({"id": LOCAL_USER}, "No event access")["id"]
    with pytest.raises(NotFound):
        report_sources.full_row(database, other, request["id"], 0)
    with client_for(database) as client:
        url = f"/api/v2/projects/{project}/report-sources/{request['id']}/rows"
        assert "payload" not in client.get(url).json()["rows"][0]["provenance"]
        assert client.get(url + "/0").json()["row"]["provenance"]["payload"]["index"] == 0
        assert client.get(url + "/99999").status_code == 404


def test_ai_worker_saves_event_draft_using_fixed_counts(database):
    from cryptography.fernet import Fernet
    from test_ai_providers import create, get_call
    from test_research_ai import ask, reply

    from threemind_lab.config import Settings

    project, run, _, _, _ = event_fixture(database)
    source = event_source(database, project, run)
    settings = Settings(database_url=database.test_url, secret_keys=(Fernet.generate_key().decode(),))
    provider = create(database, settings, project)
    spec = research_documents.defaults(database, project, source["id"])
    spec["blocks"][-1]["markdown"] = "日志条目不是独立重复，摘要未包含原始载体。"
    call, _, _ = ask(database, settings, project, provider, {"kind": "record", "sources": [str(source["id"])]})
    assert reply(database, settings, json.dumps(spec)).once()
    result = get_call(database, project, call)["result"]
    assert result["application_status"] == "recorded" and result["review_status"] == "unreviewed"
    rendered = research_documents.render(database, project, result["document_id"])
    assert next(b for b in rendered["blocks"] if b["type"] == "fact")["value"] == 120


def test_event_exports_preserve_raw_bundle_and_fixed_body_metadata(database, tmp_path):
    project, run, _, _, _ = event_fixture(database)
    source = event_source(database, project, run, through_us="5000")
    spec = research_documents.defaults(database, project, source["id"])
    spec["title"] = "事件时间、拒绝与参数变更"
    doc = uuid4()
    research_documents.save(database, project, LOCAL_USER, doc, save_body(spec))
    for format in ("markdown", "html", "docx", "pdf"):
        request = report_exports.request(
            database,
            project,
            LOCAL_USER,
            doc,
            {"operation_id": uuid4(), "revision": 1, "format": format, "include_data": True},
        )
        if format == "markdown":
            assert (
                database.claim(
                    "previous-export-worker",
                    capabilities={"features": {"worker.report_export_v1": {"state": "available"}}},
                )
                is None
            )
        assert Worker(database).once()
        with database.tx(project) as db:
            job = db.execute("SELECT * FROM jobs WHERE id=%s", (request["job_id"],)).fetchone()
        assert job["status"] == "done", job["error"]
        body = artifact(database, project, job["result"]["artifact_id"])
        (tmp_path / f"events.{format}").write_bytes(body)
        if format in ("markdown", "html"):
            assert b"rejected_input" in body and b"configuration_changed" in body
            assert b"private event carrier" not in body
        with zipfile.ZipFile(io.BytesIO(artifact(database, project, job["result"]["bundle_artifact_id"]))) as archive:
            path = next(p for p in archive.namelist() if p.endswith(".jsonl"))
            rows = [json.loads(line) for line in archive.read(path).splitlines()]
            assert len(rows) == 6 and rows[1]["quality"] == "rejected_input"
            assert rows[3]["provenance"]["payload"]["parameters"]["after"] == 0.7
