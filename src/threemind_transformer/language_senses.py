"""Explicit sentence embedding input and passive time-binned Core observation."""

import hashlib
import math

from threemind_core import Stimulus
from threemind_runtime.bus import OutputBus

from .language_protocol import LanguageProtocol
from .protocol import digest


def embedding_frame(vector, protocol: LanguageProtocol, intensity=1.0):
    if len(vector) != protocol.embedding_dimensions or any(not math.isfinite(v) for v in vector):
        raise ValueError("embedding differs from configured sensory dimension")
    if type(intensity) not in (int, float) or not math.isfinite(intensity) or not 0 <= intensity <= 100:
        raise ValueError("intensity must be finite and within 0..100")
    mask = int.from_bytes(hashlib.blake2s(f"language-input/1:{protocol.seed}".encode(), digest_size=4).digest(), "big")
    # Uniform signed sensor wiring. No token names, graph lookup or answer selection.
    channels = tuple(sorted(((2 * i + int(value < 0)) ^ mask, abs(value)) for i, value in enumerate(vector) if value))
    return Stimulus(0, channels, intensity=intensity)


class ProcessFeatures:
    def __init__(self, protocol, start_us, end_us):
        self.protocol, self.start, self.end = protocol, start_us, end_us
        self.sums = [[0.0] * protocol.feature_buckets for _ in range(protocol.feature_bins)]
        self.counts = [0] * protocol.feature_bins
        self.trajectory = []
        self.node_samples = 0
        self.bus = OutputBus()
        self.bus.subscribe("language-process", self.observe_frame)

    def sample(self, engine):
        self.bus.publish({"time_us": engine.time_us, "nodes": engine.observation_nodes()}, owned=True)

    def observe_frame(self, frame):
        index = min(
            self.protocol.feature_bins - 1,
            (int(frame["time_us"]) - self.start) * self.protocol.feature_bins // max(1, self.end - self.start),
        )
        values, raw = [0.0] * self.protocol.feature_buckets, []
        for node in frame["nodes"]:
            activation = float(node["activation"])
            if activation <= 0:
                continue
            raw.append({"id": str(node["id"]), "channel": node["channel"], "activation": activation})
            h = int.from_bytes(
                hashlib.blake2s(
                    f"language-readout/1:{self.protocol.seed}:{node['channel']}".encode(), digest_size=4
                ).digest(),
                "big",
            )
            bucket = h % self.protocol.feature_buckets
            if self.protocol.feature_layout == "unsigned-peak":
                values[bucket] = max(values[bucket], activation)
            else:
                values[bucket] += activation * (1 if h & 0x80000000 else -1)
        for i, value in enumerate(values):
            if self.protocol.feature_layout == "unsigned-peak":
                self.sums[index][i] = max(self.sums[index][i], value)
            else:
                self.sums[index][i] += value
        self.counts[index] += 1
        self.trajectory.append({"time_us": str(frame["time_us"]), "nodes": raw})
        self.node_samples += len(raw)

    def result(self):
        features = [
            v if self.protocol.feature_layout == "unsigned-peak" else v / max(1, self.counts[i])
            for i, row in enumerate(self.sums)
            for v in row
        ]
        return {
            "schema": "threemind.language-process/2"
            if self.protocol.schema_id.endswith("/2")
            else "threemind.language-process/1",
            "mapping_hash": self.protocol.mapping_hash,
            "start_us": str(self.start),
            "planned_end_us": str(self.end),
            "end_us": self.trajectory[-1]["time_us"],
            "censored": int(self.trajectory[-1]["time_us"]) < self.end,
            "features": features,
            "samples_per_bin": self.counts,
            "trajectory": self.trajectory,
            "features_hash": digest(features),
            "has_activity": self.node_samples > 0,
        }


def advance_language(engine, frames, protocol, session=None, guard=None):
    from threemind_runtime.readout_session import ReadoutSession

    if engine.life == "dead":
        raise ValueError("consciousness is dead; no automatic revival")
    start = engine.time_us
    frames = [frame if isinstance(frame, dict) else {"stimulus": frame, "labels": {}} for frame in frames]
    final_input = start + max((frame["stimulus"].time_us for frame in frames), default=0)
    session = session or ReadoutSession(engine, record=lambda _: None)
    if frames:
        session.schedule(
            frames,
            source="manual-language-adapter",
            adapter_id="text-sensor" if protocol.input_model == "text" else "language-transformer",
        )
    end = final_input + protocol.response_us
    features = ProcessFeatures(protocol, start, end)
    features.sample(engine)
    while engine.time_us < end and engine.life != "dead":
        session.advance_to(min(end, engine.time_us + protocol.sample_us), guard=guard)
        features.sample(engine)
        if features.node_samples > 250000:
            raise ValueError("language observation exceeds 250000 active-node samples")
    return features.result()
