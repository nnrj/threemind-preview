import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from threemind_lab.document_api import register_document_routes
from threemind_lab.documents import Documents
from threemind_lab.report_revisions import ReportRevisions, RevisionConflict, checksum


def original(tmp_path, *, language="zh"):
    path = tmp_path / "lab" / "explorations" / "fixture" / f"report.{language}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"\xef\xbb\xbf# Original report\r\n\r\nPreserved observations.\r\n"
    path.write_bytes(raw)
    return path.relative_to(tmp_path).as_posix(), raw


def request(name, raw, **changes):
    return {
        "original": name, "body": "# Revised report\n\nPreserved observations.\n",
        "reason": "Register a new evidence location; keep the original conclusions.",
        "date": "2026-10-09", "operation_id": str(uuid4()),
        "expected_edition": 1, "expected_parent_hash": checksum(raw), **changes,
    }


def test_original_bytes_bilingual_series_and_cas_idempotency(tmp_path):
    name, raw = original(tmp_path)
    store = ReportRevisions(tmp_path)
    arguments = request(name, raw)
    saved = store.revise(**arguments)
    assert saved["edition"] == 2 and not saved["replayed"]
    assert saved["path"].endswith("report.r2.zh.md")
    assert (tmp_path / name).read_bytes() == raw
    revised = (tmp_path / saved["path"]).read_text(encoding="utf-8")
    assert revised.startswith("# Revised report\n\n> **修订 r2 · 2026-10-09**")
    assert "[report.zh.md](report.zh.md)" in revised
    history = store.history(name)
    assert history["revisions"][0]["date"] is None
    assert history["revisions"][0]["sha256"] == checksum(raw)
    assert store.revise(**arguments) == saved | {"replayed": True}
    with pytest.raises(RevisionConflict, match="different content"):
        store.revise(**(arguments | {"reason": "Different correction"}))
    with pytest.raises(RevisionConflict, match="parent changed"):
        store.revise(**request(name, raw))
    next_saved = store.revise(**request(
        name, raw, expected_edition=2, expected_parent_hash=saved["sha256"],
    ))
    assert next_saved["edition"] == 3 and next_saved["parent"] == 2
    assert (tmp_path / name).read_bytes() == raw
    en, english_raw = original(tmp_path, language="en")
    en_saved = store.revise(**request(en, english_raw, language="en"))
    assert en_saved["series"] == saved["series"] == "report"
    assert "Revision reason:" in (tmp_path / en_saved["path"]).read_text(encoding="utf-8")
    manifest = json.loads((tmp_path / name).parent.joinpath("report-revisions.json").read_text())
    assert {g["language"] for g in manifest["series"]} == {"zh", "en"}


def test_concurrent_authors_do_not_overwrite_same_parent(tmp_path):
    name, raw = original(tmp_path)

    def write(index):
        try:
            return ReportRevisions(tmp_path).revise(**request(name, raw, reason=f"Author {index}"))
        except RevisionConflict:
            return None

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(write, range(2)))
    assert sum(value is not None for value in results) == 1
    assert len(ReportRevisions(tmp_path).history(name)["revisions"]) == 2
    assert (tmp_path / name).read_bytes() == raw


def test_interruption_before_manifest_is_recoverable_without_duplicate(tmp_path, monkeypatch):
    from threemind_lab import report_revisions

    name, raw = original(tmp_path)
    store = ReportRevisions(tmp_path)
    arguments = request(name, raw)
    publish = report_revisions._publish_file

    def interrupted(path, raw, *, replace):
        if replace:
            raise OSError("simulated manifest commit failure")
        publish(path, raw, replace=replace)

    monkeypatch.setattr(report_revisions, "_publish_file", interrupted)
    with pytest.raises(OSError, match="simulated"):
        store.revise(**arguments)
    edition = (tmp_path / name).with_name("report.r2.zh.md")
    assert edition.is_file() and store.history(name) is None
    orphan = edition.read_bytes()
    assert (tmp_path / name).read_bytes() == raw
    monkeypatch.setattr(report_revisions, "_publish_file", publish)
    completed = store.revise(**arguments)
    assert completed["edition"] == 2 and edition.read_bytes() == orphan
    assert len(store.history(name)["revisions"]) == 2


def test_foreign_edition_hash_corruption_and_path_escape_are_rejected(tmp_path):
    name, raw = original(tmp_path)
    store = ReportRevisions(tmp_path)
    destination = (tmp_path / name).with_name("report.r2.zh.md")
    destination.write_text("Existing independent document", encoding="utf-8")
    with pytest.raises(RevisionConflict, match="different content"):
        store.revise(**request(name, raw))
    assert destination.read_text() == "Existing independent document"
    assert not destination.with_name("report-revisions.json").exists()
    for path in (".env", "lab/../.env", str(tmp_path / name)):
        with pytest.raises(ValueError):
            store.revise(**request(path, raw))
    destination.unlink()
    saved = store.revise(**request(name, raw))
    (tmp_path / saved["path"]).write_text("Tampered edition", encoding="utf-8")
    with pytest.raises(ValueError, match="content hash"):
        store.history(name)
    with pytest.raises(ValueError, match="content hash"):
        store.revise(**request(name, raw, expected_edition=2, expected_parent_hash=saved["sha256"]))


def test_manifest_cannot_change_series_or_publish_private_markdown(tmp_path):
    name, raw = original(tmp_path)
    store = ReportRevisions(tmp_path)
    store.revise(**request(name, raw))
    with pytest.raises(RevisionConflict, match="another report series"):
        store.revise(**request(name, raw, series="unrelated"))
    manifest_path = (tmp_path / name).with_name("report-revisions.json")
    value = json.loads(manifest_path.read_text())
    value["series"][0]["revisions"][0]["path"] = "../../../.env"
    manifest_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="filenames"):
        store.history(name)
    private_name = "docs/en/private/report.en.md"
    private = tmp_path / private_name
    private.parent.mkdir(parents=True)
    private.write_bytes(raw)
    store.revise(**request(private_name, raw, language="en"))
    docs = Documents(tmp_path)
    with pytest.raises(KeyError):
        docs.read(private_name, latest=True)


def test_live_document_reader_and_read_only_http_versions(tmp_path):
    name, raw = original(tmp_path)
    documents = Documents(tmp_path)
    assert documents.read(name)["title"] == "Original report"
    saved = ReportRevisions(tmp_path).revise(**request(name, raw))
    assert documents.read(name)["report_revision"]["edition"] == 1
    assert documents.read(name)["title"] == "Original report"
    assert documents.read(name, revision=2)["id"] == saved["path"]
    assert documents.read(name, latest=True)["title"] == "Revised report"
    assert documents.read(saved["path"], revision=1)["id"] == name
    indexed = {d["id"]: d for d in documents.index()["documents"]}
    assert indexed[name]["report_revision"]["edition"] == 1
    assert indexed[saved["path"]]["report_revision"]["original"] == name
    app = FastAPI()
    app.state.documents = documents
    register_document_routes(app)
    with TestClient(app) as client:
        assert client.get("/api/v2/documents/content", params={"path": name}).json()["id"] == name
        assert client.get("/api/v2/documents/content", params={"path": name, "latest": True}).json()["id"] == saved["path"]
        versions = client.get("/api/v2/documents/versions", params={"path": name})
        assert versions.status_code == 200 and len(versions.json()["revisions"]) == 2
        assert client.get("/api/v2/documents/content", params={"path": name, "revision": 3}).status_code == 404
        assert client.get("/api/v2/documents/content", params={"path": name, "revision": 0}).status_code == 422
        assert client.get("/api/v2/documents/content", params={"path": name, "revision": 1, "latest": True}).status_code == 400
        assert client.post("/api/v2/documents/versions", params={"path": name}).status_code == 405
        (tmp_path / saved["path"]).write_text("Modified", encoding="utf-8")
        assert client.get("/api/v2/documents/content", params={"path": name, "latest": True}).status_code == 409


def test_relocated_public_figures_do_not_expose_other_archived_data(tmp_path):
    name, _ = original(tmp_path)
    (tmp_path / name).write_text("# Public report\n\n![Figure](figures/measured.png)\n", encoding="utf-8")
    archived = tmp_path / "data" / "experiments" / "figure.png"
    archived.parent.mkdir(parents=True)
    archived.write_bytes(b"preserved figure bytes")
    legacy = str(Path(name).parent / "figures" / "measured.png").replace("\\", "/")
    calls = []

    def registered(path):
        calls.append(path)
        return archived if path == legacy else None

    docs = Documents(tmp_path, resource_resolver=registered)
    assert docs.resource(legacy) == archived
    for forbidden in ("data/experiments/figure.png", "lab/explorations/fixture/state.json", ".env",
                      "docs/images/../../.env", "lab/explorations/fixture/figures/unlisted.png"):
        with pytest.raises(KeyError):
            docs.resource(forbidden)
    assert calls == [legacy]


def publication(tmp_path, database):
    from lab.tools.study_publication import Publication

    project = str(uuid4())
    study = SimpleNamespace(
        db=database, project=project, work=tmp_path,
        identity=lambda key: str(uuid5(UUID(project), key)),
    )
    return Publication(study)


def test_publication_retry_keeps_identity_parent_data_and_newer_head(tmp_path, monkeypatch):
    from lab.tools import study_publication
    from threemind_lab import notebooks, research_documents
    from threemind_lab.database import Conflict

    pub = publication(tmp_path, object())
    document_id = str(uuid4())
    source, record = str(uuid4()), str(uuid4())
    spec = {
        "kind": "report", "title": "Original", "sources": [source],
        "blocks": [
            {"id": "narrative", "type": "commentary", "section": "results", "markdown": "Original evidence"},
            {"id": "curve", "type": "chart", "source": source, "metric": "activation", "chart": "line"},
            {"id": "fixed", "type": "record_block", "record_id": record, "revision": 1, "block_id": "fact"},
        ],
    }
    parent = {"spec": spec, "content_hash": notebooks.digest(spec), "content_revision": 1, "ai_call_id": None}
    original_parent = deepcopy(parent)
    pub.state["report:zh"] = {"id": document_id, "revision": 1, "content_hash": parent["content_hash"]}
    monkeypatch.setattr(research_documents, "get", lambda *a, **kw: deepcopy(parent) if kw.get("revision") else {
        "content_hash": "3" * 64, "content_revision": 3,
    })
    calls = []

    def save(*args):
        calls.append(deepcopy(args[-1]))
        assert args[-2] == document_id
        return {"id": document_id, "revision": 2, "content_hash": "2" * 64, "replayed": len(calls) > 1}

    monkeypatch.setattr(study_publication.research_documents, "save", save)
    arguments = {
        "reason": "Update the evidence location", "date": "2026-10-09", "operation_id": str(uuid4()),
        "expected_revision": 1, "expected_parent_hash": parent["content_hash"],
    }
    remember = pub.remember
    monkeypatch.setattr(pub, "remember", lambda *a: (_ for _ in ()).throw(OSError("lost publication write")))
    with pytest.raises(OSError, match="lost"):
        pub.revise_document("report:zh", "Revised evidence", **arguments)
    monkeypatch.setattr(pub, "remember", remember)
    result = pub.revise_document("report:zh", "Revised evidence", **arguments)
    assert result["replayed"] and calls[0] == calls[1]
    assert parent == original_parent
    assert calls[0]["spec"]["blocks"][0]["id"] == "revision_notice"
    assert calls[0]["spec"]["blocks"][-2:] == original_parent["spec"]["blocks"][-2:]
    assert calls[0]["spec"]["sources"] == [source] and calls[0]["review"] == "draft"
    assert pub.state["report:zh"]["revision"] == 3
    with pytest.raises(Conflict, match="parent hash"):
        pub.revise_document("report:zh", **(arguments | {"expected_parent_hash": "9" * 64}))
    assert len(calls) == 2


def test_fresh_git_checkout_preserves_explicit_text_and_original_byte_identities(tmp_path):
    source, checkout = tmp_path / "source", tmp_path / "checkout"
    original = source / "lab/E1/report.zh.md"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"# Original\r\n\r\nEvidence\r\n")
    registry = ReportRevisions(source)
    result = registry.revise("lab/E1/report.zh.md", "# Revision\n\nEvidence\n", reason="Location correction",
                             date="2026-10-10", operation_id=uuid4(), expected_edition=1,
                             expected_parent_hash=checksum(original.read_bytes()))
    source.joinpath(".gitignore").write_text(".report-revisions.lock\n", encoding="utf-8")

    def git(*arguments, cwd=source):
        subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)

    git("init", "--quiet")
    git("config", "core.autocrlf", "true")
    git("add", ".")
    git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "-m", "fixture")
    git("-c", "core.autocrlf=true", "clone", "--quiet", "--no-local", str(source), str(checkout))
    rows = ReportRevisions(checkout).history("lab/E1/report.zh.md")["revisions"]
    revised = rows[1]
    assert revised["sha256"] == result["sha256"]
    assert revised["read_sha256"] == checksum(checkout.joinpath(result["path"]).read_bytes())
    assert revised["integrity"] == "git_text_eol" and not revised["byte_identity_matches"]
    assert rows[0]["byte_identity_matches"]
    checkout.joinpath(result["path"]).write_bytes(b"Different scientific statement\r\n")
    with pytest.raises(ValueError, match="content hash"):
        ReportRevisions(checkout).history("lab/E1/report.zh.md")


def test_old_registries_keep_strict_byte_validation(tmp_path):
    original = tmp_path / "lab/E1/report.md"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"# Original\nEvidence\n")
    registry = ReportRevisions(tmp_path)
    registry.revise("lab/E1/report.md", "# Revision\nEvidence\n", reason="Correction", date="2026-10-10",
                    operation_id=uuid4(), expected_edition=1, expected_parent_hash=checksum(original.read_bytes()))
    path = original.parent / "report-revisions.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    for row in value["series"][0]["revisions"]:
        row.pop("canonical_sha256")
        row.pop("canonicalization")
    path.write_text(json.dumps(value), encoding="utf-8")
    original.write_bytes(original.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(ValueError, match="content hash"):
        registry.history("lab/E1/report.md")


def test_publication_database_versions_are_append_only(database, tmp_path):
    from lab.tools.study_publication import Publication
    from threemind_lab import research_documents
    from threemind_lab.database import LOCAL_USER

    project = str(database.create_project({"id": LOCAL_USER}, "Publication edition fixture")["id"])
    study = SimpleNamespace(db=database, project=project, work=tmp_path,
                            identity=lambda key: str(uuid5(UUID(project), key)))
    pub = Publication(study)
    first = pub.document("report:zh", "report", "Preserved", "Original evidence")
    old = research_documents.get(database, project, first["id"], revision=1)
    arguments = {
        "reason": "Clarify an evidence path", "date": "2026-10-09", "operation_id": uuid4(),
        "expected_revision": 1, "expected_parent_hash": first["content_hash"],
    }
    saved = pub.revise_document("report:zh", "Corrected evidence path", **arguments)
    assert saved["revision"] == 2 and str(saved["id"]) == str(first["id"])
    preserved = research_documents.get(database, project, first["id"], revision=1)
    for field in ("spec", "content_hash", "content_revision", "version_created_at", "review", "ai_call_id"):
        assert preserved[field] == old[field]
    assert pub.revise_document("report:zh", "Corrected evidence path", **arguments)["replayed"]
    assert len(research_documents.versions(database, project, first["id"])["rows"]) == 2
