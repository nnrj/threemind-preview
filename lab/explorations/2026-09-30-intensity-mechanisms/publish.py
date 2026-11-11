"""Publish this study's reports, records and evidence without running Core."""

import json
import re
from urllib.parse import quote

from experiment import HERE, WORK, settings

from lab.tools.service_study import Study, new_json, read_json
from lab.tools.study_publication import Publication
from threemind_lab import report_sources
from threemind_lab.database import LOCAL_USER


def main():
    study = Study(settings())
    p = Publication(study)
    try:
        audit = read_json(WORK / "audit.json")
        assert audit["cases"] == 1246 and audit["unchanged_core"]
        results = read_json(WORK / "analysis-final.json")
        sources = []
        for key, case, title in (
            ("ordinary-rule", "matrix/930401/i0f0l1/single4/wait30/cue0.5", "取消额外强刺激项后，30 秒的关联唤起"),
            ("facilitation", "matrix/930401/i0f1l1/single4/wait1/cue0.5", "易化与提示时的短暂响应"),
            ("explicit-control", "matrix/930401/i1f0l1/single4/wait30/cue0.5", "保留额外强刺激项的对照"),
        ):
            row = next(r for r in results["rows"] if r["key"] == case)
            label = "source:" + key
            if label not in p.state:
                p.queue_clear()
                request = report_sources.request(
                    p.db,
                    p.project,
                    LOCAL_USER,
                    {
                        "operation_id": study.identity(label + ":request"),
                        "kind": "temporal_nodes",
                        "run_id": row["id"],
                        "window_ids": [row["window_id"]],
                        "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                    },
                )
                with p.owned(request["job_id"]) as job:
                    out = report_sources.capture(p.db, job)
                    p.db.finish(job, result=out)
                p.remember(label, {"id": str(request["id"]), "run_id": row["id"], "content_hash": out["content_hash"]})
            sources.append((key, case, title, p.state[label]))
        figures = {}
        for name in ("factorial", "sensitivity", "mechanism-location"):
            figures[name] = p.image(name, HERE / "figures" / f"{name}.png")
            figures[name + ".en"] = p.image(name + ".en", HERE / "figures" / f"{name}.en.png")
        archive = p.archive("intensity-mechanisms-evidence.zip")
        appendix = (
            f"\n\n[完整证据 / Complete evidence](/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']})\n"
        )
        for language in ("zh", "en"):
            title = (
                "强刺激机制替代与经历敏感性"
                if language == "zh"
                else "Intensity mechanism substitution and history dependent sensitivity"
            )
            body = (HERE / f"report.{language}.md").read_text(encoding="utf-8")
            for name, image in figures.items():
                body = re.sub(
                    r"!\[[^\]]*\]\(figures/" + re.escape(name) + r"\.png\)", lambda _, image=image: image, body
                )
            body = re.sub(
                r"\[([^\]]+)\]\(([A-Za-z0-9_./-]+\.md)\)",
                lambda m: (
                    f"[{m[1]}](/docs?doc={quote((HERE / m[2]).resolve().relative_to(HERE.parents[2]).as_posix(), safe='')})"
                ),
                body,
            )
            p.document("report:" + language, "report", title, body + appendix)
            p.note("results:" + language, title, body + appendix)
        for key, case, title, source in sources:
            p.document(
                "record:" + key,
                "record",
                title,
                f"案例 `{case}`。固定选择首个材料块作为示例，完整结论使用全部对照。表中的判定时刻激活不等于完整过程积分；目标响应短暂时，最终排名可能没有目标。\n\n"
                "Illustrative first-block case, not a substitute for the complete matrix. Decision-time activation and full-window integrals are distinct; a transient target response can be absent from the final ranking."
                + appendix,
                sources=[source["id"]],
                blocks=[
                    {
                        "id": "readout",
                        "type": "table",
                        "source": source["id"],
                        "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                        "title": "判定时刻、峰值与累计激活 / Decision, peak and integral",
                    }
                ],
            )
        p.document(
            "record:interventions",
            "record",
            "强刺激来源与表达：消融、恢复和阶段切换",
            (HERE / "extension.zh.md").read_text(encoding="utf-8")
            + "\n\n"
            + (HERE / "phase-extension.zh.md").read_text(encoding="utf-8")
            + "\n\n"
            + figures["mechanism-location"]
            + "\n\n详细正负结果见本研究项目的中英文总报告。"
            + appendix,
        )
        p.verify()
        with p.db.tx() as tx:
            size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        local = sum(f.stat().st_size for f in WORK.rglob("*") if f.is_file())
        result = audit | {
            "project_id": p.project,
            "reports": {lang: p.state["report:" + lang]["id"] for lang in ("zh", "en")},
            "records": {k: v["id"] for k, v in p.state.items() if k.startswith("record:")},
            "archive": archive,
            "archive_readback_verified": True,
            "new_evidence_bytes": local + max(0, size - study.meta["database_bytes_before"]),
            "usage_at_delivery": read_json(WORK / "usage.json")["used_percent"],
        }
        new_json(WORK / "delivery.json", result)
        delivery = (
            "# 交付校验 / Delivery verification\n\n"
            f"Project `{p.project}`; {audit['cases']} checkpoints, 2 reports and 4 records.\n\n"
            f"Archive `{archive['artifact_id']}`; SHA-256 `{archive['sha256']}`; readback verified.\n\n"
            f"New local files and conservative database growth: {result['new_evidence_bytes'] / 2**20:.2f} MiB.\n\n"
            f"Simulation wall time: {audit['simulation_wall_seconds']:.2f} seconds. "
            f"Shared account usage: {audit['usage_start']} → {result['usage_at_delivery']}%.\n\n"
            f"[中文报告](/reports?tab=report&document={result['reports']['zh']}) · "
            f"[English report](/reports?tab=report&document={result['reports']['en']})\n"
        )
        for language in ("zh", "en"):
            (HERE / f"delivery.{language}.md").write_text(delivery, encoding="utf-8")
        print(
            json.dumps(
                {
                    "project": p.project,
                    "reports": result["reports"],
                    "new_evidence_MiB": result["new_evidence_bytes"] / 2**20,
                },
                ensure_ascii=False,
            )
        )
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
