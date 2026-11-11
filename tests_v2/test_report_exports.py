import hashlib
import io
import json
import zipfile
from datetime import datetime
from uuid import uuid4

import pytest
from test_api import client_for
from test_research_documents import capture, save_body, setup

from threemind_lab import report_exports, report_sources, research_documents
from threemind_lab.database import LOCAL_USER, Conflict, NotFound
from threemind_lab.report_sources import encode
from threemind_lab.worker import Worker


def fixture_document(database):
    project, run, _cp, _engine = setup(database)
    source, _ = capture(database, project, run)
    spec = research_documents.defaults(database, project, source["id"])
    spec["title"] = "刺激撤除后的活动变化"
    spec["blocks"][0]["markdown"] = (
        "中文 **研究说明** 与 English observations，保留 $x^2$。\n\n"
        "$$\nE(t)=\\int_0^t e^{-s}\\,ds\n$$\n\n"
        "1. 对照分析\n2. 检查缺失值\n\n"
        "[原文](https://example.org/paper) ![远程图片](https://127.0.0.1:9/not-fetched.png)\n\n"
        "<script>window.exportMustNotExecute=true</script>\n\n"
        "| 变量 | 解释 |\n| --- | --- |\n| $x^2$ | 平方 |"
    )
    document = uuid4()
    research_documents.save(database, project, LOCAL_USER, document, save_body(spec))
    return project, document, source, spec


def test_export_references_pin_old_record_and_failures_do_not_publish(database, monkeypatch):
    project, record, source, spec = fixture_document(database)
    report_id = uuid4()
    ref = {
        "id": "old-record",
        "type": "record_block",
        "record_id": str(record),
        "revision": 1,
        "block_id": spec["blocks"][0]["id"],
    }
    research_documents.save(
        database,
        project,
        LOCAL_USER,
        report_id,
        save_body({"kind": "report", "title": "固定引用", "sources": [], "blocks": [ref]}),
    )
    research_documents.save(database, project, LOCAL_USER, record, save_body(spec | {"title": "改变标题"}, 1))
    request = report_exports.request(
        database, project, LOCAL_USER, report_id, {"operation_id": str(uuid4()), "revision": 1, "format": "markdown"}
    )
    assert Worker(database, name="report-reference-export").once()
    row = report_exports.listing(database, project, report_id)["rows"][0]
    assert row["status"] == "done", row["error"]
    with zipfile.ZipFile(io.BytesIO(artifact(database, project, row["result"]["bundle_artifact_id"]))) as archive:
        saved = json.loads(archive.read(f"records/{record}-r1.json"))
        assert saved["revision"] == 1 and saved["title"] == spec["title"]
        assert saved["content_hash"] == research_documents.get(database, project, record, 1)["content_hash"]
    compact = report_sources.get_source(database, project, source["id"], compact=True)
    assert "replay" not in compact["manifest"]["provenance"]["protocol"]
    assert compact["manifest"]["replay_event_count"] == 0
    assert "replay" in source["manifest"]["provenance"]["protocol"]
    assert compact["content_hash"] == source["content_hash"]
    monkeypatch.setattr(report_exports, "MAX_PACKAGE_BYTES", 1)
    failed = report_exports.request(
        database, project, LOCAL_USER, record, {"operation_id": str(uuid4()), "revision": 1, "format": "markdown"}
    )
    assert Worker(database, name="export-budget").once()
    with database.tx(project) as db:
        job = db.execute("SELECT status,error FROM jobs WHERE id=%s", (failed["job_id"],)).fetchone()
        assert job["status"] == "failed" and "2 GiB" in job["error"]
        assert (
            db.execute("SELECT count(*) AS n FROM artifacts WHERE job_id=%s", (failed["job_id"],)).fetchone()["n"] == 0
        )
    assert request["id"] != failed["id"]


def test_unsupported_equation_is_explicit_and_markdown_preserves_source():
    from threemind_lab.report_publication import equation, markdown_output

    with pytest.raises(ValueError, match="公式无法可靠导出"):
        equation(r"\unsupportedThreeMindMacro{a}")
    text = "[link](https://example.org)\n\n$$\\unsupportedThreeMindMacro{a}$$"
    assert markdown_output([{"type": "markdown", "text": text}]).decode() == text + "\n"


def artifact(database, project, artifact_id):
    with database.tx(project) as db:
        return b"".join(
            bytes(row["body"])
            for row in db.execute(
                "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (artifact_id,)
            ).fetchall()
        )


def test_exports_fixed_revision_formats_complete_evidence_and_isolation(database, tmp_path):
    from docx import Document
    from pypdf import PdfReader

    project, document, source, spec = fixture_document(database)
    requests = []
    for fmt in ("markdown", "html", "docx", "pdf"):
        body = {
            "operation_id": str(uuid4()),
            "revision": 1,
            "format": fmt,
            "include_data": True,
            "table_rows": 110,
            "chart_points": 10,
        }
        requested = report_exports.request(database, project, LOCAL_USER, document, body)
        requests.append((fmt, requested))
        assert report_exports.request(database, project, LOCAL_USER, document, body)["replayed"]
        with pytest.raises(Conflict):
            report_exports.request(database, project, LOCAL_USER, document, body | {"table_rows": 120})
    research_documents.save(
        database, project, LOCAL_USER, document, save_body(spec | {"title": "后续修改不属于旧导出"}, 1)
    )
    worker = Worker(database, name="report-export-test")
    for _ in requests:
        assert worker.once()
    exports = {str(r["id"]): r for r in report_exports.listing(database, project, document)["rows"]}
    for fmt, request in requests:
        row = exports[str(request["id"])]
        assert row["status"] == "done", row["error"]
        content = artifact(database, project, row["result"]["artifact_id"])
        bundle = artifact(database, project, row["result"]["bundle_artifact_id"])
        assert hashlib.sha256(content).hexdigest() == row["result"]["sha256"]
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["revision"] == 1 and len(manifest["sources"]) == 1
            assert manifest["export_id"] == str(request["id"])
            assert datetime.fromisoformat(manifest["generated_at"]) >= datetime.fromisoformat(manifest["requested_at"])
            for name, checksum in manifest["files"].items():
                assert hashlib.sha256(archive.read(name)).hexdigest() == checksum
            source_manifest = json.loads(archive.read(f"sources/{source['id']}/manifest.json"))
            coverage = source_manifest.pop("coverage")
            checksum = hashlib.sha256(encode(source_manifest) + b"\n")
            rows = archive.read(f"sources/{source['id']}/rows.jsonl")
            checksum.update(rows)
            checksum.update(encode(coverage))
            assert checksum.hexdigest() == source["content_hash"]
            assert len(rows.splitlines()) == 79 and b'"activation":null' in rows
            saved = json.loads(archive.read("document.json"))
            assert saved["spec"]["title"] == spec["title"]
            assert saved["content_revision"] == saved["revision"] == 1
            assert saved["title"] == spec["title"] and "updated_at" not in saved
        if fmt == "docx":
            parsed = Document(io.BytesIO(content))
            assert parsed.paragraphs[0].text == spec["title"] and len(parsed.inline_shapes) >= 1
            with zipfile.ZipFile(io.BytesIO(content)) as docx:
                xml = docx.read("word/document.xml")
                assert b"oMath" in xml and b"tblHeader" in xml
                assert b"int_0" not in xml
        elif fmt == "pdf":
            parsed = PdfReader(io.BytesIO(content))
            text = "\n".join(p.extract_text() for p in parsed.pages)
            assert spec["title"] in text and "后续修改不属于旧导出" not in text
            assert len(parsed.pages) >= 3 and "77" in text
        elif fmt == "html":
            assert b"<script>" not in content and b"Content-Security-Policy" in content
            assert b"data:image/svg+xml;base64," in content
            assert b'<a href="https://example.org/paper">' in content
        else:
            assert b"E(t)=\\int_0" in content and b"figures/figure-001.png" in content
        extension = "md" if fmt == "markdown" else fmt
        (tmp_path / f"research.{extension}").write_bytes(content)
        (tmp_path / f"evidence-{fmt}.zip").write_bytes(bundle)
    other = database.create_project({"id": LOCAL_USER}, "Other project")["id"]
    with pytest.raises(NotFound):
        report_exports.listing(database, other, document)
    with pytest.raises(NotFound):
        report_exports.request(
            database, other, LOCAL_USER, document, {"operation_id": str(uuid4()), "revision": 1, "format": "pdf"}
        )
    with client_for(database) as client:
        response = client.post(
            f"/api/v2/projects/{project}/research-documents/{document}/exports",
            json={"operation_id": str(uuid4()), "revision": 1, "table_rows": 5001},
        )
        assert response.status_code == 422


def test_export_excerpt_no_full_data_and_old_worker_cannot_claim(database):
    project, document, source, _spec = fixture_document(database)
    body = {"operation_id": str(uuid4()), "revision": 1, "format": "markdown", "table_rows": 3}
    request = report_exports.request(database, project, LOCAL_USER, document, body)
    from threemind_runtime.capabilities import probe_worker

    old = probe_worker("native")
    old["features"]["worker.research_documents"] = {"state": "available"}
    assert database.claim("e2a-worker", capabilities=old) is None
    assert Worker(database, name="export-capable").once()
    row = report_exports.listing(database, project, document)["rows"][0]
    assert row["status"] == "done", row["error"]
    assert row["job_id"] == request["job_id"]
    assert any(w["kind"] == "table_excerpt" and w["included"] == 3 for w in row["result"]["warnings"])
    with zipfile.ZipFile(io.BytesIO(artifact(database, project, row["result"]["bundle_artifact_id"]))) as archive:
        assert not any(name.endswith("rows.jsonl") for name in archive.namelist())
        assert str(source["id"]) in json.loads(archive.read("manifest.json"))["sources"]


def test_network_table_preserves_object_identity_and_checkpoint_time():
    from threemind_lab.report_publication import content_nodes

    document = {
        "spec": {"title": "Network"},
        "kind": "record",
        "content_revision": 1,
        "review": "draft",
        "content_hash": "hash",
    }
    rendered = {
        "sources": {"source": {"manifest": {"kind": "edges"}, "content_hash": "hash"}},
        "blocks": [
            {
                "id": "edges",
                "type": "table",
                "source": "source",
                "metrics": ["weight"],
                "row_count": 1,
                "rows": [
                    {"ordinal": 0, "time_us": "0", "label": "12→42", "quality": "complete", "values": {"weight": 0.1}}
                ],
            }
        ],
    }
    nodes, _, _ = content_nodes(document, rendered, {"language": "zh-CN", "include_data": False})
    table = next(node for node in nodes if node["type"] == "table")
    assert table["rows"][1][1] == "12→42\n0 μs"
