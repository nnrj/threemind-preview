"""Read-only R47a analysis of frozen complete evidence."""

import argparse
import gzip
import json
import math
from pathlib import Path

from assay import COURSES, CURVES, DELAYS, FIELDS


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def vector(probe):
    return [
        b[name][field] - a[name][field]
        for a, b in zip(probe["baseline"]["frames"], probe["response"]["frames"])
        for name in ("out0", "out1")
        for field in FIELDS
    ]


def rms(v):
    return math.sqrt(sum(x * x for x in v) / len(v))


def expression(early, late):
    a, b = rms(early), rms(late)
    cosine = sum(x * y for x, y in zip(early, late)) / (len(early) * a * b) if a * b else 0.0
    return dict(early_rms=a, late_rms=b, cosine=cosine, passed=a > 1e-4 and b > 1e-4 and b >= 0.1 * a and cosine >= 0.8)


def target_edges(graph, history):
    pair = {"cue", f"out{history}"}
    return [e for e in graph["edges"] if {e["source_symbol"], e["target_symbol"]} == pair]


def mean_weight(graph, history):
    return sum(e["weight"] for e in target_edges(graph, history)) / 2


def remaining(curve, a):
    # Independent direct formulas, not the kernel's decay helper.
    if curve == "exponential":
        return 2.0 ** (-a)
    if curve == "power-law":
        return 1 / (1 + a)
    if curve == "inverse-logarithmic":
        return 1 / (1 + math.log1p(math.expm1(1) * a))
    if curve == "power-exponential":
        return 1 / (1 + a) if a <= 10 else math.exp(-(a - 10) / 11) / 11
    raise ValueError(curve)


def tail_weight(e, curve):
    age = e["decay_age"]
    later = age + 30 * 86400 / e["half_life"]
    if curve == "exponential":
        ratio = 2.0 ** (-(later - age))
    elif curve == "power-exponential" and age >= 10:
        ratio = math.exp(-(later - age) / 11)
    else:
        ratio = remaining(curve, later) / remaining(curve, age)
    return e["weight"] * ratio


def interval(successes, n):
    z = 1.959963984540054
    p = successes / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [center - half, center + half]


def analyze(work):
    cases = load(work / "cases.json")
    if load(work / "status.json")["sequences_completed"] != len(cases):
        raise ValueError("batch incomplete")
    rows = {}
    for c in cases:
        p = work / "subjects" / c["key"]
        rows[(c["origin"], c["curve"], c["course"], c["delay"], c["history"], c["cue"])] = (
            load(p / "teaching/result.json.gz"),
            load(p / "probe/result.json.gz"),
        )
    origins = sorted({c["origin"] for c in cases})
    details = []
    for o in origins:
        for curve in CURVES:
            results = {}
            vectors = {}
            weights = {}
            for course in COURSES + ("strong-gain-zero", "novelty", "novelty-gain-zero"):
                for delay in DELAYS:
                    per_history = []
                    survival = []
                    tails = []
                    for h in (0, 1):
                        t, a = rows[o, curve, course, delay, h, True]
                        _, b = rows[o, curve, course, delay, h, False]
                        if a["before"] != b["before"]:
                            raise ValueError("matched histories differ before cue")
                        per_history.append([x - y for x, y in zip(vector(a), vector(b))])
                        edges = target_edges(a["before"], h)
                        survival.append(len(edges) == 2)
                        tails.extend(tail_weight(e, curve) for e in edges)
                        weights[course, h] = mean_weight(t["samples"][-1], h)
                    vectors[course, delay] = [x - y for x, y in zip(per_history[1], per_history[0])]
                    results[course, delay] = dict(
                        both_histories_survive=all(survival),
                        both_histories_absent=all(
                            not target_edges(rows[o, curve, course, delay, h, True][1]["before"], h) for h in (0, 1)
                        ),
                        max_tail_weight=max(tails, default=0.0),
                        tail_pass=all(v < 0.008 for v in tails),
                    )
            goals = {}
            observations = {}
            for course in ("massed", "spaced", "strong"):
                goals["S:" + course] = results[course, 300]["both_histories_survive"]
                expr = expression(vectors[course, 1], vectors[course, 300])
                goals["E:" + course] = expr["passed"]
                goals["F:" + course] = results[course, 300]["tail_pass"]
                observations[course] = dict(expression=expr, structure=results[course, 300])
            goals["W"] = results["weak", 30]["both_histories_absent"]
            for kind, control in (("strong", "strong-gain-zero"), ("novelty", "novelty-gain-zero")):
                gains = [weights[kind, h] - weights[control, h] for h in (0, 1)]
                goals["G:" + kind] = all(v > 1e-8 for v in gains)
                observations[kind + "-gain"] = gains
            details.append(dict(origin=o, curve=curve, goals=goals, measurements=observations))
    summary = []
    for curve in CURVES:
        rows_for_curve = [r for r in details if r["curve"] == curve]
        scores = {
            k: dict(passed=sum(r["goals"][k] for r in rows_for_curve), n=len(origins))
            for k in rows_for_curve[0]["goals"]
        }
        for v in scores.values():
            v["wilson95"] = interval(v["passed"], v["n"])
            v["target_met"] = v["passed"] >= math.ceil(0.75 * v["n"])
        candidate = all(v["target_met"] for k, v in scores.items() if not k.startswith("G:"))
        summary.append(dict(curve=curve, scores=scores, combined_candidate=candidate))
    return dict(
        schema="threemind.r47a-analysis/1",
        independent_origins=len(origins),
        sequences=len(cases),
        summary=summary,
        details=details,
        exploratory=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, required=True)
    work = p.parse_args().work
    result = analyze(work)
    with (work / "analysis-v1.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
