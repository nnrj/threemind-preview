from __future__ import annotations

"""Read-only statistics and reproducible evidence export for ThreeMind."""

import csv
import hashlib
import io
import json
import math
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


DATASET_SCHEMA = "threemind-evidence-dataset/1.0.0"


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _json_digest(value: Any, *, size: int = 10) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.blake2b(encoded, digest_size=size).hexdigest()


def _source_values(event: dict[str, Any]) -> list[str]:
    values = event.get("source_provenance")
    if isinstance(values, list) and values:
        return [str(value) for value in values]
    source = event.get("source")
    return [str(source)] if source else ["unknown"]


def _structure_identity(event: dict[str, Any]) -> tuple[str, str]:
    exact = str(event.get("structure_id") or "")
    if exact:
        return exact, "exact"
    node_ids = sorted(int(value) for value in event.get("node_ids", []) if isinstance(value, (int, float, str)) and str(value).lstrip("-").isdigit())
    subgraph = event.get("subgraph") if isinstance(event.get("subgraph"), dict) else {}
    edges = sorted(
        (int(edge.get("source", -1)), int(edge.get("target", -1)))
        for edge in subgraph.get("edges", []) if isinstance(edge, dict)
    )
    if edges:
        return _json_digest({"nodes": node_ids, "edges": edges}), "reconstructed-exact"
    # Older observer records stored an edge count but not edge identity.  Keep
    # them queryable while marking the identity as approximate rather than
    # pretending they are equivalent to post-contract evidence.
    return _json_digest({"nodes": node_ids, "edge_count": int(event.get("internal_edges", 0))}), "legacy-approximate"


class AnalyticsService:
    """Derive statistics from one immutable history document and graph view."""

    def __init__(self, document: dict[str, Any], graph: dict[str, Any] | None = None, *, origin: str = "unknown") -> None:
        self.document = dict(document)
        self.graph = dict(graph) if isinstance(graph, dict) else None
        self.origin = str(origin)

    @property
    def consciousness_id(self) -> str:
        return str(self.document.get("consciousness_id") or (self.graph or {}).get("metrics", {}).get("id") or "")

    def overview(self) -> dict[str, Any]:
        structures = self.structure_catalog()
        temporal = self.temporal_catalog()
        trace = sorted(_rows(self.document.get("trace_entries")), key=lambda row: int(row.get("tick", 0)))
        stimuli = _rows(self.document.get("stimuli"))
        observations = _rows(self.document.get("observations"))
        metrics = dict((self.graph or {}).get("metrics") or {})
        if not metrics:
            metrics = {
                "id": self.consciousness_id,
                "name": self.document.get("consciousness_name"),
                "tick": int(self.document.get("tick", 0)),
                "life_state": self.document.get("life_state", "stored"),
            }
        sources = Counter(str(row.get("source") or "unknown") for row in stimuli)
        return {
            "schema": "threemind-analytics-overview/1.0.0",
            "consciousness_id": self.consciousness_id,
            "origin": self.origin,
            "metrics": metrics,
            "counts": {
                "stimuli": len(stimuli),
                "events": len(_rows(self.document.get("events"))),
                "observations": len(observations),
                "interpretations": len(_rows(self.document.get("interpretations"))),
                "trace_entries": len(trace),
                "repeatable_structures": len(structures),
                "temporal_windows": len(temporal),
            },
            "stimulus_sources": dict(sources),
            "trace": {
                "available": bool(trace),
                "starts_with_keyframe": bool(trace and trace[0].get("kind") == "dynamics_keyframe"),
                "first_tick": int(trace[0].get("tick", 0)) if trace else None,
                "last_tick": int(trace[-1].get("tick", 0)) if trace else None,
            },
            "measurement_contract": {
                "structure_identity": "exact node and directed-edge identity where available",
                "topology_class": "identity-free candidate class, not a proof of graph isomorphism",
                "state_signature": "quantized instantaneous activation/stability fingerprint",
                "labels": "external observation annotations, never Core dynamics",
            },
        }

    def dynamics(
        self,
        *,
        from_tick: int | None = None,
        to_tick: int | None = None,
        max_points: int = 1500,
        node_ids: Iterable[int] = (),
    ) -> dict[str, Any]:
        trace = sorted(_rows(self.document.get("trace_entries")), key=lambda row: int(row.get("tick", 0)))
        selected_node_ids = tuple(dict.fromkeys(int(value) for value in node_ids))[:64]
        nodes: dict[int, dict[str, float]] = {}
        node_count: int | None = None
        edge_count: int | None = None
        series: list[dict[str, Any]] = []
        for entry in trace:
            tick = int(entry.get("tick", 0))
            if entry.get("kind") == "dynamics_keyframe":
                nodes = {
                    int(row["id"]): {
                        "activation": float(row.get("activation", 0.0)),
                        "inhibition": float(row.get("inhibition", 0.0)),
                        "support": float(row.get("support", 0.0)),
                    }
                    for row in entry.get("nodes", []) if isinstance(row, dict) and "id" in row
                }
                node_count = int(entry.get("node_count", len(nodes)))
                edge_count = int(entry["edge_count"]) if entry.get("edge_count") is not None else (len(entry["edges"]) if isinstance(entry.get("edges"), list) else None)
            else:
                for row in entry.get("node_dynamics", []):
                    if not isinstance(row, dict) or "id" not in row:
                        continue
                    node_id = int(row["id"])
                    after = row.get("after") if isinstance(row.get("after"), dict) else {}
                    nodes[node_id] = {
                        "activation": float(after.get("activation", 0.0)),
                        "inhibition": float(after.get("inhibition", 0.0)),
                        "support": float(after.get("support", 0.0)),
                    }
                created_nodes = len(entry.get("created_nodes", []))
                removed_nodes = len(entry.get("removed_nodes", []))
                if node_count is not None:
                    node_count += created_nodes - removed_nodes
                for value in entry.get("removed_nodes", []):
                    try:
                        nodes.pop(int(value), None)
                    except (TypeError, ValueError):
                        pass
                created_edges = len(entry.get("created_edges", []))
                removed_edges = len(entry.get("removed_edges", []))
                if edge_count is not None:
                    edge_count += created_edges - removed_edges
            if from_tick is not None and tick < int(from_tick):
                continue
            if to_tick is not None and tick > int(to_tick):
                continue
            activations = [max(0.0, row["activation"]) for row in nodes.values()]
            inhibitions = [max(0.0, row["inhibition"]) for row in nodes.values()]
            point: dict[str, Any] = {
                "tick": tick,
                "node_count": node_count if node_count is not None else len(nodes),
                "edge_count": edge_count,
                "active_nodes": sum(value > 0.0 for value in activations),
                "total_activation": round(sum(activations), 8),
                "total_inhibition": round(sum(inhibitions), 8),
                "created_nodes": len(entry.get("created_nodes", [])),
                "removed_nodes": len(entry.get("removed_nodes", [])),
                "created_edges": len(entry.get("created_edges", [])),
                "removed_edges": len(entry.get("removed_edges", [])),
                "strengthened_edges": len(entry.get("strengthened_edges", [])),
                "weakened_edges": len(entry.get("weakened_edges", [])),
                "direct_nodes": len(entry.get("direct_nodes", [])),
                "associated_nodes": len(entry.get("associated_nodes", [])),
                "external_energy": float(entry.get("external_energy", 0.0)),
                "inhibition_generated": float(entry.get("inhibition_generated", 0.0)),
                "inhibition_transferred": float(entry.get("inhibition_transferred", 0.0)),
            }
            if selected_node_ids:
                # Kept on the point until downsampling so node traces use the
                # exact same sampled ticks as the aggregate series. Missing or
                # lesioned nodes are explicit rather than silently omitted.
                point["_selected_nodes"] = {
                    str(node_id): ({**nodes[node_id], "present": True} if node_id in nodes else {
                        "activation": 0.0,
                        "inhibition": 0.0,
                        "support": 0.0,
                        "present": False,
                    })
                    for node_id in selected_node_ids
                }
            series.append(point)
        original_count = len(series)
        limit = max(10, min(int(max_points), 10_000))
        if len(series) > limit:
            stride = math.ceil(len(series) / limit)
            sampled = series[::stride]
            if sampled[-1] is not series[-1]:
                sampled.append(series[-1])
            series = sampled
        node_series: list[dict[str, Any]] = []
        if selected_node_ids:
            for point in series:
                selected = point.pop("_selected_nodes", {})
                for node_id in selected_node_ids:
                    state = dict(selected.get(str(node_id), {}))
                    node_series.append({
                        "tick": int(point["tick"]),
                        "node_id": node_id,
                        "present": bool(state.get("present", False)),
                        "activation": round(float(state.get("activation", 0.0)), 8),
                        "inhibition": round(float(state.get("inhibition", 0.0)), 8),
                        "support": round(float(state.get("support", 0.0)), 8),
                    })
        return {
            "schema": "threemind-dynamics-series/1.0.0",
            "consciousness_id": self.consciousness_id,
            "origin": self.origin,
            "trace_available": bool(trace),
            "exact_edge_counts": any(row.get("edge_count") is not None for row in trace if row.get("kind") == "dynamics_keyframe"),
            "original_points": original_count,
            "sampled": original_count != len(series),
            "selected_node_ids": list(selected_node_ids),
            "node_series": node_series,
            "series": series,
        }

    def structure_catalog(self) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for event in sorted(_rows(self.document.get("observations")), key=lambda row: int(row.get("tick", 0))):
            if str(event.get("kind") or "") not in {"structural_readout", "repeatable_output_structure"}:
                continue
            structure_id, quality = _structure_identity(event)
            state_signature = str(event.get("state_signature") or event.get("signature") or "")
            tick = int(event.get("tick", event.get("last_seen_tick", 0)))
            occurrence_key = str(event.get("occurrence_id") or f"{tick}:{structure_id}:{state_signature}")
            row = groups.setdefault(structure_id, {
                "structure_id": structure_id,
                "identity_quality": quality,
                "topology_class_id": str(event.get("topology_class_id") or ""),
                "first_tick": tick,
                "last_tick": tick,
                "occurrences": 0,
                "repeatable_alerts": 0,
                "state_signatures": Counter(),
                "source_counts": Counter(),
                "node_ids": list(event.get("node_ids", [])),
                "node_count": len(event.get("node_ids", [])),
                "internal_edges": int(event.get("internal_edges", 0)),
                "mean_activation_sum": 0.0,
                "labels": [],
                "latest_subgraph": dict(event.get("subgraph") or {}),
                "latest_event": dict(event),
            })
            row["first_tick"] = min(int(row["first_tick"]), tick)
            row["last_tick"] = max(int(row["last_tick"]), tick)
            if event.get("subgraph"):
                row["latest_subgraph"] = dict(event["subgraph"])
            row["latest_event"] = dict(event)
            if str(event.get("kind")) == "repeatable_output_structure":
                row["repeatable_alerts"] += 1
            if occurrence_key in seen:
                continue
            seen.add(occurrence_key)
            row["occurrences"] += 1
            row["mean_activation_sum"] += float(event.get("mean_activation", 0.0))
            row["state_signatures"][state_signature or "unknown"] += 1
            for source in _source_values(event):
                row["source_counts"][source] += 1
            for label in event.get("readable_labels", []):
                value = str(label)
                if value and value not in row["labels"]:
                    row["labels"].append(value)
        output: list[dict[str, Any]] = []
        for row in groups.values():
            count = max(1, int(row.pop("occurrences")))
            row["occurrences"] = count
            row["mean_activation"] = round(float(row.pop("mean_activation_sum")) / count, 8)
            row["state_signatures"] = dict(row["state_signatures"])
            row["source_counts"] = dict(row["source_counts"])
            total_sources = sum(row["source_counts"].values()) or 1
            row["source_proportions"] = {key: round(value / total_sources, 8) for key, value in row["source_counts"].items()}
            output.append(row)
        output.sort(key=lambda row: (int(row["occurrences"]), int(row["last_tick"])), reverse=True)
        return output

    def structure_detail(self, structure_id: str) -> dict[str, Any]:
        for row in self.structure_catalog():
            if row["structure_id"] == structure_id:
                return row
        raise KeyError("repeatable structure not found")

    def temporal_catalog(self) -> list[dict[str, Any]]:
        output = [
            dict(event) for event in _rows(self.document.get("observations"))
            if str(event.get("kind") or "") == "temporal_convergence_readout"
        ]
        output.sort(key=lambda row: int(row.get("end_tick", row.get("tick", 0))), reverse=True)
        return output

    def temporal_summary(self) -> dict[str, Any]:
        rows = self.temporal_catalog()
        classes = Counter(str(row.get("classification") or "unknown") for row in rows)
        sources = Counter(source for row in rows for source in _source_values(row))
        return {
            "schema": "threemind-temporal-summary/1.0.0",
            "consciousness_id": self.consciousness_id,
            "total": len(rows),
            "classifications": dict(classes),
            "sources": dict(sources),
            "items": rows,
        }


class EvidenceExporter:
    """Write one self-describing, checksum-protected research dataset ZIP."""

    def __init__(self, analytics: AnalyticsService) -> None:
        self.analytics = analytics

    @staticmethod
    def _jsonl(rows: Iterable[dict[str, Any]]) -> bytes:
        return ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n").encode("utf-8")

    @staticmethod
    def _csv(rows: list[dict[str, Any]], fields: list[str]) -> bytes:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row[key], ensure_ascii=False, sort_keys=True) if isinstance(row.get(key), (dict, list)) else row.get(key) for key in fields})
        return stream.getvalue().encode("utf-8-sig")

    def write(self, path: Path) -> Path:
        document = self.analytics.document
        overview = self.analytics.overview()
        structures = self.analytics.structure_catalog()
        temporal = self.analytics.temporal_catalog()
        dynamics = self.analytics.dynamics(max_points=10_000)
        files: dict[str, bytes] = {}
        manifest = {
            "schema": DATASET_SCHEMA,
            "created_at": time.time(),
            "consciousness_id": self.analytics.consciousness_id,
            "history_origin": self.analytics.origin,
            "primary_formats": ["CSV", "JSON Lines", "JSON"],
            "notes": [
                "Anonymous node and edge identities are the primary evidence.",
                "Readable labels are external annotations and do not participate in Core dynamics.",
                "CSV files start with a UTF-8 BOM for spreadsheet interoperability; JSON files are UTF-8.",
            ],
        }
        files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        files["overview.json"] = json.dumps(overview, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        dictionary_rows = [
            {"table": "stimuli", "field": "envelope_id", "meaning": "Host audit identity for one ordered carrier; never used by graph dynamics."},
            {"table": "structures", "field": "structure_id", "meaning": "Exact node and directed-edge identity where available."},
            {"table": "structures", "field": "topology_class_id", "meaning": "Identity-free topology candidate class."},
            {"table": "structures", "field": "state_signatures", "meaning": "Quantized instantaneous state fingerprints observed for the structure."},
            {"table": "temporal_readouts", "field": "classification", "meaning": "Observed temporal response class: converged, oscillatory, decay, transient, unresolved, or interrupted."},
            {"table": "dynamics", "field": "total_activation", "meaning": "Sum of reconstructed node activations for a recorded trace tick."},
        ]
        files["data_dictionary.csv"] = self._csv(dictionary_rows, ["table", "field", "meaning"])
        for name, key in (("stimuli", "stimuli"), ("events", "events"), ("observations", "observations"), ("interpretations", "interpretations"), ("trace", "trace_entries")):
            files[f"records/{name}.jsonl"] = self._jsonl(_rows(document.get(key)))
        structure_fields = ["structure_id", "identity_quality", "topology_class_id", "first_tick", "last_tick", "occurrences", "repeatable_alerts", "node_count", "internal_edges", "mean_activation", "source_counts", "source_proportions", "labels", "state_signatures"]
        files["tables/repeatable_structures.csv"] = self._csv(structures, structure_fields)
        temporal_fields = ["id", "start_tick", "delivery_end_tick", "end_tick", "classification", "signature", "envelope_id", "adapter_id", "source_provenance", "node_ids", "mean_activation", "window", "convergence"]
        files["tables/temporal_readouts.csv"] = self._csv(temporal, temporal_fields)
        files["tables/dynamics.csv"] = self._csv(dynamics["series"], list(dynamics["series"][0]) if dynamics["series"] else ["tick"])
        for row in structures:
            files[f"subgraphs/{row['structure_id']}.json"] = json.dumps({
                "schema": "threemind-frozen-subgraph/1.0.0",
                "structure_id": row["structure_id"],
                "identity_quality": row["identity_quality"],
                "topology_class_id": row["topology_class_id"],
                "subgraph": row["latest_subgraph"],
                "labels": row["labels"],
            }, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        checksums = "".join(f"{hashlib.sha256(content).hexdigest()}  {name}\n" for name, content in sorted(files.items()))
        files["checksums.sha256"] = checksums.encode("ascii")
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, content in sorted(files.items()):
                archive.writestr(name, content)
        return path
