"""Fixed E23 analyses and complete input/state provenance audit, without simulation."""

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import random
import statistics
from collections import Counter

from common import HERE, ROOT, WORK, Study, ids, new_json, read_json, settings

from lab.tools.study_input_audit import jsonb_value_equal, verify_input_bundle
from threemind_core import StateImage
from threemind_lab.inputs import export_stream
from threemind_lab.provenance import capture_implementation


def cases():
    return {r["key"]: r for p in (WORK / "cases").rglob("result.json") for r in [read_json(p)]}


def summary():
    allrows = cases()
    rows = [
        r
        for r in allrows.values()
        if r["key"].startswith("replication-v2/")
        and r["extra"].get("stage") == "probe"
        and r["extra"]["observation"]["mode"] == "dense"
    ]
    comparisons = []
    for r in rows:
        m = r["extra"]
        if m["cue"] != "X":
            continue
        control = allrows[r["key"].removesuffix("cueX") + "cuenone"]
        b = control["extra"]
        available = m["probe_available"] and b["probe_available"] and m["complete_window"] and b["complete_window"]
        item = {
            "seed": r["seed"],
            "background": m["background"],
            "order": m["order"],
            "delay_s": m["delay_s"],
            "available": available,
            "life": r["life"],
            "end_us": r["time_us"],
            "id": r["id"],
        }
        if available:
            for symbol in ("A", "B"):
                item["net_" + symbol] = m["target_values"][symbol]["integral"] - b["target_values"][symbol]["integral"]
                item["terminal_" + symbol] = m["target_values"][symbol]["terminal"]
                item["peak_" + symbol] = m["target_values"][symbol]["peak"]
            item["later_minus_earlier"] = item["net_" + m["order"][1]] - item["net_" + m["order"][0]]
        comparisons.append(item)
    paired = []
    for kind, delay in itertools.product(("periodic", "none", "random"), (1, 30)):
        group = [r for r in comparisons if r["background"] == kind and r["delay_s"] == delay]
        margins = [r["later_minus_earlier"] for r in group if r["available"]]
        seedpass = {}
        for seed in sorted({r["seed"] for r in group}):
            subset = [r for r in group if r["seed"] == seed]
            seedpass[str(seed)] = (
                all(r["available"] for r in subset)
                and len(subset) == 2
                and all(r["later_minus_earlier"] > 1e-6 for r in subset)
            )
        paired.append(
            {
                "background": kind,
                "delay_s": delay,
                "available_directions": len(margins),
                "total_directions": len(group),
                "mean_margin": statistics.mean(margins) if margins else None,
                "min_margin": min(margins) if margins else None,
                "max_margin": max(margins) if margins else None,
                "passing_blocks": sum(seedpass.values()),
                "tested_blocks": sum(1 for s in seedpass if all(r["available"] for r in group if str(r["seed"]) == s)),
                "passing_directions_1e9": sum(x > 1e-9 for x in margins),
                "terminal_nonzero": sum(
                    r.get("terminal_A", 0) != 0 or r.get("terminal_B", 0) != 0 for r in group if r["available"]
                ),
            }
        )
    checks = []
    for key, r in allrows.items():
        if key.startswith("replication-v2/") and "/dense/" in key:
            ref = allrows[key.replace("/dense/", "/minimal/")]
            assert r["state_sha256"] == ref["state_sha256"]
            if r["extra"]["stage"] == "probe":
                assert r["extra"]["pre_probe_sha256"] == ref["extra"]["pre_probe_sha256"]
            checks.append(key)
    process_checks = []
    for key, r in allrows.items():
        if not key.startswith("replication-v2/") or "/dense/" not in key or r["extra"].get("stage") != "probe":
            continue
        m = r["extra"]
        if m["background"] == "periodic" or not m["probe_available"]:
            continue
        original = key.replace("/" + m["background"] + "/", "/periodic/")

        def series(name, seed=r["seed"]):
            points = json.loads(gzip.decompress((WORK / "cases" / name / "trajectory.json.gz").read_bytes()))
            channels = [ids(seed)[s] for s in ("A", "B")]
            return {
                int(p["time_us"]): [
                    next((n["activation"] for n in p["nodes"] if n["channel"] == ch), 0.0) for ch in channels
                ]
                for p in points
            }

        a, b = series(key), series(original)
        assert a.keys() <= b.keys()
        process_checks.append(
            {
                "key": key,
                "same_target_trajectory": all(b[t] == v for t, v in a.items()),
                "observed_samples": len(a),
                "truncated": not m["complete_window"],
            }
        )
    live = [
        r for r in allrows.values() if r["extra"].get("stage") == "live" and r["key"].startswith("live-kernel-meter/")
    ]
    livedetail = []
    for r in sorted(live, key=lambda x: x["key"]):
        replay = allrows[r["key"] + "/replay"]
        assert replay["state_sha256"] == r["state_sha256"]
        raw = json.loads(gzip.decompress((WORK / "cases" / r["key"] / "inputs.json.gz").read_bytes()))
        sources = Counter(e["source"] for e in raw["envelopes"])
        events = [
            json.loads(line)
            for line in gzip.decompress((WORK / "cases" / r["key"] / "events.jsonl.gz").read_bytes()).splitlines()
        ]
        measurements = {}
        for e in events:
            if e["kind"] != "telemetry_sample":
                continue
            for scope, value in e["payload"]["scopes"].items():
                for name, measurement in value["measurements"].items():
                    physical = measurement["raw"]
                    if physical.get("available") and physical.get("raw_value") is not None:
                        measurements.setdefault(scope + "/" + name, []).append(physical["raw_value"])
        livedetail.append(
            {
                "key": r["key"],
                "hash": r["state_sha256"],
                "tape": r["extra"]["tape_sha256"],
                "sources": dict(sources),
                "observation": r["extra"]["observation"],
                "reproduced": True,
                "mean_measurements": {k: statistics.mean(v) for k, v in measurements.items()},
                "activation": r["metrics"]["activation"],
                "nodes": r["metrics"]["nodes"],
                "edges": r["metrics"]["edges"],
            }
        )
    later = [r for r in allrows.values() if r["extra"].get("stage") == "later_choice"]
    late = {"cases": len(later)}
    if later:
        ys, choices, orders = [], [], []
        for r in sorted(later, key=lambda x: x["key"]):
            folder = WORK / "cases" / r["key"]
            raw = (folder / "early-commitment.json").read_bytes()
            choice = read_json(folder / "later-choice.json")
            assert hashlib.sha256(raw).hexdigest() == choice["early_sha256"]
            assert choice["choice_ns"] > choice["commit_ns"] and choice["choice"] == choice["byte"] & 1
            early = json.loads(raw)
            assert (
                hashlib.sha256((folder / "early-trajectory.json.gz").read_bytes()).hexdigest()
                == early["trajectory_sha256"]
            )
            assert (
                StateImage(gzip.decompress((folder / "early-state.json.gz").read_bytes())).digest
                == early["state_sha256"]
            )
            assert early == r["extra"]["early"]
            ys.append(early["targets"]["A"]["integral"] - early["targets"]["B"]["integral"])
            choices.append(choice["choice"])
            orders.append(early["order"])

        def difference(labels):
            return statistics.mean(v for v, c in zip(ys, labels) if c) - statistics.mean(
                v for v, c in zip(ys, labels) if not c
            )

        actual = difference(choices)
        groups = [[i for i, o in enumerate(orders) if o == order] for order in ("AB", "BA")]
        rng = random.Random(23099)
        exceed = 0
        for _ in range(9999):
            perm = choices.copy()
            for indices in groups:
                labels = [choices[i] for i in indices]
                rng.shuffle(labels)
                for i, c in zip(indices, labels):
                    perm[i] = c
            exceed += abs(difference(perm)) >= abs(actual)
        sd = statistics.stdev(ys)
        late.update(
            choice_counts=dict(Counter(choices)),
            mean_early_difference=actual,
            standardized_by_all_outcomes=actual / sd if sd else None,
            two_sided_permutation_p=(exceed + 1) / 10000,
            permutations=9999,
            unique_early_outcomes=len(set(ys)),
            enough_group_count=min(Counter(choices).values()) >= 48,
            commitments_verified=len(ys),
            physical_quantum_test=False,
        )
    result = {
        "total_cases": len(allrows),
        "groups": dict(Counter(k.split("/")[0] for k in allrows)),
        "aggregate_wall_seconds": sum(r["wall_seconds"] for r in allrows.values()),
        "background": paired,
        "same_input_hash_checks": len(checks),
        "target_trajectory_comparisons": process_checks,
        "live": livedetail,
        "later": late,
        "failed_cases": [r["key"] for r in allrows.values() if r["extra"].get("failure")],
    }
    new_json(WORK / "summary-final.json", result)
    out = HERE / "tables"
    out.mkdir(exist_ok=True)
    fields = sorted({k for r in comparisons for k in r})
    with (out / "background-final.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(comparisons)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


def audit():
    study = Study(settings())
    try:
        allrows = cases()
        sources = read_json(WORK / "sources.json")
        for name, sha in sources.items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
        assert capture_implementation("native") == study.meta["implementation"]
        totals = Counter()
        for key, r in allrows.items():
            folder = WORK / "cases" / key
            _, state = study.db.load_checkpoint(study.project, r["id"])
            assert state.digest == r["state_sha256"]
            assert StateImage(gzip.decompress((folder / "parent-state.json.gz").read_bytes())).digest == state.digest
            raw = json.loads(gzip.decompress((folder / "inputs.json.gz").read_bytes()))
            if r["extra"].get("stage") != "live":
                check = verify_input_bundle(study, folder, r, require_complete=False)
                totals.update({k: check[k] for k in ("frames", "pending_frames", "envelopes")})
            else:
                # Physical carriers reference a recorded sample, not an anonymous
                # payload. Compare the persisted encoded stimuli directly.
                for kind in ("envelopes", "frames"):
                    lines = list(export_stream(study.db, study.project, r["id"], records=kind, format="jsonl"))
                    destination = folder / f"inputs-{kind}.jsonl.gz"
                    if destination.exists():
                        assert gzip.decompress(destination.read_bytes()) == "".join(lines).encode()
                    else:
                        with gzip.open(destination, "xb") as f:
                            for line in lines:
                                f.write(line.encode())
                    records = [json.loads(line) for line in lines[1:]]
                    assert len(records) == len(raw[kind])
                    if kind == "frames":
                        expected = {(v["envelope_id"], v["frame_index"]): v for v in raw[kind]}
                        for v in records:
                            source = expected[(v["envelope_id"], v["frame_index"])]
                            assert jsonb_value_equal(v["stimulus"], source["stimulus"])
                            if v["status"] == "delivered":
                                assert v["delivered_time_us"] == v["scheduled_time_us"]
                            else:
                                totals["pending_frames"] += 1
                        totals["frames"] += len(records)
                    else:
                        totals["envelopes"] += len(records)
                assert not raw["rejected"]
            totals["cases"] += 1
        new_json(
            WORK / "audit-final.json",
            {
                "unchanged_core": True,
                "historical_sources_unchanged": True,
                "historical_files": len(sources),
                "inputs": dict(totals),
                "cases": len(allrows),
            },
        )
        print(dict(totals), flush=True)
    finally:
        study.db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("summary", "audit"))
    args = p.parse_args()
    globals()[args.action]()
