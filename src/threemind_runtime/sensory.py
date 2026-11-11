"""Versioned carrier transduction. Labels and carriers never enter Core."""

from __future__ import annotations

import hashlib
import math
import unicodedata
from dataclasses import asdict, dataclass
from typing import Literal

from threemind_core import Stimulus

from .receptors import ReceptorWiring

TEXT_VERSION = "text-sensor/2"
TEXT_LIMITS = {
    "channel_count": (32, 4096),
    "frame_characters": (1, 1024),
    "frame_interval_us": (1, 10_000_000),
    "max_carrier_characters": (1, 1_000_000),
}
INPUT_BUS_LIMITS = {"max_pending_frames": (1, 100000), "max_pending_channels": (1, 10_000_000)}


@dataclass(frozen=True)
class TextSensorConfig:
    enabled: bool = True
    encoding: Literal["anonymous-distributed", "labeled-observation", "literal-character"] = "anonymous-distributed"
    normalization: Literal["NFKC", "none"] = "NFKC"
    channel_count: int = 192
    frame_characters: int = 24
    frame_interval_us: int = 20_000
    gain: float = 1.0
    max_carrier_characters: int = 100_000

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError("text_sensor.enabled must be boolean")
        if self.encoding not in ("anonymous-distributed", "labeled-observation", "literal-character"):
            raise ValueError("unsupported text encoding")
        if self.normalization not in ("NFKC", "none"):
            raise ValueError("unsupported text normalization")
        for name, (lower, upper) in TEXT_LIMITS.items():
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"text_sensor.{name} must be an integer in [{lower}, {upper}]")
        if (
            isinstance(self.gain, bool)
            or not isinstance(self.gain, (int, float))
            or not math.isfinite(self.gain)
            or not 0 <= self.gain <= 100
        ):
            raise ValueError("text_sensor.gain must lie in [0, 100]")


@dataclass(frozen=True)
class InputBusConfig:
    max_pending_frames: int = 8192
    max_pending_channels: int = 524288

    def __post_init__(self):
        for name, (_, upper) in INPUT_BUS_LIMITS.items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError(f"input_bus.{name} must be an integer in [1, {upper}]")


class TextSensor(ReceptorWiring):
    """Port of the legacy nonsemantic byte/byte-pair/position transducer.

    A seeded bijection gives each receptor a stable u32 identity. The new
    receptor domain avoids the already released planar/host physical wiring.
    This is instrument wiring, not a choice of graph edges or meanings.
    """

    def __init__(self, seed: int, config: TextSensorConfig | None = None):
        super().__init__(seed)
        self.seed, self.config = seed, config or TextSensorConfig()
        self.key = seed.to_bytes(16, "big", signed=False)

    def bank(self, value: bytes) -> int:
        index = (
            int.from_bytes(hashlib.blake2b(value, key=self.key, digest_size=8).digest(), "big")
            % self.config.channel_count
        )
        return self.identity(0x100000 + index)

    def normalize(self, text: str) -> str:
        if not isinstance(text, str) or not text or len(text) > self.config.max_carrier_characters:
            raise ValueError(
                f"文本须为非空字符串，且不超过 {self.config.max_carrier_characters} 个字符；不会截断载体。"
            )
        text.encode("utf-8")  # Reject unpaired surrogates instead of silently replacing the carrier.
        return unicodedata.normalize("NFKC", text) if self.config.normalization == "NFKC" else text

    def frames(self, text: str, intensity: float = 1.0):
        carrier = self.normalize(text)
        if (
            isinstance(intensity, bool)
            or not isinstance(intensity, (int, float))
            or not math.isfinite(intensity)
            or not 0 <= intensity <= 100
        ):
            raise ValueError("刺激强度必须为 0 至 100 的有限数值。")
        width, previous, byte_offset = self.config.frame_characters, None, 0
        total_bytes = len(carrier.encode("utf-8"))
        for frame_index, offset in enumerate(range(0, len(carrier), width)):
            fragment = carrier[offset : offset + width]
            payload = fragment.encode("utf-8")
            pulses, labels = {}, {}

            def add(channel, amplitude, pulses=pulses):
                pulses[channel] = pulses.get(channel, 0) + amplitude

            def label(channel, value, labels=labels):
                labels.setdefault(channel, set()).add(value)

            if self.config.encoding == "literal-character":
                for character in fragment:
                    channel = self.identity(0x400000 + ord(character))
                    add(channel, 0.72)
                    label(channel, character)
                scale = max(1, math.sqrt(len(fragment)))
            else:
                for index, value in enumerate(payload):
                    add(self.bank(b"b" + bytes([value])), 0.42)
                    prior = payload[index - 1] if index else previous
                    if prior is not None:
                        add(self.bank(b"p" + bytes([prior, value])), 0.32)
                    add(self.bank(b"t" + bytes([(byte_offset + index) % 11, value])), 0.18)
                if offset + width >= len(carrier):
                    add(self.bank(b"l" + bytes([min(total_bytes // 4, 31)])), 0.20)
                if self.config.encoding == "labeled-observation":
                    for character in fragment:
                        label(self.bank(b"b" + character.encode("utf-8")[:1]), character)
                scale = max(1, math.sqrt(len(payload)))
            previous, byte_offset = payload[-1], byte_offset + len(payload)
            yield {
                "stimulus": Stimulus(
                    frame_index * self.config.frame_interval_us,
                    tuple(sorted((c, min(1, v / scale * self.config.gain)) for c, v in pulses.items())),
                    intensity,
                ),
                "labels": {str(c): sorted(values) for c, values in labels.items()},
            }

    def describe(self, text: str) -> dict:
        normalized = self.normalize(text)
        return {
            "version": TEXT_VERSION,
            "seed": self.seed,
            "config": asdict(self.config),
            "normalization": self.config.normalization,
            "normalized_characters": len(normalized),
            "normalized_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        }


def carrier_frames(adapter_id, payload, seed, config):
    if adapter_id == "stimulus-units":
        from .stimulus_units import unit_frames

        yield from unit_frames(payload)
    elif adapter_id == "transformer-probability":
        from threemind_transformer.adapter import probability_frame

        if set(payload) != {"response", "channel_ids", "intensity", "prediction_job_id"}:
            raise ValueError("invalid external probability carrier")
        frame = probability_frame(
            payload["response"], payload["channel_ids"], time_us=0, intensity=payload["intensity"]
        )
        yield {"stimulus": frame["stimulus"], "labels": {}}
    elif adapter_id == "text-sensor":
        if set(payload) - {"text", "intensity", "preset"}:
            raise ValueError("unknown text carrier fields")
        from .stimulus_presets import resolve_intensity

        yield from TextSensor(seed, TextSensorConfig(**config)).frames(
            payload.get("text"), resolve_intensity(payload.get("intensity"), payload.get("preset"))
        )
    elif adapter_id == "remote-anonymous":
        if set(payload) != {"frames", "remote", "device_session_id", "capture_us"}:
            raise ValueError("invalid remote carrier envelope")
        yield from carrier_frames("anonymous-frames", {"frames": payload["frames"]}, seed, config)
    elif adapter_id == "anonymous-frames":
        if set(payload) != {"frames"} or not isinstance(payload["frames"], list) or not payload["frames"]:
            raise ValueError("匿名载体必须提供非空 frames 数组。")
        prior = -1
        for frame in payload["frames"]:
            try:
                if not isinstance(frame, dict) or set(frame) - {"time_us", "channels", "intensity"}:
                    raise ValueError("帧只能包含 time_us、channels、intensity。")
                if type(frame.get("intensity", 1)) not in (int, float) or any(
                    type(value) not in (int, float) for _, value in frame["channels"]
                ):
                    raise ValueError("幅值与强度必须为数值，不能用布尔值或字符串代替。")
                if not isinstance(frame, dict) or set(frame) - {"time_us", "channels", "intensity"}:
                    raise ValueError("匿名载体只包含时间、通道和强度；竞争绕过请在来源策略中设置。")
                stimulus = Stimulus.from_dict(frame)
            except (KeyError, TypeError, OverflowError) as error:
                raise ValueError("匿名帧必须提供合法的 time_us 和 channels。") from error
            if stimulus.time_us < prior:
                raise ValueError("载体帧时间须单调不减，不能重排原始序列。")
            prior = stimulus.time_us
            yield {"stimulus": stimulus, "labels": {}}
    else:
        raise ValueError("unsupported carrier adapter")
