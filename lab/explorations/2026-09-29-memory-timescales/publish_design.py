"""Append discussion to versioned reports and save a new bilingual design.

This command publishes authored documents only. It does not execute experiments,
edit model state, change kernel defaults, or replace the previous evidence ZIP.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from uuid import UUID, uuid5

from threemind_lab import notebooks, research_documents
from threemind_lab.config import ROOT, Settings
from threemind_lab.database import LOCAL_USER, Database

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "2026-09-29-continuous-mechanisms"
WORK = ROOT / ".work/memory-timescales-20260929"
META = WORK / "planning-publication.json"
NAMESPACE = UUID("51f1fd7b-9324-493a-89ae-8b34d4c5428f")
OLD_PROJECT = "e769cd2d-c636-41b0-a266-6af1cca4b805"
REPORTS = {
    "zh": ("8ee40b06-2440-56d2-8fc2-1025146b093b", "## 讨论补记：短时资源、易化、巩固与发现的意义（2026-09-29）"),
    "en": ("c73c7fd5-5fe2-5a36-b889-6e3265572a9a", "## Discussion addendum: resources, facilitation, consolidation and discovery (2026-09-29)"),
}


def identity(key):
    return str(uuid5(NAMESPACE, key))


def app_markdown(text):
    # File sibling links belong in Documents, not the platform rich-text editor.
    # External primary references remain clickable and unchanged.
    return re.sub(r"\[([^\]]+)\]\(([^):]+\.md)\)", r"\1", text)


def persist(meta):
    WORK.mkdir(parents=True, exist_ok=True)
    temporary = META.with_suffix(".tmp")
    temporary.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(META)


def publish():
    db = Database(Settings.from_env().database_url)
    meta = json.loads(META.read_bytes()) if META.exists() else {"status": "design-only", "reports": {}, "notes": {}}
    try:
        db.require_current_schema()
        for lang, (report_id, marker) in REPORTS.items():
            raw = (OLD / f"report.{lang}.md").read_text(encoding="utf-8")
            if raw.count(marker) != 1:
                raise ValueError("expected one appended discussion section")
            appendix = "\n\n---\n\n" + app_markdown(raw[raw.index(marker):])
            original = research_documents.get(db, OLD_PROJECT, report_id, revision=1)
            current = research_documents.get(db, OLD_PROJECT, report_id)
            spec = copy.deepcopy(original["spec"])
            narrative = next(b for b in spec["blocks"] if b["id"] == "narrative")
            original_text = narrative["markdown"]
            narrative["markdown"] += appendix
            if current["revision"] == 1:
                saved = research_documents.save(db, OLD_PROJECT, LOCAL_USER, report_id, {
                    "operation_id": identity("append-discussion:" + lang), "expected_revision": 1,
                    "spec": spec, "review": current["review"],
                })
            elif current["revision"] == 2 and current["spec"] == spec:
                saved = {"id": report_id, "revision": 2, "content_hash": current["content_hash"], "replayed": True}
            else:
                raise ValueError("report changed independently; preserve and review before appending")
            check = research_documents.get(db, OLD_PROJECT, report_id)
            assert check["spec"] == spec
            assert narrative["markdown"].startswith(original_text)
            assert research_documents.get(db, OLD_PROJECT, report_id, revision=1)["content_hash"] == original["content_hash"]
            meta["reports"][lang] = dict(saved, original_revision=1, original_hash=original["content_hash"])
            persist(meta)

        if "project_id" not in meta:
            title = "2026-09-29 耗竭、易化与连接巩固（实验设计）"
            # Recover a completed project-create after interruption, not a duplicate.
            found = [p for p in db.projects({"id": LOCAL_USER}) if p["name"] == title]
            if len(found) > 1:
                raise ValueError("multiple matching design projects; select explicitly")
            project = found[0] if found else db.create_project({"id": LOCAL_USER}, title)
            meta["project_id"] = str(project["id"])
            persist(meta)
        project_id = meta["project_id"]
        collection = notebooks.ensure_default(db, project_id, LOCAL_USER)
        meta["notebook_id"] = str(collection["id"])
        for lang in ("zh", "en"):
            path = HERE / f"design.{lang}.md"
            body = app_markdown(path.read_text(encoding="utf-8"))
            note_id = identity("design-note:" + lang)
            saved = notebooks.save_note(db, project_id, LOCAL_USER, note_id, {
                "operation_id": identity("design-note-write:" + lang), "expected_revision": 0,
                "kind": "note", "collection_id": str(collection["id"]),
                "title": "实验设计：耗竭、易化与巩固的八组合及时间尺度" if lang == "zh"
                else "Study design: depletion, facilitation and consolidation across timescales",
                "body": {"format": "markdown", "text": body},
            })
            actual = notebooks.note(db, project_id, LOCAL_USER, note_id)
            assert actual["body"] == {"format": "markdown", "text": body}
            meta["notes"][lang] = dict(saved, id=note_id, source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            persist(meta)
        with db.tx(project_id) as tx:
            meta["run_count"] = tx.execute("SELECT count(*) AS n FROM runs").fetchone()["n"]
        assert meta["run_count"] == 0, "design publication must not create simulated results"
        persist(meta)
        print(json.dumps({"project": project_id, "reports": meta["reports"], "notes": meta["notes"],
                          "status": meta["status"], "runs": meta["run_count"]}, default=str, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="publish documents through Lab services")
    args = parser.parse_args()
    if not args.apply:
        parser.error("use --apply to publish documents; no experiments are run")
    publish()
