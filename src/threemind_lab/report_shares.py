"""Explicit publication of completed, immutable document export revisions."""

import hashlib
from datetime import timedelta
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import Field

from . import research_documents
from .database import Conflict, NotFound
from .notebooks import digest
from .permissions import connection_access
from .protocols import StrictModel

MAX_BODY_BYTES = 32 * 1024**2
MAX_BUNDLE_BYTES = 8 * 1024**3
PUBLIC_FIELDS = "id,revision,metadata,created_at,expires_at,revoked_at"
PUBLISHER_ACTIVE = """u.enabled AND EXISTS(
    SELECT 1 FROM platform_user_roles ur JOIN platform_roles r ON r.id=ur.role_id
    WHERE ur.user_id=s.actor_id AND (r.key='superadmin'
      OR r.permissions @> '[{"action":"reports.share","scope":"all_projects"}]'::jsonb
      OR (m.role='owner' AND r.permissions @> '[{"action":"reports.share","scope":"member_projects"}]'::jsonb)))"""


def require_actor(db, project, actor, *, owner=False):
    return connection_access(db, actor, project, action="reports.share", write=True, owner=owner)


class ShareRequest(StrictModel):
    operation_id: UUID
    export_id: UUID
    expected_body_hash: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    expires_days: int | None = Field(default=7, ge=1, le=3650, strict=True)
    include_bundle: bool = Field(default=False, strict=True)


def artifact(db, identifier, job_id):
    row = db.execute("SELECT * FROM artifacts WHERE id=%s AND job_id=%s FOR UPDATE", (identifier, job_id)).fetchone()
    if row is None:
        raise Conflict("the selected export artifact is unavailable")
    return row


def file_metadata(row):
    return {"sha256": row["sha256"], "bytes": row["bytes"], "media_type": row["media_type"]}


def artifact_identity(row):
    return str(row["id"]), row["sha256"], int(row["bytes"]), str(row.get("blob_id"))


def create(database, project, actor, document_id, body):
    body = ShareRequest.model_validate(body)
    fingerprint = digest(
        {
            "document_id": str(document_id),
            "actor_id": str(actor),
            **body.model_dump(mode="json", exclude={"operation_id"}),
        }
    )
    # Verify every published body before taking publishing locks. Slow external
    # reads and visitor backpressure never occupy a database connection. The
    # publishing transaction rechecks these exact frozen resource identities.
    verified = {}
    with database.tx(project) as inspection:
        require_actor(inspection, project, actor, owner=True)
        inspection.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
        previous = inspection.execute(
            "SELECT " + PUBLIC_FIELDS + ",request_hash FROM research_document_shares WHERE operation_id=%s",
            (body.operation_id,),
        ).fetchone()
        if previous:
            if previous.pop("request_hash") != fingerprint:
                raise Conflict("share operation ID reused with different publication options")
            return previous | {"replayed": True}
        candidate = inspection.execute(
            "SELECT e.job_id,j.result FROM research_document_exports e JOIN jobs j ON j.id=e.job_id "
            "WHERE e.id=%s AND e.document_id=%s AND j.status='done'",
            (body.export_id, document_id),
        ).fetchone()
        selected = []
        if candidate:
            for kind in ("body", "bundle") if body.include_bundle else ("body",):
                key = "artifact_id" if kind == "body" else "bundle_artifact_id"
                row = inspection.execute(
                    "SELECT * FROM artifacts WHERE id=%s AND job_id=%s",
                    (candidate["result"].get(key), candidate["job_id"]),
                ).fetchone()
                if row:
                    selected.append((kind, row))
    from .blob_store import object_chunks

    for kind, row in selected:
        maximum = MAX_BODY_BYTES if kind == "body" else MAX_BUNDLE_BYTES
        if not 0 < int(row["bytes"]) <= maximum:
            raise Conflict("published export exceeds its verification budget")
        if kind == "body" and row["sha256"] != body.expected_body_hash:
            raise Conflict("the prepared body changed; preview and confirm its current hash")
        checksum, size = hashlib.sha256(), 0
        try:
            for raw in object_chunks(database, project, "artifact", row["id"], actor=actor):
                checksum.update(raw)
                size += len(raw)
                if size > maximum:
                    raise Conflict("published export exceeds its verification budget")
        except (ValueError, OSError) as error:
            raise Conflict("prepared export bytes failed integrity verification") from error
        if size != row["bytes"] or checksum.hexdigest() != row["sha256"]:
            raise Conflict("prepared export bytes failed integrity verification")
        verified[kind] = artifact_identity(row)
    with database.tx(project) as db:
        require_actor(db, project, actor, owner=True)
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
        # Also serializes concurrent publication count and lost-acknowledgement retries.
        db.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project,))
        previous = db.execute(
            "SELECT " + PUBLIC_FIELDS + ",request_hash FROM research_document_shares WHERE operation_id=%s",
            (body.operation_id,),
        ).fetchone()
        if previous:
            if previous.pop("request_hash") != fingerprint:
                raise Conflict("share operation ID reused with different publication options")
            return previous | {"replayed": True}
        export = db.execute(
            "SELECT e.*,j.status,j.result FROM research_document_exports e JOIN jobs j ON j.id=e.job_id "
            "WHERE e.id=%s AND e.document_id=%s",
            (body.export_id, document_id),
        ).fetchone()
        if export is None or export["status"] != "done" or export["options"]["format"] != "html":
            raise Conflict("prepare a completed HTML export of this document before sharing")
        if body.include_bundle and not export["options"]["include_data"]:
            raise Conflict("prepare an export with complete evidence rows before sharing an evidence bundle")
        document = research_documents.document(db, document_id, export["revision"])
        if document["content_hash"] != export["result"]["document_hash"]:
            raise Conflict("export document hash does not match its fixed revision")
        main = artifact(db, export["result"]["artifact_id"], export["job_id"])
        if main["media_type"].split(";")[0] != "text/html" or not 0 < main["bytes"] <= MAX_BODY_BYTES:
            raise Conflict("shared HTML bodies must fit the 32 MiB preview budget; split the document")
        if body.expected_body_hash != main["sha256"] or main["sha256"] != export["result"]["sha256"]:
            raise Conflict("the prepared body changed; preview and confirm its current hash")
        if verified.get("body") != artifact_identity(main):
            raise Conflict("export was not verified for this revision")
        bundle = artifact(db, export["result"]["bundle_artifact_id"], export["job_id"]) if body.include_bundle else None
        if bundle and (
            bundle["media_type"] != "application/zip" or bundle["sha256"] != export["result"]["bundle_sha256"]
        ):
            raise Conflict("prepared evidence bundle does not match the completed export")
        if bundle and verified.get("bundle") != artifact_identity(bundle):
            raise Conflict("evidence bundle was not verified for this revision")
        count = db.execute(
            "SELECT count(*) AS n FROM research_document_shares WHERE revoked_at IS NULL "
            "AND (expires_at IS NULL OR expires_at>clock_timestamp())"
        ).fetchone()["n"]
        if count >= 1000:
            raise Conflict("this project has 1000 active publications; revoke unused links first")
        created = db.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
        recorded_ai = db.execute(
            "SELECT 1 FROM research_document_versions v WHERE v.document_id=%s AND v.revision=%s "
            "AND (v.ai_call_id IS NOT NULL OR v.import_ai_generated) UNION ALL "
            "SELECT 1 FROM research_document_refs r JOIN research_document_versions v "
            "ON v.document_id=r.record_id AND v.revision=r.record_revision "
            "WHERE r.document_id=%s AND r.revision=%s "
            "AND (v.ai_call_id IS NOT NULL OR v.import_ai_generated) LIMIT 1",
            (document_id, export["revision"], document_id, export["revision"]),
        ).fetchone()
        metadata = {
            "title": document["spec"]["title"],
            "kind": document["kind"],
            "document_hash": document["content_hash"],
            "review": document["review"],
            "ai_generated": bool(document["ai_call_id"] or recorded_ai),
            "language": export["options"]["language"],
            "body": file_metadata(main),
            "bundle": file_metadata(bundle) if bundle else None,
        }
        row = db.execute(
            "INSERT INTO research_document_shares(id,project_id,document_id,revision,export_id,actor_id,operation_id,"
            "request_hash,body_artifact_id,bundle_artifact_id,metadata,created_at,expires_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING " + PUBLIC_FIELDS,
            (
                uuid4(),
                project,
                document_id,
                export["revision"],
                export["id"],
                actor,
                body.operation_id,
                fingerprint,
                main["id"],
                bundle["id"] if bundle else None,
                Jsonb(metadata),
                created,
                created + timedelta(days=body.expires_days) if body.expires_days is not None else None,
            ),
        ).fetchone()
        return row | {"replayed": False}


def listing(database, project, actor, document_id, offset=0):
    with database.tx(project) as db:
        require_actor(db, project, actor, owner=True)
        research_documents.document(db, document_id)
        rows = db.execute(
            "SELECT s.*,CASE WHEN s.revoked_at IS NOT NULL THEN 'revoked' "
            "WHEN s.expires_at<=clock_timestamp() THEN 'expired' "
            "WHEN NOT coalesce(" + PUBLISHER_ACTIVE + ",false) THEN 'unavailable' ELSE 'active' END AS status "
            "FROM research_document_shares s LEFT JOIN users u ON u.id=s.actor_id "
            "LEFT JOIN members m ON m.project_id=s.project_id AND m.user_id=s.actor_id "
            "WHERE s.document_id=%s ORDER BY s.created_at DESC,s.id DESC LIMIT 21 OFFSET %s",
            (document_id, offset),
        ).fetchall()
        return {
            "rows": [{key: row[key] for key in (*PUBLIC_FIELDS.split(","), "status")} for row in rows[:20]],
            "more": len(rows) > 20,
        }


def revoke(database, project, actor, document_id, share_id):
    with database.tx(project) as db:
        require_actor(db, project, actor, owner=True)
        row = db.execute(
            "UPDATE research_document_shares SET revoked_at=coalesce(revoked_at,clock_timestamp()) "
            "WHERE id=%s AND document_id=%s RETURNING " + PUBLIC_FIELDS,
            (share_id, document_id),
        ).fetchone()
        if row is None:
            raise NotFound()
        return row


def resolve(database, share_id):
    with database.tx() as db:
        db.execute("SELECT set_config('tm.shared_document_id',%s,true)", (str(share_id),))
        row = db.execute(
            "SELECT s.* FROM research_document_shares s JOIN users u ON u.id=s.actor_id "
            "LEFT JOIN members m ON m.project_id=s.project_id AND m.user_id=s.actor_id "
            "WHERE s.id=%s AND s.revoked_at IS NULL AND (s.expires_at IS NULL OR s.expires_at>clock_timestamp()) "
            "AND " + PUBLISHER_ACTIVE,
            (share_id,),
        ).fetchone()
        if row is None:
            raise NotFound()
        return row


def public_metadata(database, share_id):
    row = resolve(database, share_id)
    return {key: row[key] for key in PUBLIC_FIELDS.split(",") if key != "revoked_at"}


def file_stream(database, publication, kind):
    identifier = publication[f"{kind}_artifact_id"]
    from .blob_store import object_chunks

    yield from object_chunks(database, publication["project_id"], "artifact", identifier, actor=publication["actor_id"])
