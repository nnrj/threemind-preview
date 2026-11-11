from common import HERE, WORK, Study, new_json

from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER

s = Study()
try:
    row = notebooks.save_note(
        s.db,
        s.project,
        LOCAL_USER,
        s.identity("body-removal-design"),
        {
            "operation_id": s.identity("body-removal-design:write"),
            "expected_revision": 0,
            "kind": "note",
            "collection_id": s.meta["notebook_id"],
            "title": "闭环环境：全部本体感官移除的补充对照",
            "body": {"format": "markdown", "text": (HERE / "body-removal-registration.md").read_text(encoding="utf-8")},
        },
    )
    new_json(WORK / "body-removal-note.json", row)
finally:
    s.db.close()
