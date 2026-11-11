"""Publish derived evidence only; no Core execution or old-data mutation."""

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from lab.tools.service_study import Study, StudyConfig
from lab.tools.study_publication import Publication

HERE = Path(__file__).resolve().parent
WORK = ROOT / ".work/response-readout-20261002"


def local_links(body):
    return re.sub(
        r"\[([^\]]+)\]\(([A-Za-z0-9_./-]+\.md)\)",
        lambda m: f"[{m[1]}](/docs?doc={quote((HERE / m[2]).resolve().relative_to(ROOT).as_posix(), safe='')})",
        body,
    )


class ReadoutStudy(Study):
    def note(self, key, title, text):
        return super().note(key, title, local_links(text))


def main():
    settings = StudyConfig(
        "brief-response-readout/1",
        "E25 短暂响应读出校准",
        HERE,
        WORK,
        95,
        instance_limit=1,
        wall_seconds=600,
        storage_soft=400 * 1024**2,
        storage_hard=512 * 1024**2,
        usage_soft_delta=1,
        usage_hard_delta=2,
    )
    # Study's positive instance budget is a framework requirement; no Case or
    # engine is created, and this study explicitly records zero simulations.
    study = ReadoutStudy(settings, prepare=not (WORK / "platform.json").exists())
    # Resume a partially completed registration safely; note operation IDs are
    # idempotent, and existing immutable sources must match before any reuse.
    for lang in ("zh", "en"):
        source = HERE / f"design.{lang}.md"
        study.note(f"design:{lang}", f"执行登记 / Study registration {lang}", source.read_text(encoding="utf-8"))
        target = WORK / f"design-frozen.{lang}.md"
        if not target.exists():
            shutil.copy2(source, target)
        assert target.read_bytes() == source.read_bytes()
    for name, sha in study.implementation["source_files"].items():
        source, target = ROOT / name, WORK / "frozen-sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == sha
    publication = Publication(study)
    publication.guard()
    sources = json.loads((WORK / "verified/source-checksums.json").read_bytes())
    for relative, expected in sources.items():
        source = ROOT / relative
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
        target = WORK / "selected-history" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected
    for source in (HERE / "figures").iterdir():
        target = WORK / "figures" / source.name
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
    picture = publication.image("brief-response", HERE / "figures/brief-response.png")
    archive = publication.archive("brief-response-evidence.zip", historical_data_included=True)
    url = f"/api/v2/projects/{study.project}/artifacts/{archive['artifact_id']}"
    for lang in ("zh", "en"):
        body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
        body = re.sub(r"!\[[^\]]*\]\(figures/brief-response\.png\)", lambda _: picture, body)
        body = local_links(body)
        body += f"\n\n[完整校准证据 / Complete calibration evidence]({url})\n"
        title = "E25：响应短暂，不等于没有响应" if lang == "zh" else "E25: brief responses remain responses"
        publication.document("report:" + lang, "report", title, body)
        publication.note("results:" + lang, title, body)
    publication.note(
        "execution-notes",
        "E25 执行更正 / Execution correction",
        (HERE / "execution-notes.md").read_text(encoding="utf-8"),
    )
    publication.verify()
    with study.db.tx() as tx:
        db_bytes = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    result = {
        "project_id": study.project,
        "simulations": 0,
        "reports": {lang: publication.state["report:" + lang]["id"] for lang in ("zh", "en")},
        "archive": archive,
        "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
        "database_growth_bytes": max(0, db_bytes - study.meta["database_bytes_before"]),
        "verification": "report hashes and database archive bytes matched",
    }
    (WORK / "delivery.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    study.db.close()
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
