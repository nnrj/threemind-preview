"""Store E26 reports/evidence using Lab services; never execute existing jobs."""

import hashlib
import importlib.metadata
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
        publication = Publication(s)
        publication.guard()
        # Capture external code as well as the framework's frozen Core sources.
        sources = []
        for package in ("threemind_runtime", "threemind_transformer"):
            for source in (ROOT / "src" / package).rglob("*"):
                if source.suffix in (".py", ".json") and "__pycache__" not in source.parts:
                    sources.append(source)
        hashes = {}
        for source in sorted(sources):
            name = source.relative_to(ROOT).as_posix()
            destination = WORK / "frozen-adapter-sources" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                shutil.copy2(source, destination)
            raw = source.read_bytes()
            assert destination.read_bytes() == raw, "adapter source changed during the study"
            hashes[name] = hashlib.sha256(raw).hexdigest()
        manifest = WORK / "external-implementation.json"
        if not manifest.exists():
            new_json(
                manifest,
                {
                    "source_hashes": hashes,
                    "packages": {
                        name: importlib.metadata.version(name)
                        for name in ("torch", "mujoco", "numpy", "safetensors", "transformers", "peft", "psutil")
                    },
                    "random_weights": "reconstruction requires the recorded Torch version as well as seed and architecture",
                },
            )
        figure = HERE / "figures/robot-distance.png"
        figure.parent.mkdir(exist_ok=True)
        shutil.copy2(WORK / "analysis/robot-distance.png", figure)
        picture = publication.image("E26-robot-distance", figure)
        archive = publication.archive("robot-language-evidence.zip")
        url = f"/api/v2/projects/{s.project}/artifacts/{archive['artifact_id']}"
        for lang in ("zh", "en"):
            body = (HERE / f"report.{lang}.md").read_text(encoding="utf-8")
            body = re.sub(r"!\[[^\]]*\]\(figures/robot-distance\.png\)", lambda _: picture, body)
            body = local_links(body) + f"\n\n[完整证据 / Complete evidence]({url})\n"
            title = (
                "E26：外设已通，任务学习尚待解决"
                if lang == "zh"
                else "E26: peripherals work; practical learning remains open"
            )
            publication.document("report:" + lang, "report", title, body)
            publication.note("results:" + lang, title, body)
        publication.document(
            "record:execution",
            "record",
            "E26 执行记录 / Execution record",
            (HERE / "execution-notes.md").read_text(encoding="utf-8") + f"\n\n[Evidence]({url})\n",
        )
        publication.verify()
        with s.db.tx() as tx:
            db_bytes = tx.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
        result = {
            "project_id": s.project,
            "instances": 160,
            "reports": {lang: publication.state["report:" + lang]["id"] for lang in ("zh", "en")},
            "archive": archive,
            "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
            "database_growth_bytes": max(0, db_bytes - s.meta["database_bytes_before"]),
            "verification": "report hashes and streamed archive contents re-read from PostgreSQL and matched",
        }
        destination = WORK / "delivery.json"
        if not destination.exists():
            new_json(destination, result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
