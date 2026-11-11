"""Read-only E26 aggregation. Descriptive process checks are not new primary tests."""

import gzip
import json
import math
import statistics
from collections import defaultdict

from experiment import WORK


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def mean(rows):
    return statistics.mean(rows)


def rms(a, b):
    assert len(a) == len(b)
    return math.sqrt(mean([(x - y) ** 2 for x, y in zip(a, b)]))


def analyze():
    target = WORK / "analysis"
    target.mkdir(exist_ok=True)
    robot_rows = [read(p) for p in sorted((WORK / "cases/robot").rglob("result.json"))]
    assert len(robot_rows) == 108 and all(r["completed"] for r in robot_rows)
    groups = defaultdict(list)
    episodes = []
    for row in robot_rows:
        if "/test-" not in row["key"]:
            continue
        samples, inside = 0, 0
        with gzip.open(WORK / "cases" / row["key"] / "events.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                event = json.loads(line)
                samples += 1
                inside += event["observation"]["task_metrics"]["task_distance"] <= 0.05
        assert samples == 400
        item = {
            "condition": row["condition"],
            "seed": row["seed"],
            "environment_seed": row["environment_seed"],
            **row["metrics"],
            "within_target_seconds": inside * 0.01,
        }
        groups[row["condition"]].append(item)
        episodes.append(item)
    aggregated = {}
    for name, rows in groups.items():
        aggregated[name] = {
            "episodes": len(rows),
            "final_distance_m": mean([r["task_distance"] for r in rows]),
            "best_distance_m": mean([r["task_best_distance"] for r in rows]),
            "distance_improvement_m": mean([r["task_distance_improvement"] for r in rows]),
            "ever_reached": sum(r["task_success"] for r in rows),
            "end_inside": sum(r["task_distance"] <= 0.05 for r in rows),
            "mean_time_inside_s": mean([r["within_target_seconds"] for r in rows]),
            "work_j": mean([r["task_mechanical_work_j"] for r in rows]),
            "by_wiring_seed_m": {
                str(seed): mean([r["task_distance"] for r in rows if r["seed"] == seed])
                for seed in sorted({r["seed"] for r in rows})
            },
        }
    selected_pairs = []
    for row in groups["selected"]:
        blank = next(
            r for r in groups["blank"] if (r["seed"], r["environment_seed"]) == (row["seed"], row["environment_seed"])
        )
        selected_pairs.append(blank["task_distance"] - row["task_distance"])
    robot = {
        "all_episodes": len(robot_rows),
        "episode_wall_seconds": sum(r["wall_seconds"] for r in robot_rows),
        "conditions": aggregated,
        "selected_better_than_blank_pairs": sum(v > 0 for v in selected_pairs),
        "selected_minus_blank_improvement_m": mean(selected_pairs),
        "selection": [read(p) for p in sorted(WORK.glob("selection-*.json"))],
        "episodes": episodes,
    }
    languages = {}
    for route in ("text", "scratch"):
        base = WORK / "language" / route
        probes = read(base / "probes.json")
        by_kind = defaultdict(dict)
        for row in probes:
            by_kind[row["condition"]][row["cue"]] = row
        comparisons = {}
        for kind in ("reversed", "blank", "exchanged", "shuffled", "constant", "transformer_only"):
            comparisons[kind] = {
                "decoded_changed": sum(
                    r["output"].get("text") != by_kind["ordinary"][cue]["output"].get("text")
                    for cue, r in by_kind[kind].items()
                )
            }
            if kind in ("reversed", "blank"):
                comparisons[kind]["process_feature_rms_by_cue"] = {
                    cue: rms(r["raw"]["process"]["features"], by_kind["ordinary"][cue]["raw"]["process"]["features"])
                    for cue, r in by_kind[kind].items()
                }
        languages[route] = read(base / "summary.json") | {
            "comparisons_against_ordinary": comparisons,
            "calibration": [
                {"expected": r["expected"], "decoded": r["output"].get("text")} for r in read(base / "calibration.json")
            ],
            "responses": [
                {
                    "condition": r["condition"],
                    "cue": r["cue"],
                    "expected": r["expected"],
                    "decoded": r["output"].get("text"),
                    "status": r["output"]["status"],
                }
                for r in probes
            ],
            "training": read(base / "training.json"),
            "censored_probes": sum(r.get("raw", {}).get("process", {}).get("censored", False) for r in probes),
        }
    result = {
        "schema": "threemind.robot-language-pilot-analysis/1",
        "robot": robot,
        "language": languages,
        "note": "Only means and matched descriptive differences; no independent-sample significance claim. "
        "Time in target and process-feature RMS are post-execution descriptive checks, not replacements for registered outcomes.",
    }
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    file = target / "summary.json"
    if file.exists():
        assert file.read_bytes() == encoded, "existing analysis differs; append a revision"
    else:
        file.write_bytes(encoded)
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    names = ["blank", "trained", "selected", "frozen", "random", "position", "skill"]
    fig, ax = plt.subplots(figsize=(9, 4.3), layout="constrained")
    ax.bar(names, [aggregated[n]["final_distance_m"] for n in names], color="#3a887b", alpha=0.75)
    for index, name in enumerate(names):
        ys = list(aggregated[name]["by_wiring_seed_m"].values())
        ax.scatter([index - 0.15 + n * 0.1 for n in range(len(ys))], ys, color="#233c38", s=23, zorder=3)
    ax.axhline(0.05, color="#bd743d", linestyle="--", linewidth=1, label="5 cm target radius")
    ax.set(
        ylabel="Final target distance (m), lower is better", title="E26: four wiring seeds, three unseen targets each"
    )
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(target / "robot-distance.png", dpi=170)
    plt.close(fig)
    print(
        json.dumps(
            {
                "robot": aggregated,
                "language": {
                    k: {
                        "scores": v["scores"],
                        "calibration": v["calibration"],
                        "comparisons": v["comparisons_against_ordinary"],
                    }
                    for k, v in languages.items()
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    analyze()
