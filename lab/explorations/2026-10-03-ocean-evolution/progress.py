"""Small read-only progress summary from complete population checkpoints."""

import json

from experiment import WORK, active_workers

from lab.tools.ocean_cli import read_json


def main():
    workers = {v["case"]: v for v in active_workers()}
    rows = []
    for root in sorted((WORK / "cases").glob("*")):
        candidates = []
        for p in root.rglob("progress-*.json"):
            v = read_json(p)
            candidates.append((v["time_us"], p.parent / "checkpoints" / str(v["time_us"])))
        for p in root.rglob("result.json"):
            v = read_json(p)
            candidates.append((v["time_us"], p.parent / "final"))
        if not candidates:
            rows.append({"case": root.name, "checkpoint": "first interval pending"})
            continue
        at, path = max(candidates, key=lambda x: x[0])
        v = read_json(path / "manifest.json")["context"]
        row = {
            "case": root.name,
            "sim_s": at / 1e6,
            "physical": sum(m["physical"] for m in v["bodies"]),
            "retained": len(v["bodies"]),
            "births": v["totals"]["births"],
            "food": round(v["totals"]["food_consumed"] / v["protocol"]["nutrient_energy"]),
            "food_left": len(v["food"]),
            "body_cost": round(v["totals"]["body_heat"], 2),
            "predations": v["totals"]["predations"],
            "exchanges": v["totals"]["sharing_contacts"],
            "recombinations": v["totals"]["recombinations"],
            "transfers": v["totals"]["horizontal_transfers"],
            "running": root.name in workers,
        }
        if root.name in workers:
            row["RSS_MiB"] = round(workers[root.name]["rss"] / 2**20, 1)
        rows.append(row)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
