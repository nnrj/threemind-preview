"""Publish E42 through Lab services; never advance a Core or claim other jobs."""

import re
from urllib.parse import quote

from experiment import HERE, ROOT, WORK, protocol, read_json

from lab.tools.evidence_archive import archive_once, artifact_once
from lab.tools.service_study import new_json
from lab.tools.study_publication import ArchivedStudy, Publication
from threemind_lab.database import LOCAL_USER
from threemind_lab.language_archive import import_bundle
from threemind_runtime.codec import ArtifactCodec
from threemind_transformer.language_bundle import pack


def main():
    s = ArchivedStudy(WORK)
    s.name = s.settings.name
    p = Publication(s)
    try:
        analysis = read_json(WORK / "analysis-v1.json")
        evidence = artifact_once(
            p, "analysis", HERE / "results.json", "E42 measured results and diagnostics", "application/json"
        )
        stream = artifact_once(
            p,
            "activity-stream",
            WORK / "spontaneous-stream.json",
            "E42 activity and language windows",
            "application/json",
        )
        viewer = artifact_once(p, "stream-viewer", WORK / "spontaneous-stream.html", "E42 activity viewer", "text/html")
        figure = artifact_once(p, "figure", HERE / "findings.png", "E42 findings", "image/png")
        demo_rows = []
        for seed in analysis["seeds"]:
            if not seed["formal_complete"]:
                continue
            selection = seed["chosen"]
            # These are explicitly new external-observer bindings to exact
            # existing Core snapshots. Never rewrite the source context/file.
            head = (WORK / "computations" / selection["head_key"] / "weights.safetensors").read_bytes()
            for condition in ("ordinary", "reversed"):
                key = f"s{seed['seed']}-{condition}"
                source = WORK / "cases" / key
                image = ArtifactCodec.decode((source / "final.tmind").read_bytes())
                context = read_json(source / "context.json")
                context["protocol"] = protocol(seed["seed"], selection["layout"]).model_dump()
                raw = pack(image, context, {"head": head})
                bundle = WORK / "demos" / (key + ".tmlanguage")
                if not bundle.exists():
                    bundle.parent.mkdir(exist_ok=True)
                    with bundle.open("xb") as destination:
                        destination.write(raw)
                identity = s.identity("demo:" + key)
                title = f"E42 · {condition} · {seed['seed']} · frozen Qwen"
                result = import_bundle(s.db, s.project, LOCAL_USER, identity, title, raw)
                demo_rows.append(
                    {
                        "source_case": key,
                        "run_id": result["run_id"],
                        "state_hash": image.digest,
                        "layout": selection["layout"],
                        "external_binding_changed_only": True,
                    }
                )

        def link(match):
            label, url = match.group(1), match.group(2)
            if url == "results.json":
                url = f"/api/v2/projects/{s.project}/artifacts/{evidence['artifact_id']}"
            elif url == "findings.png":
                url = f"/api/v2/projects/{s.project}/artifacts/{figure['artifact_id']}"
            elif url.endswith(".md") and not url.startswith(("/", "http", "#")):
                url = "/docs?doc=" + quote((HERE / url).resolve().relative_to(ROOT).as_posix(), safe="")
            return f"[{label}]({url})"

        for language in ("zh", "en"):
            body = re.sub(
                r"\[([^\]]+)\]\(([^)]+)\)", link, (HERE / f"report.{language}.md").read_text(encoding="utf-8")
            )
            p.document("report:" + language, "report", "E42 Qwen 语言可行性 / Language feasibility " + language, body)
            p.note("findings:" + language, "E42 Results " + language, body)
        body = "# E42 · 无新输入活动 / No-new-input activity\n\n"
        body += f"[HTML viewer](/api/v2/projects/{s.project}/artifacts/{viewer['artifact_id']}) · [JSON](/api/v2/projects/{s.project}/artifacts/{stream['artifact_id']})\n\n"
        body += "这些文字没有进入Core；均为真实活动经冻结外设转换。静默与错误保留。 / Generated text is not fed back. Silence and errors are retained.\n\n"
        for row in demo_rows:
            body += f"- [{row['source_case']}](/dialogue?run={row['run_id']})：教学终态的新观察副本 / new observation copy of final teaching state\n"
        p.document("record:activity", "record", "E42 内部活动与语言窗口 / Activity and language", body)
        archived = archive_once(p, "E42 reproducible evidence.zip")
        p.document(
            "record:evidence",
            "record",
            "E42 完整证据 / Complete evidence",
            f"[Evidence ZIP](/api/v2/projects/{s.project}/artifacts/{archived['artifact_id']})",
        )
        delivery = {
            "project": s.project,
            "reports": {k: v["id"] for k, v in p.state.items() if k.startswith(("report:", "record:"))},
            "demos": demo_rows,
            "archive": archived,
            "raw_path": str(WORK),
        }
        target = HERE / "delivery.json"
        if not target.exists():
            new_json(target, delivery)
        print("E42 publication complete")
    finally:
        s.db.close()


if __name__ == "__main__":
    main()
