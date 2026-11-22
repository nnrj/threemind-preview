"""Read-only reconstruction and preregistered statistics for AS63-01.

This program never creates a live engine, advances time, teaches, or modifies
scientific originals. Calling the pure birth transformation checks saved lineage.
"""
import argparse
import csv
import io
import math
from pathlib import Path
import random

import numpy as np
from scipy.stats import binomtest

import ring as r

ARMS = ("region0", "region1", "random")
WORK = r.ROOT / ".work/artificial-selection63-20261117"


def close(a, b, label=""):
    if not math.isclose(a, b, rel_tol=0, abs_tol=1e-12):
        raise AssertionError((label, a, b))


def write_csv(path, rows):
    rows = list(rows)
    assert rows
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    payload = stream.getvalue().encode("utf8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == payload, path
    else:
        path.write_bytes(payload)


def audit_population(folder):
    pop = r.read(folder / "complete.json")
    seed = pop["seed"]
    results = sorted(folder.glob("**/result.json"))
    candidates = sorted(folder.glob("**/candidate.json"))
    assert len(results) == 316 and len(candidates) == 52
    all_candidates = {r.read(p)["key"]: r.read(p) for p in candidates}
    stage_rows, candidate_rows = [], []
    snapshots, births, blanks = 0, 0, 0
    for p in results:
        stage = p.parent
        result = r.read(p)
        initial = r.read(stage / "initial.json.gz")
        final = r.read(stage / "final.json.gz")
        trace = r.read(stage / "trajectory.json.gz")
        assert result["seed"] == seed and result["kernel"] == r.KERNEL
        assert initial["kernel"] == final["kernel"] == r.KERNEL
        assert initial["seed"] == final["seed"] == seed
        assert initial["body"]["phase"] == final["body"]["phase"] == 0
        assert r.digest(initial) == result["initial_whole_hash"]
        assert r.digest(final) == result["final_whole_hash"]
        assert r.StateImage.from_dict(initial["core"]).digest == result["initial_core_hash"]
        assert r.StateImage.from_dict(final["core"]).digest == result["final_core_hash"]
        ancestry = r.read(stage / "ancestry.json")
        assert ancestry == result["ancestry"]
        rows = trace["rows"]
        assert len(rows) == result["samples"] == 600
        begin, end = result["begin_us"], result["planned_end_us"]
        assert end - begin == 60000000
        occupied, physical_distance, zero_steps, net_displacement = 0, 0., 0, 0.
        for j, row in enumerate(rows):
            assert row["time_us"] == begin + j * 100000
            assert row["body"]["phase"] == 0
            observed_region = int(row["body"]["x"] >= .5)
            assert row["region"] == observed_region
            next_time = rows[j+1]["time_us"] if j+1 < len(rows) else end
            occupied += (next_time - row["time_us"]) * observed_region
            # Independent displacement using exact constant-force integration.
            vel, command = row["body"]["v"], row["control"]
            terminal = .3 * command / .8
            dx = terminal * .1 + (vel - terminal) * (1 - math.exp(-.08)) / .8
            physical_distance += abs(dx)
            net_displacement += dx
            zero_steps += abs(vel) <= 1e-12 and abs(command) <= 1e-12
            after = rows[j+1]["body"] if j+1 < len(rows) else final["body"]
            close(after["x"], (row["body"]["x"] + dx) % 1., str(p))
            close(after["v"], terminal + (vel-terminal)*math.exp(-.08), str(p))
        close(result["region1"], occupied/(end-begin), str(p))
        close(result["travel_distance"], physical_distance, str(p))
        candidate_key = stage.parent.relative_to(folder).as_posix()
        candidate = all_candidates[candidate_key]
        if stage.name != "development":
            # Body positioning is the only declared assessment intervention.
            parent = r.read(stage.parent / "development/final.json.gz")
            for field in ("core", "session", "supplier", "next_sense", "next_background", "next_motor"):
                assert initial[field] == parent[field], (p, field)
            expected_position = (r.SELECT_STARTS if stage.name.startswith("selection") else r.TEST_STARTS)[int(stage.name.rsplit("-", 1)[1])]
            assert initial["body"] == {"x": expected_position, "v": 0., "phase": 0.}
            assert ancestry["kind"] == "exact-state-assessment-copy" and ancestry["birth_called"] is False
            assert ancestry["parent_whole_hash"] == r.digest(parent)
            snapshots += 1
        else:
            assert int(initial["core"]["time_us"]) == 0
            assert initial["body"]["x"] == r.STARTS[(candidate["index"]+candidate["generation"]) % 4]
            if candidate["parent_id"] is not None:
                parent = r.read(folder / candidate["parent_id"] / "development/final.json.gz")
                assert ancestry["parent_whole_hash"] == r.digest(parent)
                if candidate["blank_control"]:
                    assert ancestry["kind"] == "uninherited-control" and ancestry["birth_called"] is False
                    assert not initial["core"]["nodes"] and not initial["core"]["edges"]
                    assert initial["core"]["config"] == parent["core"]["config"]
                    blanks += 1
                else:
                    expected = r.birth(r.StateImage.from_dict(parent["core"]), decay_age="preserve")
                    assert expected.digest == result["initial_core_hash"]
                    assert ancestry["inheritance_rule"] == "threemind.birth/2"
                    assert ancestry["inheritance_decay_age"] == "preserve"
                    births += 1
        stage_rows.append({"seed": seed, "key": result["key"], "region1": result["region1"],
                           "life": result["life"], "death_us": result["death_us"],
                           "travel_distance": physical_distance, "net_displacement": net_displacement,
                           "zero_motion_steps": zero_steps,
                           "initial_core_hash": result["initial_core_hash"],
                           "final_core_hash": result["final_core_hash"]})
    assert snapshots == 264 and births == blanks == 24
    for key, c in all_candidates.items():
        dev = r.read(folder / key / "development/result.json")
        assert c["development"] == dev
        assert c["candidate_whole_hash"] == dev["final_whole_hash"]
        held = [r.read(folder / key / f"held-{j}/result.json")["region1"] for j in range(4)]
        assert held == c["test_scores"]
        close(np.mean(held), c["test_region1"])
        if not c["blank_control"]:
            scores = [r.read(folder / key / f"selection-{j}/result.json")["region1"] for j in range(2)]
            assert scores == c["selection_scores"]
            close(np.mean(scores), c["selection_region1"])
        candidate_rows.append({"seed": seed, "key": key, "generation": c["generation"],
            "index": c["index"], "parent_id": c["parent_id"], "blank_control": c["blank_control"],
            "selection_region1": c["selection_region1"], "test_region1": c["test_region1"]})
    for decision in pop["decisions"]:
        previous = [all_candidates[key] for key in decision["candidate_ids"]]
        values = [c["selection_region1"] for c in previous]
        assert values == decision["selection_region1"]
        generation = decision["offspring_generation"]
        arm = decision["arm"]
        if arm == "random":
            chosen = random.Random(seed + generation - 1).sample(range(4), 2)
        else:
            order = sorted(range(4), key=lambda i: (values[i] if arm == "region0" else -values[i], i))
            chosen = order[:2]
        assert chosen == decision["selected_indices"]
        assert decision["selected_ids"] == [previous[i]["key"] for i in chosen]
        assert decision["held_out_scores_used"] is False
        for i, child in enumerate(pop["groups"][arm][str(generation)]):
            assert child == all_candidates[child["key"]]
            assert child["parent_id"] == previous[chosen[i//2]]["key"]
            blank = pop["uninherited"][arm][str(generation)][i]
            assert blank == all_candidates[blank["key"]]
            assert blank["parent_id"] == child["parent_id"]
    return pop, {"seed": seed, "stages": 316, "candidates": 52, "exact_assessment_copies": snapshots,
                  "verified_births": births, "blank_controls": blanks, "passed": True}, stage_rows, candidate_rows


def target(candidate, arm):
    value = candidate["test_region1"]
    return 1-value if arm == "region0" else value


def descriptive(values, rng):
    a = np.asarray(values, dtype=float)
    draws = rng.integers(0, len(a), (20000, len(a)))
    low, high = np.percentile(a[draws].mean(axis=1), [2.5, 97.5])
    return {"mean": float(a.mean()), "ci95": [float(low), float(high)], "values": a.tolist()}


def statistics(populations):
    rng = np.random.default_rng(1117177)
    scores, pairs, retention, counts = [], [], [], []
    for pop in populations:
        seed = pop["seed"]
        for arm in ARMS:
            for generation in range(3):
                group = pop["groups"][arm][str(generation)]
                mean = float(np.mean([c["test_region1"] for c in group]))
                blank = pop["uninherited"][arm].get(str(generation))
                scores.append({"seed": seed, "arm": arm, "generation": generation,
                    "region1": mean, "region0": 1-mean,
                    "blank_region1": float(np.mean([c["test_region1"] for c in blank])) if blank else None})
        passed = True
        for arm in ("region0", "region1"):
            for generation in (1, 2):
                previous = {c["key"]: c for c in pop["groups"][arm][str(generation-1)]}
                children = pop["groups"][arm][str(generation)]
                selected = list(dict.fromkeys(c["parent_id"] for c in children))
                qualifying = [k for k in selected if target(previous[k], arm) >= .55]
                eligible = [c for c in children if c["parent_id"] in qualifying]
                retained = sum(target(c, arm) >= .55 for c in eligible)
                rate = retained/len(eligible) if eligible else None
                cell_pass = bool(qualifying) and rate >= .75
                passed = passed and cell_pass
                retention.append({"seed": seed, "arm": arm, "offspring_generation": generation,
                    "qualifying_selected_parents": len(qualifying), "eligible_children": len(eligible),
                    "retained_children": retained, "retention_rate": rate, "passed": cell_pass})
                for c in children:
                    pairs.append({"seed": seed, "arm": arm, "generation": generation,
                        "parent": c["parent_id"], "child": c["key"],
                        "parent_target": target(previous[c["parent_id"]], arm), "child_target": target(c, arm),
                        "parent_qualifies": c["parent_id"] in qualifying})
        counts.append({"seed": seed, "passed": bool(passed)})
    score_lookup = {(s["seed"], s["arm"], s["generation"]): s for s in scores}
    tests = []
    for hypothesis in ("H2", "H3", "H4"):
        for arm in ("region0", "region1"):
            for generation in ((1, 2) if hypothesis == "H3" else (2,)):
                differences = []
                for pop in populations:
                    seed = pop["seed"]
                    cur = score_lookup[seed, arm, generation]
                    if hypothesis == "H2":
                        other = score_lookup[seed, "random", generation][arm]
                    elif hypothesis == "H3":
                        other = score_lookup[seed, arm, generation-1][arm]
                    else:
                        other = 1-cur["blank_region1"] if arm == "region0" else cur["blank_region1"]
                    differences.append(cur[arm]-other)
                positive = sum(x > 1e-12 for x in differences)
                negative = sum(x < -1e-12 for x in differences)
                n = positive+negative
                p = float(binomtest(positive, n, .5, alternative="greater").pvalue) if n else 1.
                tests.append({"hypothesis": hypothesis, "arm": arm, "generation": generation,
                    **descriptive(differences, rng), "positive": positive, "negative": negative,
                    "ties": len(differences)-n, "p_raw": p})
    order = sorted(range(8), key=lambda i: tests[i]["p_raw"])
    running = 0.
    for rank, i in enumerate(order):
        running = max(running, min(1., (8-rank)*tests[i]["p_raw"]))
        tests[i]["p_holm"] = running
        tests[i]["passed"] = tests[i]["mean"] >= .01 and running <= .05
    successes = sum(x["passed"] for x in counts)
    ci = binomtest(successes, len(populations)).proportion_ci(method="exact")
    trajectories = []
    for arm in ARMS:
        for direction in ("region0", "region1"):
            for generation in range(3):
                values = [score_lookup[p["seed"], arm, generation][direction] for p in populations]
                trajectories.append({"arm": arm, "direction": direction, "generation": generation,
                                     **descriptive(values, rng)})
    total_change = []
    for arm in ("region0", "region1"):
        values = [score_lookup[p["seed"], arm, 2][arm]-score_lookup[p["seed"], arm, 0][arm] for p in populations]
        total_change.append({"arm": arm, **descriptive(values, rng)})
    analysis = {"schema": "artificial-selection63/analysis/1", "independent_n": len(populations),
        "H1": {"passed_populations": successes, "total_populations": len(populations),
               "proportion": successes/len(populations), "ci95": [ci.low, ci.high],
               "required_populations": 4, "passed": successes >= 4, "populations": counts},
        "hypotheses": {h: all(t["passed"] for t in tests if t["hypothesis"] == h) for h in ("H2", "H3", "H4")},
        "tests": tests, "trajectories": trajectories, "G2_minus_G0": total_change}
    return analysis, scores, pairs, retention


def main(work):
    assert r.read(work / "science-complete.json")["populations"] == 16
    destination = work / "analysis-v1"
    populations, audits, stages, candidates = [], [], [], []
    for seed in r.SEEDS:
        pop, audit, rows, people = audit_population(work / "populations" / str(seed))
        populations.append(pop)
        audits.append(audit)
        stages.extend(rows)
        candidates.extend(people)
        print(f"audited {seed}: 316 stages", flush=True)
    analysis, scores, pairs, retention = statistics(populations)
    r.save(destination / "analysis.json", analysis)
    r.save(destination / "audit.json", {"passed": True, "populations": audits,
        "stage_count": len(stages), "candidate_count": len(candidates),
        "dead_stages": [s for s in stages if s["life"] == "dead"]})
    for name, rows in (("stages", stages), ("candidates", candidates), ("population-scores", scores),
                       ("parent-child", pairs), ("retention", retention)):
        write_csv(destination / (name+".csv"), rows)
    print({"H1": analysis["H1"], "hypotheses": analysis["hypotheses"]}, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, default=WORK)
    args = parser.parse_args()
    main(args.work.resolve())
