import json
from pathlib import Path

import pytest

from threemind_lab.documents import Documents

ROOT = Path(__file__).resolve().parents[1]


def test_history_editions_and_all_sources_are_readable():
    docs = Documents(ROOT)
    catalog = docs.history()
    assert {w["id"] for w in catalog["works"]} == {
        "modern-zh",
        "modern-en",
        "classical-biographical",
        "classical-chronological",
    }
    for chapter in catalog["chapters"]:
        assert docs.read(chapter["path"])["markdown"].startswith("# ")
    assert docs.read("lab/en/" + next((ROOT / "lab/en").glob("001_*.md")).name)
    assert docs.resource("lab/explorations/2026-09-30-intensity-mechanisms/figures/factorial.png")


def test_catalog_and_local_links():
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_history", ROOT / "tools/validate_history.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.validate(ROOT) == []


def test_history_http_is_public_read_only_and_needs_no_database():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from threemind_lab.document_api import register_document_routes

    app = FastAPI()
    app.state.documents = Documents(ROOT)
    register_document_routes(app)
    client = TestClient(app)
    response = client.get("/api/v2/history")
    assert response.status_code == 200
    assert response.json()["schema"] == "threemind.history/1"
    assert client.post("/api/v2/history", json={}).status_code == 405
    assert client.get("/api/v2/documents/content", params={"path": ".env"}).status_code == 404
    assert client.get("/api/v2/documents/content", params={"path": "docs/en/history/index.md"}).status_code == 200


def test_unlisted_peers_and_unreferenced_lab_assets_stay_private(tmp_path):
    for lang in ("zh", "en"):
        folder = tmp_path / "lab" / lang
        folder.mkdir(parents=True)
        (folder / "note.md").write_text("# Published\n", encoding="utf-8")
    (tmp_path / "lab/en/private.md").write_text("private", encoding="utf-8")
    (tmp_path / "lab/en/secret.png").write_bytes(b"private")
    docs = Documents(tmp_path)
    assert docs.read("lab/en/note.md")["title"] == "Published"
    for name in ("lab/en/private.md", "lab/en/../../.env"):
        with pytest.raises(KeyError):
            docs.read(name)
    for name in ("lab/en/secret.png", "lab/en/../../.env", "lab/records.json"):
        with pytest.raises(KeyError):
            docs.resource(name)


def test_catalog_rejects_foreign_and_duplicate_chapters(tmp_path):
    folder = tmp_path / "docs/history"
    folder.mkdir(parents=True)
    public = tmp_path / "docs/zh/history"
    public.mkdir(parents=True)
    (public / "index.md").write_text("# History\n", encoding="utf-8")
    doc = {"id": "a", "work": "zh", "path": "docs/zh/history/index.md"}
    catalog = {"schema": "threemind.history/1", "works": [{"id": "zh"}], "chapters": [doc]}
    target = folder / "catalog.json"
    target.write_text(json.dumps(catalog), encoding="utf-8")
    docs = Documents(tmp_path)
    assert docs.history()["chapters"][0]["id"] == "a"
    catalog["chapters"].append(doc.copy())
    target.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ValueError):
        docs.history()
    catalog["chapters"] = [{**doc, "path": ".env"}]
    target.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(ValueError):
        docs.history()
