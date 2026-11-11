"""Publish E24 evidence and bilingual records using existing ThreeMind services."""

import hashlib
import json
import re
import shutil
from urllib.parse import quote

from analyze import coordinates, metrics, windows
from common import HERE, ROOT, WORK, Study, new_json, read_json, settings

from lab.tools.study_publication import Publication
from threemind_lab import notebooks, report_sources, research_documents
from threemind_lab.database import LOCAL_USER

EXAMPLES = (
    ("telemetry", "matrix/100121/telemetry/AB/wait30/cue1", "真实遥测：30 秒后的目标响应"),
    ("random", "matrix/100121/random/AB/wait30/cue1", "配平随机：全局未定仍有目标响应"),
    ("none", "matrix/100121/none/AB/wait1/cue1", "无背景：死亡前的目标响应"),
)


def note_text(body):
    return re.sub(
        r"\[([^\]]+)\]\(([A-Za-z0-9_./-]+\.md)\)",
        lambda m: f"[{m[1]}](/docs?doc={quote((HERE / m[2]).resolve().relative_to(ROOT).as_posix(), safe='')})",
        body,
    )


def publish(study):
    summary, audit = (read_json(WORK / name) for name in ("summary.json", "audit.json"))
    assert summary["cases"] == audit["inputs"]["cases"] == 160
    assert not summary["failed"] and all(row["replay_matches"] for row in summary["live"])
    p = Publication(study)
    p.guard()
    sources = read_json(WORK / "historical-sources.json") | read_json(WORK / "calibration/source-checksums.json")
    for relative, digest in sources.items():
        original = ROOT / relative
        assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
        dest = WORK / "selected-history" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(original, dest)
        assert hashlib.sha256(dest.read_bytes()).hexdigest() == digest
    for directory in ("tables", "figures"):
        dest = WORK / directory
        dest.mkdir(exist_ok=True)
        for path in (HERE / directory).glob("*"):
            if path.is_file():
                shutil.copy2(path, dest / path.name)
    records = []
    for label, key, title in EXAMPLES:
        row = read_json(WORK / "cases" / key / "result.json")
        token = "source:" + label
        if token not in p.state:
            p.queue_clear()
            request = report_sources.request(
                p.db,
                p.project,
                LOCAL_USER,
                {
                    "operation_id": study.identity(token + ":request"),
                    "kind": "temporal_nodes",
                    "run_id": row["id"],
                    "window_ids": [w["window_id"] for w in windows(row)],
                    "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                },
            )
            with p.owned(request["job_id"]) as job:
                result = report_sources.capture(p.db, job)
                p.db.finish(job, result=result)
            p.remember(token, {"id": str(request["id"]), "content_hash": result["content_hash"]})
        records.append((label, row, title, p.state[token]))
    image = p.image("target-background", HERE / "figures/target-background.png")
    archive = p.archive("target-background-evidence.zip", historical_data_included=True)
    url = f"/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']}"
    appendix = f"\n\n[完整证据（输入、快照、CSV、历史来源） / Complete evidence]({url})\n"
    for lang in ("zh", "en"):
        body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
        body = re.sub(r"!\[[^\]]*\]\(figures/target-background\.png\)", lambda _: image, body)
        body = re.sub(r"\[([^\]]+)\]\(tables/[^)]+\)", lambda m: f"[{m[1]} (ZIP)]({url})", body)
        body = note_text(body) + appendix
        title = "E24：目标响应与遥测背景对照" if lang == "zh" else "E24: target response and telemetry controls"
        p.document("report:" + lang, "report", title, body)
        p.note("results:" + lang, title, body)
    p.note(
        "execution-notes",
        "E24 执行记录 / Execution notes",
        (HERE / "execution-notes.md").read_text(encoding="utf-8") + appendix,
    )
    rendered = []
    for label, row, title, source in records:
        selected = coordinates(row)
        legend = "\n\n| Symbol | Node ID |\n| --- | --- |\n" + "\n".join(f"| {s} | {n} |" for s, n in selected.items())
        body = "完整时序节点表，保留全局分类和全部节点。目标 A/B 的过程响应、局部稳定与全局收敛分别解释。\n\nComplete temporal node table. Target response, local stability and global convergence remain separate."
        if label == "none":
            body += "\n\n**死亡截短，不是完整五秒观察。 / Death-truncated, not a complete five-second window.**"
        item = p.document(
            "record:" + label,
            "record",
            title,
            body + legend + appendix,
            sources=[source["id"]],
            blocks=[
                {
                    "id": "raw-readout",
                    "type": "table",
                    "source": source["id"],
                    "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                    "title": "原始判定、峰值与积分 / Original decision, peak and integral",
                }
            ],
        )
        preview = research_documents.render(p.db, p.project, item["id"], revision=item["revision"])
        table = next(b for b in preview["blocks"] if b["id"] == "raw-readout")
        shown = {r["provenance"]["raw_node"]["node_id"]: r["values"] for r in table["rows"]}
        expected = metrics(row)
        for symbol, node in selected.items():
            value = shown[node]
            assert abs(value["activation_integral"] - expected["targets"][symbol]["trapezoid"]) < 1e-14
            assert value["peak_activation"] == expected["targets"][symbol]["peak"]
            if label == "random":
                assert value["decision_activation"] is None
            elif label == "telemetry":
                assert value["decision_activation"] == 0
        rendered.append({"record": item["id"], "target_rows_verified": True, "row_count": table["row_count"]})
    p.verify()
    for lang in ("zh", "en"):
        item = p.state["results:" + lang]
        value = notebooks.note(p.db, p.project, LOCAL_USER, item["id"], revision=item["revision"])
        assert len(value["body"]["text"]) > 2000
    with p.db.tx() as tx:
        size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    total = sum(x.stat().st_size for x in WORK.rglob("*") if x.is_file()) + max(
        0, size - study.meta["database_bytes_before"]
    )
    assert total < study.settings.storage_hard
    delivery = {
        "project_id": p.project,
        "reports": {k: p.state["report:" + k]["id"] for k in ("zh", "en")},
        "cases": 160,
        "archive": archive,
        "archive_readback_verified": True,
        "record_render_checks": rendered,
        "new_evidence_bytes": total,
        "usage_start": study.settings.usage_start,
        "usage_at_delivery": read_json(WORK / "usage.json")["used_percent"],
        "audit": audit,
        "simulation_wall_seconds": summary["wall_seconds"],
    }
    if not (WORK / "delivery.json").exists():
        new_json(WORK / "delivery.json", delivery)
    receipt = (
        f"E24 完成交付 / Completed delivery\n\n160 cases; {audit['inputs']['frames']} verified input frames; {audit['inputs']['pending_frames']} preserved pending frames; three rendered raw-node tables checked.\n\n"
        f"Evidence including local copies, archive and database growth: {total / 2**30:.3f} GiB. Case execution wall time: {summary['wall_seconds']:.2f} s. Shared-account observed usage: {study.settings.usage_start}% → {delivery['usage_at_delivery']}%. This is not task-exclusive billing.\n\n"
        "Historical sources and Core unchanged. No push.\n" + appendix
    )
    p.note("delivery-note", "E24 交付核查 / Delivery verification", receipt)
    print(json.dumps(delivery, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    study = Study(settings())
    try:
        publish(study)
    finally:
        study.db.close()
