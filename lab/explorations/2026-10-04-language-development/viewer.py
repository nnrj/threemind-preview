"""Build an offline responsive viewer of actual continuous E44 source histories."""

import gzip
import json

from experiment import HERE, WORK, read_json


def main():
    sources = []
    for meta in sorted((WORK / "continuous-text").glob("*.json")):
        value = read_json(meta)
        if value["variant"] != "base":
            continue
        with gzip.open(meta.with_suffix(".jsonl.gz"), "rt", encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream]
        with gzip.open(meta.with_name(meta.stem + "-weak.jsonl.gz"), "rt", encoding="utf-8") as stream:
            weak = [json.loads(line) for line in stream]
        compact = []
        for left, right in zip(rows, weak, strict=True):
            if left["start_us"] != right["start_us"] or left["activity"] != right["activity"]:
                raise ValueError("expression heads must use the identical recorded trajectory")
            compact.append({"s": int(left["start_us"]) / 1e6, "e": int(left["end_us"]) / 1e6,
                            "b": left["output"]["text"], "w": right["output"]["text"],
                            "input": [a["text"] for a in left["acquisition"]],
                            "sent": left["transport"]["sent"], "rise": left["changes"]["positive_change"],
                            "reentry": left["changes"]["reentries"], "life": left["life"],
                            "curve": [[(t / 1e6), a] for t, a in left["activity"]]})
        sources.append({k: value[k] for k in ("source", "route", "seed", "condition")} | {"rows": compact})
    results = read_json(HERE / "results.json")
    payload = json.dumps({"sources": sources, "bridge": results["bridge_ablation"],
                          "recall": results["visual_recall_summary"]}, ensure_ascii=False, separators=(",", ":"))
    template = (HERE / "viewer-template.html").read_text(encoding="utf-8")
    # Safe even if a future decoder emits HTML/script-like strings.
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    target = WORK / "language-development.html"
    publication = WORK / "publication.json"
    if publication.exists() and read_json(publication).get("viewer", {}).get("artifact_id"):
        raise RuntimeError("published viewer is immutable; create a new artifact revision")
    with target.open("w", encoding="utf-8") as out:
        out.write(template.replace("__DATA__", payload))
    print(json.dumps({"viewer": str(target), "sources": len(sources), "bytes": target.stat().st_size}))


if __name__ == "__main__":
    main()
