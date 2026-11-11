"""Versioned external activity readout; no imports or writes to Core dynamics.

The prototype reader is deliberately a finite phrase library. Its probabilities
are similarity scores, not calibrated probabilities of semantic truth.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np

from .development import TrajectoryBasis


@dataclass(frozen=True)
class NativeProjection:
    channels: tuple[int, ...]
    excluded_channels: tuple[int, ...] = ()
    bins: int = 16
    residual_buckets: int = 16
    minimum_magnitude: float = 1e-8
    schema: str = "threemind.native-expression-features/1"

    def __post_init__(self):
        object.__setattr__(self, "channels", tuple(self.channels))
        object.__setattr__(self, "excluded_channels", tuple(self.excluded_channels))
        if self.schema != "threemind.native-expression-features/1":
            raise ValueError("unknown native feature protocol")
        if not np.isfinite(self.minimum_magnitude) or self.minimum_magnitude <= 0:
            raise ValueError("a positive finite observation floor is required")
        if set(self.channels) & set(self.excluded_channels):
            raise ValueError("excluded inputs cannot also be feature columns")
        self.basis  # Validate the frozen observation basis.

    @property
    def basis(self):
        return TrajectoryBasis(self.channels, self.bins, self.residual_buckets)

    def project(self, process):
        excluded = set(self.excluded_channels)
        scoped = {k: process[k] for k in ("start_us", "end_us", "planned_end_us")}
        scoped["trajectory"] = [
            {"time_us": frame["time_us"], "nodes": [node for node in frame["nodes"]
                if int(node["channel"]) not in excluded]}
            for frame in process["trajectory"]
        ]
        projected = self.basis.project(scoped)
        values = np.asarray(projected["values"], dtype=np.float32)
        total = float(values.sum())
        resolvable = total >= self.minimum_magnitude
        values = values / total if resolvable else np.zeros_like(values)
        return projected | {"schema": self.schema, "values": values.tolist(),
            "raw_sum": total, "resolvable": resolvable,
            "scope": "all_activity_except_declared_input_channels",
            "all_nodes_accounted_for": not bool(excluded),
            "excluded_channels": list(self.excluded_channels)}

    def to_dict(self):
        return asdict(self)


class PrototypeLanguage:
    """Mean cosine attention per phrase, so class frequency gives no bonus."""
    schema = "threemind.prototype-language/1"

    def __init__(self, references, *, temperature=0.1, minimum_margin=1e-6):
        if not references or any(row.get("split") != "train" for row in references):
            raise ValueError("only explicitly labelled training references may be fitted")
        if not np.isfinite(temperature) or temperature <= 0 or minimum_margin < 0:
            raise ValueError("invalid similarity readout parameters")
        self.references = references
        self.temperature, self.minimum_margin = float(temperature), float(minimum_margin)
        self.labels = sorted({row["text"] for row in references})
        if len(self.labels) < 2:
            raise ValueError("at least two output classes are required")
        self.shape = np.asarray(references[0]["values"]).shape
        if any(np.asarray(row["values"]).shape != self.shape for row in references):
            raise ValueError("all references must use the same observation basis")
        values = np.asarray([row["values"] for row in references], dtype=float).reshape(len(references), -1)
        if not np.isfinite(values).all():
            raise ValueError("nonfinite activity features")
        norm = np.linalg.norm(values, axis=1)
        self.unit = values / np.maximum(norm[:, None], 1e-30)
        self.norm = norm

    def decode(self, values):
        query = np.asarray(values, dtype=float)
        if query.shape[1:] != self.shape or not np.isfinite(query).all():
            raise ValueError("query shape or values do not match calibration")
        query = query.reshape(len(query), -1)
        norm = np.linalg.norm(query, axis=1)
        cosine = (query / np.maximum(norm[:, None], 1e-30)) @ self.unit.T
        scores = np.stack([cosine[:, [r["text"] == label for r in self.references]].mean(axis=1)
                           for label in self.labels], axis=1)
        result = []
        for i, row in enumerate(scores):
            order = np.argsort(-row, kind="stable")
            margin = float(row[order[0]] - row[order[1]])
            resolved = norm[i] >= 1e-8 and row[order[0]] > 0 and margin > self.minimum_margin
            weights = np.exp((row - row.max()) / self.temperature)
            weights /= weights.sum()
            result.append({"text": self.labels[order[0]] if resolved else "", "resolved": bool(resolved),
                "margin": margin, "probabilities": dict(zip(self.labels, weights.tolist(), strict=True)),
                "scores": row.tolist(), "exposure": ["anonymous_activity_trajectory"],
                "free_generation": False, "probability_meaning": "uncalibrated_similarity_attention"})
        return result

    def to_dict(self):
        return {"schema": self.schema, "references": self.references,
                "temperature": self.temperature, "minimum_margin": self.minimum_margin}

    @classmethod
    def from_dict(cls, value):
        if value.get("schema") != cls.schema:
            raise ValueError("unknown prototype language protocol")
        return cls(value["references"], temperature=value["temperature"], minimum_margin=value["minimum_margin"])


def main():
    parser = argparse.ArgumentParser(description="External native-pattern projection and finite-vocabulary readout")
    parser.add_argument("operation", choices=("project", "fit", "decode"))
    parser.add_argument("--input", required=True, type=Path, help="JSONL processes or training/features")
    parser.add_argument("--output", required=True, type=Path, help="new file, never overwritten")
    parser.add_argument("--config", required=True, type=Path, help="projection config or prototype model")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.input.stat().st_size > 256 * 2**20:
        raise ValueError("split the input into bounded files of at most256MiB")
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not 1 <= len(rows) <= 16384:
        raise ValueError("bounded nonempty input required")
    if args.operation == "project":
        projection = NativeProjection(**config)
        output = [projection.project(row.get("process", row)) for row in rows]
    elif args.operation == "fit":
        output = [PrototypeLanguage(rows, **config).to_dict()]
    else:
        output = PrototypeLanguage.from_dict(config).decode([row["values"] for row in rows])
    with args.output.open("x", encoding="utf-8") as stream:
        for row in output:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
