"""Deterministic, paired contrasts; no pseudoreplicated significance tests."""

import gzip
import itertools
import statistics

from common import WORK, new_json, read_json
from run import COMBINATIONS, TOKENS


def expected(row):
    value = "C" if row["probe"].startswith("A") else "E"
    if row["training"]["swap"]:
        value = "E" if value == "C" else "C"
    return value


def margin(row, phase="post_B", metric="peak"):
    target = expected(row)
    other = "E" if target == "C" else "C"
    return row[phase][target][metric] - row[phase][other][metric]


def group_summary(rows):
    cues = [r for r in rows if r["probe"] in ("AB", "DB")]
    margins = [margin(r) for r in cues]
    return {"n": len(cues), "positive": sum(x > 1e-12 for x in margins),
            "min": min(margins), "max": max(margins), "mean": statistics.mean(margins),
            "area_mean": statistics.mean(margin(r, metric="area") for r in cues),
            "reader_mean": statistics.mean(r["reader_peak"][expected(r)] - r["reader_peak"]["E" if expected(r) == "C" else "C"] for r in cues),
            "converged": sum(r["primary_available"] for r in cues),
            "pre_B_max": max(r["pre_B"][s]["peak"] for r in cues for s in "CE"),
            "rows": [{"key": r["key"], "probe": r["probe"], "swap": r["training"]["swap"],
                      "reverse": r["training"]["reverse"], "margin": margin(r),
                      "area_margin": margin(r, metric="area"), "classification": r["classification"]} for r in cues]}


def trajectory(key):
    with gzip.open(WORK / "cases" / key / "trajectory.jsonl.gz", "rt", encoding="utf-8") as f:
        return [__import__("json").loads(line) for line in f]


def activations(row):
    return {s: next((n["activation"] for n in row["nodes"] if n["channel"] == TOKENS[s]), 0.0) for s in "CE"}


def matched_delta(full, control):
    # Both clones use the same observation grid. If one has died, its actual
    # zero activation persists; never impute a positive continuation.
    baseline = {r["relative_us"]: activations(r) for r in trajectory(control["key"])}
    last_time = max(baseline)
    raw = trajectory(control["key"])
    dead = raw[-1]["life"] == "dead"
    if control["probe"] == "B" and control["classification"] == "no_window":
        return {"available": False, "reason": "control died before scheduled B; not a measured B response"}
    target = expected(full)
    other = "E" if target == "C" else "C"
    differences = []
    for row in trajectory(full["key"]):
        t = row["relative_us"]
        if t < 1_000_000:
            continue
        base = baseline.get(t)
        if base is None and dead and t > last_time:
            base = {s: 0.0 for s in "CE"}
        if base is None:
            raise RuntimeError("unmatched live observation time")
        actual = activations(row)
        differences.append((t, (actual[target] - actual[other]) - (base[target] - base[other])))
    area = sum((b[0] - a[0]) / 1e6 * (a[1] + b[1]) / 2 for a, b in zip(differences, differences[1:]))
    return {"available": True, "max": max((v for _, v in differences), default=0),
            "min": min((v for _, v in differences), default=0), "area": area}


def main():
    cells = {bits: read_json(WORK / f"factorial-{bits}.json") for bits in COMBINATIONS}
    result = {"factorial": {bits: group_summary(rows) for bits, rows in cells.items()}}
    switches = read_json(WORK / "test-switch.json")
    result["test_switch"] = {bits: group_summary(cells["111"] if bits == "111" else [r for r in switches if r["test_bits"] == bits]) for bits in COMBINATIONS}
    result["baseline"] = group_summary(read_json(WORK / "baseline.json"))
    result["background"] = {bits: group_summary([r for r in read_json(WORK / "background.json") if r["training"]["bits"] == bits]) for bits in COMBINATIONS}
    means = {bits: result["factorial"][bits]["mean"] for bits in COMBINATIONS}
    effects = {}
    for i, label in enumerate("SFC"):
        paired = []
        for bits in COMBINATIONS:
            if bits[i] == "0":
                on = bits[:i] + "1" + bits[i+1:]
                paired.append({"off": bits, "on": on, "difference": means[on] - means[bits]})
        effects[label] = {"paired": paired, "mean": statistics.mean(p["difference"] for p in paired)}
    interactions = {}
    for i, j in itertools.combinations(range(3), 2):
        other = next(k for k in range(3) if k not in (i, j))
        values = []
        for v in "01":
            def get(a, b):
                bits = ["0"] * 3
                bits[i], bits[j], bits[other] = a, b, v
                return means["".join(bits)]
            values.append({"remaining_bit": v, "difference": get("1", "1")-get("1", "0")-get("0", "1")+get("0", "0")})
        interactions["SFC"[i]+"SFC"[j]] = values
    result["effects"], result["interactions"] = effects, interactions
    controls = []
    rows = cells["111"]
    for r in rows:
        if r["probe"] not in ("AB", "DB"):
            continue
        controls_by_name = {x["probe"]: x for x in rows if x["parent_id"] == r["parent_id"]}
        controls.append({"key": r["key"], "expected": expected(r),
                         "minus_B_only": matched_delta(r, controls_by_name["B"]),
                         "minus_prefix_only": matched_delta(r, controls_by_name[r["probe"][0]]),
                         "B_only": controls_by_name["B"]["post_B"],
                         "prefix_only": controls_by_name[r["probe"][0]]["post_B"],
                         "no_input": controls_by_name["none"]["post_B"]})
    result["default_controls"] = controls
    background = [r for r in read_json(WORK / "background.json") if r["training"]["bits"] == "111"]
    control = next(r for r in background if r["probe"] == "B")
    result["background_B_control"] = [{"key": r["key"], "minus_B_only": matched_delta(r, control)}
                                      for r in background if r["probe"] in ("AB", "DB")]
    result["cases"] = len(list((WORK / "cases").rglob("result.json")))
    result["revision"] = 2
    result["analysis_correction"] = "No-background B-only died before delivery; mark unavailable and use the matched background B-only control. Original analysis.json retained."
    new_json(WORK / "analysis-v2.json", result)
    for bits in COMBINATIONS:
        r, t, b = result["factorial"][bits], result["test_switch"][bits], result["background"][bits]
        print(bits, f"factorial {r['positive']}/{r['n']} margin={r['mean']:.9f}",
              f"test-switch {t['positive']}/{t['n']} margin={t['mean']:.9f}",
              f"background {b['positive']}/{b['n']} margin={b['mean']:.9f}", flush=True)


if __name__ == "__main__":
    main()
