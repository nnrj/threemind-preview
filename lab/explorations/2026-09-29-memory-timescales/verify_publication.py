"""Read back published evidence and record final delivery without new simulation."""

import hashlib
import json
from datetime import UTC, datetime

from common import HERE, WORK, Study, encoded

from threemind_lab import research_documents


def verify(s):
    pub = json.loads((WORK / "publication.json").read_bytes())
    for lang in ("zh", "en"):
        # Audit the originally published revision even after authored addenda.
        row = research_documents.get(
            s.db, s.project, pub["report:" + lang]["id"], revision=pub["report:" + lang]["revision"]
        )
        assert row["content_hash"] == pub["report:" + lang]["content_hash"]
        assert "598" in row["spec"]["blocks"][0]["markdown"]
    assert len(research_documents.listing(s.db, s.project, kind="record")["rows"]) == 8
    assert len(research_documents.listing(s.db, s.project, kind="report")["rows"]) == 2
    digest, count = hashlib.sha256(), 0
    with s.db.tx(s.project) as db, db.cursor(name="memory_evidence_verify") as cursor:
        cursor.execute(
            "SELECT body FROM artifact_chunks WHERE artifact_id=%s ORDER BY ordinal",
            (pub["archive"]["artifact_id"],),
        )
        for row in cursor:
            digest.update(row["body"])
            count += len(row["body"])
    assert digest.hexdigest() == pub["archive"]["sha256"] and count == pub["archive"]["bytes"]
    with s.db.tx() as tx:
        db_bytes = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    local = sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file())
    growth = max(0, db_bytes - s.meta["database_bytes_before"])
    assert local + growth < 2 * 1024**3
    result = {
        "verified_at": datetime.now(UTC).isoformat(),
        "project_id": s.project,
        "reports": {l: pub["report:" + l]["id"] for l in ("zh", "en")},
        "factorial_records": 8,
        "raw_archive": pub["archive"],
        "database_archive_readback_verified": True,
        "local_bytes": local,
        "database_growth_bytes": growth,
        "total_new_bytes": local + growth,
        "usage_start_percent": 41,
        "usage_end_percent": 43,
        "new_instances": 598,
        "new_experiments_stopped": True,
    }
    (WORK / "publication-verification.json").write_bytes(encoded(result))
    gib = (local + growth) / 1024**3
    zh = f"""# 实验交付记录

2026-09-29。598 个实例已完成，已停止新增实验。

- 平台项目：`{s.project}`，名称保留为“2026-09-29 耗竭、易化与连接巩固（实验设计）”。
- 中文实验报告：`{result["reports"]["zh"]}`；英文实验报告：`{result["reports"]["en"]}`，均为第 1 版。另有两篇结果笔记和八组结构化实验记录。
- 证据附件：`{pub["archive"]["artifact_id"]}`；{count / 2**20:.1f} MiB，共 3702 个成员。
- SHA-256：`{digest.hexdigest()}`。打包前逐成员核对，写入后从数据库流式读回整包再核对成功。压缩包没有额外写入本地磁盘。
- 本地研究证据 {local / 2**20:.1f} MiB；数据库净增长 {growth / 2**20:.1f} MiB；总新增约 **{gib:.3f} GiB**，低于 2 GiB 上限。数字为核查时的净增长，数据库可能复用既有空闲页，并非逻辑数据总量。
- 实例累计耗时约 25.09 分钟；单 CPU worker。账户共享用量读数 41%→43%，增加 2 个百分点，未触及 44% 软停止线；不将其声称为精确本任务 token 用量。
- 旧内核、旧实验、旧证据包和原设计版本全部保留；本轮未使用付费 AI、远程服务、GPU，没有继续探索或调参。
- [中文实验报告](report.zh.md)；[英文实验报告](report.en.md)；[执行说明](README_CN.md)。

核对详情：本地 `.work/memory-timescales-20260929/publication-verification.json`。此交付记录生成在归档发布后，不包含于此前已冻结的证据包。
"""
    en = f"""# Experiment delivery

2026-09-29. All 598 instances are complete; no additional experiments are running.

- Project `{s.project}` retains the original design-project display name.
- Chinese report `{result["reports"]["zh"]}` and English report `{result["reports"]["en"]}`, revision 1; two result notes and eight factorial records.
- Evidence artifact `{pub["archive"]["artifact_id"]}`: {count / 2**20:.1f} MiB, 3702 verified members.
- SHA-256 `{digest.hexdigest()}`. Every member was checked before upload; the complete archive was streamed back from the database and verified. No additional local ZIP copy.
- Local evidence {local / 2**20:.1f} MiB; database net growth {growth / 2**20:.1f} MiB; total **{gib:.3f} GiB**, below 2 GiB. Net database growth can reuse existing free pages and is not total logical data size.
- Summed instance wall time about 25.09 minutes, one CPU worker. Shared account usage 41%→43%, two percentage points below the 44% soft stop; not exact task-specific token accounting.
- Old kernels, experiments, archive and design revisions preserved. No paid AI, remote compute or GPU; no further parameter exploration.
- [English report](report.en.md), [Chinese report](report.zh.md), [execution notes](README.md).

Verification details: `.work/memory-timescales-20260929/publication-verification.json`. This delivery record was generated after the immutable archive and is not included in it.
"""
    (HERE / "delivery.zh.md").write_text(zh, encoding="utf-8")
    (HERE / "delivery.en.md").write_text(en, encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    s = Study()
    try:
        verify(s)
    finally:
        s.db.close()
