"""Publish immutable records/reports for this study only, with readback verification."""

import hashlib
import json
import re
from urllib.parse import quote

from common import HERE, WORK, new_json, read_json
from publication_base import Publisher

from threemind_lab import notebooks, report_sources, research_documents
from threemind_lab.database import LOCAL_USER


def note_markdown(body):
    # Repository-relative Markdown links need the application's document route.
    return re.sub(
        r"\[([^\]]+)\]\(([A-Za-z0-9_.-]+\.md)\)",
        lambda match: (
            f"[{match[1]}](/docs?doc={quote('lab/explorations/2026-09-30-memory-transfer/' + match[2], safe='')})"
        ),
        body,
    )


def main():
    p = Publisher()
    try:
        audit = read_json(WORK / "audit.json")
        assert audit["verified_checkpoints"] == 1536
        input_export = read_json(WORK / "inputs-export.json")
        assert input_export["project_id"] == p.project
        assert input_export["totals"]["cases"] == audit["verified_checkpoints"]
        assert input_export["unfinished_inputs"] == 0
        delivery_check = read_json(WORK / "inputs-delivery-verification.json")
        assert delivery_check["exact_core_inputs"] == input_export["totals"]["frames"]
        assert delivery_check["unresolved_mismatches"] == 0
        rows = read_json(WORK / "analysis-final.json")["rows"]
        choices = [
            ("memory", "memory/930101/ordinary/full/wait-300/A", "300 秒后的关联唤起与收敛读出"),
            ("sequence", "sequence/930101/ordinary/full/ordered/1/delay-5", "顺序：相同结尾下的输出"),
            ("transfer", "transfer/930101/ordinary/full/angle/1", "迁移：新角度下的标记唤起"),
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
        illustrations = []
        for name in (
            "memory-retention",
            "memory-intervention",
            "sequence-transfer",
            "transfer-phases",
            "environment-adaptation",
        ):
            image_id = p.identity(name + ":image")
            notebooks.save_asset(
                p.db, p.project, LOCAL_USER, image_id, name + ".png", (WORK / (name + ".png")).read_bytes()
            )
            illustrations.append(f"![{name}](/api/v2/projects/{p.project}/note-assets/{image_id})")
        appendix = (
            "\n\n"
            + "\n\n".join(illustrations)
            + f"\n\n[完整证据 / Complete evidence](/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']})\n"
        )
        for lang in ("zh", "en"):
            title = (
                "记忆、顺序、迁移与环境适应：1536 个实例"
                if lang == "zh"
                else "Memory, sequence, transfer and adaptation: 1536 instances"
            )
            body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8") + appendix
            p.document("report:" + lang, "report", title, body)
            p.note("results:" + lang, title, note_markdown(body))
        for key, title, row, source in sources:
            p.document(
                "record:" + key,
                "record",
                title,
                f"案例 `{row['key']}`，意识 `{row['id']}`。这是已声明选择的示例，不替代全组结果。判定时刻排序为主要指标；提示后的短暂变化按轨迹另行报告。详细分组、未训练／无提示对照与失败结果见中英文总报告。\n\n"
                "One declared illustrative case, not a substitute for the full matrix. Decision-time activation ranking is primary; transient activity is reported separately. The report and archive preserve all controls and negative outcomes."
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
            "record:intervention",
            "record",
            "300 秒关联记忆：连接屏蔽、恢复与匹配对照",
            (HERE / "memory-intervention-registration.md").read_text(encoding="utf-8")
            + "\n\n结果：32/32 个定点屏蔽使提示引起的目标累计激活增量降为零；32 个解除屏蔽、32 个匹配连接对照均与原实例的全部记录时点激活一致。巩固后的关联仍能在 300 模拟秒后被唤起。\n\n"
            "Results: all 32 targeted silencing interventions removed the cue-specific target integral. All 32 restorations and 32 matched-edge controls reproduced every sampled node activation of the original probe. The association remained cue-accessible after 300 simulated seconds.\n"
            + appendix,
        )
        p.document(
            "record:adaptation",
            "record",
            "闭环躯体：完整、去惯性、延迟与无本体感官",
            (HERE / "body-removal-registration.md").read_text(encoding="utf-8")
            + "\n\n结果：本轮未观察到朝轨道居中目标的稳定平均改善。56 个配对条件中，开启巩固的第三段误差较低 18 个、较高 30 个、不变 8 个；本轮没有奖励或种群选择。完整行为数值和相反外力验证见中英文总报告。\n\n"
            "Results: no consistent mean improvement toward the external centring objective. Consolidation lowered third-episode error in 18 paired conditions, raised it in 30 and left it unchanged in 8. No reward or population selection was used. Full numerical and force-reversal results are in the bilingual report.\n"
            + appendix,
        )
        for key, item in p.state.items():
            if key.startswith(("report:", "record:")):
                got = research_documents.get(p.db, p.project, item["id"], revision=item["revision"])
                assert got["content_hash"] == item["content_hash"]
        sha, size = hashlib.sha256(), 0
        with p.db.tx(p.project) as tx, tx.cursor(name="memory_transfer_archive_verify") as cursor:
            cursor.execute(
                "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (archive["artifact_id"],)
            )
            for r in cursor:
                sha.update(r["body"])
                size += len(r["body"])
        assert sha.hexdigest() == archive["sha256"] and size == archive["bytes"]
        with p.db.tx() as tx:
            current = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local = sum(f.stat().st_size for f in WORK.rglob("*") if f.is_file())
        total = local + max(0, current - p.meta["database_bytes_before"])
        assert total < 4 * 1024**3
        result = {
            **audit,
            "project_id": p.project,
            "reports": {lang: p.state["report:" + lang]["id"] for lang in ("zh", "en")},
            "records": {key: v["id"] for key, v in p.state.items() if key.startswith("record:")},
            "archive": archive,
            "archive_readback_verified": True,
            "inputs_export": {k: v for k, v in input_export.items() if k != "files"},
            "inputs_delivery_verification": delivery_check,
            "new_evidence_bytes": total,
            "usage_at_delivery_percent": read_json(WORK / "usage.json")["used_percent"],
        }
        new_json(WORK / "delivery.json", result)
        for lang in ("zh", "en"):
            (HERE / f"delivery.{lang}.md").write_text(
                "# 交付校验 / Delivery verification\n\n"
                + f"Project `{p.project}`; {audit['verified_checkpoints']} checkpoints verified; 2 reports and 5 records.\n\n"
                + f"Archive `{archive['artifact_id']}`, SHA-256 `{archive['sha256']}`; database readback verified.\n\n"
                + f"New local evidence + conservative database growth: {total / 1024**2:.2f} MiB.\n\n"
                + f"Simulation wall time: {audit['simulation_wall_seconds']:.2f} s; account {audit['usage_start_percent']}→{audit['usage_end_percent']}%.\n\n"
                + f"Shared usage at publication: {result['usage_at_delivery_percent']}%.\n\n"
                + f"[中文报告](/reports?tab=report&document={result['reports']['zh']}) · [English report](/reports?tab=report&document={result['reports']['en']})\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "project": p.project,
                    "reports": result["reports"],
                    "new_evidence_MiB": total / 1024**2,
                    "archive_verified": True,
                }
            )
        )
    finally:
        p.db.close()


if __name__ == "__main__":
    main()
