"""Append a delivery note after publication without revising scientific results."""

from common import HERE, WORK, Study, read_json

from threemind_lab import notebooks
from threemind_lab.database import LOCAL_USER


def main():
    study = Study()
    try:
        closure = read_json(WORK / "post-publication-closure.json")
        published = read_json(WORK / "publication.json")
        assert all(published[f"export:{lang}:{fmt}"]["done"] for lang in ("zh", "en") for fmt in ("markdown", "html"))
        assert not closure["changed_previous_metadata"]
        for lang in ("zh", "en"):
            body = (HERE / f"delivery.{lang}.md").read_text(encoding="utf-8")
            title = body.splitlines()[0].lstrip("# ")
            key = "delivery-note:" + lang
            result = notebooks.save_note(
                study.db,
                study.project,
                LOCAL_USER,
                study.identity(key),
                {
                    "operation_id": study.identity(key + ":write"),
                    "expected_revision": 0,
                    "kind": "note",
                    "collection_id": study.meta["notebook_id"],
                    "title": title,
                    "body": {"format": "markdown", "text": body},
                },
            )
            print(lang, result["id"])
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
