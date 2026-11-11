"""Publish only this study's verified records, readout tables and archive."""

import hashlib
import json

from common import HERE, WORK, new_json, read_json
from publication_base import Publisher

from threemind_lab import notebooks, report_sources, research_documents
from threemind_lab.database import LOCAL_USER


def main():
    p = Publisher()
    try:
        audit = read_json(WORK / "audit.json")
        assert audit["verified_checkpoints"] == 295
        rows = read_json(WORK / "analysis-v3.json")["rows"]
        choices = [
            ("background", "background/93001/ordinary/telemetry/cue0.5/registered", "真实遥测背景的读出"),
            ("intensity", "intensity/93001/ordinary/repeated1/cue0.2/registered", "重复经历后的弱提示"),
            ("physical", "physical/93001/ordinary/inertial-cart/complete/cue0.5/registered", "共同物理观测后的读出"),
        ]
        sources = []
        for key, case, title in choices:
            row = next(r for r in rows if r["key"] == case)
            name = "source:" + key
            if name not in p.state:
                req = report_sources.request(
                    p.db,
                    p.project,
                    LOCAL_USER,
                    {
                        "operation_id": p.identity(name + ":request"),
                        "kind": "temporal_nodes",
                        "run_id": row["id"],
                        "window_ids": [row["window_id"]],
                        "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                    },
                )
                with p.owned(req["job_id"]) as job:
                    out = report_sources.capture(p.db, job)
                    p.db.finish(job, result=out)
                p.remember(name, {"id": str(req["id"]), "run_id": row["id"], "content_hash": out["content_hash"]})
            sources.append((key, title, row, p.state[name]))
        archive = p.archive()
        image_id = p.identity("overview-image")
        notebooks.save_asset(
            p.db, p.project, LOCAL_USER, image_id, "stimulus-spacetime.png", (WORK / "overview.png").read_bytes()
        )
        appendix = (
            f"\n\n![结构对照 / Structural comparisons](/api/v2/projects/{p.project}/note-assets/{image_id})\n\n"
            f"[完整证据 / Complete evidence](/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']})\n"
        )
        for lang in ("zh", "en"):
            title = (
                "刺激、背景与物理参照：295 个实例" if lang == "zh" else "Stimuli and physical references: 295 instances"
            )
            body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8") + appendix
            p.document("report:" + lang, "report", title, body)
            p.note("results:" + lang, title, body)
        for key, title, row, source in sources:
            p.document(
                "record:" + key,
                "record",
                title,
                f"选取案例 `{row['key']}`。本表是全部结果中的一个观察例，不代替全组对照。收敛候选按判定时激活排序；无提示对照、未收敛、原始轨迹与完整结论见双语总报告。\n\n"
                f"One explicitly selected example; not a replacement for all-condition comparisons. Consciousness `{row['id']}`."
                + appendix,
                sources=[source["id"]],
                blocks=[
                    {
                        "id": "readout",
                        "type": "table",
                        "source": source["id"],
                        "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                        "title": "判定时刻、峰值与积分 / Decision, peak and integral",
                    }
                ],
            )
        p.document(
            "record:retention",
            "record",
            "独立刺激维持活动时的弱连接寿命",
            (HERE / "retention-extension.md").read_text(encoding="utf-8")
            + "\n\n结果：4/4 副本的 96 条弱边自然消失，原有两条强化边保留，新通道跨边为零。Results: 96 weak edges disappeared in all four clones; two reinforced edges persisted and no cross-link was created."
            + appendix,
        )
        for lang in ("zh", "en"):
            item = p.state["report:" + lang]
            restored = research_documents.get(p.db, p.project, item["id"], revision=item["revision"])
            assert restored["content_hash"] == item["content_hash"]
        sha, size = hashlib.sha256(), 0
        with p.db.tx(p.project) as db, db.cursor(name="stimulus_archive_verify") as cursor:
            cursor.execute(
                "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (archive["artifact_id"],)
            )
            for r in cursor:
                sha.update(r["body"])
                size += len(r["body"])
        assert sha.hexdigest() == archive["sha256"] and size == archive["bytes"]
        with p.db.tx() as tx:
            database_size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local = sum(f.stat().st_size for f in WORK.rglob("*") if f.is_file())
        total = local + max(0, database_size - p.meta["database_bytes_before"])
        assert total < 4 * 1024**3
        out = {
            "project_id": p.project,
            "reports": {lang: p.state["report:" + lang]["id"] for lang in ("zh", "en")},
            "archive": archive,
            "archive_readback_verified": True,
            "new_evidence_bytes": total,
            **audit,
        }
        new_json(WORK / "delivery.json", out)
        for lang in ("zh", "en"):
            (HERE / f"delivery.{lang}.md").write_text(
                "# 交付校验 / Delivery verification\n\n"
                + f"Project `{p.project}`; 295 checkpoints verified; 2 reports + 4 records.\n\n"
                + f"Archive `{archive['artifact_id']}`, SHA-256 `{archive['sha256']}`; database readback verified.\n\n"
                + f"New local evidence + conservative database growth: {total / 1024**2:.2f} MiB.\n\n"
                + f"Simulation wall time: {audit['simulation_wall_seconds']:.2f} s; account {audit['usage_start_percent']}→{audit['usage_end_percent']}%.\n\n"
                + f"[中文报告](/reports?tab=report&document={out['reports']['zh']}) · [English report](/reports?tab=report&document={out['reports']['en']})\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "project": p.project,
                    "reports": out["reports"],
                    "evidence_MiB": total / 1024**2,
                    "archive_verified": True,
                }
            )
        )
    finally:
        p.db.close()


if __name__ == "__main__":
    main()
