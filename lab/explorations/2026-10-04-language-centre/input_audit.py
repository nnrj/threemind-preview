"""Descriptive input geometry and secondary raw-state diagnostics; no fitting."""

import json
from collections import Counter

import numpy as np
from analyse import internal_changes, predictions
from experiment import NAMES, SEEDS, WORDS, WORK, read_json

from lab.tools.language_observation import nearest_word
from lab.tools.service_study import new_json


def cosine(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / max(1e-12, np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    source = WORK / "computations" / "encoded-material-approved-retry"
    request, result = read_json(source / "request.json"), read_json(source / "result.json")
    vectors = dict(zip(request["payload"]["texts"], result["vectors"]))
    audit = {
        "schema": "threemind.e42-input-audit/1",
        "scope": "descriptive secondary analysis; not a new success criterion",
        "embedding_prior": {},
        "sentence_overlap": [],
        "raw_diagnostic": {},
    }
    for name in NAMES:
        for cue in (name, name + "是"):
            audit["embedding_prior"][cue] = sorted(
                [(w, cosine(vectors[cue], vectors[w])) for w in WORDS], key=lambda r: -r[1]
            )
        for i in range(len(WORDS)):
            for j in range(i + 1, len(WORDS)):
                left, right = name + "是" + WORDS[i] + "。", name + "是" + WORDS[j] + "。"
                a, b = vectors[left], vectors[right]
                audit["sentence_overlap"].append(
                    {
                        "left": left,
                        "right": right,
                        "cosine": cosine(a, b),
                        "same_signed_channels": sum((x < 0) == (y < 0) for x, y in zip(a, b)),
                        "dimensions": len(a),
                    }
                )
    for seed in SEEDS:
        rows = predictions(seed, "formal")
        if not rows:
            continue
        training = [read_json(p) for p in (WORK / "cases").glob(f"s{seed}-cal-*/result.json")]
        exemplars = [
            (c["label"], w["raw"])
            for c in training
            if c["split"] == "train"
            for w in c["windows"]
            if w["summary"]["has_activity"]
        ]
        conditions = {}
        for condition in ("ordinary", "reversed", "blank", "frozen"):
            own = [r for r in rows if r["key"].startswith(f"s{seed}-{condition}-probe-") and r["window"] == 1]
            answers = [
                {
                    "probe": r["probe"],
                    "target": r["label"],
                    "text": r["decoded"].get("text"),
                    "raw_scores": nearest_word(r["raw"], exemplars),
                }
                for r in own
            ]
            conditions[condition] = {
                "answers": answers,
                "raw_correct": sum(bool(a["raw_scores"]) and a["raw_scores"][0][0] == a["target"] for a in answers),
                "text_correct": sum(r["prediction"] == r["label"] for r in own),
                "total": len(own),
                "text_distribution": dict(Counter(r["decoded"].get("text") or "<silence>" for r in own)),
                "no_input_changes": internal_changes(f"s{seed}-{condition}-spontaneous"),
            }
        audit["raw_diagnostic"][str(seed)] = conditions
    target = WORK / ("input-audit-" + "-".join(audit["raw_diagnostic"]) + ".json")
    new_json(target, audit)
    print(
        json.dumps(
            {
                "path": str(target),
                "sentence_cosine_range": [
                    min(r["cosine"] for r in audit["sentence_overlap"]),
                    max(r["cosine"] for r in audit["sentence_overlap"]),
                ],
                "same_channels_range": [
                    min(r["same_signed_channels"] for r in audit["sentence_overlap"]),
                    max(r["same_signed_channels"] for r in audit["sentence_overlap"]),
                ],
                "scores": {
                    s: {c: {k: v for k, v in row.items() if k != "answers"} for c, row in conditions.items()}
                    for s, conditions in audit["raw_diagnostic"].items()
                },
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
