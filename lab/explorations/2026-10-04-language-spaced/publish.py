"""Publish E43 through Lab services without running or replacing consciousnesses."""

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
            ("viewer", WORK / "language-stream.html", "text/html"),
            ("figure", HERE / "findings.png", "image/png"),
        ):
            artifacts[key] = artifact_once(publication, key, path, "E43 " + key, mime)

        def links(match):
            label, url = match.group(1), match.group(2)
            key = {"results.json": "results", "findings.png": "figure"}.get(url)
            if key:
                url = f"/api/v2/projects/{study.project}/artifacts/{artifacts[key]['artifact_id']}"
            elif url.endswith(".md") and not url.startswith(("http", "/", "#")):
                url = "/docs?doc=" + quote((HERE / url).resolve().relative_to(ROOT).as_posix(), safe="")
            return f"[{label}]({url})"

        for language in ("zh", "en"):
            body = re.sub(
                r"\[([^\]]+)\]\(([^)]+)\)", links, (HERE / f"report.{language}.md").read_text(encoding="utf-8")
            )
            publication.document("report:" + language, "report", "E43 间隔复习 / Spaced reviews " + language, body)
            publication.note("findings:" + language, "E43 Results " + language, body)
        publication.document(
            "record:activity",
            "record",
            "E43 无新语言输入活动 / No-new-language activity",
            f"[真实活动与原样译文 / Activity and verbatim output](/api/v2/projects/{study.project}/artifacts/{artifacts['viewer']['artifact_id']})\n\n"
            "物理背景持续，不是完全无刺激。各检查点独立分支，不能拼成连续独白。 / Physical background continues; checkpoint branches are independent, not one continuous monologue.",
        )
        archive = archive_once(publication, "E43 reproducible evidence.zip")
        publication.document(
            "record:evidence",
            "record",
            "E43 完整证据 / Complete evidence",
            f"[Evidence ZIP](/api/v2/projects/{study.project}/artifacts/{archive['artifact_id']})\n\n"
            "含真实遥测、每句复习计划、冻结转换头、完整检查点及测试轨迹。 / Includes physical telemetry, exact schedules, frozen heads, full checkpoints and probe trajectories.",
        )
        target = HERE / "delivery.json"
        if not target.exists():
            new_json(
                target,
                {
                    "project": study.project,
                    "reports": {
                        k: v["id"] for k, v in publication.state.items() if k.startswith(("report:", "record:"))
                    },
                    "archive": archive,
                    "artifacts": artifacts,
                    "raw_path": str(WORK),
                    "completed_cases": read_json(HERE / "results.json")["completed_cases"],
                },
            )
        print("E43 publication complete")
    finally:
        study.db.close()


if __name__ == "__main__":
    main()
