"""Frozen seed-block analysis of retained calibration measurements. No Core execution."""

import csv
import hashlib
import json
import statistics
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from run import HERE, META, WORK, encoded

from threemind_lab.statistics import compare_pairs


def load(phase):
    meta = json.loads(META.read_bytes())
    return json.loads((WORK / meta["completed_phases"][phase]).read_bytes())


def memory_score(case):
    m = case["measurement"]
    pairs = case["pairs"]
    values = []
    for cue, target in pairs:
        r = next(r for r in m["rows"] if r["cue"] == cue)
        foil = next(w for c, w in pairs if c != cue)
        a, b = r["net_endpoint"][target], r["net_endpoint"][foil]
        values.append(a - b if a is not None and b is not None else None)
    return statistics.mean(values) if all(v is not None for v in values) else None


def relation_score(case):
    a, b, c, d, e, z = case["names"]
    rows = {r["cue"]: r for r in case["measurement"]["rows"]}
    values = []
    for grand, father, child in [(a, b, c), (d, e, z)]:
        r, s = rows[child + "的爷爷"]["net_endpoint"], rows[child + "的父亲"]["net_endpoint"]
        v = [r[grand], r[father], s[grand], s[father]]
        values.append(v[0] - v[1] - v[2] + v[3] if all(x is not None for x in v) else None)
    return statistics.mean(values) if all(v is not None for v in values) else None


def relation_diagnostics(cases):
    """Descriptive only: dominance of the canonical name, never answer accuracy."""
    groups = defaultdict(list)
    for case in cases:
        a, b, c, d, e, z = case["names"]
        rows = {r["cue"]: r for r in case["measurement"]["rows"]}
        for grand, father, child in [(a, b, c), (d, e, z)]:
            for suffix, target in [("的爷爷", grand), ("的父亲", father), ("", grand)]:
                values = rows[child + suffix]["net_endpoint"]
                available = all(v is not None for v in values.values())
                groups[(case["arm"], suffix)].append(
                    (values[target] - max(v for name, v in values.items() if name != target)) if available else None
                )
    return [
        {
            "arm": arm,
            "query": suffix or "bare name",
            "cases": len(values),
            "unscorable": sum(v is None for v in values),
            "strict_canonical_target_dominance": sum(v is not None and v > 0 for v in values),
            "ties_at_maximum": sum(v == 0 for v in values),
            "mean_target_minus_strongest_other": statistics.mean([v for v in values if v is not None])
            if any(v is not None for v in values)
            else None,
        }
        for (arm, suffix), values in groups.items()
    ]


def blocks(rows, expected):
    values = defaultdict(list)
    for r in rows:
        values[r["seed"]].append(r["score"])
    return {
        s: statistics.mean(v) if len(v) == expected and all(x is not None for x in v) else None
        for s, v in values.items()
    }


def compare(control, treatment, name):
    return compare_pairs(
        [
            {"seed": s, "control": {name: control.get(s)}, "treatment": {name: treatment.get(s)}}
            for s in sorted(set(control) | set(treatment))
        ],
        seed=20260909,
        resamples=5000,
    )


def descriptive(values):
    valid = [v for v in values.values() if v is not None]
    return {
        "seed_count": len(valid),
        "unscorable_seed_count": len(values) - len(valid),
        "mean": statistics.mean(valid) if valid else None,
        "minimum": min(valid) if valid else None,
        "maximum": max(valid) if valid else None,
        "seed_values": values,
    }


def analyze():
    memory, relations = load("memory"), load("relations")
    for r in memory["rows"]:
        r["score"] = memory_score(r)
    for r in relations["rows"]:
        r["score"] = relation_score(r)
    main = [r for r in memory["rows"] if r["mode"] == "anonymous-distributed" and r["n"] == 12]
    arms = {
        arm: blocks([r for r in main if r["arm"] == arm], 15) for arm in ["paired", "mixed", "swapped", "learning_off"]
    }
    relation_arms = {
        arm: blocks([r for r in relations["rows"] if r["arm"] == arm], 4)
        for arm in ["correct", "wrong_template", "reversed_chain"]
    }
    analyses = {
        "memory": compare(arms["mixed"], arms["paired"], "pair_specific_activation"),
        "relations": compare(relation_arms["wrong_template"], relation_arms["correct"], "query_role_specificity"),
    }
    ordered = sorted(
        [v["metrics"][0] for v in analyses.values() if v["metrics"][0]["p"] is not None], key=lambda r: r["p"]
    )
    correction = 0
    for i, r in enumerate(ordered):
        correction = max(correction, min(1, r["p"] * (len(ordered) - i)))
        r["p_holm"] = correction
    for v in analyses.values():
        v["unit"] = "encoding seed blocks; all declared within-seed cells required; no sample/probe pseudoreplication"
        v["inference"] = (
            "two predeclared primary contrasts, Holm correction across both; conditional on fixed materials"
        )
    grids = []
    for mode, n in [("anonymous-distributed", 12), ("anonymous-distributed", 4), ("literal-character", 12)]:
        selected = [r for r in memory["rows"] if r["mode"] == mode and r["n"] == n]
        for v in sorted({r["vocab"] for r in selected}):
            for gap in sorted({r["gap_us"] for r in selected}):
                data = {
                    a: blocks([r for r in selected if r["vocab"] == v and r["gap_us"] == gap and r["arm"] == a], 1)
                    for a in sorted({r["arm"] for r in selected})
                }
                cmp = compare(data["mixed"], data["paired"], "pair_specific_activation")["metrics"][0]
                cmp.pop("p")
                cmp.pop("p_holm")
                grids.append(
                    {
                        "mode": mode,
                        "repetitions": n,
                        "vocab": v,
                        "gap_s": gap / 1e6,
                        "comparison": cmp,
                        "arms": {a: descriptive(v) for a, v in data.items()},
                    }
                )
    family = []
    for f in range(4):
        data = {
            a: blocks([r for r in relations["rows"] if r["family"] == f and r["arm"] == a], 1) for a in relation_arms
        }
        cmp = compare(data["wrong_template"], data["correct"], "query_role_specificity")["metrics"][0]
        cmp.pop("p")
        cmp.pop("p_holm")
        family.append({"family": f, "comparison": cmp, "arms": {a: descriptive(v) for a, v in data.items()}})
    counts = {
        phase: {
            "training_cases": len(data["rows"]),
            "probe_copies": sum(len(r["measurement"]["rows"]) for r in data["rows"]),
            "unscorable_training_cases": sum(r["score"] is None for r in data["rows"]),
            "elapsed_s": data["elapsed_s"],
            "peak_rss": data["peak_rss"],
        }
        for phase, data in [("memory", memory), ("relations", relations)]
    }
    measurement = {}
    for phase, data in [("memory", memory), ("relations", relations)]:
        rows = [p for r in data["rows"] for p in r["measurement"]["rows"] if p["cue"]]
        measurement[phase] = {
            "nonzero_deliveries": sum(r["delivered_signal_amount"] > 0 for r in rows),
            "probes": len(rows),
            "peak_saturated_fraction": max(r["max_saturated_fraction"] for r in rows),
            "minimum_exclusive_channels": min(
                v["exclusive_channels"] for r in data["rows"] for v in r["measurement"]["mapping"]["coverage"].values()
            ),
        }
    summary = {
        "analyses": analyses,
        "memory_arms": {a: descriptive(v) for a, v in arms.items()},
        "relation_arms": {a: descriptive(v) for a, v in relation_arms.items()},
        "relation_diagnostics_descriptive": relation_diagnostics(relations["rows"]),
        "memory_grid": grids,
        "relation_families": family,
        "counts": counts,
        "measurement": measurement,
        "decision": json.loads((HERE / "calibration-decision.json").read_bytes()),
        "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in WORK.glob("*-results.json")},
    }
    (HERE / "summary.json").write_bytes(encoded(summary) + b"\n")
    for phase, data in [("memory", memory), ("relations", relations)]:
        fields = (
            ["seed", "arm", "score", "mode", "n", "vocab", "gap_us"]
            if phase == "memory"
            else ["seed", "arm", "score", "family", "names"]
        )
        with (HERE / f"{phase}-cases.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields + ["run_id", "calibration_id", "source_hash"])
            writer.writeheader()
            for r in data["rows"]:
                writer.writerow(
                    {k: r.get(k) for k in fields}
                    | {
                        "run_id": r["measurement"]["run_id"],
                        "calibration_id": r["measurement"]["id"],
                        "source_hash": r["measurement"]["source_hash"],
                    }
                )
    plot(summary)
    return summary


def plot(summary):
    plt.rcParams.update(
        {"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False}
    )
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), layout="constrained")
    matrix = np.array(
        [
            [
                next(
                    g
                    for g in summary["memory_grid"]
                    if g["mode"] == "anonymous-distributed"
                    and g["repetitions"] == 12
                    and g["vocab"] == v
                    and g["gap_s"] == gap
                )["comparison"]["difference"]
                for gap in [0.4, 0.8, 1.6]
            ]
            for v in range(5)
        ],
        dtype=float,
    )
    lim = max(abs(matrix).max(), 1e-8)
    im = axes[0].imshow(matrix, cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
    axes[0].set(
        xticks=range(3),
        xticklabels=["0.4 s", "0.8 s", "1.6 s"],
        yticks=range(5),
        yticklabels=[f"Vocabulary {i + 1}" for i in range(5)],
        title="Paired minus mixed: 12 encoding seeds",
    )
    for i in range(5):
        for j in range(3):
            axes[0].text(
                j,
                i,
                f"{matrix[i, j]:.1e}",
                ha="center",
                va="center",
                color="white" if abs(matrix[i, j]) > 0.6 * lim else "black",
            )
    fig.colorbar(im, ax=axes[0], label="Net target-minus-foil activation (a.u.)", shrink=0.8)
    arms = list(summary["memory_arms"])
    for i, a in enumerate(arms):
        values = list(summary["memory_arms"][a]["seed_values"].values())
        axes[1].scatter(np.full(len(values), i), values, alpha=0.65, color="#237969")
        axes[1].plot([i - 0.22, i + 0.22], [summary["memory_arms"][a]["mean"]] * 2, color="black", lw=2)
    axes[1].axhline(0, color="grey", lw=0.7)
    axes[1].set(
        xticks=range(4),
        xticklabels=["Paired", "Mixed", "Swapped", "Learning off"],
        title="One dot per seed\nAll words and gaps averaged",
        ylabel="Original-pair activation contrast (a.u.)",
    )
    axes[1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    fig.savefig(HERE / "memory-results.png", dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), layout="constrained")
    for i, (a, values) in enumerate(summary["relation_arms"].items()):
        v = [x for x in values["seed_values"].values() if x is not None]
        axes[0].scatter(np.full(len(v), i), v, color="#566fac", alpha=0.7)
        if v:
            axes[0].plot([i - 0.2, i + 0.2], [statistics.mean(v)] * 2, color="black", lw=2)
    axes[0].set(
        xticks=range(3),
        xticklabels=["Correct", "Wrong template", "Reversed chain"],
        title="Role specificity\nIndependent new-name families",
        ylabel="Grandfather-vs-father query interaction (a.u.)",
    )
    for i, g in enumerate(summary["relation_families"]):
        r = g["comparison"]
        if r["difference"] is None:
            continue
        axes[1].plot([i, i], r["ci95"], color="#566fac", lw=2)
        axes[1].scatter([i], [r["difference"]], color="#566fac")
    axes[1].set(
        xticks=range(4),
        xticklabels=[f"Name set {i + 1}" for i in range(4)],
        title="Correct minus wrong template\nSeed bootstrap 95% CI",
    )
    for ax in axes:
        ax.axhline(0, color="grey", lw=0.7)
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    fig.savefig(HERE / "relation-results.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    result = analyze()
    print(encoded({k: v["metrics"] for k, v in result["analyses"].items()}).decode())
