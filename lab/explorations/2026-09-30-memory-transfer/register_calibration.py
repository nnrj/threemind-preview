"""Freeze the measured common dose in the study notebook before main comparisons."""

import json

from common import WORK, Study, new_json, read_json

from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER


def main():
    study = Study()
    try:
        result = read_json(WORK / "calibration.json")
        selected = result["selected"]
        text = (
            f"# 强度校准已锁定 / Dose calibration frozen\n\n16 个独立校准实例，正式物理输入统一使用强度 **{selected['intensity']}**。"
            "选择只参考共同关节响应、存活和饱和，没有计算教学答案或本体感官优势。提示强度仍为 0.45，维持输入为 0.2。"
            "\n\nSixteen calibration cases; selection uses shared-joint activity and saturation, never task accuracy or sensory advantage."
            "\n\n```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```\n"
        )
        row = notebooks.save_note(
            study.db,
            study.project,
            LOCAL_USER,
            study.identity("calibration-note"),
            {
                "operation_id": study.identity("calibration-note:write"),
                "expected_revision": 0,
                "kind": "note",
                "collection_id": study.meta["notebook_id"],
                "title": "正式实验前：强度校准锁定 / Calibration lock",
                "body": {"format": "markdown", "text": text},
            },
        )
        new_json(WORK / "calibration-note.json", row)
        print(json.dumps({"project": study.project, "note": str(row["id"]), "intensity": selected["intensity"]}))
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
