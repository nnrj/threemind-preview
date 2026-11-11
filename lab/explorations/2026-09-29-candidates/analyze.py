"""Descriptive, unit-aware summaries. Missing primary evidence is never zero."""

import argparse
import statistics
from collections import Counter, defaultdict

from common import KERNELS, WORK, new_json, read_json


def advantage(row, field, expected=None):
    values = row.get(field)
    if values is None:
        return None
    expected = str(row["expected"] if expected is None else expected)
    return values.get(expected, 0.0) - max((v for k, v in values.items() if k != expected), default=0.0)


def summarize(values):
    values = [v for v in values if v is not None]
    return {
        "n": len(values),
        "median": statistics.median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def analyze(partial=False):
    blocks = sorted(WORK.glob("block-*.json"))
    if len(blocks) != 6 and not partial:
        raise RuntimeError("six formal blocks have not completed")
    rows = [r for p in blocks for r in read_json(p)]
    grouped = defaultdict(list)
    for r in rows:
        if r["kind"] == "pair":
            key = (r["kind"], r["kernel"], r["background"], r["condition"], r["hold_us"])
        elif r["kind"] == "sequence":
            key = (r["kind"], r["kernel"], r["background"], r["overlap"], r["swap"])
        else:
            key = (r["kind"], r["kernel"], r["background"], r["variant"], r.get("hold_us", 0))
        grouped[key].append(r)
    groups = []
    for key, rs in grouped.items():
        item = {"condition": key, "n": len(rs), "blocks": sorted({r["block"] for r in rs})}
        if key[0] in ("pair", "sequence"):
            observed = [r for r in rs if r["classification"] != "not_observed"]
            item |= {
                "classification": dict(Counter(r["classification"] for r in rs)),
                "primary_margin": summarize([advantage(r, "primary") for r in rs]),
                "primary_strict_wins": sum(advantage(r, "primary") > 1e-9 for r in rs if r["primary"] is not None),
                "secondary_peak_margin": summarize([advantage(r, "peak_activation") for r in observed]),
                "secondary_observed_count": len(observed),
                "secondary_peak_strict_wins": sum(advantage(r, "peak_activation") > 1e-9 for r in observed),
                "death_before_probe": sum(r["life_at_probe"] == "dead" for r in rs),
                "probe_spikes": summarize([r.get("probe_spikes_delta") for r in rs]),
            }
            if key[0] == "pair" and key[3] == "remapped":
                item["new_target_primary_margin"] = summarize([advantage(r, "primary", r["new_expected"]) for r in rs])
                item["new_target_peak_margin"] = summarize(
                    [advantage(r, "peak_activation", r["new_expected"]) for r in observed]
                )
            # One favored target can score 1/4 or 1/2 without cue discrimination.
            contrasts = {"primary": [], "peak_activation": []}
            for block in item["blocks"]:
                block_rows = [r for r in rs if r["block"] == block]
                for field, values in contrasts.items():
                    if any(r[field] is None or r["classification"] == "not_observed" for r in block_rows):
                        continue
                    matched, unmatched = [], []
                    for row in block_rows:
                        target = str(row["expected"])
                        matched.append(row[field].get(target, 0.0))
                        unmatched.extend(v for k, v in row[field].items() if k != target)
                    values.append(
                        {
                            "block": block,
                            "matched_minus_other": statistics.mean(matched) - statistics.mean(unmatched),
                        }
                    )
            item["cue_contrasts"] = contrasts
        else:
            values = []
            for r in rs:
                pulses = r["pulses"]
                if not pulses:
                    continue
                field = "sent_na" if key[1].endswith("lif/1") else "sent"
                delta = lambda p, field=field: p["transport_after"][field] - p["transport_before"][field]
                values.append(
                    {
                        "block": r["block"],
                        "pulses": len(pulses),
                        "first_peak": pulses[0]["peak_mean"],
                        "last_peak": pulses[-1]["peak_mean"],
                        "first_sent": delta(pulses[0]),
                        "last_sent": delta(pulses[-1]),
                        "emission_series": [delta(p) for p in pulses],
                        "first_spikes": pulses[0]["spikes_delta"],
                        "last_spikes": pulses[-1]["spikes_delta"],
                    }
                )
            item["measurements"] = values
            item["transport_unit"] = "nA" if key[1].endswith("lif/1") else "activation impulse"
        groups.append(item)
    tf = read_json(WORK / "transformer-results.json")
    probabilities = [p["probabilities"][expected] for r in tf for p, expected in zip(r["predictions"], r["expected"])]
    report = {
        "schema": "threemind.candidate-exploration-summary/1",
        "complete_blocks": len(blocks),
        "rows": len(rows),
        "groups": groups,
        "calibration": read_json(WORK / "frozen.json"),
        "transformer": {
            "models": len(tf),
            "target_probability": summarize(probabilities),
            "steps": sorted({r["training"]["steps_completed"] for r in tf}),
            "devices": sorted({r["training"]["device"] for r in tf}),
            "core_feedback": False,
            "frequency_baselines": {"raw_corpus_target_frequency": 1 / 6, "next_label_target_frequency": 1 / 4},
            "peak_rss_bytes": max(r["training"]["peak_rss_bytes"] for r in tf),
            "claim": "Rehearsed two-context discrimination only; no held-out rule/generalization test.",
        },
    }
    if partial:
        print(report["complete_blocks"], report["rows"], report["transformer"])
    else:
        new_json(WORK / "summary.json", report)
        plots(report)
        print(f"Analyzed {len(blocks)} blocks, {len(rows)} outcomes.")
    return report


def plots(report):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout="constrained")
    for i, kernel in enumerate(KERNELS):
        groups = [
            g
            for g in report["groups"]
            if g["condition"][0] == "adaptation" and g["condition"][1] == kernel and not g["condition"][2]
        ]
        for g in groups:
            traces = [r["emission_series"] for r in g["measurements"]]
            if traces:
                means = [statistics.mean(t[j] for t in traces if len(t) > j) for j in range(max(map(len, traces)))]
                axes[0, i].plot(range(1, len(means) + 1), means, marker="o", markersize=3, label=g["condition"][3])
        axes[0, i].set(
            title=kernel.split(".")[-1],
            xlabel="Repetition",
            ylabel="Emitted current (nA)" if kernel.endswith("lif/1") else "Emitted activation impulse",
            xticks=[1, 20],
        )
        axes[0, i].legend(fontsize=8)
        pair = [
            g
            for g in report["groups"]
            if g["condition"][0] == "pair"
            and g["condition"][1] == kernel
            and g["condition"][2]
            and g["condition"][4] == 1000000
        ]
        labels = [g["condition"][3] for g in pair]
        x = np.arange(len(pair))
        leads = np.array([g["primary_strict_wins"] for g in pair])
        other = np.array([g["primary_margin"]["n"] for g in pair]) - leads
        missing = np.array([g["n"] - g["primary_margin"]["n"] for g in pair])
        axes[1, i].bar(x, leads, color="#217c6c", label="Converged + original-target lead")
        axes[1, i].bar(x, other, bottom=leads, color="#cfac63", label="Converged, no strict lead")
        axes[1, i].bar(x, missing, bottom=leads + other, color="#dde3e0", label="No qualifying primary window")
        axes[1, i].set(
            xlabel="Pair condition; recorded host; retention 1 s", ylabel="Window count", xticks=x, xticklabels=labels
        )
        axes[1, i].tick_params(axis="x", rotation=25)
    fig.legend(*axes[1, 0].get_legend_handles_labels(), loc="outside lower center", ncol=3, fontsize=9, frameon=False)
    fig.suptitle(
        f"ThreeMind exploration: {report['complete_blocks']} blocks — distinct quantities, no intelligence ranking"
    )
    fig.savefig(WORK / "overview.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--partial", action="store_true")
    args = p.parse_args()
    analyze(args.partial)
