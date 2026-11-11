"""Read-only output adapters for anonymous ThreeMind activity frames."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Callable

from threemind.frames import OutputFrame


class StructuralReadoutAdapter:
    """Passive structural observer attached to an :class:`OutputBus`.

    This adapter never queries or mutates a runtime.  It sees anonymous output
    frames only.  A renderer may add external labels for observation, but those
    labels are stored separately from the anonymous structural record.
    """

    def __init__(self) -> None:
        self._occurrences: dict[str, list[int]] = defaultdict(list)
        self._cooldowns: dict[str, int] = {}
        self._last_tick = -1
        self._last_background_tick = -1
        self._seen_passive_signatures: set[str] = set()
        self._seen_background_signatures: set[str] = set()
        self._current: dict[str, Any] | None = None
        self._events: list[dict[str, Any]] = []

    def restore(self, observations: list[dict[str, Any]]) -> None:
        """Restore recurrence evidence from durable observer records.

        The adapter remains an output-only observer.  This method only rebuilds
        its own counters after a host restart; it never replays an observation
        into Core and never fabricates an occurrence that was not persisted.
        """
        for raw in observations:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("kind") or "")
            if kind not in {"structural_readout", "repeatable_output_structure"}:
                continue
            state_signature = str(raw.get("state_signature") or raw.get("signature") or "")
            if not state_signature:
                continue
            tick = int(raw.get("tick", raw.get("last_seen_tick", -1)))
            if tick < 0:
                continue
            ticks = self._occurrences[state_signature]
            if tick not in ticks:
                ticks.append(tick)
                ticks.sort()
            if kind == "repeatable_output_structure":
                self._cooldowns[state_signature] = max(self._cooldowns.get(state_signature, -1), tick)

    @staticmethod
    def _digest(value: Any) -> str:
        material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.blake2b(material.encode("utf-8"), digest_size=10).hexdigest()

    @classmethod
    def _topology_class_id(cls, node_ids: set[int], edges: list[dict[str, Any]]) -> str:
        """Return an identity-free directed topology fingerprint.

        This lightweight Weisfeiler-Lehman refinement is deterministic and
        intentionally ignores activation, weights, labels and node ids.  It is
        suitable for grouping candidate isomorphism classes; the frozen
        subgraph remains the primary auditable evidence.
        """
        outgoing = {node_id: [] for node_id in node_ids}
        incoming = {node_id: [] for node_id in node_ids}
        for edge in edges:
            source, target = int(edge["source"]), int(edge["target"])
            if source in outgoing and target in incoming:
                outgoing[source].append(target)
                incoming[target].append(source)
        colors = {
            node_id: f"{len(incoming[node_id])}:{len(outgoing[node_id])}"
            for node_id in node_ids
        }
        for _ in range(max(1, min(8, len(node_ids)))):
            refined = {
                node_id: cls._digest({
                    "self": colors[node_id],
                    "in": sorted(colors[value] for value in incoming[node_id]),
                    "out": sorted(colors[value] for value in outgoing[node_id]),
                })
                for node_id in node_ids
            }
            if all(refined[node_id] == colors[node_id] for node_id in node_ids):
                break
            colors = refined
        edge_colors = sorted((colors[int(edge["source"])], colors[int(edge["target"])]) for edge in edges)
        return cls._digest({"nodes": sorted(colors.values()), "edges": edge_colors})

    def consume(
        self,
        frame: OutputFrame,
        config: dict[str, Any],
        *,
        render: Callable[[list[int], str], str] | None = None,
        describe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """Observe one output frame and produce passive output events.

        A repeatable structure is intentionally a stricter observation than a
        local response.  The former needs a stable induced subgraph; the
        latter is an auditable projection of the *actual direct and
        associative touch set* published by the output bus.  Keeping the two
        paths separate means a small, short-lived associative response is not
        silently discarded merely because it is not yet a repeatable graph
        structure.
        """
        if frame.tick == self._last_tick and self._current is not None:
            return {
                "current": self._current,
                "events": self._events[-100:],
                "config": config,
                "new_event": None,
                "new_passive_event": None,
                "advanced": False,
            }
        self._last_tick = frame.tick
        structural = self._structural_current(frame, config, render=render, describe=describe)
        activity = self._touched_activity_current(frame, config, render=render, describe=describe)
        # A direct/associative packet is the most immediate evidence of the
        # response to the newest sensory frame.  It is shown in preference to
        # the broader structural candidate while preserving the latter for
        # recurrence detection below.
        self._current = activity or structural or self._empty(frame.tick, 0)
        strict_deduplicate = bool(config.get("strict_deduplicate", False))
        new_passive_event = None
        if activity is not None:
            passive_signature = f"activity|{activity['signature']}"
            if not strict_deduplicate or passive_signature not in self._seen_passive_signatures:
                self._seen_passive_signatures.add(passive_signature)
                new_passive_event = self._passive_event(
                    frame=frame,
                    current=activity,
                    kind="activated_node_readout",
                    event_id=f"output-activity-{frame.consciousness_id[:8]}-{activity['signature']}-{frame.tick}",
                )
        elif structural is not None:
            passive_signature = f"structure|{structural['signature']}|{tuple(structural['node_ids'])}|{structural['internal_edges']}"
            if not strict_deduplicate or passive_signature not in self._seen_passive_signatures:
                self._seen_passive_signatures.add(passive_signature)
                new_passive_event = self._passive_event(
                    frame=frame,
                    current=structural,
                    kind="structural_readout",
                    event_id=f"output-readout-{frame.consciousness_id[:8]}-{structural['signature']}-{frame.tick}",
                )

        new_event = self._repeatable_event(frame, structural, config)
        return self._view(config, new_event=new_event, new_passive_event=new_passive_event, advanced=True)

    def _structural_current(
        self,
        frame: OutputFrame,
        config: dict[str, Any],
        *,
        render: Callable[[list[int], str], str] | None,
        describe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None,
    ) -> dict[str, Any] | None:
        """Build the strict induced-subgraph candidate used for recurrence."""
        threshold = float(config.get("activation_threshold", .055))
        min_nodes = max(1, int(config.get("min_nodes", 3)))
        max_nodes = max(min_nodes, int(config.get("max_nodes", 7)))
        min_edges = max(0, int(config.get("min_internal_edges", 2)))
        selected = sorted(
            (node for node in frame.nodes if float(node["activation"]) >= threshold),
            key=self._activity_rank,
            reverse=True,
        )[:max_nodes]
        if len(selected) < min_nodes:
            return None
        ids = {int(node["id"]) for node in selected}
        internal = [edge for edge in frame.edges if int(edge["source"]) in ids and int(edge["target"]) in ids]
        if len(internal) < min_edges:
            return None
        fingerprint = [
            (round(float(node["activation"]) * 5), round(float(node["stability"]) * 5), min(4, int(node["touch_count"]) // 3))
            for node in selected
        ]
        edge_fingerprint = sorted(
            (round(float(edge["weight"]) * 5), round(float(edge["stability"]) * 5))
            for edge in internal
        )
        state_signature = hashlib.blake2b(repr((sorted(fingerprint), edge_fingerprint)).encode(), digest_size=8).hexdigest()
        exact_edges = sorted((int(edge["source"]), int(edge["target"])) for edge in internal)
        structure_id = self._digest({"nodes": sorted(ids), "edges": exact_edges})
        topology_class_id = self._topology_class_id(ids, internal)
        window = max(1, int(config.get("recurrence_window_ticks", 240)))
        occurrences = [tick for tick in self._occurrences[state_signature] if frame.tick - tick <= window]
        occurrences.append(frame.tick)
        self._occurrences[state_signature] = occurrences
        display_nodes = self._display_nodes(selected, config)
        node_ids = [int(node["id"]) for node in display_nodes]
        anonymous_readout = f"anonymous structure {state_signature}"
        label_entries = self._label_entries(display_nodes, describe)
        readable_labels = self._readable_labels(label_entries)
        display_readout = self._display_readout(node_ids, anonymous_readout, readable_labels, render, config)
        return {
            "tick": frame.tick,
            "text": display_readout,
            "anonymous_readout": anonymous_readout,
            "display_readout": display_readout,
            # ``signature`` remains a compatibility alias for the former
            # instantaneous state fingerprint.  Scientific consumers should
            # choose explicitly between the three identities below.
            "signature": state_signature,
            "state_signature": state_signature,
            "structure_id": structure_id,
            "topology_class_id": topology_class_id,
            "occurrence_id": f"{frame.consciousness_id}:{frame.tick}:{structure_id}:{state_signature}",
            "node_ids": node_ids,
            "label_entries": label_entries,
            "readable_labels": readable_labels,
            "internal_edges": len(internal),
            "mean_activation": round(sum(float(node["activation"]) for node in selected) / len(selected), 6),
            "occurrences": len(occurrences),
            "repeatable": False,
            "readout_kind": "structural",
            "background": bool(frame.delta.get("background_only", False)),
            "source_provenance": [str(source) for source in frame.delta.get("causal_sources", frame.delta.get("frame_sources", []))],
            "subgraph": {
                "tick": frame.tick,
                "nodes": [
                    {
                        "id": int(node["id"]),
                        "activation": round(float(node.get("activation", 0.0)), 8),
                        "inhibition": round(float(node.get("inhibition", 0.0)), 8),
                        "stability": round(float(node.get("stability", 0.0)), 8),
                        "touch_count": int(node.get("touch_count", 0)),
                        "direct_touch": round(float(node.get("direct_touch", 0.0)), 8),
                        "associative_touch": round(float(node.get("associative_touch", 0.0)), 8),
                        "position": list(node.get("position")) if node.get("position") is not None else None,
                    }
                    for node in selected
                ],
                "edges": [
                    {
                        "source": int(edge["source"]),
                        "target": int(edge["target"]),
                        "weight": round(float(edge.get("weight", 0.0)), 8),
                        "stability": round(float(edge.get("stability", 0.0)), 8),
                    }
                    for edge in internal
                ],
            },
        }

    def _touched_activity_current(
        self,
        frame: OutputFrame,
        config: dict[str, Any],
        *,
        render: Callable[[list[int], str], str] | None,
        describe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None,
    ) -> dict[str, Any] | None:
        """Project the local direct/associative response of the current frame.

        This is deliberately not a second graph operation.  ``direct_nodes``
        and ``associated_nodes`` are already produced by Core's local cascade;
        the readout adapter only projects that published evidence.
        """
        if not bool(config.get("read_touched_activity", True)):
            return None
        direct_ids = [int(value) for value in frame.delta.get("direct_nodes", ())]
        associated_ids = [int(value) for value in frame.delta.get("associated_nodes", ())]
        touched_ids = list(dict.fromkeys(direct_ids + associated_ids))
        if not touched_ids:
            return None
        nodes_by_id = {int(node["id"]): node for node in frame.nodes}
        selected = [nodes_by_id[node_id] for node_id in touched_ids if node_id in nodes_by_id]
        if not selected:
            return None
        display_nodes = self._display_nodes(selected, config)
        node_ids = [int(node["id"]) for node in display_nodes]
        direct_set = set(direct_ids)
        associated_set = set(associated_ids)
        signature = hashlib.blake2b(
            repr((tuple(sorted(node_ids)), tuple(sorted(direct_set)), tuple(sorted(associated_set)))).encode(),
            digest_size=8,
        ).hexdigest()
        selected_ids = set(node_ids)
        internal = [edge for edge in frame.edges if int(edge["source"]) in selected_ids and int(edge["target"]) in selected_ids]
        anonymous_readout = f"anonymous activation {signature}"
        label_entries = self._label_entries(display_nodes, describe)
        readable_labels = self._readable_labels(label_entries)
        display_readout = self._display_readout(node_ids, anonymous_readout, readable_labels, render, config)
        return {
            "tick": frame.tick,
            "text": display_readout,
            "anonymous_readout": anonymous_readout,
            "display_readout": display_readout,
            "signature": signature,
            "node_ids": node_ids,
            "label_entries": label_entries,
            "readable_labels": readable_labels,
            "internal_edges": len(internal),
            "mean_activation": round(sum(float(node["activation"]) for node in selected) / len(selected), 6),
            "occurrences": 1,
            "repeatable": False,
            "readout_kind": "touched_activity",
            "direct_node_ids": sorted(direct_set),
            "associative_node_ids": sorted(associated_set),
            "background": bool(frame.delta.get("background_only", False)),
            "source_provenance": [str(source) for source in frame.delta.get("causal_sources", frame.delta.get("frame_sources", []))],
        }

    def _repeatable_event(
        self,
        frame: OutputFrame,
        current: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        if current is None:
            return None
        min_occurrences = max(1, int(config.get("min_occurrences", 4)))
        min_span = max(0, int(config.get("min_span_ticks", 8)))
        cooldown = max(0, int(config.get("alert_cooldown_ticks", 1200)))
        signature = str(current["signature"])
        occurrences = self._occurrences[signature]
        if not (
            len(occurrences) >= min_occurrences
            and occurrences[-1] - occurrences[0] >= min_span
        ):
            return None
        current["repeatable"] = True
        if not bool(config.get("repeatable_structure_readout", True)):
            return None
        if frame.tick - self._cooldowns.get(signature, -cooldown) < cooldown:
            return None
        self._cooldowns[signature] = frame.tick
        event = {
            "id": f"output-struct-{frame.consciousness_id[:8]}-{signature}-{frame.tick}",
            "kind": "repeatable_output_structure",
            "output_adapter": "structural-readout",
            "tick": frame.tick,
            "first_seen_tick": occurrences[0],
            "last_seen_tick": occurrences[-1],
            "occurrences": len(occurrences),
            "signature": signature,
            "state_signature": str(current.get("state_signature") or signature),
            "structure_id": str(current.get("structure_id") or ""),
            "topology_class_id": str(current.get("topology_class_id") or ""),
            "occurrence_id": str(current.get("occurrence_id") or ""),
            "node_ids": list(current["node_ids"]),
            "internal_edges": int(current["internal_edges"]),
            "mean_activation": current["mean_activation"],
            # The anonymous record is the scientific primary.  The labels
            # below are only annotations supplied outside Core.
            "readout": current["anonymous_readout"],
            "anonymous_readout": current["anonymous_readout"],
            "display_readout": current["display_readout"],
            "label_entries": list(current["label_entries"]),
            "readable_labels": list(current["readable_labels"]),
            "background": bool(current["background"]),
            "source_provenance": list(current["source_provenance"]),
            "subgraph": dict(current.get("subgraph") or {}),
            "delivery": {"state": "not_configured"},
        }
        self._events.append(event)
        self._events = self._events[-2_000:]
        return event

    def consume_background_activity(
        self,
        frame: OutputFrame,
        config: dict[str, Any],
        *,
        render: Callable[[list[int], str], str] | None = None,
        describe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        """Read a background-only activation frame without involving an AI.

        ``background_only`` is provenance supplied by the runtime for a single
        input-frame transition.  This method cannot change the graph or create
        a Core stimulus; it only makes that already-existing activity visible.
        """
        if frame.tick == self._last_background_tick:
            return {"current": None, "new_event": None, "advanced": False}
        self._last_background_tick = frame.tick
        if not bool(frame.delta.get("background_only", False)):
            return {"current": None, "new_event": None, "advanced": True}
        low = max(0.0, min(1.0, float(config.get("activation_min", .08))))
        high = max(low, min(1.0, float(config.get("activation_max", 1.0))))
        max_nodes = max(1, int(config.get("max_nodes", 7)))
        selected = sorted(
            (node for node in frame.nodes if low <= float(node.get("activation", 0.0)) <= high),
            key=self._activity_rank,
            reverse=True,
        )[:max_nodes]
        if not selected:
            return {"current": None, "new_event": None, "advanced": True}
        display_nodes = self._display_nodes(selected, config)
        node_ids = [int(node["id"]) for node in display_nodes]
        signature = hashlib.blake2b(repr(tuple(node_ids)).encode(), digest_size=8).hexdigest()
        anonymous_readout = f"anonymous background activity {signature}"
        label_entries = self._label_entries(display_nodes, describe)
        readable_labels = self._readable_labels(label_entries)
        display_readout = self._display_readout(node_ids, anonymous_readout, readable_labels, render, config)
        current = {
            "tick": frame.tick,
            "text": display_readout,
            "anonymous_readout": anonymous_readout,
            "display_readout": display_readout,
            "signature": signature,
            "node_ids": node_ids,
            "label_entries": label_entries,
            "readable_labels": readable_labels,
            "internal_edges": 0,
            "mean_activation": round(sum(float(node["activation"]) for node in selected) / len(selected), 6),
            "occurrences": 1,
            "repeatable": False,
            "readout_kind": "background_activity",
            "background": True,
            "source_provenance": [str(source) for source in frame.delta.get("causal_sources", frame.delta.get("frame_sources", []))],
        }
        strict_deduplicate = bool(config.get("strict_deduplicate", False))
        if strict_deduplicate and signature in self._seen_background_signatures:
            return {"current": current, "new_event": None, "advanced": True}
        self._seen_background_signatures.add(signature)
        event = self._passive_event(
            frame=frame,
            current=current,
            kind="background_active_nodes",
            event_id=f"output-background-{frame.consciousness_id[:8]}-{signature}-{frame.tick}",
        )
        event["background"] = True
        return {"current": current, "new_event": event, "advanced": True}

    def _view(
        self,
        config: dict[str, Any],
        *,
        new_event: dict[str, Any] | None,
        new_passive_event: dict[str, Any] | None,
        advanced: bool,
    ) -> dict[str, Any]:
        return {
            "current": self._current,
            "events": self._events[-100:],
            "config": config,
            "new_event": new_event,
            "new_passive_event": new_passive_event,
            "advanced": advanced,
        }

    @staticmethod
    def _activity_rank(node: dict[str, Any]) -> tuple[float, float, float, int]:
        """Deterministic ranking used only for choosing candidate activity."""
        return (
            float(node.get("activation", 0.0)),
            float(node.get("direct_touch", 0.0)) + float(node.get("associative_touch", 0.0)),
            float(node.get("stability", 0.0)),
            -int(node.get("id", 0)),
        )

    def _display_nodes(self, selected: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
        """Order only the human-facing label projection, never Core state."""
        if bool(config.get("label_sort_by_activation", True)):
            return sorted(selected, key=self._activity_rank, reverse=True)
        # Numeric identity is deliberately used only as a stable visual order
        # when the observer's activation-order presentation is disabled.
        return sorted(selected, key=lambda node: int(node.get("id", 0)))

    @staticmethod
    def _display_readout(
        node_ids: list[int],
        fallback: str,
        readable_labels: list[str],
        render: Callable[[list[int], str], str] | None,
        config: dict[str, Any],
    ) -> str:
        """Render all external labels unless an explicit display limit exists."""
        if readable_labels:
            raw_limit = int(config.get("label_display_limit", 0) or 0)
            labels = readable_labels if raw_limit <= 0 else readable_labels[:raw_limit]
            return " · ".join(labels)
        return render(node_ids, fallback) if render else fallback

    @staticmethod
    def _label_entries(
        selected: list[dict[str, Any]],
        describe: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None,
    ) -> list[dict[str, Any]]:
        if describe is None:
            return []
        entries: list[dict[str, Any]] = []
        for raw in describe(selected):
            if not isinstance(raw, dict):
                continue
            label = str(raw.get("label") or "").strip()
            if not label:
                continue
            entries.append({
                "node_id": int(raw.get("node_id", -1)),
                "label": label[:80],
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

    @staticmethod
    def _passive_event(
        *,
        frame: OutputFrame,
        current: dict[str, Any],
        kind: str,
        event_id: str,
    ) -> dict[str, Any]:
        return {
            "id": event_id,
            "kind": kind,
            "output_adapter": "structural-readout",
            "tick": frame.tick,
            "signature": current["signature"],
            "state_signature": str(current.get("state_signature") or current["signature"]),
            "structure_id": str(current.get("structure_id") or ""),
            "topology_class_id": str(current.get("topology_class_id") or ""),
            "occurrence_id": str(current.get("occurrence_id") or event_id),
            "node_ids": list(current["node_ids"]),
            "internal_edges": int(current["internal_edges"]),
            "mean_activation": current["mean_activation"],
            "readout_kind": str(current.get("readout_kind", "structural")),
            "direct_node_ids": list(current.get("direct_node_ids", [])),
            "associative_node_ids": list(current.get("associative_node_ids", [])),
            # Anonymous structure remains the primary exported record.  Labels
            # are explicitly external annotations for observation/debugging.
            "readout": current["anonymous_readout"],
            "anonymous_readout": current["anonymous_readout"],
            "display_readout": current["display_readout"],
            "label_entries": list(current["label_entries"]),
            "readable_labels": list(current["readable_labels"]),
            "occurrences": int(current["occurrences"]),
            "background": bool(current.get("background", frame.delta.get("background_only", False))),
            "source_provenance": [str(source) for source in current.get("source_provenance", frame.delta.get("causal_sources", frame.delta.get("frame_sources", [])))],
            "subgraph": dict(current.get("subgraph") or {}),
        }

    @staticmethod
    def _empty(tick: int, internal_edges: int) -> dict[str, Any]:
        text = "(no repeatable structural pattern)"
        return {
            "tick": tick,
            "text": text,
            "anonymous_readout": text,
            "display_readout": text,
            "node_ids": [],
            "label_entries": [],
            "readable_labels": [],
            "occurrences": 0,
            "internal_edges": internal_edges,
            "repeatable": False,
            "readout_kind": "none",
        }


class CharacterDriver:
    """Optional external character/label projection for structural readouts.

    It is absent for anonymous models.  It never supplies labels to Core; it
    only reads annotations that an input adapter already registered.
    """

    def __init__(self, label_for_node: Callable[[int], str | None]) -> None:
        self._label_for_node = label_for_node

    def render(self, node_ids: list[int], fallback: str) -> str:
        labels = [self._label_for_node(node_id) for node_id in node_ids]
        labels = [label for label in labels if label]
        return " · ".join(dict.fromkeys(labels[:7])) if labels else fallback

    def describe(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return display-only annotations in the input activation order."""
        entries: list[dict[str, Any]] = []
        for node in nodes:
            node_id = int(node["id"])
            label = self._label_for_node(node_id)
            if not label:
                continue
            entries.append({
                "node_id": node_id,
                "label": label,
                "activation": float(node.get("activation", 0.0)),
                "stability": float(node.get("stability", 0.0)),
                "touch_count": int(node.get("touch_count", 0)),
                "direct_touch": float(node.get("direct_touch", 0.0)),
                "associative_touch": float(node.get("associative_touch", 0.0)),
            })
        return entries
