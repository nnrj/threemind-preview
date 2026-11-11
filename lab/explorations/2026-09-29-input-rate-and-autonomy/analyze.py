"""Audit only this study, then summarize raw curves, temporal readouts and actions."""

import gzip
import json
from collections import Counter

from common import WORK, Study, encoded, load_case

from threemind_core import StateImage


def read(path):
    return json.loads(path.read_bytes())


def gz(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def analyze(study):
    paths = sorted((WORK / "cases").rglob("result.json"))
    results = [read(p) for p in paths]
    failures, temporal, by_stage = [], Counter(), Counter()
    interventions, world, lif, replays = [], [], [], []
    for r, p in zip(results, paths):
        by_stage[r["key"].split("/")[0]] += 1
        if r["extra"].get("budget_stop"):
            failures.append({"key": r["key"], "reason": r["extra"]})
        raw = gzip.decompress((p.parent / "parent-state.json.gz").read_bytes())
        if StateImage(raw).digest != r["state_sha256"]:
            failures.append({"key": r["key"], "reason": "local state checksum"})
        saved = load_case(study, r["key"])
        # Model hashes preserve normalized float bits; JSON byte layout can differ
        # between native capture and database decoding. Archive byte hashes are separate.
        assert saved["image"].to_dict() == json.loads(raw)
        with gzip.open(p.parent / "events.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e["kind"] == "temporal_readout":
                    temporal[e["payload"]["classification"]] += 1
                if e["kind"] == "research_intervention":
                    interventions.append({"key": r["key"], "event": e})
        if r["extra"]["kind"] == "ring_world":
            x = r["extra"]
            energy = x["energy"]
            assert energy["unserved_total"] == 0
            assert energy["consumed_direct"] > 0
            if r["config"]["propagation_rate"]:
                assert energy["consumed_associative"] > 0
            else:
                assert energy["consumed_associative"] == 0
            assert r["config"]["depletion_enabled"] and r["config"]["inhibition"]
            assert r["config"]["stp_facilitation_tau_s"] == 1
            assert energy["reserve"] >= 0 and x["supply"]["configuration"]["total_supply_limit"] is None
            world.append({"key": r["key"], **x})
        if r["key"].startswith("rate/lif") and r["extra"]["kind"] == "rate_training":
            s = json.loads(raw)
            channels = set(r["extra"]["tokens"].values())
            ids = {n["id"] for n in s["nodes"] if n["channel"] in channels}
            edges = [e for e in s["edges"] if e["source"] in ids and e["target"] in ids]
            lif.append(
                {
                    "key": r["key"],
                    "interval_us": r["extra"]["interval_us"],
                    "spikes": r["metrics"]["spikes"],
                    "task_edges": edges,
                }
            )
        if "/controls/" in r["key"] and r["key"].endswith("sensory-replay"):
            original = r["key"].replace("/controls/", "/final/").replace("/sensory-replay", "/swap0")
            other = read(WORK / "cases" / original / "result.json")
            equal = r["state_sha256"] == other["state_sha256"]
            replays.append({"key": r["key"], "original": original, "identical_core_state": equal})
            if not equal:
                failures.append({"key": r["key"], "reason": "identical input replay changed Core"})
    selection = read(WORK / "selection-results.json") if (WORK / "selection-results.json").exists() else None
    held = {}
    controls = {}
    if selection:
        for seed in (9293201, 9293202):
            held[str(seed)] = {}
            for arm in ("region0", "region1", "random"):
                rows = [r for r in selection["held_out"] if r["seed"] == seed and r["arm"] == arm]
                held[str(seed)][arm] = {
                    "mean_region1": sum(r["extra"]["region1_fraction"] for r in rows) / len(rows),
                    "range_region1": [
                        min(r["extra"]["region1_fraction"] for r in rows),
                        max(r["extra"]["region1_fraction"] for r in rows),
                    ],
                    "mean_distance": sum(r["extra"]["travel_distance"] for r in rows) / len(rows),
                }
                values = {}
                for label, tail in (("closed_swap", "final/p{p}/swap1"),
                                    ("recorded_swap", "controls/p{p}/motor-replay"),
                                    ("reversal", "controls/p{p}/reversal")):
                    occupancies, first, second = [], [], []
                    for position in (0, 2):
                        folder = WORK / "cases" / f"selection/s{seed}/{arm}" / tail.format(p=position)
                        item = read(folder / "result.json")
                        occupancies.append(item["extra"]["region1_fraction"])
                        if label == "reversal":
                            trajectory = gz(folder / "world.json.gz")["rows"]
                            first.append(sum(r["region"] for r in trajectory[:300]) / 300)
                            second.append(sum(r["region"] for r in trajectory[300:]) / 300)
                    values[label] = sum(occupancies) / 2
                    if first:
                        values["reversal_first_half"] = sum(first) / 2
                        values["reversal_second_half"] = sum(second) / 2
                controls[f"{seed}/{arm}"] = values
    with study.db.tx() as db:
        database = db.execute("SELECT pg_database_size(current_database()) AS bytes").fetchone()["bytes"]
    summary = {
        "cases": len(results),
        "stages": dict(by_stage),
        "failures": failures,
        "temporal_windows": dict(temporal),
        "compute_seconds": sum(r["wall_seconds"] for r in results),
        "local_bytes": sum(p.stat().st_size for p in WORK.rglob("*") if p.is_file()),
        "database_growth_bytes": max(0, database - study.meta["database_bytes_before"]),
        "lif_training": lif,
        "world_cases": len(world),
        "held_out": held,
        "controls": controls,
        "replays": replays,
        "interventions": interventions,
    }
    (WORK / "analysis.json").write_bytes(encoded(summary))
    print(
        json.dumps({k: v for k, v in summary.items() if k not in ("lif_training", "replays", "interventions")}),
        flush=True,
    )


if __name__ == "__main__":
    study = Study()
    try:
        analyze(study)
    finally:
        study.db.close()
