from common import HERE, WORK, Study, new_json

from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER

s = Study()
try:
    row = notebooks.save_note(
        s.db,
        s.project,
        LOCAL_USER,
        s.identity("analysis-details"),
        {
            "operation_id": s.identity("analysis-details:write"),
            "expected_revision": 0,
            "kind": "note",
            "collection_id": s.meta["notebook_id"],
            "title": "顺序参照与分析规则：执行前补充登记",
            "body": {"format": "markdown", "text": (HERE / "analysis-registration.md").read_text(encoding="utf-8")},
        },
    )
    new_json(WORK / "analysis-details-note.json", row)
finally:
    s.db.close()
