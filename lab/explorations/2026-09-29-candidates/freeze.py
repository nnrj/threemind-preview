"""Publish calibration selection and a pre-formal age-matching clarification."""

import hashlib

from common import HERE, WORK, Study, new_json, read_json

from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER


def main():
    study = Study()
    try:
        selection = read_json(WORK / "frozen.json")
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob("*.py")}
        text = (HERE / "design.md").read_text(encoding="utf-8")
        text += "\n\n## 校准后的冻结与事先澄清\n\n"
        text += "72 格校准完成。共同训练强度 1.0，输入间隔 1,000,000 微秒；线索强度 0.5。背景记录每块 300 秒，共六个不重叠时间段。\n\n"
        text += "重新配对比原训练多 40 次输入，为避免把额外经过的时间误认为干扰，增加 trained-aged 条件：完成原训练后等待同等 40 秒，背景处理保持一致。这是正式实验开始前的对照补充，不改变模型。\n\n"
        text += "匿名通道重命名不会自动带来统计独立性；逐块原始值和范围优先于显著性检验。独立 Transformer 测试采用 200 步、32 维、2 层、4 头、5 个符号、2 线程、30 秒预算，不使用测试反馈。\n\n"
        text += "校准、正式执行器源码 SHA-256 与环境版本保留在原始证据中。没有修改内核公式。\n"
        note = notebooks.save_note(
            study.db,
            study.project,
            LOCAL_USER,
            study.meta["design_note_id"],
            {
                "operation_id": study.identity("design-v2"),
                "expected_revision": 1,
                "kind": "note",
                "collection_id": study.meta["notebook_id"],
                "title": "实验设计：三内核校准、适应、配对与上下文",
                "body": {"format": "markdown", "text": text},
            },
        )
        new_json(WORK / "formal-freeze.json", {"selection": selection, "source_sha256": hashes, "note": note})
        print("Formal selection and age-matched control frozen before block 0.")
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
