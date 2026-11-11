"""Temporal, read-only convergence observations for ThreeMind OutputBus frames.

The adapter deliberately owns every time-window rule.  Core publishes anonymous
activity and causal delivery identities, while this module accumulates evidence
without feeding a score, label, or decision back into consciousness dynamics.
"""
from __future__ import annotations

import hashlib
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from threemind.frames import OutputFrame


DEFAULT_TEMPORAL_CONFIG: dict[str, Any] = {
    "enabled": True,
    "trigger_manual": True,
    "trigger_ai": False,
    "trigger_ambient": False,
    "consider_activation_strength": True,
    "ranking_mode": "composite",
    "candidate_scope": "associative-or-persistent",
    "baseline_ticks": 12,
    "min_response_ticks": 12,
    "max_response_ticks": 120,
    "settle_ticks": 8,
    "activation_threshold": .055,
    "excess_activation_min": .005,
    "baseline_noise_gain": 1.0,
    "convergence_jaccard_min": .80,
    "convergence_drift_max": .12,
    "display_limit": 7,
}


@dataclass(slots=True)
class _NodeTimeline:
    node_id: int
    baseline_mean: float
    baseline_noise: float
    active_ticks: int = 0
    tail_active_ticks: int = 0
    longest_active_run: int = 0
    current_active_run: int = 0
    reentry_count: int = 0
    activation_integral: float = 0.0
    excess_activation_integral: float = 0.0
    peak_activation: float = 0.0
    inhibition_integral: float = 0.0
    peak_inhibition: float = 0.0
    direct_touch_integral: float = 0.0
    associative_touch_integral: float = 0.0
    direct_touch_ticks: int = 0
    associative_touch_ticks: int = 0
    first_active_tick: int | None = None
    last_active_tick: int | None = None
    last_activation: float = 0.0
    last_stability: float = 0.0
    _was_active: bool = False

    def observe(
        self,
        *,
        tick: int,
        activation: float,
        excess: float,
        inhibition: float,
        stability: float,
        direct_touch: float,
        associative_touch: float,
        active: bool,
        tail: bool,
    ) -> None:
        self.last_activation = activation
        self.last_stability = stability
        self.inhibition_integral += inhibition
        self.peak_inhibition = max(self.peak_inhibition, inhibition)
        self.direct_touch_integral += direct_touch
        self.associative_touch_integral += associative_touch
        if direct_touch > 0:
            self.direct_touch_ticks += 1
        if associative_touch > 0:
            self.associative_touch_ticks += 1
        if active:
            if not self._was_active:
                self.reentry_count += 1
                self.current_active_run = 0
            self._was_active = True
            self.current_active_run += 1
            self.longest_active_run = max(self.longest_active_run, self.current_active_run)
            self.active_ticks += 1
            if tail:
                self.tail_active_ticks += 1
            self.activation_integral += activation
            self.excess_activation_integral += excess
            self.peak_activation = max(self.peak_activation, activation)
            if self.first_active_tick is None:
                self.first_active_tick = tick
            self.last_active_tick = tick
        else:
            self._was_active = False
            self.current_active_run = 0

    def mark_absent(self) -> None:
        self._was_active = False
        self.current_active_run = 0


@dataclass(slots=True)
class _TemporalWindow:
    envelope_id: str
    source: str
    adapter_id: str
    frame_count: int
    start_tick: int
    baseline_start_tick: int | None
    baseline_end_tick: int | None
    baseline: dict[int, tuple[float, float]]
    config: dict[str, Any]
    partial_start: bool = False
    delivery_end_tick: int | None = None
    last_tick: int = 0
    observed_ticks: int = 0
    tail_ticks: int = 0
    nodes: dict[int, _NodeTimeline] = field(default_factory=dict)
    tail_top_sets: list[tuple[int, ...]] = field(default_factory=list)
    tail_vectors: list[dict[int, float]] = field(default_factory=list)
    tail_total_excess: list[float] = field(default_factory=list)
    overlapping_envelopes: set[str] = field(default_factory=set)


class TemporalConvergenceReadoutAdapter:
    """Accumulate stimulus-anchored response windows from immutable frames."""

    def __init__(self) -> None:
        self._baseline_frames: deque[tuple[int, dict[int, float]]] = deque()
        self._windows: dict[str, _TemporalWindow] = {}
        self._completed_envelopes: set[str] = set()
        self._completed_order: deque[str] = deque()
        self._last_tick = -1
        self._current: dict[str, Any] | None = None
        self._events: list[dict[str, Any]] = []

    def consume(
        self,
        frame: OutputFrame,
        config: dict[str, Any] | None = None,
        *,
        render: Callable[[list[int], str], str] | None = None,
        describe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """Observe exactly one tick and emit zero or more closed windows."""
        resolved = {**DEFAULT_TEMPORAL_CONFIG, **dict(config or {})}
        if frame.tick == self._last_tick:
            return self._view([], advanced=False)
        self._last_tick = frame.tick
        contexts = [dict(row) for row in frame.delta.get("input_envelopes", []) if isinstance(row, dict) and row.get("envelope_id")]

        new_ids: list[str] = []
        if bool(resolved.get("enabled", True)):
            for context in contexts:
                envelope_id = str(context["envelope_id"])
                if envelope_id in self._completed_envelopes:
                    continue
                if envelope_id not in self._windows and self._source_enabled(str(context.get("source", "unknown")), resolved):
                    self._windows[envelope_id] = self._start_window(frame, context, resolved)
                    new_ids.append(envelope_id)
                window = self._windows.get(envelope_id)
                if window is not None and int(context.get("frame_index", 0)) >= int(context.get("frame_count", 1)) - 1:
                    window.delivery_end_tick = frame.tick
        elif self._windows:
            events = [self._finish(window, frame, "interrupted", render=render, describe=describe) for window in list(self._windows.values())]
            self._windows.clear()
            self._append_baseline(frame, resolved)
            return self._record_events(events)

        if new_ids:
            active_ids = set(self._windows)
            for envelope_id in new_ids:
                for other in active_ids - {envelope_id}:
                    self._windows[envelope_id].overlapping_envelopes.add(other)
                    self._windows[other].overlapping_envelopes.add(envelope_id)

        closed: list[dict[str, Any]] = []
        for envelope_id, window in list(self._windows.items()):
            self._observe_window(window, frame)
            classification = self._closure_classification(window)
            if classification is None:
                continue
            closed.append(self._finish(window, frame, classification, render=render, describe=describe))
            self._windows.pop(envelope_id, None)
            self._mark_completed(envelope_id)

        self._append_baseline(frame, resolved)
        return self._record_events(closed)

    def _mark_completed(self, envelope_id: str) -> None:
        """Bound replay protection without retaining a lifetime of carriers."""
        if envelope_id in self._completed_envelopes:
            return
        while len(self._completed_order) >= 4096:
            expired = self._completed_order.popleft()
            self._completed_envelopes.discard(expired)
        self._completed_order.append(envelope_id)
        self._completed_envelopes.add(envelope_id)

    def _start_window(self, frame: OutputFrame, context: dict[str, Any], config: dict[str, Any]) -> _TemporalWindow:
        baseline, start_tick, end_tick = self._baseline_statistics(int(config.get("baseline_ticks", 12)))
        return _TemporalWindow(
            envelope_id=str(context["envelope_id"]),
            source=str(context.get("source", "unknown")),
            adapter_id=str(context.get("adapter_id", "unknown")),
            frame_count=max(1, int(context.get("frame_count", 1))),
            start_tick=frame.tick,
            baseline_start_tick=start_tick,
            baseline_end_tick=end_tick,
            baseline=baseline,
            config=dict(config),
            partial_start=int(context.get("frame_index", 0)) > 0,
            last_tick=frame.tick,
        )

    def _observe_window(self, window: _TemporalWindow, frame: OutputFrame) -> None:
        config = window.config
        threshold = max(0.0, float(config.get("activation_threshold", .055)))
        excess_min = max(0.0, float(config.get("excess_activation_min", .005)))
        noise_gain = max(0.0, float(config.get("baseline_noise_gain", 1.0)))
        tail = window.delivery_end_tick is not None and frame.tick > window.delivery_end_tick
        window.observed_ticks += 1
        if tail:
            window.tail_ticks += 1
        present: set[int] = set()
        active_excess: dict[int, float] = {}
        total_excess = 0.0
        for raw in frame.nodes:
            node_id = int(raw.get("id", -1))
            if node_id < 0:
                continue
            present.add(node_id)
            activation = max(0.0, float(raw.get("activation", 0.0)))
            inhibition = max(0.0, float(raw.get("inhibition", 0.0)))
            stability = max(0.0, float(raw.get("stability", 0.0)))
            direct_touch = max(0.0, float(raw.get("direct_touch", 0.0)))
            associative_touch = max(0.0, float(raw.get("associative_touch", 0.0)))
            baseline_mean, baseline_noise = window.baseline.get(node_id, (0.0, 0.0))
            excess = max(0.0, activation - baseline_mean - baseline_noise * noise_gain)
            active = activation >= threshold and excess >= excess_min
            if not active and direct_touch <= 0 and associative_touch <= 0 and node_id not in window.nodes:
                continue
            timeline = window.nodes.setdefault(node_id, _NodeTimeline(node_id, baseline_mean, baseline_noise))
            timeline.observe(
                tick=frame.tick, activation=activation, excess=excess, inhibition=inhibition,
                stability=stability, direct_touch=direct_touch, associative_touch=associative_touch,
                active=active, tail=tail,
            )
            if active:
                active_excess[node_id] = excess
                total_excess += excess
        for node_id in set(window.nodes) - present:
            window.nodes[node_id].mark_absent()
        window.last_tick = frame.tick
        if tail:
            top_count = max(1, int(config.get("display_limit", 7) or 7))
            ranked = sorted(active_excess, key=lambda node_id: (active_excess[node_id], -node_id), reverse=True)[:top_count]
            window.tail_top_sets.append(tuple(sorted(ranked)))
            window.tail_vectors.append({node_id: active_excess[node_id] for node_id in ranked})
            window.tail_total_excess.append(total_excess)

    def _closure_classification(self, window: _TemporalWindow) -> str | None:
        if window.delivery_end_tick is None:
            return None
        config = window.config
        minimum = max(1, int(config.get("min_response_ticks", 12)))
        maximum = max(minimum, int(config.get("max_response_ticks", 120)))
        settle = max(2, int(config.get("settle_ticks", 8)))
        if window.tail_ticks < minimum:
            return None
        sets = window.tail_top_sets[-settle:]
        vectors = window.tail_vectors[-settle:]
        totals = window.tail_total_excess[-settle:]
        period = self._period(window.tail_top_sets)
        if period is not None:
            return "oscillatory"
        if len(sets) >= settle and any(sets):
            jaccard = self._mean_jaccard(sets)
            drift = self._mean_distribution_drift(vectors)
            if jaccard >= float(config.get("convergence_jaccard_min", .80)) and drift <= float(config.get("convergence_drift_max", .12)):
                return "converged"
        if len(sets) >= settle and not any(sets):
            return "residual_decay" if max(window.tail_total_excess or [0.0]) > 0 else "transient"
        if window.tail_ticks < maximum:
            return None
        if self._is_decay(totals or window.tail_total_excess):
            return "residual_decay"
        return "unresolved"

    def _finish(
        self,
        window: _TemporalWindow,
        frame: OutputFrame,
        classification: str,
        *,
        render: Callable[[list[int], str], str] | None,
        describe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None,
    ) -> dict[str, Any]:
        ranked_all = self._rank(window)
        raw_limit = int(window.config.get("display_limit", 7) or 0)
        displayed = ranked_all if raw_limit <= 0 else ranked_all[:raw_limit]
        node_ids = [int(row["node_id"]) for row in displayed]
        selected_ids = set(node_ids)
        internal_edges = sum(1 for edge in frame.edges if int(edge.get("source", -1)) in selected_ids and int(edge.get("target", -1)) in selected_ids)
        signature_material = (
            classification,
            tuple((row["node_id"], round(float(row["active_ratio"]), 2), round(float(row["excess_activation_integral"]), 2)) for row in displayed),
        )
        signature = hashlib.blake2b(repr(signature_material).encode(), digest_size=8).hexdigest()
        anonymous_readout = f"temporal response {signature}"
        label_entries = self._label_entries(displayed, describe)
        readable_labels = self._readable_labels(label_entries)
        display_readout = " · ".join(readable_labels) if readable_labels else (render(node_ids, anonymous_readout) if render else anonymous_readout)
        convergence = self._convergence_metrics(window)
        return {
            "id": f"temporal-{frame.consciousness_id[:8]}-{signature}-{frame.tick}",
            "kind": "temporal_convergence_readout",
            "output_adapter": "temporal-convergence-readout",
            "readout_kind": "temporal",
            "tick": frame.tick,
            "start_tick": window.start_tick,
            "delivery_end_tick": window.delivery_end_tick,
            "end_tick": frame.tick,
            "baseline_start_tick": window.baseline_start_tick,
            "baseline_end_tick": window.baseline_end_tick,
            "envelope_id": window.envelope_id,
            "adapter_id": window.adapter_id,
            "source_provenance": [window.source],
            "background": self._source_category(window.source) == "ambient",
            "frame_count": window.frame_count,
            "partial_start": window.partial_start,
            "overlapping_envelopes": sorted(window.overlapping_envelopes),
            "classification": classification,
            "signature": signature,
            "readout": anonymous_readout,
            "anonymous_readout": anonymous_readout,
            "display_readout": display_readout,
            "node_ids": node_ids,
            "label_entries": label_entries,
            "readable_labels": readable_labels,
            "rankings": displayed,
            # All candidate metrics remain auditable; display_limit affects only
            # the human-facing projection above.
            "node_metrics": ranked_all,
            "internal_edges": internal_edges,
            "mean_activation": round(sum(float(row["mean_activation"]) for row in displayed) / len(displayed), 8) if displayed else 0.0,
            "occurrences": 1,
            "repeatable": classification in {"converged", "oscillatory"},
            "window": {"observed_ticks": window.observed_ticks, "tail_ticks": window.tail_ticks},
            "convergence": convergence,
            "configuration_snapshot": dict(window.config),
        }

    def _rank(self, window: _TemporalWindow) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        total_ticks = max(1, window.observed_ticks)
        tail_ticks = max(1, window.tail_ticks)
        for timeline in window.nodes.values():
            if timeline.active_ticks <= 0 and timeline.direct_touch_ticks <= 0 and timeline.associative_touch_ticks <= 0:
                continue
            origin = "mixed" if timeline.direct_touch_ticks and timeline.associative_touch_ticks else "associative" if timeline.associative_touch_ticks else "direct"
            rows.append({
                "node_id": timeline.node_id,
                "origin": origin,
                "baseline_mean": round(timeline.baseline_mean, 8),
                "baseline_noise": round(timeline.baseline_noise, 8),
                "active_ticks": timeline.active_ticks,
                "active_ratio": round(timeline.active_ticks / total_ticks, 8),
                "tail_active_ticks": timeline.tail_active_ticks,
                "tail_active_ratio": round(timeline.tail_active_ticks / tail_ticks, 8),
                "longest_active_run": timeline.longest_active_run,
                "reentry_count": timeline.reentry_count,
                "activation_integral": round(timeline.activation_integral, 8),
                "excess_activation_integral": round(timeline.excess_activation_integral, 8),
                "peak_activation": round(timeline.peak_activation, 8),
                "mean_activation": round(timeline.activation_integral / timeline.active_ticks, 8) if timeline.active_ticks else 0.0,
                "inhibition_integral": round(timeline.inhibition_integral, 8),
                "peak_inhibition": round(timeline.peak_inhibition, 8),
                "direct_touch_integral": round(timeline.direct_touch_integral, 8),
                "associative_touch_integral": round(timeline.associative_touch_integral, 8),
                "direct_touch_ticks": timeline.direct_touch_ticks,
                "associative_touch_ticks": timeline.associative_touch_ticks,
                "first_active_tick": timeline.first_active_tick,
                "last_active_tick": timeline.last_active_tick,
                "last_activation": round(timeline.last_activation, 8),
                "stability": round(timeline.last_stability, 8),
            })
        scope = str(window.config.get("candidate_scope", "associative-or-persistent"))
        candidates = rows
        if scope == "associative-or-persistent":
            filtered = [row for row in rows if int(row["associative_touch_ticks"]) > 0 or int(row["tail_active_ticks"]) > 0]
            candidates = filtered or rows
        elif scope == "associative-only":
            filtered = [row for row in rows if int(row["associative_touch_ticks"]) > 0]
            candidates = filtered or rows
        max_integral = max((float(row["excess_activation_integral"]) for row in candidates), default=0.0)
        consider_strength = bool(window.config.get("consider_activation_strength", True))
        for row in candidates:
            duration = float(row["active_ratio"])
            continuity = min(1.0, float(row["longest_active_run"]) / total_ticks)
            tail = float(row["tail_active_ratio"])
            strength = float(row["excess_activation_integral"]) / max_integral if max_integral > 0 else 0.0
            if consider_strength:
                score = .30 * duration + .20 * continuity + .20 * tail + .30 * strength
            else:
                score = .43 * duration + .29 * continuity + .28 * tail
            row["score"] = round(score, 8)
        mode = str(window.config.get("ranking_mode", "composite"))
        if mode == "duration":
            key = lambda row: (int(row["active_ticks"]), int(row["longest_active_run"]), float(row["excess_activation_integral"]), -int(row["node_id"]))
        elif mode == "activation-integral":
            key = lambda row: (float(row["excess_activation_integral"]), int(row["active_ticks"]), float(row["peak_activation"]), -int(row["node_id"]))
        else:
            key = lambda row: (float(row["score"]), int(row["active_ticks"]), float(row["excess_activation_integral"]), -int(row["node_id"]))
        return sorted(candidates, key=key, reverse=True)

    def _convergence_metrics(self, window: _TemporalWindow) -> dict[str, Any]:
        settle = max(2, int(window.config.get("settle_ticks", 8)))
        sets = window.tail_top_sets[-settle:]
        vectors = window.tail_vectors[-settle:]
        return {
            "mean_top_set_jaccard": round(self._mean_jaccard(sets), 8),
            "mean_distribution_drift": round(self._mean_distribution_drift(vectors), 8),
            "detected_period_ticks": self._period(window.tail_top_sets),
            "tail_peak_excess_activation": round(max(window.tail_total_excess or [0.0]), 8),
            "tail_final_excess_activation": round(window.tail_total_excess[-1], 8) if window.tail_total_excess else 0.0,
        }

    def _baseline_statistics(self, requested: int) -> tuple[dict[int, tuple[float, float]], int | None, int | None]:
        count = max(0, int(requested))
        frames = list(self._baseline_frames)[-count:] if count else []
        if not frames:
            return {}, None, None
        node_ids = {node_id for _tick, nodes in frames for node_id in nodes}
        result: dict[int, tuple[float, float]] = {}
        for node_id in node_ids:
            values = [nodes.get(node_id, 0.0) for _tick, nodes in frames]
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / len(values)
            result[node_id] = (mean, math.sqrt(max(0.0, variance)))
        return result, frames[0][0], frames[-1][0]

    def _append_baseline(self, frame: OutputFrame, config: dict[str, Any]) -> None:
        requested = max(1, int(config.get("baseline_ticks", 12)))
        self._baseline_frames.append((frame.tick, {int(node["id"]): float(node.get("activation", 0.0)) for node in frame.nodes}))
        while len(self._baseline_frames) > requested:
            self._baseline_frames.popleft()

    def _record_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        for event in events:
            self._current = event
            self._events.append(event)
        self._events = self._events[-2_000:]
        return self._view(events, advanced=True)

    def _view(self, new_events: list[dict[str, Any]], *, advanced: bool) -> dict[str, Any]:
        return {
            "current": self._current,
            "events": self._events[-100:],
            "new_events": new_events,
            "active_windows": [
                {
                    "envelope_id": window.envelope_id,
                    "source": window.source,
                    "start_tick": window.start_tick,
                    "delivery_end_tick": window.delivery_end_tick,
                    "last_tick": window.last_tick,
                    "tail_ticks": window.tail_ticks,
                }
                for window in self._windows.values()
            ],
            "advanced": advanced,
        }

    @staticmethod
    def _source_category(source: str) -> str:
        normalized = source.lower()
        if normalized.startswith(("ambient", "body", "interoceptive", "host-load", "background")):
            return "ambient"
        if normalized.startswith("ai"):
            return "ai"
        return "manual"

    @classmethod
    def _source_enabled(cls, source: str, config: dict[str, Any]) -> bool:
        category = cls._source_category(source)
        return bool(config.get(f"trigger_{category}", category == "manual"))

    @staticmethod
    def _mean_jaccard(sets: list[tuple[int, ...]]) -> float:
        if len(sets) < 2:
            return 0.0
        values: list[float] = []
        for left_raw, right_raw in zip(sets, sets[1:]):
            left, right = set(left_raw), set(right_raw)
            union = left | right
            values.append(len(left & right) / len(union) if union else 1.0)
        return sum(values) / len(values)

    @staticmethod
    def _mean_distribution_drift(vectors: list[dict[int, float]]) -> float:
        if len(vectors) < 2:
            return 1.0
        values: list[float] = []
        for left, right in zip(vectors, vectors[1:]):
            left_total, right_total = sum(left.values()), sum(right.values())
            keys = set(left) | set(right)
            if left_total <= 0 and right_total <= 0:
                values.append(0.0)
                continue
            values.append(.5 * sum(abs((left.get(key, 0.0) / left_total if left_total else 0.0) - (right.get(key, 0.0) / right_total if right_total else 0.0)) for key in keys))
        return sum(values) / len(values)

    @staticmethod
    def _period(sets: list[tuple[int, ...]]) -> int | None:
        for period in range(2, min(8, len(sets) // 3) + 1):
            if sets[-period:] == sets[-2 * period:-period] == sets[-3 * period:-2 * period] and len(set(sets[-period:])) > 1:
                return period
        return None

    @staticmethod
    def _is_decay(values: list[float]) -> bool:
        if len(values) < 3 or max(values) <= 0:
            return False
        tolerance = max(values) * .02
        non_increasing = sum(1 for left, right in zip(values, values[1:]) if right <= left + tolerance)
        return non_increasing >= len(values) - 2 and values[-1] <= max(values) * .35

    @staticmethod
    def _label_entries(
        rows: list[dict[str, Any]],
        describe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None,
    ) -> list[dict[str, Any]]:
        if describe is None or not rows:
            return []
        synthetic = [
            {
                "id": int(row["node_id"]),
                "activation": float(row["mean_activation"]),
                "stability": float(row["stability"]),
                "touch_count": int(row["direct_touch_ticks"]) + int(row["associative_touch_ticks"]),
                "direct_touch": float(row["direct_touch_integral"]),
                "associative_touch": float(row["associative_touch_integral"]),
            }
            for row in rows
        ]
        entries: list[dict[str, Any]] = []
        for raw in describe(synthetic):
            if not isinstance(raw, dict) or not str(raw.get("label") or "").strip():
                continue
            entries.append({
                "node_id": int(raw.get("node_id", -1)),
                "label": str(raw.get("label"))[:80],
                "activation": round(float(raw.get("activation", 0.0)), 8),
                "stability": round(float(raw.get("stability", 0.0)), 8),
                "touch_count": int(raw.get("touch_count", 0)),
                "direct_touch": round(float(raw.get("direct_touch", 0.0)), 8),
                "associative_touch": round(float(raw.get("associative_touch", 0.0)), 8),
            })
        return entries

    @staticmethod
    def _readable_labels(entries: list[dict[str, Any]]) -> list[str]:
        labels: list[str] = []
        for entry in entries:
            label = str(entry["label"])
            if label not in labels:
                labels.append(label)
        return labels
