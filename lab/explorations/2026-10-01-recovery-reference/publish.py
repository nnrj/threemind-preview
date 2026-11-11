"""Publish finalized, verified artifacts to the dedicated ThreeMind project."""

import gzip
import json
import re
import shutil

from common import HERE, WORK, Study, new_json, note_text, read_json, settings

from lab.tools.study_publication import Publication
from threemind_lab import notebooks, report_sources, research_documents
from threemind_lab.database import LOCAL_USER

EXAMPLES = (
    ("cut-sham", "cut/930101/full/learn01/none/sign1/physical1", "感官原状态：假交换"),
    ("cut-weights", "cut/930101/full/learn01/W/sign1/physical1", "感官状态：只交换连接权重"),
    ("cut-persistent", "cut/930101/full/learn01/WSN/sign1/physical1", "感官状态：交换全部登记持久字段"),
    ("recovery-60", "recovery/930101/full/learn11/wait60/sign1/physical1", "感官教学后 60 秒"),
    ("maintenance-phase", "timing/100121/f0/p40000/k60000/AB/wait30/cueX", "分开教学与维护时机"),
    ("dense-jitter", "jitter/100121/jitter/AB/wait30/cueX", "密集课程：事前固定的时间抖动"),
    ("matched-shared", "reference/100121/dense/shared/AB/wait30/cueXZ", "等曝光共享参照：联合提示"),
    ("matched-separate", "reference/100121/dense/separate/AB/wait30/cueXZ", "等曝光独立参照：联合提示"),
)


def publish(study):
    audit = read_json(WORK / "audit.json")
    assert audit["unchanged_core"] and audit["historical_sources_unchanged"]
    p = Publication(study)
    records = []
    for label, key, title in EXAMPLES:
        folder = WORK / "cases" / key
        if not (folder / "result.json").exists():
            continue
        row = read_json(folder / "result.json")
        events = [json.loads(line) for line in gzip.decompress((folder / "events.jsonl.gz").read_bytes()).splitlines()]
        activity = [
            e["payload"] for e in events if e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema")
        ]
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
                    "window_ids": [a["window_id"] for a in activity],
                    "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                },
            )
            with p.owned(request["job_id"]) as job:
                result = report_sources.capture(p.db, job)
                p.db.finish(job, result=result)
            p.remember(token, {"id": str(request["id"]), "run_id": row["id"], "content_hash": result["content_hash"]})
        records.append((label, key, title, p.state[token]))
    assets = {}
    for directory in ("figures", "tables"):
        for path in sorted((HERE / directory).glob("*")):
            if path.suffix not in (".png", ".csv"):
                continue
            target = WORK / directory / path.name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(path, target)
            if path.suffix == ".png":
                assets[path.stem] = p.image(path.stem, path)
    archive = p.archive("recovery-reference-evidence.zip", historical_data_included=True)
    appendix = f"\n\n[完整证据 / Complete evidence](/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']})\n"
    for lang in ("zh", "en"):
        title = (
            "感官恢复、维护时机与共同参照"
            if lang == "zh"
            else "Sensory recovery, maintenance timing and shared references"
        )
        body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
        for stem, image in assets.items():
            body = re.sub(r"!\[[^\]]*\]\(figures/" + re.escape(stem) + r"\.png\)", lambda _, image=image: image, body)
        body = note_text(body) + appendix
        p.document("report:" + lang, "report", title, body)
        p.note("results:" + lang, title, body)
    for label, key, title, source in records:
        row = read_json(WORK / "cases" / key / "result.json")
        state = json.loads(gzip.decompress((WORK / "cases" / key / "pre-probe.json.gz").read_bytes()))
        by_channel = {n["channel"]: n["id"] for n in state["nodes"]}
        legend = "\n\n| 观察者符号 / Symbol | 节点 / Node | 匿名通道 / Channel |\n| --- | --- | --- |\n"
        legend += "\n".join(
            f"| {symbol} | {by_channel.get(channel, 'new')} | {channel} |"
            for symbol, channel in zip("AB", row["extra"]["targets"])
        )
        body = "固定示例；下表是原始窗口，报告中的净响应另减去同源无提示副本。末态、峰值、累计活动分别保留。\n\nFixed example: raw window values; net report responses additionally subtract matched uncued controls. Terminal, peak and cumulative activity remain separate."
        if label.startswith("cut-") and label != "cut-sham":
            body += "\n\n本例经过明确的人为研究交换，仅替换登记的持久字段、保留接收方全部信号，不是自然学习过程。This example has an explicit artificial persistent-field exchange retaining receiver signals; it is not natural learning."
        p.document(
            "record:" + label,
            "record",
            title,
            body + legend + appendix,
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
    p.verify()
    rendered = []
    for label, key, _title, _source in records:
        record = p.state["record:" + label]
        view = research_documents.render(p.db, p.project, record["id"], revision=record["revision"])
        table = next(b for b in view["blocks"] if b["id"] == "readout")
        row = read_json(WORK / "cases" / key / "result.json")
        state = json.loads(gzip.decompress((WORK / "cases" / key / "pre-probe.json.gz").read_bytes()))
        ids = {n["channel"]: n["id"] for n in state["nodes"]}
        targets = {ids[channel] for channel in row["extra"]["targets"]}
        shown = {r["provenance"]["raw_node"]["node_id"]: r["values"] for r in table["rows"]}
        assert targets <= shown.keys(), "target nodes missing from report preview"
        for target in targets:
            assert shown[target]["activation_integral"] is not None
            assert shown[target]["decision_activation"] is not None
        rendered.append({"record": record["id"], "targets_present": True, "row_count": table["row_count"]})
    for lang in ("zh", "en"):
        note = notebooks.note(p.db, p.project, LOCAL_USER, p.state["results:" + lang]["id"], revision=1)
        assert note["body"]["format"] == "markdown" and len(note["body"]["text"]) > 1000
    with p.db.tx() as tx:
        size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    local = sum(f.stat().st_size for f in WORK.rglob("*") if f.is_file())
    result = audit | {
        "project_id": p.project,
        "reports": {lang: p.state["report:" + lang]["id"] for lang in ("zh", "en")},
        "records": {k: v["id"] for k, v in p.state.items() if k.startswith("record:")},
        "archive": archive,
        "archive_readback_verified": True,
        "record_render_checks": rendered,
        "new_evidence_bytes": local + max(0, size - study.meta["database_bytes_before"]),
        "usage_at_delivery": read_json(WORK / "usage.json")["used_percent"],
    }
    assert result["new_evidence_bytes"] < study.settings.storage_hard
    new_json(WORK / "delivery.json", result)
    receipt = (
        "# 交付验收 / Delivery verification\n\n"
        f"研究项目 / Project: {p.project}\n\n"
        f"已完成 / Completed: {result['cases']} cases; "
        f"verified input frames: {result['inputs']['frames']}; pending: {result['inputs']['pending_frames']}.\n\n"
        f"新增证据含归档约 / New evidence including archives: {result['new_evidence_bytes'] / 2**30:.3f} GiB. "
        "Estimate includes the local study directory and positive database-size change.\n\n"
        f"共享账户 / Shared account: {result['usage_start']}% → {result['usage_at_delivery']}%.\n\n"
        "Core、产品默认与旧来源未变；强刺激替代探索暂缓。"
        "Core, product defaults and historical sources remain unchanged; intensity replacement is deferred.\n\n"
        "报告、记录预览中的目标节点和证据归档已回读核对。"
        "Reports, target nodes in record previews and archived bytes have been read back and verified.\n" + appendix
    )
    saved_note = p.note("delivery-note", "E22 交付验收 / Delivery verification", receipt)
    note = notebooks.note(p.db, p.project, LOCAL_USER, saved_note["id"], revision=1)
    assert note["body"]["text"] == receipt
    p.guard(reserve=1)
    print(
        json.dumps(
            {k: result[k] for k in ("project_id", "reports", "cases", "new_evidence_bytes", "usage_at_delivery")},
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    study = Study(settings())
    try:
        publish(study)
    finally:
        study.db.close()
