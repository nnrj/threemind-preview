"""Human annotations and whole-archive management, outside Core state and its revision."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .database import Conflict, NotFound
from .inputs import digest

TERMINAL = {"completed", "cancelled", "failed", "dead"}
RUN_FIELDS = ("name", "description", "tags", "archived_at")
VERSION_FIELDS = ("label", "notes", "tags", "pinned")
SUMMARY = "id,name,status,life,parent_id,origin_hash,origin_checkpoint_id,origin_kind,state_hash,revision,time_us,metadata_revision,tags,archived_at,created_at"
VERSIONS = "id,run_id,revision,time_us,state_hash,byte_count,created_at,storage_format,delta_depth,base_checkpoint_id,label,notes,tags,pinned,metadata_revision"


def locked_run(db, run_id):
    row = db.execute(
        f"SELECT {SUMMARY},project_id,description,spec->>'study_id' AS study_id FROM runs WHERE id=%s FOR UPDATE",
        (run_id,),
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def annotation_snapshot(db, run_id, checkpoint_id=None):
    run = db.execute(f"SELECT {SUMMARY},description FROM runs WHERE id=%s", (run_id,)).fetchone()
    if run is None:
        raise NotFound()
    version = (
        db.execute(f"SELECT {VERSIONS} FROM checkpoints WHERE run_id=%s AND id=%s", (run_id, checkpoint_id)).fetchone()
        if checkpoint_id
        else None
    )
    return {
        "schema": "threemind.model-annotations/1",
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "scope": "human annotations at export time, independent of the selected scientific checkpoint",
        "run": run,
        "checkpoint": version,
    }


def export_annotations(database, project, run_id):
    with database.tx(project, repeatable=True) as db:
        yield json.dumps(annotation_snapshot(db, run_id), ensure_ascii=False, default=str) + "\n"
        for kind, statement in (
            ("checkpoint", f"SELECT {VERSIONS} FROM checkpoints WHERE run_id=%s ORDER BY revision"),
            ("state_capture", "SELECT * FROM state_captures WHERE run_id=%s ORDER BY ordinal"),
            ("annotation_change", "SELECT * FROM model_metadata_history WHERE run_id=%s ORDER BY id"),
        ):
            with db.cursor(name=f"annotation_{kind}") as cursor:
                cursor.execute(statement, (run_id,))
                for row in cursor:
                    yield json.dumps({"kind": kind, "record": row}, ensure_ascii=False, default=str) + "\n"


def update_metadata(db, project, current, changes, actor_id, *, checkpoint=False):
    fields = VERSION_FIELDS if checkpoint else RUN_FIELDS
    before = {key: current[key] for key in fields}
    after = before | changes
    if after == before:
        return current
    if set(after) != set(fields):
        raise ValueError("unsupported annotation field")
    table = "checkpoints" if checkpoint else "runs"
    result = db.execute(
        sql.SQL("UPDATE {} SET {},metadata_revision=metadata_revision+1 WHERE id=%s RETURNING {}").format(
            sql.Identifier(table),
            sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(key)) for key in fields),
            sql.SQL(VERSIONS if checkpoint else SUMMARY + ",description"),
        ),
        tuple(after[key] for key in fields) + (current["id"],),
    ).fetchone()

    # Timestamps serialize explicitly; scientific payloads are never read or replaced here.
    def wire(value):
        return {key: v.isoformat() if isinstance(v, datetime) else v for key, v in value.items()}

    db.execute(
        "INSERT INTO model_metadata_history(project_id,run_id,checkpoint_id,metadata_revision,actor_id,before_value,after_value) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (
            project,
            current["run_id"] if checkpoint else current["id"],
            current["id"] if checkpoint else None,
            result["metadata_revision"],
            actor_id,
            Jsonb(wire(before)),
            Jsonb(wire(after)),
        ),
    )
    return result


def edit_run(database, project, run_id, actor, body):
    with database.tx(project) as db:
        row = locked_run(db, run_id)
        if row["metadata_revision"] != body.expected_metadata_revision:
            raise Conflict("档案已被修改，请重新载入后保存。")
        if body.archived and row["status"] not in TERMINAL:
            raise Conflict("请先结束意识，再归档其完整记录。")
        archived = (row["archived_at"] or datetime.now(UTC)) if body.archived else None
        return update_metadata(
            db,
            project,
            row,
            {"name": body.name, "description": body.description, "tags": body.tags, "archived_at": archived},
            actor["id"],
        )


def edit_version(database, project, run_id, checkpoint_id, actor, body):
    with database.tx(project) as db:
        locked_run(db, run_id)  # Consistent lock order with cleanup and configuration commits.
        row = db.execute(
            f"SELECT {VERSIONS} FROM checkpoints WHERE id=%s AND run_id=%s FOR UPDATE", (checkpoint_id, run_id)
        ).fetchone()
        if row is None:
            raise NotFound()
        if row["metadata_revision"] != body.expected_metadata_revision:
            raise Conflict("恢复点注释已更新，请重新载入后保存。")
        return {
            key: value
            for key, value in update_metadata(
                db,
                project,
                row,
                {key: getattr(body, key) for key in VERSION_FIELDS},
                actor["id"],
                checkpoint=True,
            ).items()
            if key != "context"
        }


def library(database, project, *, q="", tag="", status="", archived="active", offset=0, limit=30):
    with database.tx(project) as db:
        rows = db.execute(
            f"SELECT {SUMMARY},left(description,300) AS description FROM runs WHERE "
            "(%s='' OR strpos(lower(name),lower(%s))>0 OR strpos(lower(description),lower(%s))>0) "
            "AND (%s='' OR %s=ANY(tags)) AND (%s='' OR status=%s) "
            "AND (%s='all' OR (archived_at IS NOT NULL)=(%s='archived')) "
            "ORDER BY created_at DESC,id LIMIT %s OFFSET %s",
            (q, q, q, tag, tag, status, status, archived, archived, limit + 1, offset),
        ).fetchall()
    return {"rows": rows[:limit], "more": len(rows) > limit, "offset": offset, "limit": limit}


def versions(database, project, run_id, *, q="", tag="", pinned=False, before=None, limit=30):
    database.get_run(project, run_id)
    with database.tx(project) as db:
        rows = db.execute(
            f"SELECT {VERSIONS} FROM checkpoints WHERE run_id=%s "
            "AND (%s='' OR strpos(lower(label),lower(%s))>0 OR strpos(lower(notes),lower(%s))>0) "
            "AND (%s='' OR %s=ANY(tags)) AND (NOT %s OR pinned) "
            "AND (%s::bigint IS NULL OR revision<%s) ORDER BY revision DESC LIMIT %s",
            (run_id, q, q, q, tag, tag, pinned, before, before, limit + 1),
        ).fetchall()
    return {
        "rows": rows[:limit],
        "more": len(rows) > limit,
        "next": rows[limit - 1]["revision"] if len(rows) >= limit else None,
    }


def lineage(database, project, run_id, *, offset=0, limit=30):
    database.get_run(project, run_id)
    with database.tx(project) as db:
        ancestors = db.execute(
            "WITH RECURSIVE chain AS (SELECT id,parent_id,0 AS depth,ARRAY[id] AS visited FROM runs WHERE id=%s "
            "UNION ALL SELECT p.id,p.parent_id,c.depth+1,c.visited||p.id FROM chain c JOIN runs p ON p.id=c.parent_id "
            "WHERE c.depth<64 AND NOT p.id=ANY(c.visited)) "
            "SELECT r.id,r.name,r.status,r.parent_id,r.origin_checkpoint_id,r.origin_kind,r.origin_hash,r.archived_at,"
            "c.depth,cp.revision AS origin_revision,cp.label AS origin_label FROM chain c JOIN runs r ON r.id=c.id "
            "LEFT JOIN checkpoints cp ON cp.id=r.origin_checkpoint_id ORDER BY c.depth",
            (run_id,),
        ).fetchall()
        children = db.execute(
            f"SELECT {SUMMARY} FROM runs WHERE parent_id=%s ORDER BY created_at,id LIMIT %s OFFSET %s",
            (run_id, limit + 1, offset),
        ).fetchall()
    return {
        "ancestors": ancestors,
        "ancestors_truncated": bool(ancestors and ancestors[-1]["depth"] == 64 and ancestors[-1]["parent_id"]),
        "children": children[:limit],
        "more": len(children) > limit,
        "offset": offset,
    }


COUNT_TABLES = (
    "state_captures",
    "ai_calls",
    "ai_tool_versions",
    "research_operations",
    "research_plans",
    "model_metadata_history",
    "checkpoints",
    "events",
    "observations",
    "input_envelopes",
    "input_frames",
    "capture_sessions",
    "device_bindings",
    "media_uploads",
    "jobs",
)
DELETE_TABLES = (
    "state_captures",
    "research_operations",
    "research_plans",
    "ai_calls",
    "device_packets",
    "device_sessions",
    "device_bindings",
    "capture_packets",
    "capture_sessions",
    "media_uploads",
    "media_prepared_frames",
    "input_frames",
    "input_envelopes",
    "jobs",
)


def cleanup_plan(db, row):
    run_id = row["id"]
    reasons = []
    if db.execute('SELECT 1 FROM research_record_evidence WHERE run_id=%s OR checkpoint_id IN '
                  '(SELECT id FROM checkpoints WHERE run_id=%s) OR artifact_id IN '
                  '(SELECT a.id FROM artifacts a JOIN jobs j ON j.id=a.job_id WHERE j.run_id=%s) LIMIT 1',
                  (run_id, run_id, run_id)).fetchone():
        reasons.append('被统一实验索引引用；保留原始个体、恢复点及证据。')
    if (
        db.execute("SELECT 1 FROM bundle_resumes WHERE run_id=%s", (run_id,)).fetchone()
        or db.execute(
            "SELECT 1 FROM experiment_bundles b JOIN jobs j ON j.id=b.job_id WHERE j.run_id=%s", (run_id,)
        ).fetchone()
    ):
        reasons.append("实验包或其恢复谱系引用此意识；请保留原始来源，导出不等于可删除。")
    if row["archived_at"] is None:
        reasons.append("需要先归档。")
    if row["status"] not in TERMINAL:
        reasons.append("意识尚未结束。")
    if (
        row.get("study_id")
        or db.execute(
            "SELECT 1 FROM checkpoints WHERE run_id=%s AND context ? 'study_id' LIMIT 1", (run_id,)
        ).fetchone()
    ):
        reasons.append("属于冻结实验；不能单独删除实验中的意识或共同培养记录。")
    children = db.execute("SELECT count(*) AS n FROM runs WHERE parent_id=%s", (run_id,)).fetchone()["n"]
    if children:
        reasons.append(f"被 {children} 个后代意识引用；保留谱系来源。")
    pinned = db.execute("SELECT count(*) AS n FROM checkpoints WHERE run_id=%s AND pinned", (run_id,)).fetchone()["n"]
    if pinned:
        reasons.append(f"有 {pinned} 个已保留的恢复点；请先检查其用途。")
    external_ai = db.execute(
        "SELECT count(*) AS n FROM ai_call_checkpoints a JOIN ai_calls c ON c.id=a.call_id "
        "WHERE a.run_id=%s AND c.run_id IS DISTINCT FROM %s",
        (run_id, run_id),
    ).fetchone()["n"]
    if external_ai:
        reasons.append(f"被其他对象的 {external_ai} 项 AI 证据引用；需要保留来源。")
    document_sources = db.execute(
        "SELECT count(*) AS n FROM report_source_requests WHERE run_id=%s", (run_id,)
    ).fetchone()["n"]
    if document_sources:
        reasons.append(f"被记录与报告的 {document_sources} 份固定数据来源引用；需要保留恢复点与原始证据。")
    if db.execute("SELECT 1 FROM probe_calibrations WHERE run_id=%s LIMIT 1", (run_id,)).fetchone():
        reasons.append("被感官与探针校准引用；保留原始恢复点与测量依据。")
    if db.execute("SELECT 1 FROM development_sessions WHERE run_id=%s", (run_id,)).fetchone():
        reasons.append("属于发育训练；保留形成过程与选择依据，可归档。")
    if db.execute("SELECT 1 FROM ecology_members WHERE run_id=%s", (run_id,)).fetchone():
        reasons.append("属于生态训练；个体、谱系和种群恢复点须共同保留，可归档。")
    if db.execute("SELECT 1 FROM innate_versions WHERE run_id=%s LIMIT 1", (run_id,)).fetchone():
        reasons.append("恢复点已登记为先天版本；保留模型本体与谱系来源。")
    if db.execute(
        "SELECT 1 FROM jobs WHERE run_id=%s AND status IN ('pending','leased') LIMIT 1", (run_id,)
    ).fetchone():
        reasons.append("仍有未完成任务；请等待完成或取消。")
    if db.execute(
        "SELECT 1 FROM media_uploads WHERE run_id=%s AND status IN ('processing','cancel_requested') LIMIT 1", (run_id,)
    ).fetchone():
        reasons.append("原件仍在处理；请先结束媒体处理。")
    counts = {
        table: db.execute(
            sql.SQL("SELECT count(*) AS n FROM {} WHERE run_id=%s").format(sql.Identifier(table)), (run_id,)
        ).fetchone()["n"]
        for table in COUNT_TABLES
    }
    artifact = db.execute(
        "SELECT count(*) AS n,coalesce(sum(a.bytes),0)::bigint AS bytes FROM artifacts a JOIN jobs j ON j.id=a.job_id WHERE j.run_id=%s",
        (run_id,),
    ).fetchone()
    checkpoint_bytes = db.execute(
        "SELECT coalesce(sum(byte_count),0)::bigint AS n FROM checkpoints WHERE run_id=%s", (run_id,)
    ).fetchone()["n"]
    media = db.execute(
        "SELECT count(*) AS n,coalesce(sum(a.byte_length),0)::bigint AS bytes FROM media_assets a "
        "WHERE EXISTS(SELECT 1 FROM input_envelopes e WHERE e.run_id=%s AND e.asset_sha256=a.sha256) "
        "AND NOT EXISTS(SELECT 1 FROM input_envelopes e WHERE e.run_id<>%s AND e.asset_sha256=a.sha256)",
        (run_id, run_id),
    ).fetchone()
    plan = {
        "schema": "threemind.archive-cleanup/1",
        "run_id": str(run_id),
        "name": row["name"],
        "state_hash": row["state_hash"],
        "revision": row["revision"],
        "metadata_revision": row["metadata_revision"],
        "allowed": not reasons,
        "reasons": reasons,
        "counts": counts,
        "artifacts": artifact,
        "checkpoint_bytes": checkpoint_bytes,
        "unshared_media": media,
        "scope": "entire archived run, its scientific records and generated artifacts; shared carrier assets are retained",
    }
    return plan | {"token": digest(plan)}


def preview_cleanup(database, project, run_id):
    with database.tx(project, repeatable=True) as db:
        return cleanup_plan(db, locked_run(db, run_id))


def cleanup(database, project, run_id, actor, token, confirm_name):
    try:
        with database.tx(project) as db:
            row = locked_run(db, run_id)
            plan = cleanup_plan(db, row)
            if not plan["allowed"]:
                raise Conflict("；".join(plan["reasons"]))
            if plan["token"] != token or confirm_name != row["name"]:
                raise Conflict("清理预览已变化或名称不匹配；请重新预览并确认。")
            assets = db.execute(
                "SELECT a.sha256 FROM media_assets a WHERE EXISTS(SELECT 1 FROM input_envelopes e WHERE e.run_id=%s AND e.asset_sha256=a.sha256) ORDER BY a.sha256 FOR UPDATE OF a",
                (run_id,),
            ).fetchall()
            # Generated exports belong to this archive. External references remain FK-protected.
            db.execute("DELETE FROM artifacts WHERE job_id IN (SELECT id FROM jobs WHERE run_id=%s)", (run_id,))
            for table in DELETE_TABLES:
                db.execute(sql.SQL("DELETE FROM {} WHERE run_id=%s").format(sql.Identifier(table)), (run_id,))
            db.execute("DELETE FROM runs WHERE id=%s", (run_id,))
            reclaimed = 0
            for asset in assets:
                sha = asset["sha256"]
                if not db.execute("SELECT 1 FROM input_envelopes WHERE asset_sha256=%s LIMIT 1", (sha,)).fetchone():
                    db.execute("DELETE FROM media_chunks WHERE sha256=%s", (sha,))
                    removed = db.execute(
                        "DELETE FROM media_assets WHERE sha256=%s RETURNING byte_length", (sha,)
                    ).fetchone()
                    reclaimed += removed["byte_length"] if removed else 0
            receipt = {"id": str(uuid4()), "preview": plan, "reclaimed_media_bytes": reclaimed}
            db.execute(
                "INSERT INTO model_cleanup_log(id,project_id,removed_run_id,actor_id,summary) VALUES(%s,%s,%s,%s,%s)",
                (receipt["id"], project, run_id, actor["id"], Jsonb(receipt)),
            )
            db.execute(
                "INSERT INTO audit(user_id,action,resource) VALUES(%s,'model.cleanup',%s)", (actor["id"], str(run_id))
            )
            return receipt
    except psycopg.errors.ForeignKeyViolation:
        raise Conflict("仍有其他记录引用这份档案，清理已完整回滚；请先检查引用。") from None
