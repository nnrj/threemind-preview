"""Read back this study's published reports and entire evidence archive."""

import argparse
import hashlib
import json
from datetime import UTC, datetime

from common import HERE, WORK, Study, encoded

from threemind_lab import research_documents


def verify(study, usage_end):
    pub = json.loads((WORK / "publication.json").read_bytes())
    for lang in ("zh", "en"):
        doc = pub["report:" + lang]
        row = research_documents.get(study.db, study.project, doc["id"], revision=doc["revision"])
        assert row["content_hash"] == doc["content_hash"]
        assert "448" in row["spec"]["blocks"][0]["markdown"]
    assert len(research_documents.listing(study.db, study.project, kind="record")["rows"]) == 4
    assert len(research_documents.listing(study.db, study.project, kind="report")["rows"]) == 2
    digest, size = hashlib.sha256(), 0
    with study.db.tx(study.project) as db, db.cursor(name="input_activity_archive_verify") as cursor:
        cursor.execute(
            "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal", (pub["archive"]["artifact_id"],)
        )
        for row in cursor:
            digest.update(row["body"])
            size += len(row["body"])
    assert digest.hexdigest() == pub["archive"]["sha256"] and size == pub["archive"]["bytes"]
    with study.db.tx() as db:
        database = db.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    local = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
    growth = max(0, database - study.meta["database_bytes_before"])
    assert local + growth < 3 * 1024**3
    audit = json.loads((WORK / "analysis.json").read_bytes())
    result = {
        "verified_at": datetime.now(UTC).isoformat(),
        "project_id": study.project,
        "reports": {l: pub["report:" + l]["id"] for l in ("zh", "en")},
        "records": 4,
        "archive": pub["archive"],
        "archive_database_readback_verified": True,
        "local_bytes": local,
        "database_growth_bytes": growth,
        "total_new_bytes": local + growth,
        "usage_start_percent": 44,
        "usage_end_percent": usage_end,
        "instances": audit["cases"],
        "compute_seconds": audit["compute_seconds"],
        "simulations_stopped": (WORK / "STOP").exists(),
    }
    (WORK / "publication-verification.json").write_bytes(encoded(result))
    for lang in ("zh", "en"):
        text = f"""# {"实验交付记录" if lang == "zh" else "Experiment delivery"}

2026-09-29. 448 {"实例完成，已停止新增模拟。旧数据与 Core 默认保持。" if lang == "zh" else "instances complete. Further simulation stopped. Old data and Core defaults preserved."}

- {"项目" if lang == "zh" else "Project"}: `2026-09-29 刺激间隔、自主活动与环境选择` / `{study.project}`.
- {"中文报告" if lang == "zh" else "Chinese report"}: `{result["reports"]["zh"]}`; English: `{result["reports"]["en"]}`. 4 {"主题记录，笔记中含各阶段登记。" if lang == "zh" else "topical records; stage registrations in the notebook."}
- {"证据附件" if lang == "zh" else "Evidence artifact"}: `{pub["archive"]["artifact_id"]}`, {size / 2**20:.1f} MiB, {pub["archive"]["verified_members"]} {"核验成员。已流式读回整个数据库附件，SHA-256 一致。" if lang == "zh" else "verified members. Entire database archive streamed back and SHA-256 verified."}
- SHA-256: `{digest.hexdigest()}`.
- {"本地" if lang == "zh" else "Local"} {local / 2**20:.1f} MiB; {"数据库净增" if lang == "zh" else "database net growth"} {growth / 2**20:.1f} MiB; {"合计" if lang == "zh" else "total"} **{(local + growth) / 2**30:.3f} GiB / 3 GiB**.
- {"实例累计耗时" if lang == "zh" else "Aggregate instance wall time"} {audit["compute_seconds"] / 60:.2f} min. CPU. {"无 GPU、付费 AI 或云。" if lang == "zh" else "No GPU, paid AI or cloud."}
- {"账户共享额度读数" if lang == "zh" else "Shared account usage"} 44% → {usage_end}%; {"不是精确任务 token 用量。" if lang == "zh" else "not exact task-specific token accounting."}
- [中文结果](report.zh.md), [English results](report.en.md).

{"本记录写于归档后，未包含在此前已封存的 ZIP 中。核验详情在" if lang == "zh" else "This delivery record was written after archiving and is not inside the sealed ZIP. Verification details:"} `.work/input-rate-autonomy-20260929/publication-verification.json`.
"""
        (HERE / f"delivery.{lang}.md").write_text(text, encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usage-end", type=int, required=True)
    args = parser.parse_args()
    study = Study()
    try:
        verify(study, args.usage_end)
    finally:
        study.db.close()
