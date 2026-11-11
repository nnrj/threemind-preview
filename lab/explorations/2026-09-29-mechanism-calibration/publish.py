"""Publish reports, factual readout tables and a verified complete archive via Lab."""

import csv
import gzip
import hashlib
import json
import re

from common import GIB, HERE, WORK, new_json, read_json
from publication_base import Publisher

from threemind_lab import notebooks, report_sources, research_documents
from threemind_lab.database import LOCAL_USER

RECORDS = (
    ("intensity", "强刺激：输入强度与 30 秒保持", "intensity/s9293201/g0.075/single_4/probe30/cue0.5"),
    ("novelty", "新颖性：立即计算与真实延迟触达", "novelty/s9293201/i0.4/p70000/arrival-window/g0.018/probe"),
    ("forgetting", "300 秒记忆：结构遗忘与提示门槛", "forgetting/s9293201/spaced_ordinary/weight_off/probe300/cue1.0"),
    ("adaptation", "关闭遗忘后的新旧响应与饱和检查", "adaptation/s9293201/weight_off/stage2/cue0.5"),
)


def source(p, key, case_key):
    name = "source:" + key
    if name in p.state:
        return p.state[name]
    folder = WORK / "cases/execution2" / case_key
    result = read_json(folder / "result.json")
    events = map(json.loads, gzip.decompress((folder / "events.jsonl.gz").read_bytes()).splitlines())
    window = next(
        e["payload"] for e in events if e["kind"] == "temporal_readout" and e["payload"].get("analysis_schema")
    )
    selection = {
        "operation_id": p.identity(name + ":request"),
        "kind": "temporal_nodes",
        "run_id": result["id"],
        "window_ids": [window["window_id"]],
        "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
    }
    request = report_sources.request(p.db, p.project, LOCAL_USER, selection)
    with p.owned(request["job_id"]) as job:
        output = report_sources.capture(p.db, job)
        p.db.finish(job, result=output)
    return p.remember(
        name,
        {"id": str(request["id"]), "run_id": result["id"], "case": case_key, "content_hash": output["content_hash"]},
    )


def publish(p):
    audit, analysis = read_json(WORK / "audit.json"), read_json(WORK / "analysis-final.json")
    assert audit["verified_cases"] == analysis["cases"] == 786
    if not (WORK / "STOP").exists():
        (WORK / "STOP").write_text(
            "Registered calibration completed. No further simulations in this project.\n", encoding="utf-8"
        )
    csv_path = WORK / "case-summary.csv"
    if not csv_path.exists():
        columns = sorted(
            {key for row in analysis["rows"] for key, value in row.items() if not isinstance(value, (dict, list))}
        )
        with csv_path.open("x", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(analysis["rows"])
    sources = {key: source(p, key, case) for key, _, case in RECORDS}
    archive = p.archive()
    asset = p.identity("overview-image")
    notebooks.save_asset(
        p.db, p.project, LOCAL_USER, asset, "mechanism-calibration.png", (WORK / "overview.png").read_bytes()
    )
    image_url = f"/api/v2/projects/{p.project}/note-assets/{asset}"
    evidence = (
        f"\n\n[完整原始证据 / Complete evidence](/api/v2/projects/{p.project}/artifacts/{archive['artifact_id']})\n"
    )
    for lang in ("zh", "en"):
        body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
        body = body.replace("../../../docs/images/mechanism-calibration-2026-09-29.png", image_url)
        body = re.sub(r"\[([^\]]+)\]\(([^):]+\.md)\)", r"\1", body) + evidence
        title = (
            "强刺激、新颖性与 300 秒遗忘：786 实例校准"
            if lang == "zh"
            else "Intensity, novelty and retention: calibration of 786 instances"
        )
        p.document("report:" + lang, "report", title, body)
        p.note("results:" + lang, title, body)
    for key, title, case in RECORDS:
        selected = sources[key]
        text = (
            "该记录对应完整校准报告中的一组实验。全组统计、全部对照与失败记录见报告及证据包；下面是一个明确标注的机制观察例，不能代替全组结果。\n\n"
            f"案例：`{case}`，意识：`{selected['run_id']}`。表格直接读取冻结的时序证据，判定时激活与峰值分别列示；缺失排名不是零名次。\n\n"
            f"![四组结果总览]({image_url})" + evidence
        )
        p.document(
            "record:" + key,
            "record",
            title,
            text,
            sources=[selected["id"]],
            blocks=[
                {
                    "id": "readout-evidence",
                    "type": "table",
                    "source": selected["id"],
                    "metrics": ["rank", "decision_activation", "peak_activation", "activation_integral"],
                    "title": "收敛判定末尾、早期峰值与全窗积分 / Decision, peak and integral",
                }
            ],
        )
    for lang in ("zh", "en"):
        saved = p.state["report:" + lang]
        actual = research_documents.get(p.db, p.project, saved["id"], revision=saved["revision"])
        assert actual["content_hash"] == saved["content_hash"]
    assert len(research_documents.listing(p.db, p.project, kind="record")["rows"]) == 4
    assert len(research_documents.listing(p.db, p.project, kind="report")["rows"]) == 2
    sha, size = hashlib.sha256(), 0
    with p.db.tx(p.project) as db, db.cursor(name="calibration_archive_readback") as cursor:
        cursor.execute(
            "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (archive["artifact_id"],)
        )
        for row in cursor:
            sha.update(row["body"])
            size += len(row["body"])
    assert sha.hexdigest() == archive["sha256"] and size == archive["bytes"]
    with p.db.tx() as db:
        size_db = db.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    local = sum(f.stat().st_size for f in WORK.rglob("*") if f.is_file())
    total = local + max(0, size_db - p.meta["database_bytes_before"])
    assert total < 4 * GIB
    delivery = {
        "project_id": p.project,
        "reports": {lang: p.state["report:" + lang]["id"] for lang in ("zh", "en")},
        "archive": archive,
        "archive_database_readback_verified": True,
        "total_new_bytes": total,
        "verified_cases": 786,
        "failed_empty_startup_cases_preserved": 1,
        "compute_seconds": audit["compute_seconds"],
        "usage_start_percent": audit["usage_start_percent"],
        "usage_end_percent": read_json(WORK / "usage.json")["used_percent"],
        "simulation_stopped": True,
    }
    if not (WORK / "publication-verification.json").exists():
        new_json(WORK / "publication-verification.json", delivery)
    for lang in ("zh", "en"):
        body = f"""# {"校准实验交付验证" if lang == "zh" else "Calibration delivery verification"}

Project: `2026-09-29 强刺激、新颖性与遗忘校准` / `{p.project}`.

- Completed and DB-verified states: **786**; one empty failed startup retained separately.
- Reports: 中文 `{delivery["reports"]["zh"]}`; English `{delivery["reports"]["en"]}`.
- Four records with frozen factual readout tables; bilingual design and result notes.
- Archive `{archive["artifact_id"]}`: {archive["bytes"] / 2**20:.2f} MiB, {archive["verified_members"]} members individually checked.
- Archive SHA-256 `{archive["sha256"]}`; complete DB chunk readback verified.
- New local+DB storage including archive: **{total / GIB:.3f} GiB / 4 GiB**.
- Simulation wall time: **{audit["compute_seconds"] / 60:.2f} min / 120 min**; no energy deficit or resource stop.
- Shared account usage: {delivery["usage_start_percent"]}% → {delivery["usage_end_percent"]}%; not attributable exclusively to this task.
- All experiment inputs/configurations explicit; existing states and hypotheses unchanged. Further simulations stopped.
"""
        (HERE / f"delivery.{lang}.md").write_text(body, encoding="utf-8")
        p.note("delivery:" + lang, "交付验证 / Delivery verification " + lang, body)
    print(json.dumps(delivery, default=str), flush=True)


if __name__ == "__main__":
    p = Publisher()
    try:
        publish(p)
    finally:
        p.db.close()
