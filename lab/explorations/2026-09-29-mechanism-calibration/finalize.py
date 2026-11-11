"""Append delivery clarification as immutable revisions; never rerun the study."""

import copy
import json
from pathlib import Path
from uuid import UUID, uuid5

from threemind_lab import notebooks, research_documents
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2] / ".work/mechanism-calibration-20260929"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def finalize():
    assert (WORK / "STOP").is_file(), "seal simulations before delivery"
    publication = read(WORK / "publication.json")
    platform = read(WORK / "platform.json")
    project = UUID(platform["project_id"])
    assert str(project) == "d27d28d0-55f1-4783-99fd-e3a503ec1573"
    results = {"project_id": str(project), "simulations_rerun": False, "reports": {}, "notes": {}}
    database = Database(Settings.from_env().database_url)
    try:
        for lang in ("zh", "en"):
            appendix = (HERE / f"release.{lang}.md").read_text(encoding="utf-8").strip()
            if appendix.startswith("# "):
                appendix = "#" + appendix  # Standalone menu title becomes a report subsection.
            original = publication[f"report:{lang}"]
            document_id = UUID(original["id"])
            before = research_documents.get(database, project, document_id, revision=original["revision"])
            assert before["content_hash"] == original["content_hash"]
            spec = copy.deepcopy(before["spec"])
            spec["blocks"].append(
                {"id": "delivery-20260930", "type": "commentary", "markdown": appendix, "section": "discussion"}
            )
            saved = research_documents.save(
                database,
                project,
                LOCAL_USER,
                document_id,
                {
                    "operation_id": uuid5(project, "release-20260930-report:" + lang),
                    "expected_revision": original["revision"],
                    "spec": spec,
                    "review": before["review"],
                },
            )
            actual = research_documents.get(database, project, document_id, revision=saved["revision"])
            assert actual["spec"]["blocks"][:-1] == before["spec"]["blocks"]
            assert actual["spec"]["blocks"][-1]["markdown"] == appendix
            assert actual["content_hash"] == saved["content_hash"]
            assert (
                research_documents.get(database, project, document_id, original["revision"])["content_hash"]
                == original["content_hash"]
            )
            results["reports"][lang] = {
                "id": original["id"],
                "revision": saved["revision"],
                "content_hash": saved["content_hash"],
                "original_revision_preserved": True,
            }
            # Keep the notebook results in step with reports, retaining revision 1.
            prior_note = publication[f"results:{lang}"]
            note_id = UUID(prior_note["id"])
            note = notebooks.note(database, project, LOCAL_USER, note_id, revision=prior_note["revision"])
            text = note["body"]["text"].rstrip() + "\n\n" + appendix + "\n"
            saved_note = notebooks.save_note(
                database,
                project,
                LOCAL_USER,
                note_id,
                {
                    "operation_id": uuid5(project, "release-20260930-results:" + lang),
                    "expected_revision": prior_note["revision"],
                    "kind": "note",
                    "collection_id": platform["notebook_id"],
                    "title": note["version_metadata"]["title"],
                    "body": {"format": "markdown", "text": text},
                },
            )
            assert (
                notebooks.note(database, project, LOCAL_USER, note_id, saved_note["revision"])["body"]["text"] == text
            )
            assert (
                notebooks.note(database, project, LOCAL_USER, note_id, prior_note["revision"])["content_hash"]
                == prior_note["content_hash"]
            )
            results["notes"][lang] = {"id": str(note_id), "revision": saved_note["revision"]}
            # The generator and evidence archive still describe revision 1. This
            # separate script adds the same dated appendix to the local report.
            report_path = HERE / f"report.{lang}.md"
            body = report_path.read_text(encoding="utf-8")
            if appendix.splitlines()[0] not in body:
                report_path.write_text(body.rstrip() + "\n\n" + appendix + "\n", encoding="utf-8")
            else:
                assert body.rstrip().endswith(appendix)
        result_path = WORK / "release-verification.json"
        if result_path.exists():
            assert read(result_path) == results
        else:
            with result_path.open("x", encoding="utf-8") as output:
                json.dump(results, output, ensure_ascii=False, indent=2)
        print(json.dumps(results, ensure_ascii=False))
    finally:
        database.close()


if __name__ == "__main__":
    finalize()
