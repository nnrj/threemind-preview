"""Derive tables/figures from retained measurements, never from display labels."""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from threemind_lab.statistics import compare_pairs

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2] / ".work" / "memory-relations-20260909"


def load(phase):
    return json.loads((WORK / f"{phase}-results.json").read_text(encoding="utf-8"))


def block_means(rows, value="contrast"):
    groups = defaultdict(list)
    for row in rows:
        if row[value] is not None:
            groups[row["seed"]].append(row[value])
    return {seed: statistics.mean(values) for seed, values in groups.items()}


def paired(control, treatment, endpoint, *, inferential=False):
    seeds = sorted(set(control) | set(treatment))
    result = compare_pairs(
        [
            {"seed": seed, "control": {endpoint: control.get(seed)}, "treatment": {endpoint: treatment.get(seed)}}
            for seed in seeds
        ],
        seed=20260909,
        resamples=5000,
    )
    if not inferential:
        for row in result["metrics"]:
            row.update(ci95=None, paired_dz=None, p=None, p_holm=None)
    result["unit"] = "encoder-seed blocks; cues are averaged within a block"
    result["inference"] = (
        "predeclared anonymous primary endpoint"
        if inferential
        else "descriptive only; no small-sample significance claim"
    )
    return result


def analyze():
    memory, relations, sensitivity = (load(p) for p in ("memory", "relations", "sensitivity"))
    analyses, table = {}, []
    for mode in ("anonymous-distributed", "literal-character"):
        for route in ("birth", "live"):
            for n in (0, 1, 4, 12):
                for arm in ("paired", "mixed", "swapped", "learning_off"):
                    rows = [
                        r
                        for r in memory["rows"]
                        if (r["mode"], r["route"], r["repetitions"], r["arm"]) == (mode, route, n, arm)
                    ]
                    if not rows:
                        continue
                    values = block_means(rows)
                    table.append(
                        {
                            "family": "memory",
                            "mode": mode,
                            "route": route,
                            "repetitions": n,
                            "arm": arm,
                            "seed_count": len(values),
                            "mean": statistics.mean(values.values()) if values else None,
                            "minimum_seed_mean": min(values.values()) if values else None,
                            "maximum_seed_mean": max(values.values()) if values else None,
                            "seed_values": values,
                        }
                    )
    for route in ("birth", "live"):
        control = block_means(
            [
                r
                for r in memory["rows"]
                if r["mode"] == "anonymous-distributed"
                and r["route"] == route
                and r["repetitions"] == 12
                and r["arm"] == "mixed"
            ]
        )
        treatment = block_means(
            [
                r
                for r in memory["rows"]
                if r["mode"] == "anonymous-distributed"
                and r["route"] == route
                and r["repetitions"] == 12
                and r["arm"] == "paired"
            ]
        )
        analyses[f"anonymous_{route}"] = paired(
            control, treatment, f"memory.anonymous.{route}.repeat12", inferential=True
        )
    for n in (1, 4, 12):
        control = block_means(
            [
                r
                for r in memory["rows"]
                if r["mode"] == "literal-character"
                and r["route"] == "birth"
                and r["repetitions"] == n
                and r["arm"] == "mixed"
            ]
        )
        treatment = block_means(
            [
                r
                for r in memory["rows"]
                if r["mode"] == "literal-character"
                and r["route"] == "birth"
                and r["repetitions"] == n
                and r["arm"] == "paired"
            ]
        )
        analyses[f"literal_{n}"] = paired(control, treatment, f"memory.literal.birth.repeat{n}")
    for dose in (2, 4):
        for arm in ("paired", "mixed", "swapped", "learning_off"):
            values = block_means([r for r in sensitivity["rows"] if r["intensity"] == dose and r["arm"] == arm])
            table.append(
                {
                    "family": "sensitivity",
                    "intensity": dose,
                    "arm": arm,
                    "seed_count": len(values),
                    "mean": statistics.mean(values.values()),
                    "seed_values": values,
                }
            )
        control = block_means([r for r in sensitivity["rows"] if r["intensity"] == dose and r["arm"] == "mixed"])
        treatment = block_means([r for r in sensitivity["rows"] if r["intensity"] == dose and r["arm"] == "paired"])
        analyses[f"dose_{dose}"] = paired(control, treatment, f"sensitivity.anonymous.intensity{dose}")

    relation_rows = []
    for r in relations["rows"]:
        end = r["query"][0]
        target, father, foil = ("X", "Y", "U") if end == "Z" else ("U", "V", "X")
        scores = r["probe"]["scores"]
        valid = scores is not None and all(v is not None for v in scores.values())
        relation_rows.append(
            {
                "seed": r["seed"],
                "arm": r["arm"],
                "query": r["query"],
                "target": target,
                "target_score": scores[target] if scores else None,
                "father_score": scores[father] if scores else None,
                "unrelated_score": scores[foil] if scores else None,
                "target_minus_unrelated": scores[target] - scores[foil] if valid else None,
                "grandfather_minus_father": scores[target] - scores[father] if valid else None,
                "strict_grandfather_winner": valid
                and scores[target] > 1e-9
                and all(scores[target] > v + 1e-9 for w, v in scores.items() if w != target),
                "probe_run_id": r["probe"]["info"]["run_id"],
            }
        )
    control = block_means(
        [r for r in relation_rows if r["arm"] == "wrong_template" and r["query"].endswith("爷爷")],
        "target_minus_unrelated",
    )
    treatment = block_means(
        [r for r in relation_rows if r["arm"] == "correct" and r["query"].endswith("爷爷")], "target_minus_unrelated"
    )
    analyses["relations"] = paired(control, treatment, "relations.correct_vs_wrong_template")
    corrected = 0.0
    ordered = sorted(("anonymous_birth", "anonymous_live"), key=lambda k: analyses[k]["metrics"][0]["p"])
    for rank, key in enumerate(ordered):
        analyses[key]["multiple_testing_family"] = ["anonymous_birth", "anonymous_live"]
        corrected = max(corrected, min(1, analyses[key]["metrics"][0]["p"] * (2 - rank)))
        analyses[key]["metrics"][0]["p_holm"] = corrected

    result = {
        "memory_and_sensitivity": table,
        "relations": relation_rows,
        "analyses": analyses,
        "resource_usage": [
            {
                k: p.get(k)
                for k in ("phase", "elapsed_s", "peak_rss_bytes", "checkpoint_bytes", "estimated_project_db_bytes")
            }
            for p in (memory, relations, sensitivity)
        ],
        "completed_models": sum(len(load(p)["runs"]) for p in ("pilot-02", "memory", "relations", "sensitivity")),
    }
    (HERE / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, rows in (("memory", table), ("relations", relation_rows)):
        keys = sorted(set().union(*(r.keys() for r in rows)))
        with (HERE / f"{name}-summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, keys)
            writer.writeheader()
            writer.writerows({k: json.dumps(v) if isinstance(v, dict) else v for k, v in r.items()} for r in rows)
    plot(table, relation_rows)
    return result


def plot(table, relation_rows):
    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False}
    )
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), layout="constrained")
    colors = {"paired": "#16766b", "mixed": "#888b97", "swapped": "#b56a41", "learning_off": "#c84870"}
    for index, mode in enumerate(("literal-character", "anonymous-distributed")):
        ax = axes[index]
        for arm in ("paired", "mixed", "swapped"):
            rows = [
                r
                for r in table
                if r["family"] == "memory"
                and r["mode"] == mode
                and r["route"] == "birth"
                and r["arm"] == arm
                and r["repetitions"] > 0
            ]
            ax.plot([r["repetitions"] for r in rows], [r["mean"] for r in rows], "o-", color=colors[arm], label=arm)
        ax.axhline(0, color="#bbb", linewidth=0.8)
        ax.set(
            xlabel="Training repetitions",
            ylabel="Target-minus-foil activation (a.u.)",
            title=("Literal control (2 seed blocks)" if index == 0 else "Anonymous default (8 seed blocks)"),
            xticks=[1, 4, 12],
        )
        ax.legend(fontsize=8)
    ax = axes[2]
    for arm in ("paired", "mixed", "swapped", "learning_off"):
        rows = [r for r in table if r["family"] == "sensitivity" and r["arm"] == arm]
        ax.plot([1, 2, 4], [0] + [r["mean"] for r in rows], "o-", color=colors[arm], label=arm)
        for r in rows:
            ax.scatter(
                [r["intensity"]] * len(r["seed_values"]),
                list(r["seed_values"].values()),
                s=14,
                color=colors[arm],
                alpha=0.6,
            )
    ax.set(
        xlabel="Probe intensity (training unchanged)", title="Anonymous sensitivity (2 seed blocks)", xticks=[1, 2, 4]
    )
    ax.axhline(0, color="#bbb", linewidth=0.8)
    ax.legend(fontsize=8)
    for axis in axes:
        axis.set_ylim(-0.017, 0.017)
    fig.suptitle("Learned association: inherited structure, activity cleared before cue; no Core changes", fontsize=12)
    fig.savefig(HERE / "memory-results.png", dpi=170)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8.5, 3.8), layout="constrained")
    groups = [(seed, q) for seed in (41203, 41204) for q in ("Z的爷爷", "W的爷爷")]
    for offset, arm in enumerate(("correct", "wrong_template", "reversed_chain")):
        values = [
            next(
                r["target_minus_unrelated"]
                for r in relation_rows
                if r["seed"] == seed and r["query"] == q and r["arm"] == arm
            )
            for seed, q in groups
        ]
        ax.bar([i + (offset - 1) * 0.23 for i in range(4)], values, width=0.23, label=arm)
    ax.set_xticks(range(4), [f"{seed}: {q[0]} grandfather" for seed, q in groups])
    ax.axhline(0, color="#aaa", linewidth=0.8)
    ax.set(
        ylabel="Grandfather-minus-unrelated score (a.u.)",
        title="No demonstrated role-specific composition in this small exploration",
    )
    ax.legend(fontsize=8)
    fig.savefig(HERE / "relation-results.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=WORK, help="Retained phase results directory")
    parser.add_argument("--output-dir", type=Path, default=HERE, help="Derived tables and figures directory")
    args = parser.parse_args()
    WORK, HERE = args.input_dir.resolve(), args.output_dir.resolve()
    HERE.mkdir(parents=True, exist_ok=True)
    result = analyze()
    print(
        json.dumps(
            {
                "completed_models": result["completed_models"],
                "analysis_endpoints": len(result["analyses"]),
                "correct_template_target_winners_descriptive": sum(
                    r["strict_grandfather_winner"]
                    for r in result["relations"]
                    if r["arm"] == "correct" and r["query"].endswith("爷爷")
                ),
            }
        )
    )
