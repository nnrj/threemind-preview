"""Score the complete learner's declared choices and actual actuator outputs."""

import argparse
import gzip
import json
import math
from pathlib import Path

CURVES = ("inverse-logarithmic", "weight-fast", "weight-slow", "matched-fast", "matched-slow")
STAGES = ("initial", "new", "reversal", "return")


def load(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes())


def rate(rows, chosen):
    found = [r for r in rows if r["cue"] in chosen]
    assert found
    correct = sum(r["choice"] == r["target"] and r["body"]["position"] == r["choice"] for r in found)
    return dict(correct=correct, n=len(found), accuracy=correct / len(found), passed=correct / len(found) >= 0.75)


def interval(k, n):
    z = 1.959963984540054
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - half, center + half]


def analyze(work):
    assert load(work / "status.json") == dict(state="awaiting-analysis", sequences_completed=40)
    subjects = []
    for case in load(work / "cases.json"):
        root = work / "subjects" / case["key"]
        stages = {}
        goals = {}
        for stage in STAGES:
            scores = {}
            for phase in ("immediate", "delayed"):
                result = load(root / stage / phase / "result.json.gz")
                rows = result["rows"]
                assert all(r["correct"] == (r["choice"] == r["target"]) for r in rows)
                target = (
                    ("P0", "P1", "A0", "A1") if stage == "initial" else ("B0", "B1") if stage == "new" else ("A0", "A1")
                )
                protect = ("P0", "P1", "A0", "A1") if stage in ("initial", "new") else ("P0", "P1", "B0", "B1")
                scores[phase] = dict(
                    total=rate(rows, {r["cue"] for r in rows}), target=rate(rows, target), protected=rate(rows, protect)
                )
            development = []
            for name in ("development", "correction-1/development", "correction-2/development"):
                file = root / stage / name / "result.json.gz"
                if file.exists():
                    d = load(file)
                    development.append(dict(correct=d["correct"], n=d["n"], wrong=d["wrong"]))
            goals[stage] = all(
                scores[p][kind]["passed"] for p in ("immediate", "delayed") for kind in ("target", "protected")
            )
            stages[stage] = dict(scores=scores, development=development)
        states = [load(p) for p in root.rglob("complete.json")]
        last = max(states, key=lambda r: int(r["end_us"]))
        final = load(work / last["state_file"])
        subjects.append(
            dict(
                **case,
                goals=goals,
                stages=stages,
                final_time_us=final["core"]["time_us"],
                learning=final["learning"],
                final_state=last["state_file"],
                complete_boundaries=len(states),
            )
        )
    summary = []
    for curve in CURVES:
        rows = [s for s in subjects if s["curve"] == curve]
        scores = {}
        for stage in STAGES:
            k = sum(s["goals"][stage] for s in rows)
            scores[stage] = dict(passed=k, n=8, target_met=k >= 6, wilson95=interval(k, 8))
        summary.append(dict(curve=curve, scores=scores, all_tasks=all(v["target_met"] for v in scores.values())))
    return dict(
        schema="threemind.r48b-analysis/1",
        independent_origins=8,
        complete_individuals=40,
        summary=summary,
        subjects=subjects,
        exploratory=True,
        scope="Continuous joint development; delayed tests include earlier examination experience",
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, required=True)
    args = p.parse_args()
    r = analyze(args.work)
    with (args.work / "analysis-v1.json").open("x", encoding="utf-8") as f:
        json.dump(r, f, indent=2)
    print(json.dumps(r["summary"]))
