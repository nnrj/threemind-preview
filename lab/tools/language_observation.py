"""Reusable, read-only language observation diagnostics. No Core writes or answers."""

import hashlib

import numpy as np

from threemind_transformer.language_senses import ProcessFeatures


def project(process, protocol):
    observer = ProcessFeatures(protocol, int(process["start_us"]), int(process["planned_end_us"]))
    for frame in process["trajectory"]:
        observer.observe_frame(frame)
    return observer.result()["features"]


def channel_peaks(process, protocol):
    """Collision-free diagnostic for the declared +/- embedding channels only."""
    mask = int.from_bytes(hashlib.blake2s(f"language-input/1:{protocol.seed}".encode(), digest_size=4).digest(), "big")
    values = np.zeros((protocol.feature_bins, 2 * protocol.embedding_dimensions), dtype=float)
    start, end = int(process["start_us"]), int(process["planned_end_us"])
    for frame in process["trajectory"]:
        index = min(
            protocol.feature_bins - 1, (int(frame["time_us"]) - start) * protocol.feature_bins // max(1, end - start)
        )
        for node in frame["nodes"]:
            channel = int(node["channel"]) ^ mask
            if not 0 <= channel < values.shape[1]:
                raise ValueError("diagnostic encountered a channel outside the declared embedding basis")
            values[index, channel] = max(values[index, channel], float(node["activation"]))
    return values.ravel().tolist()


def nearest_word(vector, exemplars):
    """Diagnostic nearest calibration state; never used as an input or action."""
    x = np.asarray(vector, dtype=float)
    x = x / max(1e-12, np.linalg.norm(x))
    scores = {}
    for label, sample in exemplars:
        y = np.asarray(sample, dtype=float)
        similarity = float(x @ y / max(1e-12, np.linalg.norm(y)))
        scores[label] = max(scores.get(label, -2.0), similarity)
    return sorted(scores.items(), key=lambda row: (-row[1], row[0]))


def embedding_basis_peaks(process, protocol):
    """Secondary sensor-basis diagnostic, explicitly accounting for other inputs.

    The unfiltered trajectory and the main ProcessFeatures projection remain
    untouched. This probe must not be substituted for the passive output.
    """
    mask = int.from_bytes(hashlib.blake2s(f"language-input/1:{protocol.seed}".encode(), digest_size=4).digest(), "big")
    selected = []
    outside_samples, outside_peak = 0, 0.0
    for frame in process["trajectory"]:
        inside, outside = [], []
        for node in frame["nodes"]:
            if 0 <= (int(node["channel"]) ^ mask) < 2 * protocol.embedding_dimensions:
                inside.append(node)
            else:
                outside.append(node)
        outside_samples += len(outside)
        outside_peak = max(outside_peak, sum(float(n["activation"]) for n in outside))
        selected.append(frame | {"nodes": inside})
    return {
        "values": channel_peaks(process | {"trajectory": selected}, protocol),
        "outside_basis_node_samples": outside_samples,
        "outside_basis_peak_total": outside_peak,
        "scope": "secondary embedding-channel probe; main output remains unfiltered",
    }


def trace_summary(process):
    rows = process["trajectory"]
    totals = [sum(float(n["activation"]) for n in r["nodes"]) for r in rows]
    return {
        "start_us": process["start_us"],
        "end_us": process["end_us"],
        "has_activity": process["has_activity"],
        "peak_total_activation": max(totals, default=0),
        "last_total_activation": totals[-1] if totals else 0,
        "active_samples": sum(v > 0 for v in totals),
        "samples": len(totals),
        "last_active_us": next((r["time_us"] for r, total in reversed(list(zip(rows, totals))) if total > 0), None),
        "top_nodes_at_end": sorted(rows[-1]["nodes"], key=lambda n: -n["activation"])[:12] if rows else [],
    }
