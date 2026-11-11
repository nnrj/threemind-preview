"""Publish E44 evidence with public Lab services; never run other queued jobs."""

import re
from urllib.parse import quote

from experiment import HERE, ROOT, WORK, read_json

from lab.tools.evidence_archive import archive_once, artifact_once
from lab.tools.service_study import new_json
from lab.tools.study_publication import ArchivedStudy, Publication


def main():
    study = ArchivedStudy(WORK)
    study.name = study.settings.name
    publication = Publication(study)
    try:
        artifacts = {}
        for key, path, mime in (
            ("results", HERE / "results.json", "application/json"),
            ("viewer", WORK / "language-development.html", "text/html"),
            ("figure", HERE / "findings.png", "image/png"),
            ("vector", HERE / "findings.svg", "image/svg+xml"),
        ):
            artifacts[key] = artifact_once(publication, key, path, "E44 " + key, mime)

        def links(match):
            label, url = match.group(1), match.group(2)
            key = {"results.json": "results", "findings.png": "figure", "findings.svg": "vector",
                   "../../../.work/language-development-20261004/language-development.html": "viewer"}.get(url)
            if key:
                url = f"/api/v2/projects/{study.project}/artifacts/{artifacts[key]['artifact_id']}"
            elif url.endswith(".md") and not url.startswith(("http", "/", "#")):
                url = "/docs?doc=" + quote((HERE / url).resolve().relative_to(ROOT).as_posix(), safe="")
            return f"[{label}]({url})"

        for language in ("zh", "en"):
            body = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", links,
                          (HERE / f"report.{language}.md").read_text(encoding="utf-8"))
            publication.document("report:" + language, "report", "E44 从零语言与内部活动 / Scratch language " + language, body)
            publication.note("findings:" + language, "E44 Results " + language, body)
            publication.note("execution-final:" + language, "E44 Execution and limits " + language,
                             (HERE / f"delivery.{language}.md").read_text(encoding="utf-8"))
        publication.document("record:continuous", "record", "E44 连续活动与原样译文 / Continuous activity and raw words",
            f"[566秒连续记录 / Continuous histories](/api/v2/projects/{study.project}/artifacts/{artifacts['viewer']['artifact_id']})\n\n"
            "18个连续来源、两版输出器并排；真实物理遥测重放。局部静默对照另列，没有把独立分支拼成内心独白。 / "
            "Eighteen continuous sources, two frozen expression heads, recorded physical telemetry. Local interventions remain separate branches.")
        archive = archive_once(publication, "E44 reproducible evidence.zip")
        publication.document("record:evidence", "record", "E44 完整证据 / Complete evidence",
            f"[Evidence ZIP](/api/v2/projects/{study.project}/artifacts/{archive['artifact_id']})\n\n"
            "包含冻结实现、教学/感官协议、普通与反转经历、完整匿名轨迹、快照、Transformer权重、失败记录与消融结果。 / "
            "Frozen implementation, sensory/teaching protocols, normal/reversed histories, full anonymous trajectories, snapshots, Transformer weights, failures and interventions.")
        target = HERE / "delivery.json"
        if not target.exists():
            new_json(target, {"project": study.project,
                "documents": {key: value["id"] for key, value in publication.state.items() if key.startswith(("report:", "record:"))},
                "archive": archive, "artifacts": artifacts, "raw_path": str(WORK),
                "completed_cases": read_json(HERE / "results.json")["completed_cases"]})
        print("E44 publication complete")
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
