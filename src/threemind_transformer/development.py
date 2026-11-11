"""Versioned language-development instruments. No Core state writes or semantic routing.

The optional stream transducer is a NEW sensory protocol, not a modification of
language-adapter/1. Trajectory projection can also inspect archived experiments.
"""

from __future__ import annotations

import hashlib
import math
import unicodedata
from dataclasses import asdict, dataclass

import numpy as np

from threemind_core import Stimulus
from threemind_runtime.receptors import ReceptorWiring


@dataclass(frozen=True)
class StreamInput:
    schema: str = "threemind.language-character-stream/1"
    seed: int = 17
    dimensions: int = 64
    top_k: int = 4
    frame_us: int = 20000
    frame_amount: float = 1.0
    normalization: str = "NFKC"

    def __post_init__(self):
        if self.schema != "threemind.language-character-stream/1" or self.normalization != "NFKC":
            raise ValueError("unsupported stream identity or normalization")
        if not 1 <= self.dimensions <= 256 or not 0 <= self.top_k <= self.dimensions:
            raise ValueError("invalid dimensions/top_k (zero means dense)")
        if not 1 <= self.frame_us <= 1000000 or not math.isfinite(self.frame_amount) or self.frame_amount <= 0:
            raise ValueError("invalid stream cadence/amount")

    def frame(self, vector, index, intensity=1.0):
        values = np.asarray(vector, dtype=float)
        if values.shape != (self.dimensions,) or not np.isfinite(values).all():
            raise ValueError("invalid character vector")
        selected = np.arange(self.dimensions)
        if self.top_k:
            selected = np.argsort(-np.abs(values), kind="stable")[: self.top_k]
        total = float(np.abs(values[selected]).sum())
        if total <= 0:
            raise ValueError("zero feature vector cannot be normalized")
        wiring = ReceptorWiring(self.seed)
        channels = tuple(sorted(
            (wiring.identity(0xC00000 + 2 * int(i) + int(values[i] < 0)),
             float(abs(values[i]) / total * self.frame_amount))
            for i in selected if values[i] != 0
        ))
        return {"stimulus": Stimulus(index * self.frame_us, channels, intensity), "labels": {}}


def character_vectors(text, model, dimensions=64):
    """Causal hidden state at the last UTF-8 byte of each complete character."""
    import torch

    from .scratch_language import BOS

    if not isinstance(text, str) or not text or len(text) > 2048:
        raise ValueError("nonempty bounded text required")
    normalized = unicodedata.normalize("NFKC", text)
    ids, ends = [BOS], []
    for character in normalized:
        ids.extend(character.encode("utf-8"))
        ends.append(len(ids) - 1)
    if len(ids) > model.context or dimensions > model.config.hidden_size:
        raise ValueError("stream exceeds declared model context/width")
    with torch.no_grad():
        hidden = model(input_ids=torch.tensor([ids], device=model.device)).last_hidden_state
    return hidden[0, ends, :dimensions].float().cpu().numpy()


def compile_stream(text, model, spec: StreamInput, intensity=1.0):
    return [spec.frame(vector, i, intensity) for i, vector in enumerate(character_vectors(text, model, spec.dimensions))]


def input_summary(frames):
    return {
        "frames": len(frames),
        "span_us": max((int(r["stimulus"].time_us) for r in frames), default=0),
        "channels": len({int(c) for r in frames for c, _ in r["stimulus"].channels}),
        "mapped_amount": sum(float(v) * r["stimulus"].intensity for r in frames for _, v in r["stimulus"].channels),
        "peak_channel_amount": max(
            (float(v) * r["stimulus"].intensity for r in frames for _, v in r["stimulus"].channels), default=0
        ),
    }


@dataclass(frozen=True)
class TrajectoryBasis:
    channels: tuple[int, ...]
    bins: int = 16
    residual_buckets: int = 16
    schema: str = "threemind.language-trajectory-basis/1"

    def __post_init__(self):
        object.__setattr__(self, "channels", tuple(self.channels))
        if self.schema != "threemind.language-trajectory-basis/1":
            raise ValueError("unsupported trajectory basis")
        if len(set(self.channels)) != len(self.channels) or len(self.channels) > 4096:
            raise ValueError("basis channels must be unique and bounded")
        if not 1 <= self.bins <= 128 or not 1 <= self.residual_buckets <= 256:
            raise ValueError("invalid time/residual dimensions")

    @property
    def width(self):
        return len(self.channels) + self.residual_buckets

    def project(self, process):
        """Known channels never collide. Unknown channels remain explicitly counted."""
        start, end = int(process["start_us"]), int(process["planned_end_us"])
        if end <= start:
            raise ValueError("positive observation window required")
        index = {int(c): i for i, c in enumerate(self.channels)}
        values = np.zeros((self.bins, self.width), dtype=np.float32)
        unknown = set()
        samples, unknown_samples, previous_time = 0, 0, start
        for frame in process["trajectory"]:
            when = int(frame["time_us"])
            if when < previous_time or not start <= when <= end:
                raise ValueError("trajectory times must be ordered within the window")
            previous_time = when
            slot = min(self.bins - 1, (when - start) * self.bins // (end - start))
            current = np.zeros(self.width, dtype=np.float32)
            for node in frame["nodes"]:
                channel, amount = int(node["channel"]), float(node["activation"])
                if not math.isfinite(amount) or amount < 0:
                    raise ValueError("invalid activity")
                if channel in index:
                    offset = index[channel]
                else:
                    key = hashlib.blake2s(str(channel).encode(), digest_size=4).digest()
                    offset = len(index) + int.from_bytes(key, "big") % self.residual_buckets
                    unknown.add(channel)
                    unknown_samples += 1
                current[offset] += amount
                samples += 1
            values[slot] = np.maximum(values[slot], current)
        return {
            "schema": self.schema,
            "values": values.tolist(),
            "node_samples": samples,
            "unknown_node_samples": unknown_samples,
            "unknown_channels": sorted(unknown),
            "all_nodes_accounted_for": True,
        }

    def to_dict(self):
        return asdict(self)


def activity_changes(process):
    """Describe rises/re-entry, without labelling them autonomous causes."""
    previous, seen = {}, set()
    rises, reentries, increase, peak = 0, 0, 0.0, 0.0
    for frame_index, frame in enumerate(process["trajectory"]):
        now = {str(n["id"]): float(n["activation"]) for n in frame["nodes"]}
        if frame_index:
            for identity, amount in now.items():
                delta = amount - previous.get(identity, 0.0)
                if delta > 1e-10:
                    rises += 1
                    increase += delta
                    reentries += int(identity in seen and previous.get(identity, 0.0) == 0)
        seen.update(now)
        peak = max(peak, sum(now.values()))
        previous = now
    return {"rises": rises, "reentries": reentries, "positive_change": increase, "peak_total": peak,
            "interpretation": "description_only; arrivals_and_internal_transmission_require_controls"}
