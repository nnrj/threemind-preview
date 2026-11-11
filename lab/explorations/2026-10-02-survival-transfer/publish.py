"""Publish E27 through Lab services, with streamed archive and readback checks."""

import hashlib
import json
import re
import shutil
from urllib.parse import quote

from experiment import HERE, ROOT, WORK, study

from lab.tools.service_study import new_json
from lab.tools.study_publication import Publication


def local_links(body):
    return re.sub(
        r"\[([^\]]+)\]\(([A-Za-z0-9_./-]+\.md)\)",
        lambda m: f"[{m[1]}](/docs?doc={quote((HERE / m[2]).resolve().relative_to(ROOT).as_posix(), safe='')})",
        body,
    )


def main():
    s = study()
    try:
        summary = json.loads((WORK / "analysis/summary.json").read_bytes())
        assert summary["formal_count"] == 24 and summary["partial_or_failed_count"] == 0
        publication = Publication(s)
        source_names = [
            "survival",
            "granular_physics",
            "granular_protocol",
            "granular_session",
            "granular_survival",
            "granular_replay",
        ]
        sources = [ROOT / "lab/tools" / (name + ".py") for name in source_names]
        sources.append(ROOT / "tests_v2/test_survival_tools.py")
        hashes = {}
        for p in sources:
            relative = p.relative_to(ROOT)
            target = WORK / "tool-sources" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(p, target)
            assert target.read_bytes() == p.read_bytes(), "tool changed after publication began"
            hashes[relative.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest = WORK / "tool-sources/manifest.json"
        if not manifest.exists():
            new_json(manifest, hashes)
        figures = {
            name: publication.image("E27-" + name, HERE / "figures" / (name + ".png"))
            for name in ("survival", "free-sequence", "attached-sequence")
        }
        archive = publication.archive("survival-transfer-evidence.zip")
        url = f"/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']}"
        for lang in ("zh", "en"):
            body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
            for name, image in figures.items():
                body = re.sub(
                    r"!\[[^\]]*\]\(figures/" + re.escape(name) + r"\.png\)",
                    lambda _, replacement=image: replacement,
                    body,
                )
            body = local_links(body) + f"\n\n[完整证据 / Complete evidence]({url})\n"
            title = (
                "E27：生存淘汰已接通，尚未学会抓杯倾倒"
                if lang == "zh"
                else "E27: survival selection connected; grasping and pouring not learned"
            )
            publication.document("report:" + lang, "report", title, body)
            publication.note("results:" + lang, title, body)
        publication.document(
            "record:execution",
            "record",
            "E27 执行与核查记录 / Execution and verification",
            local_links((HERE / "execution-notes.md").read_text(encoding="utf-8")) + f"\n\n[Evidence]({url})",
        )
        publication.verify()
        with s.db.tx() as tx:
            db_bytes = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        receipt = {
            "project_id": s.project,
            "formal_instances": summary["formal_count"],
            "reports": {lang: publication.state["report:" + lang]["id"] for lang in ("zh", "en")},
            "record": publication.state["record:execution"]["id"],
            "archive": archive,
            "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
            "database_growth_bytes": max(0, db_bytes - s.meta["database_bytes_before"]),
            "verification": "report hashes and streamed archive bytes re-read from PostgreSQL and matched",
        }
        if not (WORK / "delivery.json").exists():
            new_json(WORK / "delivery.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
