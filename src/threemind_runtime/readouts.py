"""Passive, recoverable observers of complete anonymous node samples.

Integration is an explicit left-hold estimate between observations. Delivery
boundaries are samples too; neither a score nor a classification enters Core.
"""

from __future__ import annotations

import copy
import hashlib
import heapq
import itertools
import json
import math
from dataclasses import asdict

from .readout_config import READOUT_VERSION, StructuralReadoutConfig, TemporalReadoutConfig


def signature(value):
    return hashlib.blake2b(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(), digest_size=12
    ).hexdigest()


def wire(value):
    if isinstance(value, dict):
        # The complete-node tables contain mostly scalar leaves. Do not recurse
        # or inspect key suffixes on every float; retain the exact wire types.
        result = {}
        for key, item in value.items():
            kind = type(item)
            if kind is int and key.endswith("_us"):
                result[key] = str(item)
            elif kind in (dict, list, tuple):
                result[key] = wire(item)
            else:
                result[key] = item
        return result
    if isinstance(value, (list, tuple)):
        return [wire(v) for v in value]
    return value


def topology_fingerprint(ids, edges):
    incoming, outgoing = {i: [] for i in ids}, {i: [] for i in ids}
    for edge in edges:
        incoming[edge["target"]].append(edge["source"])
        outgoing[edge["source"]].append(edge["target"])
    colors = {i: f"{len(incoming[i])}:{len(outgoing[i])}" for i in ids}
    for _ in range(min(8, len(ids))):
        colors = {
            i: signature([colors[i], sorted(colors[n] for n in incoming[i]), sorted(colors[n] for n in outgoing[i])])
            for i in ids
        }
    return signature([sorted(colors.values()), sorted([colors[e["source"]], colors[e["target"]]] for e in edges)])


def ranked_nodes(nodes, maximum):
    return heapq.nsmallest(
        maximum, nodes, key=lambda n: (-n["activation"], -n["associative"], -n["stability"], n["id"])
    )


class StructuralReader:
    def __init__(self, config: StructuralReadoutConfig, state=None):
        self.config = config
        self.occurrences, self.cooldowns = {}, {}
        self.last_identity = None
        if state:
            if state.get("schema") != READOUT_VERSION or state.get("configuration") != asdict(config):
                raise ValueError("structural readout state/config mismatch")
            self.occurrences = copy.deepcopy(state["occurrences"])
            self.cooldowns = dict(state["cooldowns"])
            self.last_identity = state["last_identity"]

    def capture(self):
        return {
            "schema": READOUT_VERSION,
            "configuration": asdict(self.config),
            "occurrences": copy.deepcopy(self.occurrences),
            "cooldowns": dict(self.cooldowns),
            "last_identity": self.last_identity,
        }

    def candidates(self, nodes):
        return ranked_nodes(
            (n for n in nodes if n["activation"] >= self.config.activation_threshold), self.config.max_nodes
        )

    def consume(self, time_us, sequence, nodes, edges, *, annotations=None):
        cfg = self.config
        identity = f"{time_us}:{sequence}"
        if not cfg.enabled or self.last_identity == identity:
            return None
        self.last_identity = identity
        for key in list(self.occurrences):
            self.occurrences[key] = [t for t in self.occurrences[key] if t >= time_us - cfg.recurrence_window_us]
            if not self.occurrences[key]:
                del self.occurrences[key]
        self.cooldowns = {key: t for key, t in self.cooldowns.items() if time_us - t < cfg.cooldown_us}
        selected = self.candidates(nodes)
        ids = sorted(n["id"] for n in selected)
        eligible = len(ids) >= cfg.min_nodes and len(edges) >= cfg.min_internal_edges
        activity = (
            [n for n in nodes if n["activation"] >= cfg.activation_threshold and max(n["direct"], n["associative"]) > 0]
            if cfg.read_touched_activity
            else []
        )
        if not eligible and not activity and not cfg.read_touched_activity:
            return None
        structure = None
        if eligible:
            structure_id = signature([ids, sorted([e["source"], e["target"]] for e in edges)])
            state_signature = signature(
                [
                    structure_id,
                    sorted([n["id"], round(n["activation"] * 5), round(n["stability"] * 5)] for n in selected),
                    sorted(
                        [e["source"], e["target"], round(e["weight"] * 5), round(e["stability"] * 5)] for e in edges
                    ),
                ]
            )
            times = self.occurrences.setdefault(state_signature, [])
            if not times or times[-1] != time_us:
                times.append(time_us)
            recurrent = len(times) >= cfg.min_occurrences and time_us - times[0] >= cfg.min_span_us
            notified = (
                recurrent
                and cfg.repeatable_structure_readout
                and time_us - self.cooldowns.get(state_signature, -cfg.cooldown_us) >= cfg.cooldown_us
            )
            if notified:
                self.cooldowns[state_signature] = time_us
            structure = {
                "structure_id": structure_id,
                "state_signature": state_signature,
                "topology_fingerprint": topology_fingerprint(ids, edges),
                "nodes": selected,
                "edges": edges,
                "occurrences": len(times),
                "first_seen_us": times[0],
                "span_us": time_us - times[0],
                "recurrent": recurrent,
                "recurrence_notice": notified,
            }
        return wire(
            {
                "schema": READOUT_VERSION,
                "kind": "structural_readout",
                "time_us": time_us,
                "sequence": sequence,
                "configuration": asdict(cfg),
                "structure": structure,
                "activity_nodes": activity,
                # Unfiltered measurements are independent of recurrence and
                # response hypotheses. Labels never decide which nodes survive.
                "raw_nodes": nodes if cfg.read_touched_activity else [],
                "raw_observation": {
                    "schema": "threemind.raw-node-observation/1",
                    "complete": cfg.read_touched_activity,
                    "node_count": len(nodes) if cfg.read_touched_activity else 0,
                    "scope": "all-source-nodes" if cfg.read_touched_activity else "recording-disabled",
                    "causal_attribution": "not-established",
                },
                "source_node_count": len(nodes),
                "threshold_node_count": sum(n["activation"] >= cfg.activation_threshold for n in nodes),
                "annotations": annotations or {},
                "coverage": (
                    "all source-node measurements stored; candidate structure is derived"
                    if cfg.read_touched_activity
                    else "candidate structure only; unfiltered node recording disabled"
                ),
            }
        )


class TemporalReader:
    def __init__(self, config: TemporalReadoutConfig, state=None):
        self.config = config
        self.baseline = []
        self.windows = {}
        self.closed_inflight = {}
        self.last_identity = None
        self._columns = {}
        if state:
            if state.get("schema") != READOUT_VERSION or state.get("configuration") != asdict(config):
                raise ValueError("temporal readout state/config mismatch")
            self.baseline = copy.deepcopy(state["baseline"])
            self.windows = copy.deepcopy(state["windows"])
            self.closed_inflight = dict(state["closed_inflight"])
            self.last_identity = state["last_identity"]

    def capture(self):
        windows = {}
        for key, window in self.windows.items():
            columns = self._columns.get(window["window_id"])
            windows[key] = copy.deepcopy(window)
            if columns is not None:
                windows[key]["nodes"] = columns.rows()
        return {
            "schema": READOUT_VERSION,
            "configuration": asdict(self.config),
            "baseline": copy.deepcopy(self.baseline),
            "windows": windows,
            "closed_inflight": dict(self.closed_inflight),
            "last_identity": self.last_identity,
        }

    def accepts(self, source):
        category = (
            "manual"
            if source.startswith(("manual-", "upload-")) or source in ("replay", "text-sensor", "anonymous-frames")
            else "ai"
            if source.startswith("ai-")
            else "ambient"
        )
        return getattr(self.config, f"trigger_{category}")

    def _baseline(self, at_us):
        start = at_us - self.config.baseline_us
        samples = [f for f in self.baseline if f["time_us"] < at_us]
        if not samples or not self.config.baseline_us:
            return {}, 0
        sums, squares, duration = {}, {}, 0
        for index, frame in enumerate(samples):
            left = max(start, frame["time_us"])
            right = min(at_us, samples[index + 1]["time_us"] if index + 1 < len(samples) else at_us)
            dt = max(0, right - left)
            duration += dt
            if not dt:
                continue
            for key, value in frame["values"].items():
                sums[key] = sums.get(key, 0.0) + value * dt
                squares[key] = squares.get(key, 0.0) + value * value * dt
        return (
            {
                k: [value / duration, math.sqrt(max(0, squares[k] / duration - (value / duration) ** 2))]
                for k, value in sums.items()
            }
            if duration
            else {}
        ), duration

    def _open(self, context):
        start = int(context["delivered_time_us"])
        baseline, coverage = self._baseline(start)
        index = context["frame_index"]
        return {
            "window_id": signature([context["envelope_id"], start, index, asdict(self.config)]),
            "envelope_id": context["envelope_id"],
            "source": context.get("source", "unknown"),
            "adapter_id": context.get("adapter_id"),
            "start_us": start,
            "end_us": None,
            "first_frame_index": index,
            "frame_count": context.get("frame_count", 1),
            "delivery_end_us": start
            if index == context.get("last_scheduled_index", context.get("frame_count", 1) - 1)
            else None,
            "last_frame_index": context.get("last_scheduled_index", context.get("frame_count", 1) - 1),
            "partial_start": index != context.get("first_scheduled_index", 0),
            "baseline": baseline,
            "baseline_coverage_us": coverage,
            "baseline_requested_us": self.config.baseline_us,
            "last_us": None,
            "first_sample_us": None,
            "observed_us": 0,
            "tail_observed_us": 0,
            "sample_count": 0,
            "nodes": {},
            "tail": [],
            "series": [],
            "tail_peak": 0.0,
            "ever_active": False,
            "overlapping_envelopes": [],
            "annotations": {},
            "coverage_reasons": [],
            "configuration": asdict(self.config),
        }

    def consume(self, time_us, sequence, nodes, deliveries=(), *, annotations=None):
        identity = f"{time_us}:{sequence}"
        if not self.config.enabled or identity == self.last_identity and not deliveries:
            return []
        self.last_identity = identity
        records = []
        for context in deliveries:
            key = str(context.get("envelope_id", ""))
            if not key:
                continue
            if key in self.closed_inflight:
                if context["frame_index"] == self.closed_inflight[key]:
                    del self.closed_inflight[key]
                continue
            if key not in self.windows and self.accepts(context.get("source", "unknown")):
                window = self._open(context)
                if len(self.windows) >= self.config.max_active_windows:
                    window["coverage_reasons"].append("active_window_budget")
                    records.append(self._finish(window, time_us, "not_observed", "active_window_budget"))
                    if context["frame_index"] != window["last_frame_index"]:
                        self.closed_inflight[key] = window["last_frame_index"]
                    continue
                self.windows[key] = window
            window = self.windows.get(key)
            if window is not None and context["frame_index"] == window["last_frame_index"]:
                window["delivery_end_us"] = int(context["delivered_time_us"])
        concurrent = {str(c["envelope_id"]) for c in deliveries if c.get("envelope_id")}
        concurrent |= set(self.windows)
        for key, window in list(self.windows.items()):
            window["overlapping_envelopes"] = sorted(set(window["overlapping_envelopes"]) | (concurrent - {key}))
            if annotations:
                window["annotations"].update(annotations)
            if len(window["series"]) >= self.config.max_history_samples:
                window["coverage_reasons"].append("history_sample_budget")
                decision = ("censored", "history_sample_budget")
            else:
                budget_ok = self._observe(window, time_us, nodes)
                decision = self._classify(window, time_us) if budget_ok else ("censored", "node_entry_budget")
            if decision:
                records.append(self._finish(window, time_us, *decision))
                if window["delivery_end_us"] is None:
                    self.closed_inflight[key] = window["last_frame_index"]
                del self.windows[key]
        if self.baseline and self.baseline[-1]["time_us"] == time_us:
            self.baseline.pop()
        self.baseline.append({"time_us": time_us, "values": {str(n["id"]): n["activation"] for n in nodes}})
        cutoff = time_us - self.config.baseline_us
        while len(self.baseline) > 1 and self.baseline[1]["time_us"] <= cutoff:
            self.baseline.pop(0)
        # Shorten only the observer's baseline, and report its measured coverage.
        count = sum(len(f["values"]) for f in self.baseline)
        while self.baseline and count > self.config.max_node_entries:
            count -= len(self.baseline.pop(0)["values"])
        return records

    def _observe(self, window, time_us, nodes):
        columns = self._columns.get(window["window_id"])
        if columns is not None or len(nodes) >= 256:
            from .readout_columns import WindowColumns, can_batch

            if can_batch(window, time_us, nodes):
                if columns is None:
                    try:
                        columns = WindowColumns(window["nodes"])
                    except (OverflowError, TypeError):
                        return self._observe_reference(window, time_us, nodes)
                    self._columns[window["window_id"]] = columns
                    window["nodes"] = {}
                cfg, prev = self.config, window["last_us"]
                dt_us = max(0, time_us - prev) if prev is not None else 0
                tail_us = (
                    max(0, time_us - max(prev, window["delivery_end_us"]))
                    if prev is not None and window["delivery_end_us"] is not None
                    else 0
                )
                window["observed_us"] += dt_us
                window["tail_observed_us"] += tail_us
                window["sample_count"] += 1
                if window["first_sample_us"] is None:
                    window["first_sample_us"] = time_us
                columns.integrate(dt_us, tail_us)
                result = columns.observe(nodes, window["baseline"], cfg, time_us)
                if result is None:
                    window["coverage_reasons"].append("node_entry_budget")
                    window["last_us"] = time_us
                    return False
                active_excess, comparison = result
                window["ever_active"] |= bool(active_excess)
                window["last_us"] = time_us
                return self._append_sample(window, time_us, nodes, active_excess, comparison)
            window["nodes"] = columns.rows() if columns is not None else window["nodes"]
            self._columns.pop(window["window_id"], None)
        return self._observe_reference(window, time_us, nodes)

    def _observe_reference(self, window, time_us, nodes):
        cfg = self.config
        prev = window["last_us"]
        dt_us = max(0, time_us - prev) if prev is not None else 0
        dt = dt_us / 1e6
        tail_us = (
            max(0, time_us - max(prev, window["delivery_end_us"]))
            if prev is not None and window["delivery_end_us"] is not None
            else 0
        )
        window["observed_us"] += dt_us
        window["tail_observed_us"] += tail_us
        window["sample_count"] += 1
        if window["first_sample_us"] is None:
            window["first_sample_us"] = time_us
        for key in sorted(window["nodes"], key=int):
            row = window["nodes"][key]
            for field, previous in (
                ("activation_integral", "last_activation"),
                ("excess_integral", "last_excess"),
                ("inhibition_integral", "last_inhibition"),
                ("direct_trace_integral", "last_direct"),
                ("associative_trace_integral", "last_associative"),
            ):
                row[field] += row[previous] * dt
            if row["last_active"]:
                row["active_us"] += dt_us
                row["tail_active_us"] += tail_us
                row["current_run_us"] += dt_us
                row["longest_run_us"] = max(row["longest_run_us"], row["current_run_us"])
        current = {str(n["id"]): n for n in nodes}
        # Track every observed node from its first sample, including intervals
        # below threshold before it becomes a candidate. Selection happens later.
        qualifying = set(current)
        excesses = {}
        for key, raw in current.items():
            mean, noise = window["baseline"].get(key, (0.0, 0.0))
            excess = max(0, raw["activation"] - mean - cfg.baseline_noise_gain * noise)
            active = (
                raw["activation"] > 0
                and excess > 0
                and raw["activation"] >= cfg.activation_threshold
                and excess >= cfg.excess_activation_min
            )
            excesses[key] = (mean, noise, excess, active)
        if len(set(window["nodes"]) | qualifying) > cfg.max_node_entries:
            window["coverage_reasons"].append("node_entry_budget")
            window["last_us"] = time_us
            return False
        for key in sorted(qualifying - set(window["nodes"]), key=int):
            mean, noise, _, _ = excesses[key]
            window["nodes"][key] = {
                "node_id": int(key),
                "baseline_mean": mean,
                "baseline_noise": noise,
                "active_us": 0,
                "tail_active_us": 0,
                "longest_run_us": 0,
                "current_run_us": 0,
                "entries": 0,
                "activation_integral": 0.0,
                "excess_integral": 0.0,
                "inhibition_integral": 0.0,
                "direct_trace_integral": 0.0,
                "associative_trace_integral": 0.0,
                "peak_activation": 0.0,
                "peak_inhibition": 0.0,
                "has_direct_trace": False,
                "has_associative_trace": False,
                "first_active_us": None,
                "last_active_us": None,
                "last_active": False,
                "last_activation": 0.0,
                "last_excess": 0.0,
                "last_inhibition": 0.0,
                "last_direct": 0.0,
                "last_associative": 0.0,
                "stability": 0.0,
            }
        active_excess = {}
        for key in sorted(window["nodes"], key=int):
            row = window["nodes"][key]
            raw = current.get(
                key, {"activation": 0.0, "inhibition": 0.0, "direct": 0.0, "associative": 0.0, "stability": 0.0}
            )
            _, _, excess, active = excesses.get(key, (0.0, 0.0, 0.0, False))
            if active:
                if not row["last_active"]:
                    row["entries"] += 1
                    row["current_run_us"] = 0
                if row["first_active_us"] is None:
                    row["first_active_us"] = time_us
                row["last_active_us"] = time_us
                active_excess[key] = excess
            else:
                row["current_run_us"] = 0
            row.update(
                last_active=active,
                last_activation=raw["activation"],
                last_excess=excess,
                last_inhibition=raw["inhibition"],
                last_direct=raw["direct"],
                last_associative=raw["associative"],
                stability=raw["stability"],
            )
            row["peak_activation"] = max(row["peak_activation"], raw["activation"])
            row["peak_inhibition"] = max(row["peak_inhibition"], raw["inhibition"])
            row["has_direct_trace"] |= raw["direct"] >= cfg.excess_activation_min and raw["direct"] > 0
            row["has_associative_trace"] |= raw["associative"] >= cfg.excess_activation_min and raw["associative"] > 0
        window["ever_active"] |= bool(active_excess)
        window["last_us"] = time_us
        comparison = {
            k: v
            for k, v in active_excess.items()
            if cfg.candidate_scope == "all-active"
            or window["nodes"][k]["has_associative_trace"]
            or cfg.candidate_scope == "associative-or-persistent"
            and window["nodes"][k]["tail_active_us"] > 0
        }
        return self._append_sample(window, time_us, nodes, active_excess, comparison)

    def _append_sample(self, window, time_us, nodes, active_excess, comparison):
        cfg = self.config
        top = heapq.nsmallest(cfg.comparison_top_k, comparison, key=lambda k: (-comparison[k], int(k)))
        # These dictionaries were populated in numeric node-id order above.
        # Preserve that sum order, including floating-point rounding.
        total = sum(active_excess.values())
        sample = {
            "time_us": time_us,
            "top": sorted(top, key=int),
            "vector": {k: active_excess[k] for k in top},
            "total": total,
            "candidate_total": sum(comparison.values()),
            "active_node_count": len(active_excess),
            "source_node_count": len(nodes),
        }
        if window["series"] and window["series"][-1]["time_us"] == time_us:
            window["series"][-1] = sample
        else:
            window["series"].append(sample)
        if window["delivery_end_us"] is not None and time_us >= window["delivery_end_us"]:
            window["tail_peak"] = max(window["tail_peak"], total)
            if window["tail"] and window["tail"][-1]["time_us"] == time_us:
                window["tail"][-1] = sample
            else:
                window["tail"].append(sample)
            keep = max(cfg.settle_us, cfg.interval_us * 24)
            while len(window["tail"]) > 1 and window["tail"][1]["time_us"] < time_us - keep:
                window["tail"].pop(0)
        return True

    def _convergence(self, window, time_us):
        tail = window["tail"]
        cutoff = time_us - self.config.settle_us
        selected = [
            s
            for i, s in enumerate(tail)
            if s["time_us"] >= cutoff or i + 1 < len(tail) and tail[i + 1]["time_us"] > cutoff
        ]
        weight = jaccard = drift = 0.0
        for left, right in itertools.pairwise(selected):
            dt = right["time_us"] - max(left["time_us"], cutoff)
            a, b = set(left["top"]), set(right["top"])
            jaccard += (len(a & b) / len(a | b) if a | b else 1.0) * dt
            x, y = left["vector"], right["vector"]
            sx, sy = sum(x[k] for k in sorted(x, key=int)), sum(y[k] for k in sorted(y, key=int))
            drift += (
                0.5
                * sum(
                    abs((x.get(k, 0) / sx if sx else 0) - (y.get(k, 0) / sy if sy else 0))
                    for k in sorted(set(x) | set(y), key=int)
                )
                * dt
            )
            weight += dt
        totals = [s["total"] for s in selected]
        amplitude = (max(totals) - min(totals)) / max(max(totals), 1e-30) if len(selected) > 1 else None
        period_us = None
        for period in range(2, min(8, len(tail) // 3) + 1):
            samples = tail[-period * 3 :]
            gaps = [b["time_us"] - a["time_us"] for a, b in itertools.pairwise(samples)]
            sets = [tuple(s["top"]) for s in samples]
            if (
                gaps
                and min(gaps) > 0
                and max(gaps) == min(gaps)
                and sets[:period] == sets[period : period * 2] == sets[period * 2 :]
                and len(set(sets[:period])) > 1
            ):
                period_us = gaps[0] * period
                break
        return {
            "mean_jaccard": jaccard / weight if weight else None,
            "mean_distribution_drift": drift / weight if weight else None,
            "amplitude_drift": amplitude,
            "settle_coverage_us": int(weight),
            "period_us": period_us,
            "tail_peak": window["tail_peak"],
            "tail_final": tail[-1]["total"] if tail else None,
            "tail_has_activity": any(s["active_node_count"] for s in selected),
            "tail_has_candidates": any(s["top"] for s in selected),
            "settle_samples": len(selected),
            "tail_nonincreasing": len(totals) > 1 and all(b <= a + 1e-12 for a, b in itertools.pairwise(totals)),
        }

    def _classify(self, window, time_us):
        cfg = self.config
        m = self._convergence(window, time_us)
        ended = window["delivery_end_us"] is not None
        ready = (
            ended
            and time_us - window["delivery_end_us"] >= cfg.min_response_us
            and m["settle_coverage_us"] >= cfg.settle_us
            and m["settle_samples"] >= 3
        )
        if ready:
            if m["period_us"] is not None:
                return "oscillatory", "three_repeated_nonconstant_cycles"
            if (
                m["tail_peak"] > 0
                and m["tail_nonincreasing"]
                and m["tail_final"] <= m["tail_peak"] * cfg.decay_final_ratio_max
            ):
                return "residual_decay", "tail_amplitude_decline"
            if not m["tail_has_activity"]:
                return "transient", "no_sustained_tail"
            if (
                m["tail_has_candidates"]
                and m["mean_jaccard"] >= cfg.convergence_jaccard_min
                and m["mean_distribution_drift"] <= cfg.convergence_drift_max
                and m["amplitude_drift"] <= cfg.convergence_amplitude_drift_max
            ):
                return "converged", "finite_sample_window_criteria"
        if time_us - window["start_us"] >= cfg.max_response_us:
            return ("unresolved" if ended else "censored"), "maximum_window"
        return None

    def _finish(self, window, time_us, classification, reason):
        columns = self._columns.pop(window["window_id"], None)
        if columns is not None:
            window["nodes"] = columns.rows()
        cfg = self.config
        rows = []
        for key in sorted(window["nodes"], key=int):
            row = {
                k: v
                for k, v in window["nodes"][key].items()
                if k
                not in (
                    "last_active",
                    "current_run_us",
                    "last_excess",
                    "last_direct",
                    "last_associative",
                    "last_inhibition",
                    "entries",
                )
            }
            row["reentry_count"] = max(0, window["nodes"][key]["entries"] - 1)
            row["active_ratio"] = row["active_us"] / window["observed_us"] if window["observed_us"] else 0.0
            row["tail_active_ratio"] = (
                row["tail_active_us"] / window["tail_observed_us"] if window["tail_observed_us"] else 0.0
            )
            row["candidate"] = (
                (row["has_associative_trace"] or row["tail_active_us"] > 0)
                if cfg.candidate_scope == "associative-or-persistent"
                else row["has_associative_trace"]
                if cfg.candidate_scope == "associative-only"
                else row["first_active_us"] is not None
            )
            rows.append(row)
        candidates = [r for r in rows if r["candidate"]]
        maximum = max((r["excess_integral"] for r in candidates), default=0)
        for row in rows:
            continuous = row["longest_run_us"] / window["observed_us"] if window["observed_us"] else 0
            strength = row["excess_integral"] / maximum if maximum else 0
            row["score"] = (
                (0.30 * row["active_ratio"] + 0.20 * continuous + 0.20 * row["tail_active_ratio"] + 0.30 * strength)
                if cfg.consider_activation_strength
                else (0.43 * row["active_ratio"] + 0.29 * continuous + 0.28 * row["tail_active_ratio"])
            )
            if not row["candidate"]:
                row["score"] = None
        ordering = lambda r: (
            -(
                r["active_us"]
                if cfg.ranking_mode == "duration"
                else r["excess_integral"]
                if cfg.ranking_mode == "activation-integral"
                else r["score"]
            ),
            -r["excess_integral"],
            r["node_id"],
        )
        candidates.sort(key=ordering)
        return wire(
            {
                "schema": READOUT_VERSION,
                "kind": "temporal_readout",
                "window_id": window["window_id"],
                "envelope_id": window["envelope_id"],
                "causal_attribution": "not-established",
                "measurement_scope": "sampled node aggregates, not per-node continuous trajectories",
                "source": window["source"],
                "adapter_id": window["adapter_id"],
                "start_us": window["start_us"],
                "end_us": time_us,
                "delivery_end_us": window["delivery_end_us"],
                "classification": classification,
                "reason": reason,
                "partial_start": window["partial_start"],
                "censored": reason
                in (
                    "maximum_window",
                    "node_entry_budget",
                    "active_window_budget",
                    "history_sample_budget",
                    "run_ended",
                    "cancelled",
                    "configuration_changed",
                    "disabled",
                ),
                "overlapping_envelopes": window["overlapping_envelopes"],
                "configuration": window["configuration"],
                "nodes": rows,
                "candidate_ids": [r["node_id"] for r in candidates],
                "candidate_count": len(candidates),
                "annotations": window["annotations"],
                "series": window["series"],
                "convergence": self._convergence(window, time_us),
                "coverage": {
                    "method": "left-hold between complete node samples",
                    "sample_count": window["sample_count"],
                    "first_sample_us": window["first_sample_us"],
                    "last_sample_us": window["last_us"],
                    "observed_us": window["observed_us"],
                    "tail_observed_us": window["tail_observed_us"],
                    "baseline_coverage_us": window["baseline_coverage_us"],
                    "baseline_requested_us": window["baseline_requested_us"],
                    "baseline_complete": window["baseline_coverage_us"] >= window["baseline_requested_us"],
                    "reasons": window["coverage_reasons"],
                },
            }
        )

    def close(self, time_us, reason):
        output = [
            self._finish(
                self.windows[key],
                time_us,
                "interrupted" if reason in ("disabled", "configuration_changed", "cancelled") else "censored",
                reason,
            )
            for key in sorted(self.windows)
        ]
        self.windows.clear()
        self.closed_inflight.clear()
        return output
