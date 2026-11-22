"""Independent raw-state/trajectory audit and registered layout contrasts."""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.stats import binomtest

import analyze as a
import layout
import ring as r
import study


def main(work, main_work):
    assert r.read(work / "science-complete.json")["stages"] == 768
    rows, audit = [], []
    for seed in r.SEEDS:
        folder = work / "populations" / str(seed)
        population = r.read(folder / "complete.json")
        assert len(population["rows"]) == 48
        count = 0
        for recorded in population["rows"]:
            arm, i, j, condition = (recorded[x] for x in ("arm", "candidate", "start_index", "condition"))
            original = main_work / "populations" / str(seed) / arm / "g2" / f"c{i}"
            candidate = r.read(original / "development/final.json.gz")
            baseline = r.read(original / f"held-{j}/result.json")
            base_trace = r.read(original / f"held-{j}/trajectory.json.gz")["rows"]
            stage = folder / arm / f"c{i}" / f"held-{j}" / condition
            result = r.read(stage / "result.json")
            initial = r.read(stage / "initial.json.gz")
            final = r.read(stage / "final.json.gz")
            trajectory = r.read(stage / "trajectory.json.gz")
            assert result == recorded["result"] and result["phase"] == .5
            assert result["seed"] == seed and result["kernel"] == r.KERNEL
            assert r.digest(initial) == result["initial_whole_hash"]
            assert r.digest(final) == result["final_whole_hash"]
            assert r.StateImage.from_dict(initial["core"]).digest == result["initial_core_hash"]
            assert r.StateImage.from_dict(final["core"]).digest == result["final_core_hash"]
            for field in ("core", "session", "supplier", "next_sense", "next_background", "next_motor"):
                assert initial[field] == candidate[field], (seed, stage, field)
            assert initial["body"] == {"x": r.TEST_STARTS[j], "v": 0., "phase": .5}
            assert result["ancestry"]["birth_called"] is False
            assert result["ancestry"]["parent_whole_hash"] == r.digest(candidate)
            tr = trajectory["rows"]
            assert len(tr) == 600
            occupied, sum_distance = 0, 0.
            for k, row in enumerate(tr):
                assert row["time_us"] == result["begin_us"] + 100000*k
                assert row["body"]["phase"] == .5
                identity = int((row["body"]["x"]+.5) % 1 >= .5)
                assert row["region"] == identity
                assert row["physical_region"] == int(row["body"]["x"] >= .5)
                occupied += 100000*identity
                applied = row["applied_control"]
                assert applied == row["control"]
                if row["alive"]:
                    proposed = r.math.tanh(.5 * r.math.fsum(
                        (1 if r.channel_id(seed, r.MOTOR_NS, int(n["id"])) & 1 else -1)*n["activation"]
                        for n in sorted(row["nodes"], key=lambda n: n["id"])))
                    a.close(row["proposed_control"], proposed)
                    a.close(applied, proposed if condition == "closed" else base_trace[k]["control"])
                    if condition == "replay":
                        a.close(row["body"]["x"], base_trace[k]["body"]["x"])
                        a.close(row["body"]["v"], base_trace[k]["body"]["v"])
                else:
                    assert applied == 0
                terminal = .3*applied/.8
                distance = terminal*.1 + (row["body"]["v"]-terminal)*(1-r.math.exp(-.08))/.8
                sum_distance += abs(distance)
                following = tr[k+1]["body"] if k+1 < len(tr) else final["body"]
                a.close(following["x"], (row["body"]["x"]+distance) % 1)
                a.close(following["v"], terminal+(row["body"]["v"]-terminal)*r.math.exp(-.08))
            a.close(occupied/60000000, result["region1"])
            a.close(sum_distance, result["travel_distance"])
            a.close(recorded["baseline_region1"], baseline["region1"])
            a.close(recorded["region1"], result["region1"])
            rows.append({"seed": seed, "arm": arm, "candidate": i, "start_index": j,
                "condition": condition, "baseline_region1": baseline["region1"], "region1": result["region1"],
                "life": result["life"], "travel_distance": result["travel_distance"]})
            count += 1
        audit.append({"seed": seed, "stages": count, "passed": True})
        print(f"layout audited {seed}: {count} stages", flush=True)
    scores = []
    for seed in r.SEEDS:
        for arm in study.ARMS:
            group = [x for x in rows if x["seed"] == seed and x["arm"] == arm]
            baseline = np.mean([x["baseline_region1"] for x in group if x["condition"] == "closed"])
            closed = np.mean([x["region1"] for x in group if x["condition"] == "closed"])
            replay = np.mean([x["region1"] for x in group if x["condition"] == "replay"])
            scores.append({"seed": seed, "arm": arm, "baseline_region1": float(baseline),
                           "closed_region1": float(closed), "replay_region1": float(replay)})
    rng = np.random.default_rng(1117178)
    tests, descriptive = [], []
    for arm in study.ARMS:
        for direction in ("region0", "region1"):
            group = [x for x in scores if x["arm"] == arm]
            sign = 1 if direction == "region1" else -1
            delta = [sign*(x["closed_region1"]-x["replay_region1"]) for x in group]
            changed = [sign*(x["closed_region1"]-x["baseline_region1"]) for x in group]
            descriptions = {"arm": arm, "direction": direction,
                "closed_minus_replay": a.descriptive(delta, rng),
                "swapped_minus_original": a.descriptive(changed, rng)}
            descriptive.append(descriptions)
            if arm == direction:
                positive = sum(x > 1e-12 for x in delta)
                negative = sum(x < -1e-12 for x in delta)
                p = float(binomtest(positive, positive+negative, .5, alternative="greater").pvalue) if positive+negative else 1.
                tests.append({"arm": arm, **descriptions["closed_minus_replay"],
                    "positive": positive, "negative": negative, "ties": 16-positive-negative, "p_raw": p})
    running = 0.
    for rank, i in enumerate(sorted(range(2), key=lambda k: tests[k]["p_raw"])):
        running = max(running, min(1., (2-rank)*tests[i]["p_raw"]))
        tests[i]["p_holm"] = running
        tests[i]["passed"] = tests[i]["mean"] >= .01 and running <= .05
    result = {"schema": "artificial-selection63/layout-analysis/1", "independent_n": 16,
        "joint_passed": all(t["passed"] for t in tests), "tests": tests,
        "descriptive": descriptive, "population_scores": scores}
    destination = work / "analysis-v1"
    r.save(destination / "analysis.json", result)
    r.save(destination / "audit.json", {"passed": True, "populations": audit, "stages": len(rows),
                                      "dead_stages": [x for x in rows if x["life"] == "dead"]})
    a.write_csv(destination / "stages.csv", rows)
    a.write_csv(destination / "population-scores.csv", scores)
    print(json.dumps({"joint_passed": result["joint_passed"], "tests": tests}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, default=layout.WORK)
    parser.add_argument("--main", type=Path, default=study.DEFAULT_WORK)
    args = parser.parse_args()
    main(args.work.resolve(), args.main.resolve())
