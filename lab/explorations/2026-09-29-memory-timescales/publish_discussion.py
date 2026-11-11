"""Append authored discussion and save a proposed plan; execute no simulations."""

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
WORK = ROOT / ".work/memory-timescales-20260929"
NAMESPACE = UUID("f233a17c-56e8-4dbf-8716-152a75433e1e")


def identity(key):
    return str(uuid5(NAMESPACE, key))


def app_markdown(text):
    return re.sub(r"\[([^\]]+)\]\(([^):]+\.md)\)", r"\1", text)


def main():
    platform = json.loads((WORK / "platform.json").read_bytes())
    published = json.loads((WORK / "publication.json").read_bytes())
    project = platform["project_id"]
    evidence = {"status": "discussion-and-proposed-plan-only", "project": project, "reports": {}, "notes": {}}
    db = Database(Settings.from_env().database_url)
    try:
        db.require_current_schema()
        with db.tx(project) as tx:
            before = tx.execute("SELECT count(*) AS n FROM runs").fetchone()["n"]
            archive_before = tx.execute(
                "SELECT sha256,bytes FROM artifacts WHERE id=%s", (published["archive"]["artifact_id"],)
            ).fetchone()
        if archive_before["sha256"] != published["archive"]["sha256"]:
            raise ValueError("archive metadata changed; review before publication")
        for lang in ("zh", "en"):
            raw = (HERE / f"discussion.{lang}.md").read_text(encoding="utf-8")
            full = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
            if not full.endswith(raw) or full.count(raw.splitlines()[0]) != 1:
                raise ValueError("discussion must already appear once at the end of the local report")
            appendix = "\n\n---\n\n" + app_markdown(raw)
            report_id = published["report:" + lang]["id"]
            original = research_documents.get(db, project, report_id, revision=1)
            current = research_documents.get(db, project, report_id)
            if original["content_hash"] != published["report:" + lang]["content_hash"]:
                raise ValueError("original report hash differs from publication record")
            spec = copy.deepcopy(original["spec"])
            narrative = next(block for block in spec["blocks"] if block["id"] == "narrative")
            narrative["markdown"] += appendix
            if current["revision"] == 1:
                saved = research_documents.save(
                    db,
                    project,
                    LOCAL_USER,
                    report_id,
                    {
                        "operation_id": identity("append:" + lang),
                        "expected_revision": 1,
                        "spec": spec,
                        "review": current["review"],
                    },
                )
            elif current["revision"] == 2 and current["spec"] == spec:
                saved = {"id": report_id, "revision": 2, "content_hash": current["content_hash"], "replayed": True}
            else:
                raise ValueError("report edited independently; preserve changes and review")
            actual = research_documents.get(db, project, report_id)
            assert actual["spec"] == spec
            assert (
                research_documents.get(db, project, report_id, revision=1)["content_hash"] == original["content_hash"]
            )
            evidence["reports"][lang] = saved | {"original_hash": original["content_hash"]}

            for kind in ("discussion", "plan"):
                path = (
                    HERE / f"discussion.{lang}.md"
                    if kind == "discussion"
                    else ROOT / f"docs/{lang}/plans/autonomous-activity.md"
                )
                text = path.read_text(encoding="utf-8")
                title = (
                    (
                        "实验讨论：能量、持续活动与毫秒级输入"
                        if kind == "discussion"
                        else "待讨论方案：输入间隔校准与自主活动"
                    )
                    if lang == "zh"
                    else (
                        "Discussion: energy, persistent activity and millisecond input"
                        if kind == "discussion"
                        else "Proposed study: input-spacing calibration and autonomous activity"
                    )
                )
                note_id = identity(kind + ":" + lang)
                body = {"format": "markdown", "text": app_markdown(text)}
                saved = notebooks.save_note(
                    db,
                    project,
                    LOCAL_USER,
                    note_id,
                    {
                        "operation_id": identity("write:" + kind + ":" + lang),
                        "expected_revision": 0,
                        "kind": "note",
                        "collection_id": platform["notebook_id"],
                        "title": title,
                        "body": body,
                    },
                )
                assert notebooks.note(db, project, LOCAL_USER, note_id)["body"] == body
                evidence["notes"][kind + ":" + lang] = saved | {
                    "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
                }
        with db.tx(project) as tx:
            after = tx.execute("SELECT count(*) AS n FROM runs").fetchone()["n"]
            archive_after = tx.execute(
                "SELECT sha256,bytes FROM artifacts WHERE id=%s", (published["archive"]["artifact_id"],)
            ).fetchone()
        assert before == after and archive_before == archive_after
        evidence.update(
            runs_before=before,
            runs_after=after,
            archive_metadata_unchanged=True,
            archive_bytes_rehashed=False,
            archive_sha256=archive_after["sha256"],
        )
        output = WORK / "discussion-publication.json"
        staging = output.with_suffix(".tmp")
        staging.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        staging.replace(output)
        print(json.dumps(evidence, ensure_ascii=False, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    if not parser.parse_args().apply:
        parser.error("--apply required to publish documents; no experiment is executed")
    main()
