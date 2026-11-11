from __future__ import annotations

import hashlib
import io
import itertools
import json
import math

import numpy as np
from scipy.integrate import trapezoid

from .measurements import energy_endpoints

METHOD = "paired-bootstrap-signflip-holm/1"


def compare_pairs(pairs: list[dict], *, seed=71423, resamples=5000) -> dict:
    """One pair is one independent run/environment block, never one time sample."""
    rng = np.random.default_rng(seed)
    result = []
    metrics = sorted({k for p in pairs for k in p["control"]} | {k for p in pairs for k in p["treatment"]})
    for metric in metrics:
        values = []
        for p in pairs:
            a, b = p["control"].get(metric), p["treatment"].get(metric)
            if isinstance(a, (float, int)) and isinstance(b, (float, int)) and math.isfinite(a) and math.isfinite(b):
                values.append((a, b))
        n = len(values)
        row = {
            "metric": metric,
            "n": n,
            "missing_pairs": len(pairs) - n,
            "difference": None,
            "ci95": None,
            "paired_dz": None,
            "p": None,
            "p_holm": None,
        }
        if n:
            data = np.asarray(values, dtype=float)
            d = data[:, 1] - data[:, 0]
            row["control_mean"], row["treatment_mean"] = data.mean(axis=0).tolist()
            row["difference"] = float(d.mean())
            if n >= 2:
                boots = d[rng.integers(0, n, size=(resamples, n))].mean(axis=1)
                row["ci95"] = np.quantile(boots, [0.025, 0.975]).tolist()
                sd = float(d.std(ddof=1))
                row["paired_dz"] = float(d.mean() / sd) if sd > 0 else None
                if n <= 16:
                    null = np.asarray(list(itertools.product((-1, 1), repeat=n))) @ d / n
                    row["p"] = float(np.mean(np.abs(null) >= abs(d.mean()) - 1e-15))
                else:
                    null = (rng.choice((-1, 1), size=(resamples, n)) * d).mean(axis=1)
                    row["p"] = float((np.count_nonzero(np.abs(null) >= abs(d.mean()) - 1e-15) + 1) / (resamples + 1))
        result.append(row)
    ordered = sorted((r for r in result if r["p"] is not None), key=lambda r: r["p"])
    corrected = 0.0
    for i, row in enumerate(ordered):
        corrected = max(corrected, min(1.0, row["p"] * (len(ordered) - i)))
        row["p_holm"] = corrected
    return {
        "method": METHOD,
        "seed": seed,
        "resamples": resamples,
        "unit": "independent run/environment pair",
        "metrics": result,
        "pairs": pairs,
        "data_hash": hashlib.sha256(json.dumps(pairs, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        "notes": [
            "Intervals quantify this sampling design; they do not establish consciousness.",
            "One deterministic clone is not an independent replicate.",
            "Missing values are excluded per metric and reported, never replaced by zero.",
        ],
    }


def summarize(observations: list[dict], spec=None) -> dict:
    if not observations:
        return {}
    rows = sorted(observations, key=lambda r: int(r["time_us"]))
    last = rows[-1]
    result = {
        k: last.get(k)
        for k in (
            "nodes",
            "edges",
            "activation",
            "inhibition",
            "mean_weight",
            "mean_activation",
            "active_fraction",
            "saturated_fraction",
            "edge_density",
        )
    }
    points = [(int(r["time_us"]) / 1e6, r["activation"]) for r in rows if r.get("activation") is not None]
    if any((r.get("energy") or {}).get("parameters", {}).get("energy_simulation_enabled") for r in rows):
        result.update(energy_endpoints(last))
    result["activation_auc"] = (
        float(trapezoid([p[1] for p in points], [p[0] for p in points])) if len(points) > 1 else None
    )
    result["samples"] = len(rows)
    for phase in phase_evidence(observations, spec):
        prefix = f"phase.{phase['name']}."
        result.update({prefix + k: v for k, v in phase["endpoints"].items()})
    return result


def phase_evidence(observations, spec):
    """Sampled estimates with explicit coverage and right-censored settling.

    Settling durations are intentionally not fed into a t/sign-flip test after
    dropping censored runs. That would select only the fastest responders.
    """
    phases = (spec or {}).get("phases", [])
    rows = sorted((r for r in observations if "elapsed_us" in r), key=lambda r: int(r["elapsed_us"]))
    result, start = [], 0
    for phase in phases:
        end = start + round(phase["duration_s"] * 1e6)
        selected = [r for r in rows if start <= int(r["elapsed_us"]) < end]
        complete = (
            bool(selected) and int(selected[0]["elapsed_us"]) == start and int(selected[-1]["elapsed_us"]) == end - 1
        )
        record = {
            "name": phase["name"],
            "start_s": start / 1e6,
            "end_s": end / 1e6,
            "input_enabled": phase.get("input_enabled", True),
            "complete": complete,
            "samples": len(selected),
            "endpoints": {},
        }
        for metric in ("mean_activation", "saturated_fraction", "active_fraction", "edge_density", "mean_weight"):
            values = [r.get(metric) for r in selected]
            valid = complete and all(v is not None for v in values)
            times = [int(r["elapsed_us"]) / 1e6 for r in selected]
            record["endpoints"][metric + "_time_mean"] = (
                float(trapezoid([*values, values[-1]], [*times, end / 1e6]) / ((end - start) / 1e6)) if valid else None
            )
        if not phase.get("input_enabled", True):
            # Fixed, reported observational criterion. This does not alter the
            # core's activation floor or declare a conscious/unconscious state.
            low_start = None
            for r in selected:
                value = r.get("mean_activation")
                if value is not None and value <= 1e-4:
                    if low_start is None:
                        low_start = int(r["elapsed_us"])
                else:
                    low_start = None
            observed_end = end if complete else int(selected[-1]["elapsed_us"]) if selected else start
            observed = complete and low_start is not None and observed_end - low_start >= 500000
            record["settling"] = {
                "threshold": 1e-4,
                "minimum_hold_s": 0.5,
                "time_s": (low_start - start) / 1e6 if observed else None,
                "right_censored": not observed,
                "followup_s": (observed_end - start) / 1e6,
                "definition": "first sampled mean activation <= threshold, remaining below through phase end for at least minimum_hold_s",
            }
        result.append(record)
        start = end
    return result


def figure(observations: list[dict], *, format="svg") -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    has_fractions = any("saturated_fraction" in r for r in observations)
    energy = [energy_endpoints(r) for r in observations]
    has_energy = any(r["energy_reserve"] is not None for r in energy)
    panels = 2 + int(has_fractions) + int(has_energy)
    fig, axes = plt.subplots(panels, 1, figsize=(8, panels * 2 + 1), sharex=True, constrained_layout=True)
    times = [int(r["time_us"]) / 1e6 for r in observations]
    axes[0].plot(times, [r.get("activation", float("nan")) for r in observations], color="#237e74", label="Activation")
    axes[0].set_ylabel("Total activation (a.u.)")
    axes[1].plot(times, [r.get("edges", float("nan")) for r in observations], color="#a77530", label="Connections")
    axes[1].set_ylabel("Directed connections")
    if has_fractions:
        for name, color in (("saturated_fraction", "#ab634a"), ("active_fraction", "#237e74")):
            axes[2].plot(
                times,
                [r.get(name) if r.get(name) is not None else float("nan") for r in observations],
                color=color,
                label=name,
            )
        axes[2].set_ylabel("Node fraction")
        axes[2].set_ylim(-0.02, 1.02)
    if has_energy:
        for name, label in (
            ("energy_reserve", "Reserve"),
            ("energy_consumed", "Consumed (cumulative)"),
            ("energy_supplied", "Accepted supply (cumulative)"),
        ):
            axes[-1].plot(times, [r[name] if r[name] is not None else float("nan") for r in energy], label=label)
        axes[-1].set_ylabel("Experimental resource units")
    axes[-1].set_xlabel("Simulation time (s)")
    for ax in axes:
        ax.grid(alpha=0.2)
        ax.legend()
    output = io.BytesIO()
    fig.savefig(output, format=format, dpi=180)
    plt.close(fig)
    return output.getvalue()
