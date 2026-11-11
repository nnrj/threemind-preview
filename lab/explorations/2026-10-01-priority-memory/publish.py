"""Publish verified reports and evidence through the existing Lab services."""

from __future__ import annotations

import gzip
import json
import re
import shutil
from urllib.parse import quote

from runner import HERE, ROOT, WORK, identities, settings

from lab.tools.service_study import Study, new_json, read_json
from lab.tools.study_publication import Publication
from threemind_lab import report_sources
from threemind_lab.database import LOCAL_USER


def publish(study):
    audit = read_json(WORK / "audit.json")
    assert audit["unchanged_core"] and audit["historical_sources_unchanged"]
    p = Publication(study)
    analysis = read_json(WORK / "analysis-final.json")
    sources = []
    for label, key, title in (
        ("plain-retention", "default/100101/i1f0/single4/wait30/cue0.5", "保留额外强刺激项：30 秒后的提示响应"),
        ("lifelong-facilitation", "default/100101/i0f1/single4/wait1/cue0.5", "从创建时开启易化：1 秒后的提示响应"),
        ("ordinary-candidate", "ordinary2/100101/i0f1/single4/wait30/cue0.5", "普通触达增益候选：无额外项的保持"),
        ("order-ab", "sequence/100121/f0/shared1/gap0.05/AB/wait30/cue0.5", "顺序 AB：30 秒后相同 X 提示"),
        ("order-ba", "sequence/100121/f0/shared1/gap0.05/BA/wait30/cue0.5", "顺序 BA：30 秒后相同 X 提示"),
    ):
        row = next((r for r in analysis["rows"] if r["key"] == key), None)
        if row is None and key.startswith("sequence/"):
            folder = WORK / "cases" / key
            row = read_json(folder / "result.json")
            with gzip.open(folder / "events.jsonl.gz", "rt", encoding="utf-8") as stream:
                activity = [
                    e["payload"]
                    for line in stream
                    if (e := json.loads(line))["kind"] == "temporal_readout" and e["payload"].get("analysis_schema")
                ]
            assert len(activity) == 1
            row["window_id"] = activity[0]["window_id"]
        if row is None:
            continue
        state_key = "source:" + label
        if state_key not in p.state:
            p.queue_clear()
            request = report_sources.request(
                p.db,
                p.project,
                LOCAL_USER,
                {
                    "operation_id": study.identity(state_key + ":request"),
                    "kind": "temporal_nodes",
                    "run_id": row["id"],
                    "window_ids": [row["window_id"]],
                    "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                },
            )
            with p.owned(request["job_id"]) as job:
                result = report_sources.capture(p.db, job)
                p.db.finish(job, result=result)
            p.remember(
                state_key, {"id": str(request["id"]), "run_id": row["id"], "content_hash": result["content_hash"]}
            )
        sources.append((label, key, title, p.state[state_key]))
    figures = {}
    if (HERE / "figures").exists():
        dest = WORK / "figures"
        dest.mkdir(exist_ok=True)
        for file in sorted((HERE / "figures").glob("*.png")):
            shutil.copy2(file, dest / file.name)
            figures[file.stem] = p.image(file.stem, file)
    if (HERE / "tables").exists():
        dest = WORK / "tables"
        dest.mkdir(exist_ok=True)
        for file in sorted((HERE / "tables").glob("*.csv")):
            shutil.copy2(file, dest / file.name)
    # Includes selected old parent snapshots and physical replay material, not the old database.
    archive = p.archive("priority-memory-evidence.zip", historical_data_included=True)
    appendix = f"\n\n[完整证据 / Complete evidence](/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']})\n"
    for language in ("zh", "en"):
        title = (
            "强刺激、易化、感官响应与顺序：优先验证"
            if language == "zh"
            else "Priority tests: intensity, facilitation, sensory responses and order"
        )
        body = (HERE / f"report.{language}.md").read_text(encoding="utf-8")
        for name, image in figures.items():
            body = re.sub(r"!\[[^\]]*\]\(figures/" + re.escape(name) + r"\.png\)", lambda _, image=image: image, body)
        body = re.sub(
            r"\[([^\]]+)\]\(([A-Za-z0-9_./-]+\.md)\)",
            lambda m: f"[{m[1]}](/docs?doc={quote((HERE / m[2]).resolve().relative_to(ROOT).as_posix(), safe='')})",
            body,
        )
        p.document("report:" + language, "report", title, body + appendix)
        p.note("results:" + language, title, body + appendix)
    for label, key, title, source in sources:
        folder = WORK / "cases" / key
        case = read_json(folder / "result.json")
        if key.startswith("sequence/"):
            from sequence import ids

            channels = ids(case["seed"])
        else:
            channels = identities(case["seed"])
        image = json.loads(gzip.decompress((folder / "pre-probe.json.gz").read_bytes()))
        node_ids = {n["channel"]: n["id"] for n in image["nodes"]}
        legend = "\n\n观察者对照 / Observer legend (not Core labels):\n\n| 符号 / Symbol | 节点 / Node | 匿名通道 / Channel |\n| --- | --- | --- |\n"
        legend += "\n".join(
            f"| {symbol} | {node_ids[channel]} | {channel} |"
            for symbol, channel in channels.items()
            if channel in node_ids
        )
        p.document(
            "record:" + label,
            "record",
            title,
            f"固定示例 `{key}`；完整结论使用全部登记材料。表中是该副本的原始窗口，并非有／无提示相减后的量；配对比较见总报告和导出表。判定时刻、峰值、过程积分分别列出，不互相替代。\n\nFixed illustrative case; all registered blocks inform the conclusions. This table is the raw window, not cued-minus-uncued data; paired comparisons are in the report and exported tables. Decision-time, peak and integral measures are distinct.\n"
            + legend
            + appendix,
            sources=[source["id"]],
            blocks=[
                {
                    "id": "readout",
                    "type": "table",
                    "source": source["id"],
                    "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                    "title": "判定时刻、峰值与累计活动 / Decision, peak and integral",
                }
            ],
        )
    for label, name in (("reversal", "reversal-design.zh.md"), ("sequence", "sequence-design.zh.md")):
        body = (HERE / name).read_text(encoding="utf-8")
        if label in figures:
            body += "\n\n" + figures[label]
        body += "\n\n执行状态、全部正负结果和限制以本项目中英文总报告为准。\n\nExecution status and all outcomes are in this project's final bilingual report."
        p.document(
            "record:" + label,
            "record",
            "本体感官反向响应定位" if label == "reversal" else "顺序信息形成、保持与表达",
            body + appendix,
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
    assert result["new_evidence_bytes"] < study.settings.storage_hard
    new_json(WORK / "delivery.json", result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "project_id",
                    "reports",
                    "cases",
                    "registered_batches_complete",
                    "new_evidence_bytes",
                    "usage_at_delivery",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    study = Study(settings())
    try:
        publish(study)
    finally:
        study.db.close()
