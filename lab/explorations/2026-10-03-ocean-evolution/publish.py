"""Publish E29 only after measured results, verification and reports exist."""

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


def copy_once(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.read_bytes() == source.read_bytes(), "publication source changed"
    else:
        shutil.copy2(source, target)


def main():
    s = study()
    try:
        summary = read_json(WORK / "analysis/summary.json")
        extra_path = WORK / "analysis/followup-summary.json"
        extra = read_json(extra_path) if extra_path.exists() else {}
        verification = read_json(WORK / "formal-verification.json")
        publication = Publication(s)
        for name in (
            "ocean.py",
            "ocean_evolution.py",
            "ocean_evolution_cli.py",
            "ocean_evolution_view.py",
            "ocean_view.py",
            "ocean_input_summary.py",
            "ocean_exchange_summary.py",
            "ocean_interventions.py",
            "ocean_controls.py",
        ):
            copy_once(ROOT / "lab/tools" / name, WORK / "tool-sources/lab/tools" / name)
        for source in (
            ROOT / "tests_v2/test_ocean_evolution.py",
            ROOT / "tests_v2/test_ocean_input_summary.py",
            ROOT / "tests_v2/test_ocean_exchange_summary.py",
            ROOT / "tests_v2/test_ocean_interventions.py",
            HERE / "viewer-smoke.cjs",
        ):
            copy_once(source, WORK / "tool-sources" / source.relative_to(ROOT))
        figures = {}
        for name in ("primary", "ecology"):
            source = HERE / "figures" / (name + ".png")
            figures[name] = publication.image("E29-" + name, source)
            copy_once(source, WORK / "publication-sources/figures" / source.name)
        archive = publication.archive("ocean-evolution-evidence.zip")
        url = f"/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']}"
        for lang in ("zh", "en"):
            body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
            for name, ref in figures.items():
                body = re.sub(r"!\[[^\]]*\]\(figures/" + re.escape(name) + r"\.png\)", lambda _, ref=ref: ref, body)
            body = links(body) + f"\n\n[Complete evidence / 完整证据]({url})\n"
            title = (
                "E29：稀疏海洋中的生存、身体变异与资源交换"
                if lang == "zh"
                else "E29: survival, body variation and resource exchange in a sparse ocean"
            )
            publication.document("report:" + lang, "report", title, body)
            publication.note("results:" + lang, title, body)
        publication.document(
            "record:execution",
            "record",
            "E29 执行与验证记录 / Execution and verification",
            links((HERE / "execution-notes.md").read_text(encoding="utf-8")) + f"\n\n[Evidence]({url})",
        )
        publication.verify()
        with s.db.tx() as tx:
            size = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        answer = {
            "project_id": s.project,
            "reports": {lang: publication.state["report:" + lang]["id"] for lang in ("zh", "en")},
            "record": publication.state["record:execution"]["id"],
            "archive": archive,
            "formal_worlds": len(summary["worlds"]) + len(extra.get("worlds", [])),
            "primary_and_ecological_worlds": len(summary["worlds"]),
            "supplementary_worlds": len(extra.get("worlds", [])),
            "active_copies_and_births": summary["active_copies_and_births"] + extra.get("active_copies_and_births", 0),
            "unexecuted": summary["unexecuted"],
            "incomplete": summary["incomplete"],
            "supplementary_unexecuted": extra.get("unexecuted", []),
            "supplementary_incomplete": extra.get("incomplete", []),
            "followup_decision": read_json(WORK / "followup-delivery-decision.json"),
            "simulation_wall_seconds": summary["wall_seconds"] + extra.get("wall_seconds", 0),
            "formal_verification": verification,
            "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
            "database_growth_bytes": max(0, size - s.meta["database_bytes_before"]),
            "usage_observation": read_json(WORK / "usage.json"),
            "remaining_resources": {
                "ram_bytes": psutil.virtual_memory().available,
                "C_free_bytes": shutil.disk_usage("C:/").free,
                "E_free_bytes": shutil.disk_usage("E:/").free,
            },
            "verified": "ZIP member hashes and PostgreSQL report/archive readback matched",
        }
        if not (WORK / "delivery.json").exists():
            write_json(WORK / "delivery.json", answer)
        print(json.dumps(answer, ensure_ascii=False, indent=2), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
