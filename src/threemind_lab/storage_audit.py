"""Read-only, conservative inventory. It never authorizes or performs deletion."""

from datetime import UTC, datetime

from psycopg import sql


def scan(database, project, actor, *, offset=0, limit=50, include_database=False):
    with database.tx(project, repeatable=True, read_only=True) as db:
        db.execute("SET LOCAL statement_timeout='8s'")
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor),))
        totals = db.execute(
            "SELECT count(*) runs,coalesce(sum((metrics->>'nodes')::bigint),0) nodes,"
            "coalesce(sum((metrics->>'edges')::bigint),0) edges FROM runs WHERE project_id=%s",
            (project,),
        ).fetchone()
        counts = {}
        for table in (
            "studies",
            "research_documents",
            "probe_calibrations",
            "notes",
            "experiment_bundles",
            "bundle_resumes",
            "research_experiments",
            "research_record_entries",
            "research_record_evidence",
        ):
            counts[table] = db.execute(
                sql.SQL("SELECT count(*) n FROM {} WHERE project_id=%s").format(sql.Identifier(table)), (project,)
            ).fetchone()["n"]
        checkpoints = db.execute(
            "SELECT count(*) n,coalesce(sum(byte_count),0) bytes FROM checkpoints WHERE project_id=%s", (project,)
        ).fetchone()
        artifacts = db.execute(
            "SELECT count(*) n,coalesce(sum(bytes),0) bytes FROM artifacts WHERE project_id=%s", (project,)
        ).fetchone()
        uploads = db.execute(
            "SELECT status,count(*) n,coalesce(sum(bytes),0) declared_bytes FROM bundle_uploads WHERE project_id=%s GROUP BY status",
            (project,),
        ).fetchall()
        upload_payload = db.execute(
            "SELECT coalesce(sum(octet_length(body)),0) bytes FROM bundle_upload_chunks WHERE project_id=%s", (project,)
        ).fetchone()["bytes"]
        rows = db.execute(
            "SELECT id,name,status,revision,state_hash,archived_at,created_at FROM runs WHERE project_id=%s "
            "ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s",
            (project, limit + 1, offset),
        ).fetchall()
        ids = [r["id"] for r in rows[:limit]]
        metadata = {str(i): {} for i in ids}
        # Bounded metadata aggregates, never load model bodies, media or full logs.
        checks = {
            "checkpoints": "SELECT run_id,count(*) n,coalesce(sum(byte_count),0) bytes,count(*) FILTER(WHERE pinned) pinned FROM checkpoints WHERE project_id=%s AND run_id=ANY(%s::uuid[]) GROUP BY run_id",
            "children": "SELECT parent_id run_id,count(*) n FROM runs WHERE project_id=%s AND parent_id=ANY(%s::uuid[]) GROUP BY parent_id",
            "inputs": "SELECT run_id,count(*) n FROM input_envelopes WHERE project_id=%s AND run_id=ANY(%s::uuid[]) GROUP BY run_id",
            "events": "SELECT run_id,count(*) n FROM events WHERE project_id=%s AND run_id=ANY(%s::uuid[]) GROUP BY run_id",
            "calibrations": "SELECT run_id,count(*) n FROM probe_calibrations WHERE project_id=%s AND run_id=ANY(%s::uuid[]) GROUP BY run_id",
            "report_sources": "SELECT run_id,count(*) n FROM report_source_requests WHERE project_id=%s AND run_id=ANY(%s::uuid[]) GROUP BY run_id",
            "pending_jobs": "SELECT run_id,count(*) n FROM jobs WHERE project_id=%s AND run_id=ANY(%s::uuid[]) AND status IN ('pending','leased') GROUP BY run_id",
            "research_operations": "SELECT run_id,count(*) n FROM research_operations WHERE project_id=%s AND run_id=ANY(%s::uuid[]) GROUP BY run_id",
            "bundle_resumes": "SELECT run_id,count(*) n FROM bundle_resumes WHERE project_id=%s AND run_id=ANY(%s::uuid[]) GROUP BY run_id",
            "bundle_exports": "SELECT (manifest->'metadata'->>'origin_run')::uuid run_id,count(*) n FROM experiment_bundles WHERE project_id=%s AND manifest->'metadata'->>'origin_run'=ANY(%s::text[]) GROUP BY 1",
        }
        for key, query in checks.items():
            for value in db.execute(
                query, (project, [str(i) for i in ids] if key == "bundle_exports" else ids)
            ).fetchall():
                metadata[str(value["run_id"])][key] = {k: v for k, v in value.items() if k != "run_id"}
        for row in rows[:limit]:
            fields = metadata[str(row["id"])]
            reasons, status = [], "candidate"
            if row["status"] not in ("completed", "failed", "cancelled", "dead") or fields.get("pending_jobs"):
                status, reasons = "keep", ["仍可能继续运行或有待处理任务。"]
            if (
                fields.get("children")
                or fields.get("calibrations")
                or fields.get("report_sources")
                or fields.get("checkpoints", {}).get("pinned")
                or fields.get("bundle_resumes")
                or fields.get("bundle_exports")
            ):
                status = "keep"
                reasons.append("有谱系、固定测量来源或已保留恢复点引用。")
            if counts["studies"] or counts["research_documents"] or counts["notes"]:
                status = "keep"
                reasons.append(
                    "项目含实验、研究文档或本人笔记；自由文本和分析附件中的引用未被扫描，建议保留直至人工核对。"
                )
            if status != "keep" and (
                row["revision"] or row["state_hash"] or any(fields.get(k) for k in checks if k != "pending_jobs")
            ):
                status = "risk"
                reasons.append("包含状态、输入或研究证据；无法仅凭名称、失败状态或零结果认定没有价值。")
            if status == "candidate":
                reasons.append(
                    "未发现状态、输入、事件或已列出的引用；仅为空记录候选，清理前仍需现有完整引用预览和人工确认。"
                )
            row.update(classification=status, reasons=reasons, metadata=fields, deletion_authorized=False)
        return {
            "schema": "threemind.storage-audit/1",
            "project_id": str(project),
            "checked_at": datetime.now(UTC).isoformat(),
            "read_only": True,
            "scope": "current project; only caller-visible personal note metadata",
            "totals": totals,
            "records": counts,
            "checkpoints": checkpoints,
            "artifacts": artifacts,
            "bundle_uploads": {
                "by_status": uploads,
                "stored_bytes": int(upload_payload),
                "classification": "risk",
                "deletion_authorized": False,
            },
            "stored_payload_bytes": int(checkpoints["bytes"]) + int(artifacts["bytes"]) + int(upload_payload),
            "network_projection_estimate_bytes": 320 * (int(totals["nodes"]) + int(totals["edges"])),
            "database_physical_bytes": db.execute("SELECT pg_database_size(current_database()) n").fetchone()["n"]
            if include_database
            else None,
            "rows": rows[:limit],
            "offset": offset,
            "more": len(rows) > limit,
            "limitations": [
                "字节统计不含完整 WAL、媒体及索引；网络投影是预算估计，不是可回收空间。",
                "分析 JSON、笔记正文与旧大数据未展开扫描；未发现引用不等于已证明没有引用。",
                "不按文件名、失败或零结果自动判断垃圾。归档仍保留数据，不释放磁盘。",
                "本扫描不创建清理令牌、不删除数据；实际清理由用户在模型档案中预览并确认。",
            ],
        }
