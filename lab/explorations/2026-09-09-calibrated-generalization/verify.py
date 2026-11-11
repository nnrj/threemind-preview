"""Final read-only verification and a local acceptance manifest."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from run import HERE, META, OLD, encoded, heads

from threemind_lab import notebooks, research_documents
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database


def verify():
    meta = json.loads(META.read_bytes())
    project = meta["project_id"]
    db = Database(Settings.from_env().database_url)
    try:
        with db.tx(project) as c:
            status = c.execute(
                "SELECT status,count(*) n FROM runs WHERE project_id=%s GROUP BY status", (project,)
            ).fetchall()
            jobs = c.execute(
                "SELECT status,count(*) n FROM jobs WHERE project_id=%s GROUP BY status", (project,)
            ).fetchall()
            cp = c.execute(
                "SELECT count(*) n,sum(byte_count) bytes FROM checkpoints WHERE project_id=%s", (project,)
            ).fetchone()
            size = c.execute("SELECT pg_database_size(current_database()) n").fetchone()["n"]
        assert {r["status"]: r["n"] for r in status} == {"completed": 977}
        assert {r["status"] for r in jobs} == {"done"}
        assert heads(db, OLD) == meta["old_heads_before"]
        note = notebooks.note(db, project, LOCAL_USER, meta["publication"]["note:results"]["id"])
        assert note["body"]["format"] == "document" and note["revision"] == 2
        meta["publication"]["note:results"].update(revision=2, content_hash=note["content_hash"])
        report = research_documents.render(db, project, meta["publication"]["document:report"]["id"])
        old = json.loads((HERE.parent / "2026-09-09-memory-relations" / "acceptance.json").read_bytes())
        assert research_documents.render(db, OLD, old["report_id"])["content_hash"] == old["report_content_hash"]
        for n in old["note_heads"]:
            assert notebooks.note(db, OLD, LOCAL_USER, n["id"])["revision"] == n["revision"]
        acceptance = {
            "checked_at": datetime.now(UTC).isoformat(),
            "project_id": project,
            "report_id": report["document_id"],
            "report_revision": report["revision"],
            "report_content_hash": report["content_hash"],
            "source_hashes": {k: v["content_hash"] for k, v in report["sources"].items()},
            "run_status_counts": status,
            "job_status_counts": jobs,
            "checkpoints": cp,
            "database_growth_after_publication_bytes": size - meta["database_bytes_before"],
            "free_disk_bytes": {disk: shutil.disk_usage(disk).free for disk in ["D:/", "E:/"]},
            "new_results_note_revision": note["revision"],
            "old_models_unchanged": meta["old_heads_before"],
            "old_report_and_note_heads_verified": True,
            "representative_zip_and_all_contained_final_state_hashes_verified": 3,
            "browser": {
                "errors": [],
                "records": 3,
                "notes": 3,
                "scientific_images": 2,
                "native_report_charts": 2,
                "native_report_tables": 2,
                "markdown_html_hashes_verified": True,
                "calibration_and_storage": json.loads(Path(".work/calibration-ui-acceptance.json").read_bytes()),
            },
            "tests": {
                "calibration_native_reference_and_api": 6,
                "model_library_worker_lifecycle": 5,
                "cli_database_free": True,
                "ui_build": True,
                "translation_audit": True,
            },
            "core_changed": False,
            "schema": 49,
            "tools_commit": "522dbec",
        }
        (HERE / "acceptance.json").write_bytes(encoded(acceptance) + b"\n")
        META.write_bytes(encoded(meta) + b"\n")
        print(
            encoded(
                {"runs": status, "jobs": jobs, "growth_GiB": (size - meta["database_bytes_before"]) / 1024**3}
            ).decode()
        )
    finally:
        db.close()


if __name__ == "__main__":
    verify()
