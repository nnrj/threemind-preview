"""Append delivery receipts and a wording clarification; preserve archived reports."""

import json

from experiment import HERE, WORK, study
from publish import local_links

from lab.tools.service_study import new_json
from lab.tools.study_publication import Publication
from threemind_lab import research_documents
from threemind_lab.database import LOCAL_USER


def main():
    delivered = json.loads((WORK / "delivery.json").read_bytes())
    archive = delivered["archive"]
    local_gib = delivered["local_bytes"] / 2**30
    db_gib = delivered["database_growth_bytes"] / 2**30
    total = local_gib + db_gib
    notes = {
        "zh": "\n\n## 2026-10-03 交付校注：图例选择\n\n上文“预先选取编号000”指按编号取000作为可视化示例，**不是事前登记的抽样指标**；它不承担总体统计推断。全体数值来自24个完整样本，未按图像好坏排除候选。原报告第一版及归档原件保留，数据库第二版只追加此校注。[交付与证据编号](delivery.zh.md)。\n",
        "en": "\n\n## 2026-10-03 delivery clarification: illustrative case selection\n\nThe phrase “prespecified number-000 visualization” means that case 000 was chosen by its identifier as an illustration, **not a preregistered sampling endpoint**. It carries no population-level inference; numerical summaries include all 24 cases without image-based exclusions. Report revision 1 and its archive remain; revision 2 only appends this clarification. [Delivery receipt](delivery.en.md).\n",
    }
    texts = {
        "zh": f"""# E27 交付与入库核验

2026-10-03。[结果报告](report.zh.md) · [执行核查](execution-notes.md) · [工具](../../../docs/zh/plans/robot-survival-selection.md)

- 研究项目：`{delivered["project_id"]}`，名称为「E27 自行抓杯、颗粒转移与有限供能生存选择」。可在现有实验笔记、记录与报告页面查看。
- 中文报告：`{delivered["reports"]["zh"]}`；英文报告：`{delivered["reports"]["en"]}`。
- 执行记录：`{delivered["record"]}`。
- 证据包：`{archive["artifact_id"]}`，{archive["bytes"]:,}字节（约{archive["bytes"] / 2**20:.2f}MiB），{archive["verified_members"]}个文件。
- SHA-256：`{archive["sha256"]}`。
- 逐文件校验通过，上传后从PostgreSQL分块读回的总大小与哈希一致；中英文报告内容哈希核验通过。

封存时本地新增约{local_gib:.3f}GiB（含本地归档副本），数据库增长约{db_gib:.3f}GiB，合计约{total:.3f}GiB，未达到8GiB停扩线。账户读数由12%变为14%，共享账户增长也计入；并非逐次归因出的专属消耗。最低末次可用内存约13GiB，C盘9.77GiB、E盘105.03GiB。未清理旧数据。

正式24例，累计88.16模拟分钟、3.57计算墙钟小时。两个完整Core复算另用317.98和312.14墙钟秒；先前300秒核验超时保留，不计为新的学习样本。原核和旧实例未改。18项测试通过，3项隔离数据库测试跳过；实际归档另做了数据库读回核验。

本期完成Python/CLI研究工具和报告可视化；新的颗粒任务群体启动尚未接入完整UI，研究总表T08明确保留。完整源码和图表本地提交，不推送。报告校注与此交付收据在归档完成后追加，原归档及第一版报告不重写。
""",
        "en": f"""# E27 delivery and database verification

2026-10-03. [Report](report.en.md) · [Execution record](execution-notes.md) · [Tools](../../../docs/en/plans/robot-survival-selection.md)

- Project: `{delivered["project_id"]}` — E27 free-cup grasping, granular transfer and finite-energy survival selection, accessible through existing notebook/report pages.
- Chinese report: `{delivered["reports"]["zh"]}`; English report: `{delivered["reports"]["en"]}`.
- Execution record: `{delivered["record"]}`.
- Evidence artifact: `{archive["artifact_id"]}`, {archive["bytes"]:,} bytes ({archive["bytes"] / 2**20:.2f} MiB), {archive["verified_members"]} verified members.
- SHA-256: `{archive["sha256"]}`.
- All archive members verified. PostgreSQL chunk readback matched total bytes and hash; report content hashes also matched.

At sealing, local growth was {local_gib:.3f} GiB including the local archive copy, database growth {db_gib:.3f} GiB, combined {total:.3f} GiB, below the 8 GiB expansion threshold. Account usage moved from 12% to 14%, conservatively including shared-account activity; this is not exclusive per-task attribution. Last measured free RAM was about 13 GiB, C disk 9.77 GiB and E disk 105.03 GiB. No old evidence was deleted.

Twenty-four formal cases accumulated 88.16 simulated minutes and 3.57 summed process-wall hours. Two successful full Core replays separately took 317.98 and 312.14 wall seconds; an earlier 300-second verification timeout remains recorded and is not a new learning sample. Core and historical instances were unchanged. Eighteen tests passed and three isolated database cases were skipped; actual publication had independent database readback verification.

Python/CLI tools and report visualization are delivered; complete granular cohort launch UI remains T08. Changes are committed locally without push. This receipt and the sampling-wording clarification are appended after sealing; the archive and report revision 1 are preserved.
""",
    }
    s = study()
    try:
        pub = Publication(s)
        for lang in ("zh", "en"):
            report = HERE / f"report.{lang}.md"
            text = report.read_text(encoding="utf-8")
            if notes[lang] not in text:
                report.write_text(text + notes[lang], encoding="utf-8")
            receipt = HERE / f"delivery.{lang}.md"
            if not receipt.exists():
                receipt.write_text(texts[lang], encoding="utf-8")
            old = pub.state["report:" + lang]
            if old["revision"] == 1:
                spec = research_documents.get(s.db, s.project, old["id"], revision=1)["spec"]
                spec["blocks"].append(
                    {
                        "id": "sampling-clarification",
                        "type": "commentary",
                        "section": "limitations",
                        "markdown": local_links(notes[lang]),
                    }
                )
                updated = research_documents.save(
                    s.db,
                    s.project,
                    LOCAL_USER,
                    old["id"],
                    {
                        "operation_id": s.identity("sampling-clarification:" + lang),
                        "expected_revision": 1,
                        "spec": spec,
                    },
                )
                pub.remember("report:" + lang, updated)
            pub.note("delivery:" + lang, "E27 交付核验 / Delivery " + lang, local_links(texts[lang] + notes[lang]))
        pub.verify()
        value = {
            "report_revisions": {lang: pub.state["report:" + lang]["revision"] for lang in notes},
            "archive_unchanged": True,
            "report_and_archive_readback": "verified",
            "clarification": "illustrative case 000 is not a preregistered sampling endpoint",
        }
        path = WORK / "delivery-addendum.json"
        if not path.exists():
            new_json(path, value)
        print(json.dumps(value, ensure_ascii=False))
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
