"""Publish E28 with immutable evidence and readback through existing Lab services."""

import json
import re
import shutil
from urllib.parse import quote

import psutil
from experiment import HERE, ROOT, WORK, study

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.study_publication import Publication


def links(body):
    return re.sub(
        r"\[([^\]]+)\]\(([A-Za-z0-9_./-]+\.md)\)",
        lambda m: f"[{m[1]}](/docs?doc={quote((HERE / m[2]).resolve().relative_to(ROOT).as_posix(), safe='')})",
        body,
    )


def main():
    s = study()
    try:
        summary = read_json(WORK / "analysis/summary.json")
        publication = Publication(s)
        tool_files = [
            ROOT / "lab/tools" / n for n in ("ocean.py", "ocean_cli.py", "ocean_controls.py", "ocean_view.py")
        ]
        tool_files += [ROOT / "tests_v2/test_ocean_tools.py", HERE / "viewer-smoke.cjs"]
        for source in tool_files:
            target = WORK / "tool-sources" / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                assert target.read_bytes() == source.read_bytes(), "tool changed after publication started"
            else:
                shutil.copy2(source, target)
        figures = {
            name: publication.image("E28-" + name, HERE / "figures" / (name + ".png"))
            for name in ("population", "selection", "comparison")
        }
        for name in figures:
            source = HERE / "figures" / (name + ".png")
            target = WORK / "publication-sources/figures" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                assert target.read_bytes() == source.read_bytes(), "published figure changed"
            else:
                shutil.copy2(source, target)
        archive = publication.archive("primitive-ocean-evidence.zip")
        url = f"/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']}"
        for lang in ("zh", "en"):
            body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
            for name, ref in figures.items():
                body = re.sub(r"!\[[^\]]*\]\(figures/" + re.escape(name) + r"\.png\)", lambda _, ref=ref: ref, body)
            body = links(body) + f"\n\n[Complete evidence / 完整证据]({url})\n"
            title = (
                "E28：营养海洋中的摄食、生存与繁殖"
                if lang == "zh"
                else "E28: feeding, survival and reproduction in a nutrient ocean"
            )
            publication.document("report:" + lang, "report", title, body)
            publication.note("results:" + lang, title, body)
        publication.document(
            "record:execution",
            "record",
            "E28 执行、接续与预算记录 / Execution and continuation",
            links((HERE / "execution-notes.md").read_text(encoding="utf-8")) + f"\n\n[Evidence]({url})",
        )
        publication.verify()
        with s.db.tx() as tx:
            size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        delivery = {
            "project_id": s.project,
            "reports": {l: publication.state["report:" + l]["id"] for l in ("zh", "en")},
            "record": publication.state["record:execution"]["id"],
            "archive": archive,
            "formal_worlds": len(summary["worlds"]),
            "formal_individuals": summary["individuals"],
            "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
            "database_growth_bytes": max(0, size - s.meta["database_bytes_before"]),
            "usage_observation": read_json(WORK / "usage.json"),
            "remaining_resources": {
                "ram_bytes": psutil.virtual_memory().available,
                "C_free_bytes": shutil.disk_usage("C:/").free,
                "E_free_bytes": shutil.disk_usage("E:/").free,
            },
            "formal_verification": read_json(WORK / "formal-verification.json"),
            "simulation_wall_seconds": summary["wall_seconds"],
            "verified": "archive members and PostgreSQL report/archive readback matched",
        }
        if not (WORK / "delivery.json").exists():
            write_json(WORK / "delivery.json", delivery)
        print(json.dumps(delivery, ensure_ascii=False, indent=2), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
