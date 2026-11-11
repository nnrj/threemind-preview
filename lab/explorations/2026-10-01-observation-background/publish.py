"""Publish E23 bilingual reports and unfiltered temporal records via Lab services."""

import gzip
import hashlib
import json
import re
import shutil
import zipfile

from common import HERE, ROOT, WORK, Study, ids, new_json, note_text, read_json, settings

from lab.tools.study_publication import Publication
from threemind_lab import notebooks, report_sources, research_documents
from threemind_lab.database import LOCAL_USER

EXAMPLES = (
    ("periodic", "replication-v2/100121/periodic/AB/dense/wait30/cueX", "周期背景：30 秒后顺序响应"),
    ("random", "replication-v2/100121/random/AB/dense/wait30/cueX", "随机背景：30 秒后顺序响应"),
    ("none", "replication-v2/100121/none/AB/dense/wait1/cueX", "无背景：死亡前的实际响应"),
)


def report_addendum(p):
    if p.state.get("report-addendum", {}).get("artifact_id"):
        return p.state["report-addendum"]
    path = WORK / "report-correction.zip"
    if not path.exists():
        with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ("report.zh.md", "report.en.md", "publish.py"):
                archive.write(HERE / name, name)
            archive.writestr(
                "purpose.txt",
                "Append-only correction: random background has no convergence decision (null), not zero decision-time activation. Raw dynamics, trajectories, criteria and results are unchanged. Main evidence archive remains intact.",
            )
    p.guard(reserve=path.stat().st_size * 2)
    item = p.state.get("report-addendum")
    if item is None:
        p.queue_clear()
        item = p.remember(
            "report-addendum",
            {
                "job_id": p.db.enqueue(
                    p.project, "analysis", {"purpose": "archive report wording correction; no simulation"}
                )["id"]
            },
        )
    with p.owned(item["job_id"]) as job, path.open("rb") as stream:
        asset = p.db.put_artifact_stream(
            job,
            "E23-report-correction.zip",
            "application/zip",
            stream,
            metadata={"schema": "study-report-correction/1", "study": p.study.name},
        )
        p.db.finish(job, result={"artifact_id": str(asset["id"]), "report_correction": True})
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert asset["sha256"] == expected
    with p.db.tx(p.project) as tx:
        chunks = tx.execute(
            "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (asset["id"],)
        ).fetchall()
    assert hashlib.sha256(b"".join(x["body"] for x in chunks)).hexdigest() == expected
    return p.remember(
        "report-addendum", item | {"artifact_id": str(asset["id"]), "sha256": expected, "bytes": asset["bytes"]}
    )


def revised_narrative(p, lang, title, body):
    key = "report:" + lang
    if key in p.state:
        previous = p.state[key]
        document = research_documents.get(p.db, p.project, previous["id"], revision=previous["revision"])
        if document["spec"]["blocks"][0]["markdown"] != body:
            value = research_documents.save(
                p.db,
                p.project,
                LOCAL_USER,
                previous["id"],
                {
                    "operation_id": p.study.identity(key + ":decision-null-correction"),
                    "expected_revision": previous["revision"],
                    "spec": {
                        "kind": "report",
                        "title": title,
                        "sources": [],
                        "blocks": [{"id": "narrative", "type": "commentary", "markdown": body, "section": "results"}],
                    },
                },
            )
            p.remember(key, value)
    else:
        p.document(key, "report", title, body)
    key = "results:" + lang
    if key in p.state:
        previous = p.state[key]
        note = notebooks.note(p.db, p.project, LOCAL_USER, previous["id"], revision=previous["revision"])
        if note["body"]["text"] != body:
            value = notebooks.save_note(
                p.db,
                p.project,
                LOCAL_USER,
                previous["id"],
                {
                    "operation_id": p.study.identity(key + ":decision-null-correction"),
                    "expected_revision": previous["revision"],
                    "kind": "note",
                    "collection_id": p.study.meta["notebook_id"],
                    "title": title,
                    "body": {"format": "markdown", "text": body},
                },
            )
            p.remember(key, value)
    else:
        p.note(key, title, body)


def publish(study):
    audit = read_json(WORK / "audit-final.json")
    summary = read_json(WORK / "summary-final.json")
    assert audit["unchanged_core"] and audit["historical_sources_unchanged"]
    assert audit["cases"] == summary["total_cases"] == 502
    assert len(summary["live"]) == 12 and all(x["reproduced"] for x in summary["live"])
    p = Publication(study)
    records = []
    for label, key, title in EXAMPLES:
        folder = WORK / "cases" / key
        row = read_json(folder / "result.json")
        events = [json.loads(line) for line in gzip.decompress((folder / "events.jsonl.gz").read_bytes()).splitlines()]
        windows = [
            e["payload"]["window_id"]
            for e in events
            if e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema")
        ]
        assert windows
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
                    "window_ids": windows,
                    "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                },
            )
            with p.owned(request["job_id"]) as job:
                result = report_sources.capture(p.db, job)
                p.db.finish(job, result=result)
            p.remember(token, {"id": str(request["id"]), "content_hash": result["content_hash"]})
        records.append((label, key, title, p.state[token]))
    for directory in ("figures", "tables"):
        dest = WORK / directory
        dest.mkdir(exist_ok=True)
        for path in (HERE / directory).glob("*"):
            if path.is_file():
                shutil.copy2(path, dest / path.name)
    aux = WORK / "delivery-tools"
    aux.mkdir(exist_ok=True)
    manifest = {}
    for name in ("lab/tools/study_lock.py", "lab/tools/study_input_audit.py", "tests/test_study_runtime_protocol.py"):
        source = ROOT / name
        shutil.copy2(source, aux / source.name)
        manifest[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    if not (aux / "manifest.json").exists():
        new_json(aux / "manifest.json", manifest)
    image = p.image("observation-background-final", HERE / "figures/observation-background-final.png")
    archive = p.archive("observation-background-evidence.zip", historical_data_included=True)
    url = f"/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']}"
    appendix = f"\n\n[完整证据（含 CSV、输入与快照） / Evidence with CSV, inputs and states]({url})\n"
    addendum = report_addendum(p)
    appendix += (
        f"\n[报告措辞校订包 / Report correction](/api/v2/projects/{p.project}/artifacts/{addendum['artifact_id']})\n"
    )
    p.note(
        "execution-notes",
        "E23 执行偏差与更正 / Execution corrections",
        (HERE / "execution-notes.md").read_text(encoding="utf-8"),
    )
    for lang in ("zh", "en"):
        body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
        body = re.sub(r"!\[[^\]]*\]\(figures/observation-background-final\.png\)", lambda _: image, body)
        body = re.sub(r"\[([^\]]+)\]\(tables/[^)]+\)", lambda m: f"[{m[1]} (ZIP)]({url})", body)
        body = note_text(body) + appendix
        title = "E23：背景、观察与延后选择" if lang == "zh" else "E23: background, observation and later choice"
        revised_narrative(p, lang, title, body)
    rendered = []
    for label, key, title, source in records:
        row = read_json(WORK / "cases" / key / "result.json")
        state = json.loads(gzip.decompress((WORK / "cases" / key / "pre-probe.json.gz").read_bytes()))
        mapping = {n["channel"]: n["id"] for n in state["nodes"]}
        legend = "\n\n| Symbol | Node | Channel |\n| --- | --- | --- |\n" + "\n".join(
            f"| {s} | {mapping[ids(row['seed'])[s]]} | {ids(row['seed'])[s]} |" for s in ("A", "B")
        )
        body = "原始活动窗口；全部节点均可核查，不能只读收敛候选。净效应另减同源无提示。\n\nRaw activity window with all recorded nodes, not only convergence candidates. Net effects additionally subtract matched uncued controls."
        if label == "none":
            body += "\n\n**死亡截短窗口 / Death-truncated window**：未作为完整 5 秒通过；不补零、不复活。"
        item = p.document(
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
                    "title": "判定值、峰值与积分 / Decision, peak and integral",
                }
            ],
        )
        preview = research_documents.render(p.db, p.project, item["id"], revision=item["revision"])
        table = next(b for b in preview["blocks"] if b["id"] == "readout")
        shown = {r["provenance"]["raw_node"]["node_id"]: r["values"] for r in table["rows"]}
        for s in ("A", "B"):
            value = shown[mapping[ids(row["seed"])[s]]]
            expected = row["extra"]["target_values"][s]
            assert abs(value["activation_integral"] - expected["integral"]) < 1e-14
            assert value["peak_activation"] == expected["peak"]
            if label == "random":
                assert value["decision_activation"] is None  # unresolved, not a zero decision
            else:
                assert value["decision_activation"] == 0
        rendered.append({"record": item["id"], "target_rows_verified": True, "row_count": table["row_count"]})
    p.verify()
    for lang in ("zh", "en"):
        item = p.state["results:" + lang]
        value = notebooks.note(p.db, p.project, LOCAL_USER, item["id"], revision=item["revision"])
        assert len(value["body"]["text"]) > 2000
    with p.db.tx() as tx:
        db_size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    total = sum(x.stat().st_size for x in WORK.rglob("*") if x.is_file()) + max(
        0, db_size - study.meta["database_bytes_before"]
    )
    delivery = {
        "project_id": p.project,
        "reports": {k: p.state["report:" + k]["id"] for k in ("zh", "en")},
        "cases": 502,
        "archive": archive,
        "report_addendum": addendum,
        "archive_readback_verified": True,
        "record_render_checks": rendered,
        "new_evidence_bytes": total,
        "usage_start": 92,
        "usage_at_delivery": read_json(WORK / "usage.json")["used_percent"],
        "audit": audit,
        "simulation_wall_seconds": summary["aggregate_wall_seconds"],
    }
    assert total < study.settings.storage_hard
    new_json(WORK / "delivery.json", delivery)
    receipt = (
        f"E23 完成交付 / Completed delivery\n\n502 saved cases; {audit['inputs']['frames']} verified input frames, {audit['inputs']['pending_frames']} deliberately pending at observation boundaries. {len(rendered)} raw readout tables checked, including A/B rows.\n\nEvidence including local files, database growth and archive: {total / 2**30:.3f} GiB. Shared-account observed usage: 92% → {delivery['usage_at_delivery']}%. Simulation case wall time: {summary['aggregate_wall_seconds']:.2f} s.\n\nCore and historical data unchanged. Failed/pilot cases and corrections retained. No push.\n"
        + appendix
    )
    p.note("delivery-note", "E23 交付验收 / Delivery verification", receipt)
    print(json.dumps(delivery, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    study = Study(settings())
    try:
        publish(study)
    finally:
        study.db.close()
