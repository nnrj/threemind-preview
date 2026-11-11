import io
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from PIL import Image
from test_api import client_for

from threemind_lab import auth, notebooks
from threemind_lab.database import LOCAL_USER, Conflict, Forbidden, NotFound
from threemind_lab.note_schema import NoteEdit, body_links


def edit(text="# 观察\n\n尚待验证的假说", revision=0, **changes):
    return {
        "operation_id": str(uuid4()),
        "expected_revision": revision,
        "title": "实验笔记",
        "kind": "draft",
        "body": {"format": "markdown", "text": text},
    } | changes


def setup(database):
    return database.create_project({"id": LOCAL_USER}, "notebook tests")["id"]


@pytest.mark.parametrize("title", [None, "原始证据包"])
def test_markdown_link_title_survives_document_save_and_reload(database, title):
    # Tiptap's Markdown parser emits title:null even for [text](url).
    # Reproduce its wire payload, which previously failed with HTTP 422.
    project, note = setup(database), uuid4()
    link = {"type": "link", "attrs": {"href": "/api/v2/projects/evidence", "title": title}}
    body = {
        "format": "document",
        "content": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "数据包", "marks": [link]}],
                }
            ],
        },
    }
    with client_for(database) as client:
        endpoint = f"/api/v2/projects/{project}/notes/{note}"
        response = client.put(endpoint, json=edit(body=body))
        assert response.status_code == 200, response.text
        assert client.get(endpoint).json()["body"] == body
        link["attrs"]["href"] = "javascript:alert(1)"
        assert client.put(endpoint, json=edit(revision=1, body=body)).status_code == 422
        link["attrs"].update(href="https://example.org/evidence", title="x" * 1025)
        assert client.put(endpoint, json=edit(revision=1, body=body)).status_code == 422


def test_revisions_cas_retry_search_and_default_notebook(database):
    project, note = setup(database), uuid4()
    with ThreadPoolExecutor(2) as pool:
        defaults = list(pool.map(lambda _: notebooks.ensure_default(database, project, LOCAL_USER), range(2)))
    assert defaults[0]["id"] == defaults[1]["id"]
    first = edit("first 100%_ literal", kind="note")
    saved = notebooks.save_note(database, project, LOCAL_USER, note, first)
    assert saved["collection_id"] == defaults[0]["id"] and saved["revision"] == 1
    second = edit("second", revision=1, kind="note")
    with ThreadPoolExecutor(2) as pool:
        saved2 = list(pool.map(lambda _: notebooks.save_note(database, project, LOCAL_USER, note, second), range(2)))
    assert {v["revision"] for v in saved2} == {2}
    assert sum(v["replayed"] for v in saved2) == 1
    assert notebooks.save_note(database, project, LOCAL_USER, note, first)["revision"] == 1
    assert notebooks.note(database, project, LOCAL_USER, note, 1)["body"]["text"] == first["body"]["text"]
    with pytest.raises(Conflict):
        notebooks.save_note(database, project, LOCAL_USER, note, edit(revision=1))
    with pytest.raises(Conflict):
        notebooks.save_note(database, project, LOCAL_USER, note, first | {"title": "changed retry"})
    assert notebooks.note(database, project, LOCAL_USER, note)["body"]["text"] == "second"
    assert len(notebooks.versions(database, project, LOCAL_USER, note)["rows"]) == 2
    draft = uuid4()
    notebooks.save_note(database, project, LOCAL_USER, draft, edit("100%_ literal"))
    assert len(notebooks.list_notes(database, project, LOCAL_USER, query="%_", uncategorized=True)["rows"]) == 1
    assert notebooks.list_notes(database, project, LOCAL_USER, query="100%%")["rows"] == []


def test_private_rls_membership_and_csrf(database):
    author = auth.create_user(database, "note-author", "test password for author")
    peer = auth.create_user(database, "note-peer-admin", "test password for peer", admin=True)
    project = database.create_project(author, "private authors")["id"]
    other = database.create_project(author, "other project")["id"]
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'researcher')", (project, peer["id"]))
    note = uuid4()
    notebooks.save_note(database, project, author["id"], note, edit())
    assert notebooks.list_notes(database, project, peer["id"])["rows"] == []
    with pytest.raises(NotFound):
        notebooks.note(database, project, peer["id"], note)
    with pytest.raises(NotFound):
        notebooks.note(database, other, author["id"], note)
    with database.tx(project) as db:
        assert db.execute("SELECT * FROM notes").fetchall() == []
        assert db.execute("SELECT * FROM note_versions").fetchall() == []
    with client_for(database, "server") as client:
        csrf = client.post(
            "/api/v2/login", json={"username": "note-peer-admin", "password": "test password for peer"}
        ).json()["csrf"]
        base = f"/api/v2/projects/{project}/notes"
        assert client.get(base + f"/{note}").status_code == 404
        assert client.put(base + f"/{uuid4()}", json=edit()).status_code == 403
        client.headers["X-CSRF-Token"] = csrf
        own = uuid4()
        assert client.put(base + f"/{own}", json=edit()).status_code == 200
        with database.tx() as db:
            db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (project, peer["id"]))
        assert client.get(base + f"/{own}").status_code == 200
        assert client.put(base + f"/{own}", json=edit(revision=1)).status_code == 403
        with pytest.raises(Forbidden):
            notebooks.save_note(database, project, peer["id"], own, edit(revision=1))


def test_collections_archive_restore_and_version_pins(database):
    project, note, collection = setup(database), uuid4(), uuid4()
    value = {"name": "阶段一", "kind": "notebook"}
    first = notebooks.save_collection(database, project, LOCAL_USER, collection, value)
    assert notebooks.save_collection(database, project, LOCAL_USER, collection, value)["revision"] == 1
    notebooks.save_note(database, project, LOCAL_USER, note, edit(kind="note", collection_id=str(collection)))
    with pytest.raises(Conflict):
        notebooks.archive_collection(database, project, LOCAL_USER, collection, 1)
    op = uuid4()
    archived = notebooks.archive_note(database, project, LOCAL_USER, note, 1, True, op)
    assert archived["revision"] == 2
    assert notebooks.archive_note(database, project, LOCAL_USER, note, 1, True, op)["replayed"]
    assert notebooks.list_notes(database, project, LOCAL_USER, kind="note")["rows"] == []
    assert len(notebooks.list_notes(database, project, LOCAL_USER, kind="note", archived=True)["rows"]) == 1
    notebooks.archive_collection(database, project, LOCAL_USER, collection, first["revision"])
    with pytest.raises(Conflict):
        notebooks.archive_note(database, project, LOCAL_USER, note, 2, False, uuid4())
    notebooks.archive_collection(database, project, LOCAL_USER, collection, 2, False)
    notebooks.archive_note(database, project, LOCAL_USER, note, 2, False, uuid4())
    assert notebooks.note(database, project, LOCAL_USER, note)["revision"] == 3
    assert notebooks.note(database, project, LOCAL_USER, note, 2)["version_metadata"]["archived"]
    default = notebooks.ensure_default(database, project, LOCAL_USER)
    with pytest.raises(Conflict):
        notebooks.archive_collection(database, project, LOCAL_USER, default["id"], 1)


def png():
    stream = io.BytesIO()
    Image.new("RGB", (4, 4), "green").save(stream, format="PNG")
    return stream.getvalue()


def test_image_upload_private_revision_references_and_atomic_save(database):
    project, note, asset = setup(database), uuid4(), uuid4()
    base = f"/api/v2/projects/{project}"
    url = f"{base}/note-assets/{asset}"
    with client_for(database) as client:
        upload = client.put(url + "?filename=test.png", content=png())
        assert upload.status_code == 200, upload.text
        fetched = client.get(url)
        assert fetched.content == png() and fetched.headers["cache-control"] == "no-store"
        assert client.put(f"{base}/notes/{note}", json=edit(f"![test]({url})")).status_code == 200
        assert client.delete(url).status_code == 409
        assert client.put(f"{base}/notes/{note}", json=edit("image removed", revision=1)).status_code == 200
        assert client.delete(url).status_code == 409  # the first revision still pins it
        missing = url.rsplit("/", 1)[0] + "/" + str(uuid4())
        assert client.put(f"{base}/notes/{note}", json=edit(f"![missing]({missing})", revision=2)).status_code == 422
        assert client.get(f"{base}/notes/{note}").json()["revision"] == 2
        assert client.put(url, content=b"<script/>").status_code == 422
        import base64

        damaged = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jL1sAAAAASUVORK5CYII="
        )
        assert client.put(url, content=damaged).status_code == 422
        unused = url.rsplit("/", 1)[0] + "/" + str(uuid4())
        assert client.put(unused + "?filename=unused.png", content=png()).status_code == 200
        assert client.delete(unused).status_code == 200
    peer = auth.create_user(database, "image-peer", "test password for images")
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'researcher')", (project, peer["id"]))
    with pytest.raises(NotFound):
        notebooks.asset(database, project, peer["id"], asset)
    with pytest.raises(ValueError, match="attachment"):
        notebooks.save_note(database, project, peer["id"], uuid4(), edit(f"![x]({url})"))
    assert body_links({"format": "markdown", "text": f"```md\n![x]({url})\n```"}) == set()
    with pytest.raises(ValueError, match="canonical"):
        notebooks.save_note(database, project, LOCAL_USER, uuid4(), edit(f"![x]({url.replace('/api/', '/%61pi/')})"))
    with pytest.raises(ValueError, match="canonical"):
        notebooks.save_note(database, project, LOCAL_USER, uuid4(), edit(f"![x](https://example.invalid{url})"))


def test_saved_revisions_are_immutable_and_invalid_tables_are_rejected(database):
    from psycopg import errors

    from threemind_lab.note_schema import validate_document

    project, note = setup(database), uuid4()
    notebooks.save_note(database, project, LOCAL_USER, note, edit())
    with (
        pytest.raises(errors.ObjectNotInPrerequisiteState),
        notebooks.personal(database, project, LOCAL_USER, write=True) as db,
    ):
        db.execute("UPDATE note_versions SET content_hash='changed' WHERE note_id=%s", (note,))
    with (
        pytest.raises(errors.ObjectNotInPrerequisiteState),
        notebooks.personal(database, project, LOCAL_USER, write=True) as db,
    ):
        db.execute("DELETE FROM note_versions WHERE note_id=%s", (note,))
    paragraph = {"type": "paragraph"}
    cell = {"type": "tableCell", "content": [paragraph]}
    table = {
        "type": "table",
        "content": [{"type": "tableRow", "content": [cell, cell]}, {"type": "tableRow", "content": [cell]}],
    }
    with pytest.raises(ValueError, match="same number"):
        validate_document({"type": "doc", "content": [table]})
    table["content"][1]["content"] = [cell | {"attrs": {"colspan": 2}}]
    assert validate_document({"type": "doc", "content": [table]})


@pytest.mark.parametrize(
    "content",
    [
        {"type": []},
        {"type": "doc", "content": [{"type": {}}]},
        {
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "x", "marks": [{"type": []}]}]}],
        },
        {"type": "doc", "content": [{"type": "image", "attrs": {"src": "javascript:alert(1)"}}]},
        {"type": "doc", "content": [{"type": "paragraph", "attrs": {"textAlign": "left;position:fixed"}}]},
        {"type": "doc", "content": [{"type": "script"}]},
    ],
)
def test_malformed_documents_are_validation_errors(content):
    with pytest.raises(ValueError):
        NoteEdit.model_validate(edit(body={"format": "document", "content": content}))
