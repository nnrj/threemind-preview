"""Experiment packaging through the same project authorization as research UI."""

import hashlib
from uuid import UUID, uuid4

from fastapi import HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from psycopg.types.json import Jsonb
from pydantic import Field

from .database import Conflict, Forbidden, NotFound
from .experiment_archive import CHUNK, canonical
from .experiment_bundles import (
    GIB,
    bundle_chunks,
    compatible,
    export_private,
    export_source_targets,
    get_bundle,
    open_bundle,
    resume_source_targets,
)
from .protocols import StrictModel
from .provenance import capture_implementation


class BundleExport(StrictModel):
    name: str = Field("实验快照", min_length=1, max_length=160)
    expected_revision: int = Field(ge=1, strict=True)
    note_ids: list[UUID] = Field(default_factory=list, max_length=20)
    document_ids: list[UUID] = Field(default_factory=list, max_length=20)
    artifact_ids: list[UUID] = Field(default_factory=list, max_length=20)


class BundleUpload(StrictModel):
    request_id: UUID
    name: str = Field(min_length=1, max_length=160)
    bytes: int = Field(gt=0, le=8 * GIB, strict=True)
    sha256: str | None = Field(None, pattern=r"^[0-9a-f]{64}$")


class BundleResume(StrictModel):
    request_id: UUID
    name: str = Field(min_length=1, max_length=160)
    acknowledge_external_changes: bool = Field(False, strict=True)


def register(app, access):
    prefix = "/api/v2/projects/{project}"

    @app.post(prefix + "/runs/{run_id}/bundles", status_code=202)
    def export(project: UUID, run_id: UUID, body: BundleExport, request: Request):
        actor = access(request, project, write=True)
        with app.state.db.tx(project) as db:
            run = db.execute("SELECT * FROM runs WHERE id=%s FOR UPDATE", (run_id,)).fetchone()
            if run is None:
                raise NotFound()
            if run["revision"] != body.expected_revision or run["status"] in ("running", "queued"):
                raise Conflict("请先暂停，并使用当前已提交修订号打包。")
            cp = db.execute(
                "SELECT id FROM checkpoints WHERE run_id=%s AND revision=%s", (run_id, run["revision"])
            ).fetchone()
            if cp is None:
                raise Conflict("没有可打包的恢复点。")
            job = uuid4()
            params = body.model_dump(mode="json") | {
                "checkpoint_id": str(cp["id"]),
                "actor_id": str(actor["id"]),
                "storage_policy": app.state.db.blobs.freeze("export"),
            }
            params["source_targets"] = export_source_targets(db, run_id, params)
            params["private"] = export_private(db, params)
            return db.execute(
                "INSERT INTO jobs(id,project_id,run_id,kind,params) VALUES(%s,%s,%s,'bundle_export',%s) RETURNING *",
                (job, project, run_id, Jsonb(params)),
            ).fetchone()

    @app.get(prefix + "/bundles")
    def listing(project: UUID, request: Request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
            rows = db.execute(
                "SELECT id,name,bytes,sha256,created_at,manifest->'metadata' AS metadata FROM experiment_bundles ORDER BY created_at DESC,id LIMIT %s OFFSET %s",
                (limit + 1, offset),
            ).fetchall()
        return {"rows": rows[:limit], "more": len(rows) > limit, "offset": offset}

    @app.get(prefix + "/bundles/{bundle_id}")
    def detail(project: UUID, bundle_id: UUID, request: Request):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
            bundle = get_bundle(db, bundle_id)
        return bundle | {
            "compatibility": compatible(bundle["manifest"], capture_implementation(app.state.settings.backend))
        }

    @app.get(prefix + "/bundles/{bundle_id}/download")
    def download(project: UUID, bundle_id: UUID, request: Request):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
            bundle = get_bundle(db, bundle_id)
        return StreamingResponse(
            bundle_chunks(app.state.db, project, bundle),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{bundle_id}.tmexperiment"',
                "Content-Length": str(bundle["bytes"]),
                "ETag": '"' + bundle["sha256"] + '"',
                "X-Content-SHA256": bundle["sha256"],
            },
        )

    @app.get(prefix + "/bundles/{bundle_id}/entry")
    def entry(
        project: UUID,
        bundle_id: UUID,
        request: Request,
        name: str = Query(max_length=240),
        offset: int = Query(0, ge=0, le=100000),
        limit: int = Query(50, ge=1, le=200),
    ):
        actor = access(request, project)
        with app.state.db.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
            bundle = get_bundle(db, bundle_id)
        # Paginate actual evidence. Binary state is available via download, not
        # materialized into a huge JSON response or executed for a preview.
        with open_bundle(app.state.db, project, bundle) as reader:
            if name not in reader.manifest["files"]:
                raise NotFound()
            mime = reader.manifest["files"][name]["media_type"]
            if mime == "application/json":
                return {"entry": name, "value": reader.json(name, maximum=4 * 1024**2)}
            if mime != "application/x-ndjson":
                raise ValueError("该条目为二进制；请下载实验包查看。")
            from itertools import islice

            rows = reader.rows(name)
            try:
                page, preview_bytes = [], 0
                for row in islice(rows, offset, offset + limit + 1):
                    preview_bytes += len(canonical(row))
                    if preview_bytes > 4 * 1024**2:
                        raise ValueError("本页证据超过 4 MiB 预览预算；请减少 limit 或下载完整实验包。")
                    page.append(row)
            finally:
                rows.close()
            return {"entry": name, "rows": page[:limit], "more": len(page) > limit, "offset": offset}

    @app.post(prefix + "/bundles/{bundle_id}/resumes", status_code=202)
    def resume(project: UUID, bundle_id: UUID, body: BundleResume, request: Request):
        actor = access(request, project, write=True)
        with app.state.db.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
            bundle = get_bundle(db, bundle_id)
        conditions = compatible(bundle["manifest"], capture_implementation(app.state.settings.backend))
        if not conditions["can_resume"]:
            raise Conflict("；".join(conditions["blockers"]))
        if conditions["external_changes"] and not body.acknowledge_external_changes:
            raise Conflict("请确认恢复时外设/遥测条件变化。")
        with app.state.db.tx(project) as db:
            db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
            bundle = get_bundle(db, bundle_id)
            params = body.model_dump(mode="json") | {
                "bundle_id": str(bundle_id),
                "actor_id": str(actor["id"]),
                "source_targets": resume_source_targets(db, bundle),
            }
            return db.execute(
                "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'bundle_resume',%s) RETURNING *",
                (uuid4(), project, Jsonb(params)),
            ).fetchone()

    @app.post(prefix + "/bundle-uploads", status_code=201)
    def upload(project: UUID, body: BundleUpload, request: Request):
        actor = access(request, project, write=True)
        with app.state.db.tx(project) as db:
            # Serialize admissions in this project; concurrent uploads cannot all
            # pass the staging budget before any row is visible.
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,53))", (str(project),))
            old = db.execute(
                "SELECT * FROM bundle_uploads WHERE project_id=%s AND actor_id=%s AND request_id=%s",
                (project, actor["id"], body.request_id),
            ).fetchone()
            if old:
                if (
                    any(str(old[k]) != str(getattr(body, k)) for k in ("name", "bytes"))
                    or body.sha256 is not None
                    and old["sha256"] != body.sha256
                ):
                    raise Conflict("上传编号已用于不同文件。")
                return old
            used = db.execute("SELECT coalesce(sum(bytes),0) AS n FROM bundle_uploads").fetchone()["n"]
            if int(used) + body.bytes > 20 * GIB:
                raise Conflict("项目实验包上传预算为 20 GiB；请人工检查已有数据，系统不会自动清理。")
            return db.execute(
                "INSERT INTO bundle_uploads(id,project_id,actor_id,request_id,name,bytes,sha256) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (uuid4(), project, actor["id"], body.request_id, body.name, body.bytes, body.sha256),
            ).fetchone()

    def owned_upload(db, upload_id, actor):
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
        row = db.execute("SELECT * FROM bundle_uploads WHERE id=%s FOR UPDATE", (upload_id,)).fetchone()
        if row is None:
            raise NotFound()
        from . import permissions
        principal = permissions.current_actor()
        if str(row["actor_id"]) != str(actor) and not (principal and principal.get("superadmin") and str(principal["id"]) == str(actor)):
            raise Forbidden()
        return row

    @app.get(prefix + "/bundle-uploads/{upload_id}")
    def upload_status(project: UUID, upload_id: UUID, request: Request):
        actor = access(request, project, write=True)
        with app.state.db.tx(project) as db:
            row = owned_upload(db, upload_id, actor["id"])
            chunks = db.execute(
                "SELECT ordinal,sha256,octet_length(body) AS bytes FROM bundle_upload_chunks WHERE upload_id=%s ORDER BY ordinal",
                (upload_id,),
            ).fetchall()
        return row | {"chunks": chunks, "chunk_bytes": CHUNK}

    @app.put(
        prefix + "/bundle-uploads/{upload_id}/chunks/{ordinal}",
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
            }
        },
    )
    async def chunk(project: UUID, upload_id: UUID, ordinal: int, request: Request):
        actor = access(request, project, write=True)
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > CHUNK:
                raise HTTPException(413, "单块不得超过 4 MiB。")
        checksum = hashlib.sha256(raw).hexdigest()
        with app.state.db.tx(project) as db:
            row = owned_upload(db, upload_id, actor["id"])
            expected = min(CHUNK, int(row["bytes"]) - ordinal * CHUNK)
            if ordinal < 0 or expected <= 0 or len(raw) != expected:
                raise ValueError("分块大小或编号与已声明文件不一致。")
            old = db.execute(
                "SELECT sha256 FROM bundle_upload_chunks WHERE upload_id=%s AND ordinal=%s", (upload_id, ordinal)
            ).fetchone()
            if old:
                if old["sha256"] != checksum:
                    raise Conflict("相同分块编号的内容不同。")
                return {"ordinal": ordinal, "sha256": checksum, "replayed": True}
            if row["status"] != "receiving":
                raise Conflict("上传已提交，不能追加。")
            db.execute(
                "INSERT INTO bundle_upload_chunks VALUES(%s,%s,%s,%s,%s)",
                (project, upload_id, ordinal, checksum, bytes(raw)),
            )
        return {"ordinal": ordinal, "sha256": checksum, "bytes": len(raw)}

    @app.post(prefix + "/bundle-uploads/{upload_id}/complete", status_code=202)
    def complete(project: UUID, upload_id: UUID, request: Request):
        actor = access(request, project, write=True)
        with app.state.db.tx(project) as db:
            row = owned_upload(db, upload_id, actor["id"])
            if row["job_id"]:
                return db.execute("SELECT * FROM jobs WHERE id=%s", (row["job_id"],)).fetchone()
            count = db.execute(
                "SELECT count(*) n,coalesce(sum(octet_length(body)),0) bytes FROM bundle_upload_chunks WHERE upload_id=%s",
                (upload_id,),
            ).fetchone()
            if int(count["bytes"]) != int(row["bytes"]) or count["n"] != (int(row["bytes"]) + CHUNK - 1) // CHUNK:
                raise Conflict("仍有缺失分块，不能提交。")
            job = db.execute(
                "INSERT INTO jobs(id,project_id,kind,params) VALUES(%s,%s,'bundle_import',%s) RETURNING *",
                (uuid4(), project, Jsonb({"upload_id": str(upload_id)})),
            ).fetchone()
            db.execute("UPDATE bundle_uploads SET status='queued',job_id=%s WHERE id=%s", (job["id"], upload_id))
        return job

    @app.post(prefix + "/bundle-jobs/{job_id}/cancel")
    def cancel(project: UUID, job_id: UUID, request: Request):
        access(request, project, write=True)
        with app.state.db.tx(project) as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE id=%s AND project_id=%s FOR UPDATE", (job_id, project)
            ).fetchone()
            if row is None or row["kind"] not in ("bundle_export", "bundle_import", "bundle_resume"):
                raise NotFound()
            if row["status"] == "pending":
                db.execute("UPDATE jobs SET status='cancelled',error='user cancelled' WHERE id=%s", (job_id,))
            elif row["status"] == "leased":
                db.execute(
                    "UPDATE jobs SET params=params || '{\"cancel_requested\":true}'::jsonb WHERE id=%s", (job_id,)
                )
        return {"accepted": True, "meaning": "stops before final commit; committed archives/experiments remain"}
