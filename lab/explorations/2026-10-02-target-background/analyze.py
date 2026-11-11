"""E24 preregistered contrasts and saved-evidence audits; no simulation."""

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import statistics
from collections import Counter

from common import HERE, KINDS, ROOT, SEEDS, WORK, Study, ids, new_json, read_json, settings

from lab.tools.study_input_audit import jsonb_value_equal, verify_input_bundle
from threemind_core import StateImage
from threemind_lab.inputs import export_stream
from threemind_lab.provenance import capture_implementation
from threemind_runtime.target_observation import target_observation


def cases():
    return {r["key"]: r for p in (WORK / "cases").rglob("result.json") for r in [read_json(p)]}


def windows(row):
    folder = WORK / "cases" / row["key"]
    events = [json.loads(line) for line in gzip.decompress((folder / "events.jsonl.gz").read_bytes()).splitlines()]
    return [e["payload"] for e in events if e.get("payload", {}).get("analysis_schema")]


def coordinates(row):
    state = json.loads(gzip.decompress((WORK / "cases" / row["key"] / "parent-state.json.gz").read_bytes()))
    by_channel = {n["channel"]: n["id"] for n in state["nodes"]}
    return {s: by_channel[ids(row["seed"])[s]] for s in "AB"}


def metrics(row, end=None):
    records = windows(row)
    if not records:
        return None
    r = records[-1]
    selected = coordinates(row)
    series = [s for s in r["series"] if end is None or int(s["time_us"]) <= end]
    if not series:
        return None
    target = target_observation(
        series, r["nodes"], list(selected.values()), expected_interval_us=int(r["configuration"]["interval_us"])
    )
    by_id = {n["node_id"]: n for n in target["nodes"]}
    values = {}
    for s, node in selected.items():
        key = str(node)
        points = [(int(v["time_us"]), v["activation_vector"].get(key, 0)) for v in series]
        values[s] = {
            "integral": by_id[node]["sampled_activation_integral"],
            "trapezoid": math.fsum((a[1] + b[1]) * (b[0] - a[0]) / 2e6 for a, b in itertools.pairwise(points)),
            "peak": by_id[node]["process_peak_activation"],
            "terminal": points[-1][1],
        }
    return {
        "targets": values,
        "start": int(series[0]["time_us"]),
        "end": int(series[-1]["time_us"]),
        "global": r["classification"],
        "local_pattern": target["first_pattern_convergence"],
        "local_steady": target["first_steady_convergence"],
        "censored": r["censored"],
    }


def contrast(cue, control):
    a, b = metrics(cue), metrics(control)
    result = {
        "key": cue["key"],
        "seed": cue["seed"],
        "order": cue["extra"]["order"],
        "background": cue["extra"].get("background"),
        "delay_s": cue["extra"].get("delay_s"),
        "available": a is not None and b is not None,
        "complete": cue["extra"].get("complete_window", True) and control["extra"].get("complete_window", True),
        "cue_life": cue["life"],
        "control_life": control["life"],
        "global": a["global"] if a else None,
        "local_pattern": a["local_pattern"]["time_us"] if a and a["local_pattern"] else None,
        "local_steady": a["local_steady"]["time_us"] if a and a["local_steady"] else None,
    }
    if a is None or b is None:
        return result
    end = min(a["end"], b["end"])
    a, b = metrics(cue, end), metrics(control, end)
    assert a["start"] == b["start"] and a["end"] == b["end"]
    for symbol in "AB":
        result["net_" + symbol] = a["targets"][symbol]["integral"] - b["targets"][symbol]["integral"]
        result["peak_" + symbol] = a["targets"][symbol]["peak"]
        result["terminal_" + symbol] = a["targets"][symbol]["terminal"]
    early, later = result["order"]
    result["later_minus_earlier"] = result["net_" + later] - result["net_" + early]
    result["trapezoid_margin"] = (a["targets"][later]["trapezoid"] - b["targets"][later]["trapezoid"]) - (
        a["targets"][early]["trapezoid"] - b["targets"][early]["trapezoid"]
    )
    result["common_start_us"], result["common_end_us"] = a["start"], end
    result["direction"] = (
        "later"
        if result["later_minus_earlier"] > 1e-6
        else ("earlier" if result["later_minus_earlier"] < -1e-6 else "undifferentiated")
    )
    return result


def write_table(name, rows):
    folder = HERE / "tables"
    folder.mkdir(exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (folder / (name + ".csv")).open("x", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def target_series(row):
    selected = coordinates(row)
    r = windows(row)[-1]
    return {
        int(s["time_us"]): {c: s["activation_vector"].get(str(n), 0) for c, n in selected.items()} for s in r["series"]
    }


def full_channel_series(row):
    r = windows(row)[-1]
    state = StateImage(gzip.decompress((WORK / "cases" / row["key"] / "parent-state.json.gz").read_bytes())).to_dict()
    channels = {str(n["id"]): n["channel"] for n in state["nodes"]}
    return {int(s["time_us"]): {channels[k]: v for k, v in s["activation_vector"].items()} for s in r["series"]}


def max_difference(a, b):
    times = a.keys() & b.keys()
    return max(
        (math.fsum(abs(a[t].get(k, 0) - b[t].get(k, 0)) for k in a[t].keys() | b[t].keys()) for t in times),
        default=None,
    )


def cpu(row):
    events = [
        json.loads(line)
        for line in gzip.decompress((WORK / "cases" / row["key"] / "events.jsonl.gz").read_bytes()).splitlines()
    ]
    values = {}
    for e in events:
        if e["kind"] != "telemetry_sample":
            continue
        for scope, sample in e["payload"]["scopes"].items():
            for key, measurement in sample["measurements"].items():
                raw = measurement["raw"]
                if "cpu" in key and raw.get("available") and raw.get("raw_value") is not None:
                    values.setdefault(scope + ":" + key, []).append(raw["raw_value"])
    return {k: statistics.mean(v) for k, v in values.items()}


def summarize():
    allrows = cases()
    matrix = []
    for seed, kind, order, delay in itertools.product(SEEDS, KINDS, ("AB", "BA"), (1, 30)):
        key = f"matrix/{seed}/{kind}/{order}/wait{delay}"
        if key + "/cue1" in allrows and key + "/cue0" in allrows:
            matrix.append(contrast(allrows[key + "/cue1"], allrows[key + "/cue0"]))
    expression = []
    for kind, order in itertools.product(KINDS, ("AB", "BA")):
        key = f"expression/{kind}/{order}"
        if key + "/cue1" in allrows and key + "/cue0" in allrows:
            expression.append(contrast(allrows[key + "/cue1"], allrows[key + "/cue0"]))
    groups = []
    for kind, delay in itertools.product(KINDS, (1, 30)):
        rows = [r for r in matrix if r["background"] == kind and r["delay_s"] == delay]
        available = [r for r in rows if r["available"]]
        margins = [r["later_minus_earlier"] for r in available]
        groups.append(
            {
                "background": kind,
                "delay_s": delay,
                "tested": len(rows),
                "available": len(available),
                "complete": sum(r["complete"] for r in available),
                "later_directions": sum(r["direction"] == "later" for r in available),
                "min_margin": min(margins, default=None),
                "max_margin": max(margins, default=None),
                "mean_margin": statistics.mean(margins) if margins else None,
            }
        )
    livedetail, livepairs = [], []
    for seed in SEEDS:
        rows = []
        for mode in ("minimal", "dense"):
            key = f"live/{seed}/{mode}"
            if key + "/no-cue" not in allrows:
                continue
            original, repeated, control = (allrows[k] for k in (key, key + "/replay", key + "/no-cue"))
            row = contrast(repeated, control)
            row.update(
                mode=mode,
                replay_matches=original["state_sha256"] == repeated["state_sha256"],
                cpu=cpu(original),
                dense_process_cpu_s=original["extra"]["dense_process_cpu_s"],
            )
            rows.append(row)
            livedetail.append(row)
        if len(rows) == 2:
            a, b = [allrows[f"live/{seed}/{m}/replay"] for m in ("minimal", "dense")]
            livepairs.append(
                {
                    "seed": seed,
                    "same_final_state": a["state_sha256"] == b["state_sha256"],
                    "target_max_l1_difference": max_difference(target_series(a), target_series(b)),
                    "global_max_l1_difference": max_difference(full_channel_series(a), full_channel_series(b)),
                    "same_direction": rows[0]["direction"] == rows[1]["direction"],
                    "minimal_margin": rows[0]["later_minus_earlier"],
                    "dense_margin": rows[1]["later_minus_earlier"],
                }
            )
    comparisons = []
    for seed, order, delay, cue in itertools.product(SEEDS, ("AB", "BA"), (1, 30), (0, 1)):
        names = [f"matrix/{seed}/{kind}/{order}/wait{delay}/cue{cue}" for kind in ("telemetry", "random")]
        if all(n in allrows for n in names):
            a, b = [allrows[n] for n in names]
            if windows(a) and windows(b):
                comparisons.append(
                    {
                        "seed": seed,
                        "order": order,
                        "delay_s": delay,
                        "cue": cue,
                        "target_max_l1_difference": max_difference(target_series(a), target_series(b)),
                        "global_max_l1_difference": max_difference(full_channel_series(a), full_channel_series(b)),
                    }
                )
    summary = {
        "cases": len(allrows),
        "case_groups": dict(Counter(k.split("/")[0] for k in allrows)),
        "wall_seconds": sum(r["wall_seconds"] for r in allrows.values()),
        "groups": groups,
        "expression": expression,
        "live": livedetail,
        "live_pairs": livepairs,
        "background_trajectory_comparisons": comparisons,
        "failed": [r["key"] for r in allrows.values() if r["extra"].get("failure")],
    }
    new_json(WORK / "summary.json", summary)
    for name, rows in (
        ("matrix", matrix),
        ("expression", expression),
        ("live", livedetail),
        ("live-pairs", livepairs),
        ("background-trajectories", comparisons),
    ):
        write_table(name, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def audit():
    study = Study(settings())
    totals, paired = Counter(), []
    try:
        current = capture_implementation("native")
        assert current == study.meta["implementation"]
        source_hashes = read_json(WORK / "historical-sources.json") | read_json(
            WORK / "calibration/source-checksums.json"
        )
        for name, digest in source_hashes.items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
        old = read_json(ROOT / ".work/observation-background-20261001/platform.json")["implementation"]
        core_names = [
            n for n in old["source_files"] if n.startswith(("src/threemind_core/", "src/threemind_kernels/", "crates/"))
        ]
        assert all(current["source_files"][n] == old["source_files"][n] for n in core_names)
        assert current["native_binary_sha256"] == old["native_binary_sha256"]
        for seed in SEEDS:
            a, b = [read_json(WORK / f"materials/{seed}-{k}.json") for k in ("telemetry", "random")]
            assert len(a) == len(b)
            for x, y in zip(a, b):
                assert x["scope"] == y["scope"]
                x, y = x["stimulus"], y["stimulus"]
                assert x["time_us"] == y["time_us"] and x["intensity"] == y["intensity"]
                assert sorted(v for _, v in x["channels"]) == sorted(v for _, v in y["channels"])
            paired.append(
                {
                    "seed": seed,
                    "matched_frames": len(a),
                    "total_input": math.fsum(
                        f["stimulus"]["intensity"] * math.fsum(v for _, v in f["stimulus"]["channels"]) for f in a
                    ),
                }
            )
        allrows = cases()
        for row in allrows.values():
            folder = WORK / "cases" / row["key"]
            _, state = study.db.load_checkpoint(study.project, row["id"])
            assert state.digest == row["state_sha256"]
            assert StateImage(gzip.decompress((folder / "parent-state.json.gz").read_bytes())).digest == state.digest
            raw = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
            if row["extra"]["stage"] not in ("live", "acquisition"):
                check = verify_input_bundle(study, folder, row, require_complete=False)
                totals.update({k: check[k] for k in ("frames", "pending_frames", "envelopes")})
            else:
                for kind in ("envelopes", "frames"):
                    lines = list(export_stream(study.db, study.project, row["id"], records=kind, format="jsonl"))
                    destination = folder / f"inputs-{kind}.jsonl.gz"
                    if not destination.exists():
                        with gzip.open(destination, "xb") as out:
                            out.write("".join(lines).encode())
                    assert gzip.decompress(destination.read_bytes()) == "".join(lines).encode()
                    records = [json.loads(line) for line in lines[1:]]
                    assert len(records) == len(raw[kind])
                    totals[kind] += len(records)
                    if kind == "frames":
                        expected = {(r["envelope_id"], r["frame_index"]): r for r in raw[kind]}
                        for r in records:
                            source = expected[(r["envelope_id"], r["frame_index"])]
                            assert jsonb_value_equal(r["stimulus"], source["stimulus"])
                            assert r["input_gate"] is None
                            if r["status"] == "delivered":
                                assert r["delivered_time_us"] == r["scheduled_time_us"]
                            else:
                                assert r["status"] == "scheduled" and int(r["scheduled_time_us"]) > int(row["time_us"])
                                totals["pending_frames"] += 1
                assert not raw["rejected"]
            totals["cases"] += 1
        result = {
            "inputs": dict(totals),
            "paired_materials": paired,
            "historical_files_unchanged": len(source_hashes),
            "core_source_files_unchanged": len(core_names),
            "native_unchanged": True,
        }
        new_json(WORK / "audit.json", result)
        print(json.dumps(result, indent=2), flush=True)
    finally:
        study.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("summarize", "audit"))
    args = parser.parse_args()
    globals()[args.stage]()
