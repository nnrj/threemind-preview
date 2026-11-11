"""Private project notebooks, immutable authoring revisions and owned attachments."""

import hashlib
import json
import posixpath
import re
from contextlib import contextmanager
from urllib.parse import unquote, urlsplit
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from . import permissions
from .database import Conflict, NotFound
from .note_schema import CollectionEdit, NoteEdit, body_links, search_text


@contextmanager
def personal(database, project, actor, *, write=False):
    principal = permissions.resolve_actor(database, actor)
    action = principal.get("_request_action")
    if not action or not action.startswith("notes."):
        action = "notes.write" if write else "notes.read"
    permissions.project_access(database, principal, project, write=write, action=action)
    principal = permissions.require(database, principal, action, project=project, owner_id=principal["id"])
    with database.tx(project) as db:
        permissions.set_context(db, principal, project, action=action)
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(principal["id"]),))
        yield db


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def default_notebook(db, project, actor):
    row = db.execute("SELECT * FROM note_collections WHERE is_default AND project_id=%s AND owner_id=%s", (project, actor)).fetchone()
    if row:
        return row
    db.execute(
        "INSERT INTO note_collections(id,project_id,owner_id,kind,name,is_default,auto_named) "
        "VALUES(%s,%s,%s,'notebook','默认笔记本',true,true) ON CONFLICT DO NOTHING",
        (uuid4(), project, actor),
    )
    return db.execute("SELECT * FROM note_collections WHERE is_default AND project_id=%s AND owner_id=%s", (project, actor)).fetchone()


def ensure_default(database, project, actor):
    with personal(database, project, actor, write=True) as db:
        return default_notebook(db, project, actor)


def collections(database, project, actor, *, archived=False):
    with personal(database, project, actor) as db:
        return db.execute(
            "SELECT c.*,count(n.id) AS notes FROM note_collections c LEFT JOIN notes n ON n.collection_id=c.id "
            "AND n.archived_at IS NULL WHERE (c.archived_at IS NOT NULL)=%s GROUP BY c.id ORDER BY c.is_default DESC,c.name,c.id",
            (archived,),
        ).fetchall()


def save_collection(database, project, actor, collection, value):
    value = CollectionEdit.model_validate(value)
    with personal(database, project, actor, write=True) as db:
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("note-collection:" + str(collection),))
        row = db.execute("SELECT * FROM note_collections WHERE id=%s FOR UPDATE", (collection,)).fetchone()
        if not row:
            if value.expected_revision:
                raise NotFound()
            return db.execute(
                "INSERT INTO note_collections(id,project_id,owner_id,kind,name,color) VALUES(%s,%s,%s,%s,%s,%s) RETURNING *",
                (collection, project, actor, value.kind, value.name, value.color),
            ).fetchone()
        if (
            row["revision"] == value.expected_revision + 1
            and not row["archived_at"]
            and all(row[key] == getattr(value, key) for key in ("kind", "name", "color"))
        ):
            return row
        if row["revision"] != value.expected_revision or row["archived_at"]:
            raise Conflict("collection changed; reload before saving")
        if row["kind"] != value.kind:
            raise ValueError("collection type cannot change")
        return db.execute(
            "UPDATE note_collections SET name=%s,color=%s,auto_named=false,revision=revision+1,updated_at=now() WHERE id=%s RETURNING *",
            (value.name, value.color, collection),
        ).fetchone()


def archive_collection(database, project, actor, collection, revision, archived=True):
    with personal(database, project, actor, write=True) as db:
        row = db.execute("SELECT * FROM note_collections WHERE id=%s FOR UPDATE", (collection,)).fetchone()
        if not row:
            raise NotFound()
        if row["revision"] != revision:
            raise Conflict("collection changed; reload before archiving")
        if row["is_default"] and archived:
            raise Conflict("the default notebook must remain available")
        if (
            archived
            and db.execute(
                "SELECT 1 FROM notes WHERE collection_id=%s AND archived_at IS NULL LIMIT 1", (collection,)
            ).fetchone()
        ):
            raise Conflict("move or archive the notes before archiving this collection")
        return db.execute(
            "UPDATE note_collections SET archived_at=CASE WHEN %s THEN now() ELSE NULL END,revision=revision+1 WHERE id=%s RETURNING id,revision",
            (archived, collection),
        ).fetchone()


def note(database, project, actor, note_id, revision=None):
    with personal(database, project, actor) as db:
        row = db.execute(
            "SELECT n.*,v.body,v.content_hash,v.metadata AS version_metadata,v.revision AS content_revision "
            "FROM notes n JOIN note_versions v ON v.note_id=n.id AND v.revision=coalesce(%s,n.revision) WHERE n.id=%s",
            (revision, note_id),
        ).fetchone()
        if not row:
            raise NotFound()
        return row


def list_notes(
    database,
    project,
    actor,
    *,
    kind="draft",
    collection=None,
    query="",
    sort="updated",
    offset=0,
    archived=False,
    uncategorized=False,
):
    if kind not in ("draft", "note") or sort not in ("updated", "created", "title") or not 0 <= offset <= 100000:
        raise ValueError("invalid note filter")
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    order = {
        "updated": "n.updated_at DESC,n.id DESC",
        "created": "n.created_at DESC,n.id DESC",
        "title": "n.title,n.id",
    }[sort]
    with personal(database, project, actor) as db:
        rows = db.execute(
            "SELECT n.id,n.title,n.kind,n.collection_id,n.revision,n.archived_at,n.created_at,n.updated_at,"
            "left(n.search_text,180) AS excerpt,c.name AS collection_name,c.auto_named "
            "FROM notes n LEFT JOIN note_collections c ON c.id=n.collection_id "
            "WHERE n.kind=%s AND (n.archived_at IS NOT NULL)=%s "
            "AND (%s::uuid IS NULL OR n.collection_id=%s) AND (n.title ILIKE %s OR n.search_text ILIKE %s) "
            "AND (NOT %s OR n.collection_id IS NULL) "
            "ORDER BY " + order + " LIMIT 51 OFFSET %s",
            (kind, archived, collection, collection, f"%{escaped}%", f"%{escaped}%", uncategorized, offset),
        ).fetchall()
        return {"rows": rows[:50], "more": len(rows) > 50}


def save_note(database, project, actor, note_id, value, *, transaction=None):
    from contextlib import nullcontext
    value = NoteEdit.model_validate(value)
    request_hash = digest(value.model_dump(mode="json"))
    body = value.body.model_dump(mode="json")
    urls = body_links(body)
    asset_ids = set()
    for url in urls:
        parsed = urlsplit(url)
        decoded_path = posixpath.normpath(unquote(parsed.path))
        if decoded_path.startswith("/api/v2/") and "/note-assets/" in decoded_path:
            if parsed.scheme or parsed.netloc or parsed.path != decoded_path:
                raise ValueError("use the canonical local URL for note attachments")
            match = re.fullmatch(r"/api/v2/projects/([0-9a-fA-F-]{36})/note-assets/([0-9a-fA-F-]{36})", decoded_path)
            if not match or UUID(match[1]) != UUID(str(project)):
                raise ValueError("note attachment belongs to a different project")
            asset_ids.add(UUID(match[2]))
    with personal(database, project, actor, write=True) if transaction is None else nullcontext(transaction) as db:
        # Serializes first creation too, and makes duplicate retries return their
        # original revision even when a subsequent save has already succeeded.
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("note:" + str(note_id),))
        previous = db.execute(
            "SELECT revision,request_hash FROM note_versions WHERE note_id=%s AND operation_id=%s",
            (note_id, value.operation_id),
        ).fetchone()
        if previous:
            if previous["request_hash"] != request_hash:
                raise Conflict("operation ID reused with different note content")
            return {"id": note_id, "revision": previous["revision"], "replayed": True}
        row = db.execute("SELECT * FROM notes WHERE id=%s FOR UPDATE", (note_id,)).fetchone()
        current = row["revision"] if row else 0
        if current != value.expected_revision:
            raise Conflict("note changed; current draft was not saved over the newer revision")
        if row and row["archived_at"]:
            raise Conflict("restore the note before editing")
        author = row["owner_id"] if row else actor
        selected = value.collection_id
        if value.kind == "note" and selected is None:
            selected = default_notebook(db, project, author)["id"]
        if selected:
            container = db.execute(
                "SELECT kind FROM note_collections WHERE id=%s AND owner_id=%s AND archived_at IS NULL FOR SHARE", (selected, author)
            ).fetchone()
            if not container or container["kind"] != ("notebook" if value.kind == "note" else "category"):
                raise ValueError("select an available notebook or draft category")
        if asset_ids:
            found = db.execute("SELECT id FROM note_assets WHERE id=ANY(%s) AND owner_id=%s FOR SHARE", (list(asset_ids), author)).fetchall()
            if {r["id"] for r in found} != asset_ids:
                raise ValueError("a note attachment is unavailable or belongs to another author")
        revision = current + 1
        metadata = {"title": value.title, "kind": value.kind, "collection_id": str(selected) if selected else None}
        if str(author) != str(actor):
            metadata["editor_actor_id"] = str(actor)
        text = search_text(body)
        if row:
            db.execute(
                "UPDATE notes SET title=%s,kind=%s,collection_id=%s,revision=%s,search_text=%s,updated_at=now() WHERE id=%s",
                (value.title, value.kind, selected, revision, text, note_id),
            )
        else:
            db.execute(
                "INSERT INTO notes(id,project_id,owner_id,title,kind,collection_id,revision,search_text) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (note_id, project, actor, value.title, value.kind, selected, revision, text),
            )
        content_hash = digest({"metadata": metadata, "body": body})
        db.execute(
            "INSERT INTO note_versions(project_id,owner_id,note_id,revision,operation_id,request_hash,metadata,body,content_hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                project,
                author,
                note_id,
                revision,
                value.operation_id,
                request_hash,
                Jsonb(metadata),
                Jsonb(body),
                content_hash,
            ),
        )
        for asset in asset_ids:
            db.execute("INSERT INTO note_asset_refs VALUES(%s,%s,%s,%s,%s)", (project, author, note_id, revision, asset))
        return {
            "id": note_id,
            "revision": revision,
            "collection_id": selected,
            "content_hash": content_hash,
            "replayed": False,
        }


def versions(database, project, actor, note_id, before=None):
    with personal(database, project, actor) as db:
        if not db.execute("SELECT 1 FROM notes WHERE id=%s", (note_id,)).fetchone():
            raise NotFound()
        rows = db.execute(
            "SELECT revision,metadata,content_hash,created_at FROM note_versions WHERE note_id=%s AND (%s::bigint IS NULL OR revision<%s) ORDER BY revision DESC LIMIT 51",
            (note_id, before, before),
        ).fetchall()
        return {"rows": rows[:50], "more": len(rows) > 50, "next": rows[49]["revision"] if len(rows) > 50 else None}


def archive_note(database, project, actor, note_id, revision, archived, operation_id):
    request_hash = digest({"action": "archive", "revision": revision, "archived": archived})
    with personal(database, project, actor, write=True) as db:
        row = db.execute(
            "SELECT revision,archived_at,collection_id,owner_id FROM notes WHERE id=%s FOR UPDATE", (note_id,)
        ).fetchone()
        if not row:
            raise NotFound()
        previous = db.execute(
            "SELECT revision,request_hash FROM note_versions WHERE note_id=%s AND operation_id=%s",
            (note_id, operation_id),
        ).fetchone()
        if previous:
            if previous["request_hash"] != request_hash:
                raise Conflict("operation ID reused with a different archive request")
            return {"id": note_id, "archived": archived, "revision": previous["revision"], "replayed": True}
        if row["revision"] != revision:
            raise Conflict("note changed; reload before changing archive state")
        if (
            not archived
            and row["collection_id"]
            and not db.execute(
                "SELECT 1 FROM note_collections WHERE id=%s AND archived_at IS NULL FOR SHARE", (row["collection_id"],)
            ).fetchone()
        ):
            raise Conflict("the collection is archived; restore its notebook or category first")
        source = db.execute(
            "SELECT metadata,body FROM note_versions WHERE note_id=%s AND revision=%s", (note_id, revision)
        ).fetchone()
        metadata = source["metadata"] | {"archived": archived}
        if str(row["owner_id"]) != str(actor):
            metadata["editor_actor_id"] = str(actor)
        content_hash = digest({"metadata": metadata, "body": source["body"]})
        db.execute(
            "INSERT INTO note_versions(project_id,owner_id,note_id,revision,operation_id,request_hash,metadata,body,content_hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                project,
                row["owner_id"],
                note_id,
                revision + 1,
                operation_id,
                request_hash,
                Jsonb(metadata),
                Jsonb(source["body"]),
                content_hash,
            ),
        )
        db.execute(
            "INSERT INTO note_asset_refs SELECT project_id,owner_id,note_id,%s,asset_id FROM note_asset_refs WHERE note_id=%s AND revision=%s",
            (revision + 1, note_id, revision),
        )
        db.execute(
            "UPDATE notes SET archived_at=CASE WHEN %s THEN now() ELSE NULL END,revision=revision+1,updated_at=now() WHERE id=%s",
            (archived, note_id),
        )
        return {"id": note_id, "archived": archived, "revision": revision + 1, "replayed": False}


def save_asset(database, project, actor, asset_id, name, content):
    import io
    import warnings

    from PIL import Image

    from .note_schema import bounded_text

    bounded_text(name, 800)
    if not name.strip() or not 1 <= len(content) <= 8 * 1024 * 1024:
        raise ValueError("note images require a name and at most 8 MiB")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(content)) as image:
                if (
                    image.format not in ("PNG", "JPEG", "WEBP")
                    or image.width * image.height > 16000000
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError("use a still PNG, JPEG or WebP with at most 16 million pixels")
                mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[image.format]
                image.verify()
        except (OSError, SyntaxError, EOFError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
            raise ValueError("invalid or oversized note image") from error
    sha = hashlib.sha256(content).hexdigest()
    prepared_blob = database.blobs.prepare(
        project, "note-image", (content[i : i + 1048576] for i in range(0, len(content), 1048576))
    )
    with personal(database, project, actor, write=True) as db:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ("note-assets:" + str(project) + ":" + str(actor),)
        )
        row = db.execute("SELECT id,name,mime,bytes,sha256 FROM note_assets WHERE id=%s", (asset_id,)).fetchone()
        if row:
            if row["sha256"] != sha or row["name"] != name:
                raise Conflict("upload ID reused for a different note image")
            return row
        total = db.execute("SELECT coalesce(sum(bytes),0) AS bytes FROM note_assets WHERE owner_id=%s", (actor,)).fetchone()["bytes"]
        if int(total) + len(content) > 1024 * 1024 * 1024:
            raise Conflict("personal note images exceed the 1 GiB project budget; remove unused images first")
        return db.execute(
            "INSERT INTO note_assets(id,project_id,owner_id,name,mime,bytes,sha256,content,blob_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,name,mime,bytes,sha256",
            (
                asset_id,
                project,
                actor,
                name,
                mime,
                len(content),
                sha,
                None if prepared_blob else content,
                database.blobs.attach(db, prepared_blob),
            ),
        ).fetchone()


def asset(database, project, actor, asset_id):
    with personal(database, project, actor) as db:
        row = db.execute(
            "SELECT name,mime,bytes,content,sha256,blob_id FROM note_assets WHERE id=%s", (asset_id,)
        ).fetchone()
        if not row:
            raise NotFound()
        blob = (
            db.execute("SELECT * FROM stored_blobs WHERE id=%s", (row["blob_id"],)).fetchone()
            if row["blob_id"]
            else None
        )
    if row["blob_id"]:
        if not blob or blob["sha256"] != row["sha256"] or blob["bytes"] != row["bytes"]:
            raise ValueError("note image blob is unavailable")
        if not 0 < row["bytes"] <= 8 * 1024**2:
            raise ValueError("note image exceeds its read budget")
        row["content"] = b"".join(database.blobs.read(blob))
    row.pop("blob_id")
    row.pop("bytes")
    return row


def assets(database, project, actor, offset=0):
    with personal(database, project, actor) as db:
        rows = db.execute(
            "SELECT a.id,a.name,a.mime,a.bytes,a.sha256,a.created_at,EXISTS(SELECT 1 FROM note_asset_refs r WHERE r.asset_id=a.id) AS referenced FROM note_assets a ORDER BY a.created_at DESC,a.id DESC LIMIT 51 OFFSET %s",
            (offset,),
        ).fetchall()
        return {"rows": rows[:50], "more": len(rows) > 50}


def delete_asset(database, project, actor, asset_id):
    with personal(database, project, actor, write=True) as db:
        row = db.execute("SELECT id FROM note_assets WHERE id=%s FOR UPDATE", (asset_id,)).fetchone()
        if not row:
            raise NotFound()
        if db.execute("SELECT 1 FROM note_asset_refs WHERE asset_id=%s LIMIT 1", (asset_id,)).fetchone():
            raise Conflict("image is referenced by a saved note revision")
        db.execute("DELETE FROM note_assets WHERE id=%s", (asset_id,))
        return {"deleted": asset_id}
