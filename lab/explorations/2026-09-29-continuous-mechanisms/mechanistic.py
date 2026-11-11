"""Explain recorded trajectories by evaluating the existing local equations."""

import gzip
import json
import math
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import ROOT, WORK, new_json, read_json
from run import TOKENS, COMBINATIONS
from threemind_kernels.continuous import ContinuousConfig
from threemind_kernels.mechanisms import FastTrace, ShortTermState


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def explain(cue):
    folder = WORK / "cases/diagnostic/default" / cue
    states = rows(folder / "states.jsonl.gz")
    by_time = {r["relative_us"]: r["state"] for r in states}
    before, after = by_time[490_000], by_time[500_000]
    cfg = ContinuousConfig(**before["config"])
    mapping = {n["channel"]: n["id"] for n in before["nodes"]}
    bid = mapping[TOKENS["B"]]
    node = next(n for n in before["nodes"] if n["id"] == bid)
    when = int(before["time_us"]) + 10_000
    # At this recorded boundary there are no arrivals. Apply exactly the
    # existing relaxation and pre-emission inhibition steps, not a new model.
    assert not any(int(q["time_us"]) <= when for q in before["queue"])
    soft = lambda v: cfg.inhibition_saturation * math.tanh(max(0, v) / cfg.inhibition_saturation)
    inhibition = soft(node["inhibition"] * math.exp(-0.01 / cfg.inhibition_tau) + node["pending_inhibition"])
    activation = node["activation"] * math.exp(-0.01 / cfg.activation_tau)
    response = 1 / (1 + cfg.inhibition_response_gain * soft(inhibition))
    edges = []
    for symbol in "CE":
        target = mapping[TOKENS[symbol]]
        edge = next(e for e in before["edges"] if e["source"] == bid and e["target"] == target)
        fast = next(r["state"] for r in before["operator_state"]["fast"] if r["source"] == bid and r["target"] == target)
        efficacy = FastTrace(fast["value"], int(fast["time_us"])).efficacy(edge["weight"], when, cfg.fast_trace())
        amount = activation * response * efficacy * cfg.propagation_rate * cfg.propagation_interval_us / 1e6
        resource = next(r["state"] for r in after["operator_state"]["short_term"] if r["source"] == bid and r["target"] == target)
        released = int(resource["time_us"]) == when
        assert released == (amount >= cfg.activation_floor)
        histories = []
        previous = None
        for row in states:
            state = row["state"]
            current = next(r["state"] for r in state["operator_state"]["short_term"] if r["source"] == bid and r["target"] == target)
            if previous is not None and current["time_us"] != previous and 0 < row["relative_us"] <= 1_000_000:
                histories.append({"relative_us": row["relative_us"], "available_after": current["available"]})
            previous = current["time_us"]
        edges.append({"edge": "B→"+symbol, "weight": edge["weight"], "effective_weight": efficacy,
                      "candidate_before_release": amount, "threshold": cfg.activation_floor,
                      "resource_released": released, "release_history": histories,
                      "candidate_after_release": amount * resource["active"] if released else None})
    events = rows(folder / "transmissions.jsonl.gz")
    counts = Counter(len(r["sources"]) for e in events for r in e["payload"].get("reception", []) if "sources" in r)
    start = int(states[0]["state"]["time_us"])
    targets = {mapping[TOKENS[s]] for s in "CE"}
    last_arrival = max((int(e["time_us"])-start for e in events if e["kind"] == "signal"
                        and any(v[0] in targets for v in e["payload"].get("values", []))), default=None)
    last_active = max((r["relative_us"] for r in states if any(n["id"] in targets and n["activation"] > 0 for n in r["state"]["nodes"])), default=None)
    return {"cue": cue, "at_relative_us": 500_000, "source_activation": activation,
            "source_response": response, "edges": edges, "reception_source_counts": dict(counts),
            "last_target_arrival_us": last_arrival, "last_target_active_sample_us": last_active}


def figure():
    analysis = read_json(WORK / "analysis-v2.json")
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    bits = list(reversed(COMBINATIONS))
    colors = ["#167565" if s[0] == "1" else "#89969f" for s in bits]
    ax = axes[0, 0]
    ax.bar(bits, [analysis["factorial"][s]["mean"] for s in bits], color=colors)
    ax.set(title="All 8 combinations: S / F / C", xlabel="1 = on; 0 = off", ylabel="Matched ending minus other ending (peak)")
    ax.ticklabel_format(axis="y", style="sci", scilimits=(-3, -3))
    ax = axes[0, 1]
    for cue, style in (("AB", "-"), ("DB", "--"), ("B", ":")):
        data = rows(WORK / "cases/background/111" / cue / "trajectory.jsonl.gz")
        t = [r["relative_us"]/1e6 for r in data]
        for symbol, color in (("C", "#245b96"), ("E", "#cb7133")):
            values = [next(n["activation"] for n in r["nodes"] if n["channel"] == TOKENS[symbol]) for r in data]
            ax.plot(t, values, style, color=color, label=f"{cue}: {symbol}", linewidth=1.5)
    ax.axvline(1, color="#888", linewidth=.7)
    ax.set(xlim=(.85, 2.5), title="Same B, different prefix history", xlabel="Seconds after prefix (B at 1 s)", ylabel="Actual target activation")
    ax.legend(fontsize=8, ncol=2)
    ax = axes[1, 0]
    for cue, style in (("AB", "-"), ("DB", "--")):
        data = rows(WORK / "cases/diagnostic/default" / cue / "states.jsonl.gz")
        values = {s: [] for s in "CE"}
        times = []
        for r in data:
            if r["relative_us"] > 1_200_000:
                break
            s = r["state"]
            cfg = ContinuousConfig(**s["config"])
            ids = {n["channel"]: n["id"] for n in s["nodes"]}
            times.append(r["relative_us"]/1e6)
            for symbol in "CE":
                q = next(x["state"] for x in s["operator_state"]["short_term"] if x["source"] == ids[TOKENS["B"]] and x["target"] == ids[TOKENS[symbol]])
                state = ShortTermState(q["available"], q["active"], q["utilization"], int(q["time_us"]))
                values[symbol].append(state.recovered(int(s["time_us"]), cfg.short_term()).available)
        for symbol, color in (("C", "#245b96"), ("E", "#cb7133")):
            ax.plot(times, values[symbol], style, color=color, label=f"{cue}: B-{symbol}")
    ax.axvline(.5, color="#888", linewidth=.7)
    ax.set(title="One skipped release changes available resources", xlabel="Seconds after prefix", ylabel="Available fraction (projected to sample time)")
    ax.legend(fontsize=8, ncol=2)
    ax = axes[1, 1]
    diagnostic = read_json(WORK / "diagnostic.json")
    variants = ["default", "no-inhibition", "recovery-fast", "recovery-slow", "floor-minus10pct", "floor-plus10pct"]
    labels = ["Default", "No inhibition", "Recovery .08s", "Recovery 8s", "Floor -.0004", "Floor +.0004"]
    for offset, cue, color in ((-.17, "AB", "#245b96"), (.17, "DB", "#cb7133")):
        vals = []
        for variant in variants:
            r = next(r for r in diagnostic if r["variant"] == variant and r["probe"] == cue)
            target, other = ("C", "E") if cue == "AB" else ("E", "C")
            vals.append(r["post_B"][target]["peak"] - r["post_B"][other]["peak"])
        ax.bar([i+offset for i in range(6)], vals, width=.32, color=color, label=cue)
    ax.axhline(0, color="#555", linewidth=.8)
    ax.set(xticks=range(6), xticklabels=labels, title="The current discrimination is parameter-sensitive", ylabel="Matched-ending peak margin")
    ax.tick_params(axis="x", labelrotation=25)
    ax.legend(fontsize=8)
    for ax in axes.flat:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.15)
    destination = ROOT / "docs/images/continuous-mechanisms-2026-09-29.png"
    fig.savefig(destination, dpi=155)
    fig.savefig(WORK / "overview.png", dpi=155)
    plt.close(fig)


if __name__ == "__main__":
    new_json(WORK / "mechanistic.json", {cue: explain(cue) for cue in ("AB", "DB")})
    figure()
