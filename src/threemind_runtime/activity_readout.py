"""Versioned passive analyses of pattern, amplitude, periodicity and response end.

The historical steady-state reader is unchanged. Each decision carries its own
time and measurements; a first stable pattern does not terminate observation of
amplitude or later response end. No observer decision is fed back into Core.
"""

from __future__ import annotations

import copy
import itertools
from dataclasses import asdict

from .process_observation import process_observation
from .readout_config import READOUT_VERSION, ActivityReadoutConfig
from .readouts import TemporalReader, wire

ACTIVITY_VERSION = "threemind.activity-analysis/1"
ACTIVITY_VERSION_V2 = "threemind.activity-analysis/2"


def distribution_distance(a, b, floor):
    sa, sb = sum(a.values()), sum(b.values())
    if sa <= floor or sb <= floor:
        return None
    return 0.5 * sum(abs(a.get(k, 0) / sa - b.get(k, 0) / sb) for k in sorted(a.keys() | b.keys(), key=int))


class ActivityReader(TemporalReader):
    def __init__(self, config: ActivityReadoutConfig, state=None):
        self.analysis_schema = ACTIVITY_VERSION_V2 if config.analysis_version == 2 else ACTIVITY_VERSION
        if state is not None and state.get("analysis_schema") != self.analysis_schema:
            raise ValueError("incompatible activity analysis state")
        if state is not None:
            # Missing observer fields belong to the historical version. Active
            # window configurations and identities are deliberately not rewritten.
            state = dict(state, configuration=asdict(ActivityReadoutConfig(**state["configuration"])))
        super().__init__(config, state)
        self.diagnostics = copy.deepcopy(
            (state or {}).get("diagnostics", {"eligible_frames": 0, "untriggered_frames": 0})
        )

    def capture(self):
        return (
            super().capture()
            | {"analysis_schema": self.analysis_schema}
            | ({"diagnostics": copy.deepcopy(self.diagnostics)} if self.config.analysis_version == 2 else {})
        )

    def consume(self, time_us, sequence, nodes, deliveries=(), *, annotations=None):
        if self.config.analysis_version == 2:
            for item in deliveries:
                source = item.get("source", "unknown")
                eligible = self.config.enabled and self.accepts(source)
                key = "eligible_frames" if eligible else "untriggered_frames"
                self.diagnostics[key] += 1
                if not eligible:
                    self.diagnostics["last_untriggered"] = {
                        "time_us": str(time_us),
                        "source": source,
                        "reason": "source_trigger_disabled",
                    }
        return super().consume(time_us, sequence, nodes, deliveries, annotations=annotations)

    def _open(self, context):
        return super()._open(context) | {"analyses": {}, "series_values": 0}

    def begin_observation(self, time_us, observation_id):
        """Start a passive window, including with no delivered input. Never a Core event."""
        if not self.config.enabled or self.config.analysis_version != 2:
            raise ValueError("stimulus-free observation requires enabled activity analysis V2")
        key = "observation:" + str(observation_id)
        if key in self.windows:
            return key
        if len(self.windows) >= self.config.max_active_windows:
            raise ValueError("active observation window budget exceeded")
        window = self._open(
            {
                "envelope_id": key,
                "delivered_time_us": time_us,
                "frame_index": 0,
                "frame_count": 1,
                "source": "manual-observation",
            }
        )
        window["observation_kind"] = "stimulus-free-marker"
        self.windows[key] = window
        self.last_identity = None
        return key

    def _append_sample(self, window, time_us, nodes, active_excess, comparison):
        raw = {str(n["id"]): n["activation"] for n in nodes if n["activation"] > 0}
        size = len(raw) + len(active_excess)
        previous = window["series"][-1] if window["series"] and window["series"][-1]["time_us"] == time_us else None
        old_size = (
            len(previous.get("activation_vector", {})) + len(previous.get("pattern_vector", {})) if previous else 0
        )
        if window["series_values"] - old_size + size > self.config.max_series_values:
            window["coverage_reasons"].append("series_value_budget")
            return False
        super()._append_sample(window, time_us, nodes, active_excess, comparison)
        sample = window["series"][-1]
        sample.update(pattern_vector=dict(active_excess), activation_vector=raw, raw_total=sum(raw.values()))
        window["series_values"] += size - old_size
        # Keep enough samples for the configured period search (not just old top-set periods).
        # Full series is bounded separately and retained for reproduction.
        return True

    def _tail(self, window, at):
        end = window["delivery_end_us"]
        if end is None:
            return []
        cutoff = max(end, at - self.config.settle_us)
        series = window["tail"]
        return [
            s
            for i, s in enumerate(series)
            if s["time_us"] >= cutoff
            or s["time_us"] >= end
            and i + 1 < len(series)
            and series[i + 1]["time_us"] > cutoff
        ]

    def _period(self, window):
        cfg = self.config
        end = window["delivery_end_us"]
        if end is None:
            return None
        series = [s for s in window["series"][-cfg.periodic_max_samples * 3 :] if s["time_us"] >= end]
        for lag in range(2, min(cfg.periodic_max_samples, len(series) // 3) + 1):
            samples = series[-lag * 3 :]
            gaps = [b["time_us"] - a["time_us"] for a, b in itertools.pairwise(samples)]
            if not gaps or min(gaps) <= 0 or max(gaps) != min(gaps):
                continue
            totals = [s["total"] for s in samples]
            if min(totals) <= cfg.response_floor:
                continue
            amplitude_errors = [abs(a - b) / max(a, b) for a, b in zip(totals, totals[lag:])]
            # Evaluate cheap necessary conditions before repeated full-vector
            # comparisons. Same predicate, including the historical V1 result.
            if max(amplitude_errors) > cfg.periodic_tolerance:
                continue
            pattern_change = max(
                distribution_distance(samples[0]["pattern_vector"], s["pattern_vector"], cfg.response_floor)
                for s in samples[:lag]
            )
            amplitude_change = (max(totals[:lag]) - min(totals[:lag])) / max(totals[:lag])
            if max(pattern_change, amplitude_change) <= cfg.periodic_tolerance * 2:
                continue
            distances = [
                distribution_distance(a["pattern_vector"], b["pattern_vector"], cfg.response_floor)
                for a, b in zip(samples, samples[lag:])
            ]
            if (
                max(distances) <= cfg.periodic_tolerance
                and max(amplitude_errors) <= cfg.periodic_tolerance
                and max(pattern_change, amplitude_change) > cfg.periodic_tolerance * 2
            ):
                return {
                    "period_us": gaps[0] * lag,
                    "cycles": 3,
                    "pattern_error": max(distances),
                    "amplitude_error": max(amplitude_errors),
                    "sampled": True,
                }
        return None

    @staticmethod
    def _decision(window, time_us, status, **metrics):
        sample = window["series"][-1]
        raw = sample["activation_vector"]
        return {
            "status": status,
            "end_us": time_us,
            "ranking": "end-activation",
            "nodes": [{"node_id": int(k), "activation": raw[k]} for k in sorted(raw, key=lambda k: (-raw[k], int(k)))],
            "total_excess": sample["total"],
            **metrics,
        }

    def _classify(self, window, time_us):
        cfg = self.config
        tail = self._tail(window, time_us)
        ended = window["delivery_end_us"] is not None
        ready = (
            ended
            and time_us - window["delivery_end_us"] >= cfg.min_response_us
            and len(tail) >= 3
            and time_us - tail[0]["time_us"] >= cfg.settle_us
        )
        analyses = window["analyses"]
        if ready:
            totals = [s["total"] for s in tail]
            if cfg.amplitude_enabled:
                peak = max(totals)
                drift = (peak - min(totals)) / peak if peak > cfg.response_floor else 0.0
                status = (
                    "below_floor"
                    if peak <= cfg.response_floor
                    else "stable"
                    if drift <= cfg.convergence_amplitude_drift_max
                    else "decaying"
                    if all(b <= a + cfg.response_floor for a, b in itertools.pairwise(totals))
                    else "growing"
                    if all(b + cfg.response_floor >= a for a, b in itertools.pairwise(totals))
                    else "varying"
                )
                analyses["amplitude"] = {
                    "status": status,
                    "end_us": time_us,
                    "start_us": tail[0]["time_us"],
                    "relative_range": drift,
                    "first": totals[0],
                    "last": totals[-1],
                }
            period = self._period(window) if cfg.periodic_enabled and "periodic" not in analyses else None
            if period and "periodic" not in analyses:
                analyses["periodic"] = self._decision(window, time_us, "detected", **period)
            if cfg.pattern_enabled and "pattern" not in analyses and min(totals) > cfg.response_floor:
                distances = [
                    distribution_distance(s["pattern_vector"], tail[-1]["pattern_vector"], cfg.response_floor)
                    for s in tail
                ]
                if max(distances) <= cfg.pattern_drift_max:
                    analyses["pattern"] = self._decision(
                        window,
                        time_us,
                        "converged",
                        maximum_distance=max(distances),
                        start_us=tail[0]["time_us"],
                        samples=len(tail),
                        amplitude=copy.deepcopy(analyses.get("amplitude")),
                    )
            if cfg.response_end_enabled and max(totals) <= cfg.response_floor:
                analyses["response_end"] = {
                    "status": "ended",
                    "end_us": time_us,
                    "start_us": tail[0]["time_us"],
                    "meaning": "sampled excess response; not Core death",
                }
                if cfg.analysis_version == 1:
                    return "response_ended", "below_response_floor_for_settle_window"
        if time_us - window["start_us"] >= cfg.max_response_us:
            return ("unresolved" if ended else "censored"), "maximum_window"
        return None

    def _finish(self, window, time_us, classification, reason):
        result = super()._finish(window, time_us, classification, reason)
        if "series_value_budget" in window["coverage_reasons"]:
            result.update(classification="censored", reason="series_value_budget", censored=True)
        analyses = copy.deepcopy(window["analyses"])
        for key, enabled in (
            ("pattern", self.config.pattern_enabled),
            ("amplitude", self.config.amplitude_enabled),
            ("periodic", self.config.periodic_enabled),
            ("response_end", self.config.response_end_enabled),
        ):
            analyses.setdefault(key, {"status": "not_detected" if enabled else "disabled"})
        primary = analyses.get("pattern") if analyses.get("pattern", {}).get("status") == "converged" else None
        if primary is None and analyses.get("periodic", {}).get("status") == "detected":
            primary = analyses["periodic"]
        result["legacy_candidate_ids"] = result["candidate_ids"]
        if primary:
            result["candidate_ids"] = [n["node_id"] for n in primary["nodes"]]
            by_id = {n["node_id"]: n["activation"] for n in primary["nodes"]}
            for n in result["nodes"]:
                n["decision_activation"] = by_id.get(n["node_id"], 0.0)
                n["candidate"] = n["node_id"] in by_id
            if not result["censored"] or reason == "maximum_window":
                result["classification"] = (
                    "pattern_converged" if primary["status"] == "converged" else "periodic_activity"
                )
        else:
            # No fabricated response when all measured activity is zero.
            result["candidate_ids"] = []
            for n in result["nodes"]:
                n.update(decision_activation=None, candidate=False)
        result.update(
            schema=READOUT_VERSION,
            analysis_schema=self.analysis_schema,
            analysis_id="activity-process",
            analyses=wire(analyses),
            primary_result=wire(primary),
            candidate_count=len(result["candidate_ids"]),
            ranking="end-activation",
            ranking_time_us=str(primary["end_us"]) if primary else None,
            measurement_scope="complete sampled node aggregates and positive activation/excess trajectories",
        )
        if self.config.analysis_version == 2:
            from .observation_tools import baseline_status

            try:
                process, measurements = process_observation(
                    result["series"],
                    result["nodes"],
                    epsilon=self.config.process_epsilon,
                    delivery_end_us=None if window.get("observation_kind") else result["delivery_end_us"],
                    expected_interval_us=self.config.interval_us,
                    max_values=self.config.max_series_values,
                )
                for node in result["nodes"]:
                    node.update(measurements.get(str(node["node_id"]), {}))
                process["coverage_complete"] = (
                    reason == "maximum_window"
                    and not window["coverage_reasons"]
                    and not process.get("sampling_gap_detected", False)
                    and int(process.get("last_sample_us", -1)) == time_us
                )
                process["observation_kind"] = window.get("observation_kind", "input-triggered")
                process["baseline_coverage_us"] = result["coverage"]["baseline_coverage_us"]
                process["baseline_status"] = baseline_status(result)
                process["end_state_is_not_process"] = True
                result["process"] = process
            except ValueError as exc:
                result["process"] = {"status": "unavailable", "reason": str(exc)}
        if window.get("observation_kind"):
            result.update(
                observation_id=result["envelope_id"],
                envelope_id=None,
                observation_kind=window["observation_kind"],
                delivery_end_us=None,
                observation_anchor_us=str(window["start_us"]),
            )
        if self.config.analysis_version == 2:
            result["overlapping_observations"] = [
                x for x in result["overlapping_envelopes"] if x.startswith("observation:")
            ]
            result["overlapping_envelopes"] = [
                x for x in result["overlapping_envelopes"] if not x.startswith("observation:")
            ]
        return result
