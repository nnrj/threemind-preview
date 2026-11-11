"""Read-only analysis of this study's completed cases; no kernel advancement."""

import gzip
import hashlib
import itertools
import json
import statistics
from collections import Counter

from common import WORK, encoded
from run import BITS, DELAYS, GAPS, TOKENS, flags

from threemind_core import StateImage


def mean(xs):
    return statistics.mean(xs) if xs else None


def signed(e, field="peak"):
    target = "C" if e["probe"] in ("AB", "A") else "E"
    if e["training"]["swap"]:
        target = "E" if target == "C" else "C"
    other = "E" if target == "C" else "C"
    return e["post_cue"][target][field] - e["post_cue"][other][field]


def summarize(rows):
    values = [signed(r["extra"]) for r in rows]
    return {
        "n": len(rows),
        "mean": mean(values),
        "values": values,
        "positive": sum(v > 1e-6 for v in values),
        "negative": sum(v < -1e-6 for v in values),
        "near_zero": sum(abs(v) <= 1e-6 for v in values),
        "converged": sum(r["extra"]["primary_available"] for r in rows),
        "mean_area": mean([signed(r["extra"], "area") for r in rows]),
    }


def contrasts(values):
    out = {}
    for n in (1, 2, 3):
        for combo in itertools.combinations(range(3), n):
            name = "".join("DFL"[i] for i in combo)
            fixed_axes = [i for i in range(3) if i not in combo]
            strata = []
            for fixed in itertools.product((0, 1), repeat=len(fixed_axes)):
                s = 0
                for varied in itertools.product((0, 1), repeat=n):
                    bits = [None] * 3
                    for i, b in zip(fixed_axes, fixed):
                        bits[i] = b
                    for i, b in zip(combo, varied):
                        bits[i] = b
                    s += (-1) ** (n - sum(varied)) * values["".join(map(str, bits))]
                strata.append({"fixed": dict(zip(("DFL"[i] for i in fixed_axes), fixed)), "effect": s})
            out[name] = {"mean": mean([v["effect"] for v in strata]), "strata": strata}
    return out


def analyze():
    rows = [json.loads(p.read_bytes()) for p in sorted((WORK / "cases").rglob("result.json"))]
    failures = []
    for r in rows:
        folder = WORK / "cases" / r["key"]
        with gzip.open(folder / "parent-state.json.gz", "rb") as f:
            if StateImage(f.read()).digest != r["state_sha256"]:
                failures.append(r["key"] + ": hash")
        if r["extra"].get("budget_stop"):
            failures.append(r["key"] + ": interrupted")
        bits = r["extra"].get("bits") or r["extra"].get("training", {}).get("bits")
        if r["key"].startswith("history/"):
            bits = r["key"].split("/")[2]
        if bits:
            from threemind_kernels.memory import MemoryConfig

            expected = MemoryConfig(seed=r["seed"], **flags(bits)).to_dict()
            if r["key"].startswith("readout/") and r["extra"].get("kind") == "probe":
                expected["edge_consolidation_enabled"] = False
            if r["key"].startswith("sustain/"):
                change = r["key"].split("/")[-1]
                if change in ("depletion-on", "both"):
                    expected["depletion_enabled"] = True
                if change in ("facilitation-off", "both"):
                    expected["stp_facilitation_tau_s"] = 0.0
                if change == "consolidation-off":
                    expected["edge_consolidation_enabled"] = False
            if expected != r["config"]:
                failures.append(r["key"] + ": config")
    probes = [r for r in rows if r["extra"].get("kind") == "probe" and not r["key"].startswith("validation/")]
    short = {}
    for bits in BITS:
        short[bits] = {}
        for gap in GAPS:
            group = [
                r
                for r in probes
                if r["key"].startswith("short/")
                and r["extra"]["training"]["bits"] == bits
                and r["extra"]["gap_s"] == gap
                and r["extra"]["probe"] in ("AB", "DB")
            ]
            short[bits][str(gap)] = summarize(group)
    retention = {}
    structure = []
    for r in probes:
        if not r["key"].startswith("retention/"):
            continue
        e = r["extra"]
        with gzip.open(WORK / "cases" / r["key"] / "snapshots.json.gz", "rb") as f:
            snap = json.load(f)["before_probe"]
        ids = {n["id"]: s for n in snap["nodes"] for s, ch in TOKENS.items() if n["channel"] == ch}
        target = "C" if e["probe"] == "A" else "E"
        if e["training"]["swap"]:
            target = "E" if target == "C" else "C"
        other = "E" if target == "C" else "C"
        ws = {
            ids.get(edge["target"]): edge["weight"] for edge in snap["edges"] if ids.get(edge["source"]) == e["probe"]
        }
        structure.append(
            {
                "key": r["key"],
                "bits": e["training"]["bits"],
                "delay": e["delay_s"],
                "balanced": e["training"]["balanced"],
                "matched_weight": ws.get(target, 0),
                "other_weight": ws.get(other, 0),
                "weight_margin": ws.get(target, 0) - ws.get(other, 0),
            }
        )
    for bits in BITS:
        retention[bits] = {}
        for delay in DELAYS:
            item = {}
            for balanced in (False, True):
                group = [
                    r
                    for r in probes
                    if r["key"].startswith("retention/")
                    and r["extra"]["training"]["bits"] == bits
                    and r["extra"]["delay_s"] == delay
                    and r["extra"]["training"]["balanced"] == balanced
                ]
                stats = summarize(group)
                stats["mean_weight_margin"] = mean(
                    [
                        v["weight_margin"]
                        for v in structure
                        if v["bits"] == bits and v["delay"] == delay and v["balanced"] == balanced
                    ]
                )
                item["balanced" if balanced else "paired"] = stats
            item["specificity"] = (
                item["paired"]["mean"] - item["balanced"]["mean"]
                if item["paired"]["mean"] is not None and item["balanced"]["mean"] is not None
                else None
            )
            retention[bits][str(delay)] = item
    interactions = {"short": {}, "retention": {}}
    for gap in GAPS:
        values = {b: short[b][str(gap)]["mean"] for b in BITS}
        if all(v is not None for v in values.values()):
            interactions["short"][str(gap)] = contrasts(values)
    for delay in DELAYS:
        values = {b: retention[b][str(delay)]["specificity"] for b in BITS}
        if all(v is not None for v in values.values()):
            interactions["retention"][str(delay)] = contrasts(values)
    warm = [r for r in rows if r["extra"].get("kind") == "warm"]
    history = {}
    for bits in ("001", "101"):
        history[bits] = {}
        for delay in (1, 3):
            selection = [
                r
                for r in probes
                if r["key"].startswith("history/") and r["key"].split("/")[2] == bits and r["extra"]["delay_s"] == delay
            ]
            history[bits][str(delay)] = summarize(selection)
    readout = {}
    for r in probes:
        if not r["key"].startswith("readout/"):
            continue
        e = r["extra"]
        original_key = r["key"].replace("readout/", "retention/", 1)
        original = next((v for v in probes if v["key"] == original_key), None)
        if original:
            readout[r["key"]] = {
                "original": original_key,
                "signed_peak_L_on": signed(original["extra"]),
                "signed_peak_L_off": signed(e),
                "difference": signed(e) - signed(original["extra"]),
                "bits": e["training"]["bits"],
                "delay": e["training"]["retention_delay_s"],
                "balanced": e["training"]["balanced"],
            }
    residual = []
    for r in probes:
        if r["key"].startswith("retention/") and r["extra"]["delay_s"] == 1:
            key = r["key"].split("/d1/")[0].replace("retention/", "residual/", 1)
            control = next((v for v in probes if v["key"] == key), None)
            if control:
                e = r["extra"]
                target = "C" if e["probe"] == "A" else "E"
                if e["training"]["swap"]:
                    target = "E" if target == "C" else "C"
                other = "E" if target == "C" else "C"
                cp = control["extra"]["post_cue"]
                control_margin = cp[target]["peak"] - cp[other]["peak"]
                residual.append(
                    {
                        "key": r["key"],
                        "control": key,
                        "signed_peak": signed(e),
                        "uncued_signed_peak": control_margin,
                        "adjusted": signed(e) - control_margin,
                    }
                )
    primary = []
    sustained = []
    for r in probes:
        e = r["extra"]
        if r["key"].startswith("sustain/"):
            with gzip.open(WORK / "cases" / r["key"] / "trajectory.jsonl.gz", "rb") as f:
                trace = [json.loads(line) for line in f]
            amps = [(v["relative_us"], max((n["activation"] for n in v["nodes"]), default=0)) for v in trace]
            sustained.append(
                {
                    "key": r["key"],
                    "first": amps[0][1],
                    "end": amps[-1][1],
                    "maximum": max(a for _, a in amps),
                    "minimum": min(a for _, a in amps),
                    "last_positive_us": max((t for t, a in amps if a > 0), default=None),
                }
            )
        primary.append(
            {
                "key": r["key"],
                "classification": e["classification"],
                "reason": e["reason"],
                "available": e["primary_available"],
                "delivered_frames": len(e["cue_delivery"]),
                "ranking": sorted(
                    (e.get("window") or {}).get("nodes", []), key=lambda n: (-n["last_activation"], n["node_id"])
                ),
            }
        )
    result = {
        "cases": len(rows),
        "probes": len(probes),
        "failures": failures,
        "life": dict(Counter(r["life"] for r in rows)),
        "classifications": dict(Counter(r["extra"]["classification"] for r in probes)),
        "warm_settled": [r["extra"]["settled"] for r in warm],
        "wall_seconds": sum(r["wall_seconds"] for r in rows),
        "short": short,
        "retention": retention,
        "interactions": interactions,
        "structure": structure,
        "history": history,
        "test_time_consolidation": readout,
        "residual_controls": residual,
        "sustained": sustained,
        "primary": primary,
        "cases_sha256": hashlib.sha256(
            encoded([{k: r[k] for k in ("id", "key", "state_sha256")} for r in rows])
        ).hexdigest(),
    }
    (WORK / "analysis.json").write_bytes(encoded(result))
    print(
        json.dumps({k: result[k] for k in ("cases", "probes", "failures", "life", "classifications", "wall_seconds")})
    )
    return result


def plot(a):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    colors = plt.get_cmap("tab10")
    for i, b in enumerate(BITS):
        axs[0].plot(GAPS, [a["short"][b][str(g)]["mean"] for g in GAPS], marker="o", label=b, color=colors(i))
        if a["retention"][b]["300"]["specificity"] is not None:
            axs[1].plot(
                DELAYS, [a["retention"][b][str(d)]["specificity"] for d in DELAYS], marker="o", label=b, color=colors(i)
            )
    for ax in axs:
        ax.axhline(0, color="#777", linewidth=0.7)
        ax.set_xscale("log")
        ax.grid(alpha=0.2)
        ax.legend(title="D/F/L", ncol=2, fontsize=8)
    axs[0].set(
        xlabel="Prefix-to-B gap (simulation seconds)",
        ylabel="Matched minus other peak activation",
        title="Same trained parent, 20 s settling",
    )
    axs[1].set(
        xlabel="Retention delay (simulation seconds)",
        ylabel="Pairing-specific peak margin (paired - balanced)",
        title="Repeated training; independent test copies",
    )
    axs[0].set_xticks(GAPS, [str(v) for v in GAPS])
    axs[1].set_xticks(DELAYS, [str(v) for v in DELAYS])
    fig.suptitle("Eight mechanism combinations across time scales")
    fig.savefig(WORK / "overview.png", dpi=180)
    fig.savefig(WORK / "overview.svg")
    plt.close(fig)

    if not a["sustained"]:
        return
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.5), constrained_layout=True)
    for bits in ("001", "101", "111"):
        with gzip.open(WORK / "cases" / f"retention/s0/{bits}/paired/d300/A/trajectory.jsonl.gz", "rb") as f:
            rows = [json.loads(line) for line in f]
        xs = [r["relative_us"] / 1e6 for r in rows]
        ys = [next((n["activation"] for n in r["nodes"] if n["channel"] == TOKENS["C"]), 0) for r in rows]
        axs[0].plot(xs, ys, label=bits)
    axs[0].set(xlim=(0, 2.5), xlabel="Seconds after cue A", ylabel="Paired target C activation",
               title="Recall after 300 s; target was inactive before cue")
    for name in ("unchanged", "depletion-on", "facilitation-off", "consolidation-off"):
        with gzip.open(WORK / "cases" / f"sustain/s0/{name}/trajectory.jsonl.gz", "rb") as f:
            rows = [json.loads(line) for line in f]
        axs[1].plot([r["relative_us"] / 1e6 for r in rows],
                    [max((n["activation"] for n in r["nodes"]), default=0) for r in rows], label=name)
    axs[1].set(xlim=(0, 5), xlabel="Seconds after switch; no task stimulus", ylabel="Maximum task-node activation",
               title="Persistent 011 activity: mechanisms maintaining it")
    for ax in axs:
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    fig.savefig(WORK / "activity.png", dpi=180)
    fig.savefig(WORK / "activity.svg")
    plt.close(fig)


if __name__ == "__main__":
    analysis = analyze()
    plot(analysis)
