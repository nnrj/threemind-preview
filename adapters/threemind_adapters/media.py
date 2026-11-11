"""Non-semantic audio/visual sensory and output adapters.

These adapters operate on decoded physical samples only.  Codec access,
microphone/camera permission and durable media storage belong to the host
application.  No ASR, OCR, image classifier, pretrained embedding or other
semantic model is used here.

The visual adapter deliberately emits small retinal patches rather than one
huge co-activation frame.  ThreeMind creates edges from local co-activation;
therefore sending a whole image as one frame would accidentally turn the
carrier into a dense, quadratic graph-building instruction.
"""
from __future__ import annotations

import hashlib
import math
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any, Iterable, Sequence

from threemind.frames import OutputFrame, SensoryFrame


def _bounded(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    value = float(value)
    if not math.isfinite(value):
        return lower
    return max(lower, min(upper, value))


def _seed_key(seed: int) -> bytes:
    return (int(seed) & ((1 << 128) - 1)).to_bytes(16, "big", signed=False)


class _AnonymousChannels:
    def __init__(self, seed: int, namespace: str) -> None:
        self._key = _seed_key(seed)
        self._namespace = namespace.encode("utf-8") + b"\0"

    def channel(self, name: str) -> int:
        return int.from_bytes(
            hashlib.blake2b(
                self._namespace + name.encode("utf-8"),
                key=self._key,
                digest_size=8,
            ).digest(),
            "big",
        )


DEFAULT_AUDITORY_CONFIG: dict[str, Any] = {
    "target_sample_rate": 16000,
    "sensory_frame_rate": 20.0,
    "encoding": "band-energy",
    "band_count": 12,
    "minimum_frequency": 80.0,
    "maximum_frequency": 7600.0,
    "waveform_bins": 24,
    "level_enabled": True,
    "change_enabled": True,
    "gain": 1.0,
    "inter_frame_epochs": 1,
    "upload_limit_mb": 32,
    "live_enabled": False,
}


class AuditorySensorAdapter:
    """Encode PCM into anonymous, temporally ordered auditory frames.

    ``band-energy`` is the mainline mode.  The fallback Goertzel bank is
    intentionally small and deterministic, so arbitrary audio codecs can be
    decoded outside this adapter without importing intelligence.  A
    ``waveform`` baseline is retained for experiments that need the least
    transformed carrier possible.
    """

    def __init__(self, seed: int, config: dict[str, Any] | None = None) -> None:
        self.seed = int(seed)
        self._channels = _AnonymousChannels(seed, "auditory-sensor")
        self.config = dict(DEFAULT_AUDITORY_CONFIG)
        self._previous: list[float] | None = None
        self._live_tail: list[float] = []
        self.configure(config or {})

    def configure(self, values: dict[str, Any]) -> None:
        merged = {**self.config, **dict(values)}
        encoding = str(merged.get("encoding", "band-energy"))
        if encoding not in {"band-energy", "waveform"}:
            raise ValueError("auditory encoding must be band-energy or waveform")
        merged["encoding"] = encoding
        merged["target_sample_rate"] = max(4000, min(192000, int(merged["target_sample_rate"])))
        merged["sensory_frame_rate"] = max(1.0, min(200.0, float(merged["sensory_frame_rate"])))
        merged["band_count"] = max(3, min(64, int(merged["band_count"])))
        merged["waveform_bins"] = max(4, min(256, int(merged["waveform_bins"])))
        merged["minimum_frequency"] = max(1.0, float(merged["minimum_frequency"]))
        merged["maximum_frequency"] = max(merged["minimum_frequency"], float(merged["maximum_frequency"]))
        merged["gain"] = max(0.0, min(100.0, float(merged["gain"])))
        merged["inter_frame_epochs"] = max(1, min(10000, int(merged["inter_frame_epochs"])))
        merged["upload_limit_mb"] = max(1, min(4096, int(merged["upload_limit_mb"])))
        merged["level_enabled"] = bool(merged["level_enabled"])
        merged["change_enabled"] = bool(merged["change_enabled"])
        merged["live_enabled"] = bool(merged["live_enabled"])
        self.config = merged

    @property
    def inter_frame_epochs(self) -> int:
        return int(self.config["inter_frame_epochs"])

    def reset_baseline(self) -> None:
        self._previous = None
        self._live_tail = []

    @staticmethod
    def _resample(samples: Sequence[float], source_rate: int, target_rate: int) -> list[float]:
        if not samples:
            return []
        source_rate = max(1, int(source_rate)); target_rate = max(1, int(target_rate))
        if source_rate == target_rate:
            return [_bounded(value, -1.0, 1.0) for value in samples]
        length = max(1, round(len(samples) * target_rate / source_rate))
        if length == 1:
            return [_bounded(samples[0], -1.0, 1.0)]
        scale = (len(samples) - 1) / (length - 1)
        result: list[float] = []
        for index in range(length):
            position = index * scale
            left = int(position); right = min(len(samples) - 1, left + 1)
            fraction = position - left
            result.append(_bounded(float(samples[left]) * (1.0 - fraction) + float(samples[right]) * fraction, -1.0, 1.0))
        return result

    @staticmethod
    def _goertzel_amplitude(samples: Sequence[float], frequency: float, sample_rate: int) -> float:
        if not samples:
            return 0.0
        omega = math.tau * max(0.0, min(sample_rate / 2.0, frequency)) / sample_rate
        coefficient = 2.0 * math.cos(omega)
        previous = previous2 = 0.0
        # A Hann window suppresses frame-boundary artefacts without adding a
        # semantic preference.
        denominator = max(1, len(samples) - 1)
        for index, raw in enumerate(samples):
            windowed = float(raw) * (0.5 - 0.5 * math.cos(math.tau * index / denominator))
            current = windowed + coefficient * previous - previous2
            previous2, previous = previous, current
        power = max(0.0, previous2 * previous2 + previous * previous - coefficient * previous * previous2)
        return min(1.0, 2.0 * math.sqrt(power) / max(1, len(samples)))

    def _features(self, samples: Sequence[float], sample_rate: int) -> list[float]:
        gain = float(self.config["gain"])
        if self.config["encoding"] == "waveform":
            bins = int(self.config["waveform_bins"])
            if not samples:
                return [0.0] * (bins * 2)
            values: list[float] = []
            for index in range(bins):
                start = index * len(samples) // bins
                end = max(start + 1, (index + 1) * len(samples) // bins)
                # The Core accepts non-negative drive.  Preserve waveform
                # polarity as two anonymous physical channels rather than
                # shifting the carrier into 0..1: shifting would turn true
                # silence into a permanent 0.5-strength stimulus.
                mean = sum(float(value) for value in samples[start:end]) / max(1, end - start)
                values.extend((_bounded(mean * gain), _bounded(-mean * gain)))
            return values
        count = int(self.config["band_count"])
        minimum = float(self.config["minimum_frequency"])
        maximum = min(float(self.config["maximum_frequency"]), sample_rate * 0.49)
        ratio = (maximum / minimum) ** (1.0 / max(1, count - 1)) if maximum > minimum else 1.0
        values = []
        for index in range(count):
            amplitude = self._goertzel_amplitude(samples, minimum * ratio ** index, sample_rate)
            values.append(_bounded(math.log1p(9.0 * amplitude * gain) / math.log(10.0)))
        return values

    def encode_samples(
        self,
        samples: Sequence[float],
        sample_rate: int,
        *,
        intensity: float = 1.0,
        source: str = "manual-audio",
        bypass_filter: bool = False,
    ) -> tuple[SensoryFrame, ...]:
        target_rate = int(self.config["target_sample_rate"])
        resampled = self._resample(samples, sample_rate, target_rate)
        frame_size = max(16, round(target_rate / float(self.config["sensory_frame_rate"])))
        if not resampled:
            return ()
        chunks = [resampled[offset:offset + frame_size] for offset in range(0, len(resampled), frame_size)]
        frames: list[SensoryFrame] = []
        for chunk in chunks:
            if len(chunk) < frame_size:
                chunk = [*chunk, *([0.0] * (frame_size - len(chunk)))]
            features = self._features(chunk, target_rate)
            channels: dict[int, float] = {}
            for index, value in enumerate(features):
                # Zero drive is absence of stimulation.  Omitting it avoids
                # recording or scheduling fictitious silent sensory features;
                # a transition *to* zero is still preserved by the fall
                # channel below.
                if self.config["level_enabled"] and value > 0.0:
                    channels[self._channels.channel(f"feature:{index}:level")] = value
                if self.config["change_enabled"] and self._previous is not None:
                    delta = value - self._previous[index]
                    if delta > 0.0:
                        channels[self._channels.channel(f"feature:{index}:rise")] = _bounded(delta)
                    elif delta < 0.0:
                        channels[self._channels.channel(f"feature:{index}:fall")] = _bounded(-delta)
            self._previous = features
            if channels:
                frames.append(SensoryFrame(
                    source=source,
                    channels=channels,
                    intensity=_bounded(intensity, 0.0, 2.0),
                    bypass_filter=bool(bypass_filter),
                ))
        return tuple(frames)

    def encode_live_samples(
        self,
        samples: Sequence[float],
        sample_rate: int,
        *,
        intensity: float = 1.0,
        source: str = "live-microphone",
        bypass_filter: bool = False,
    ) -> tuple[SensoryFrame, ...]:
        """Incrementally encode PCM without padding every browser packet.

        AudioWorklet blocks are typically much shorter than one configured
        sensory window.  Padding each block would invent silence and amplify
        the effective frame rate, so incomplete physical samples stay in this
        adapter until a complete window exists.
        """
        target_rate = int(self.config["target_sample_rate"])
        self._live_tail.extend(self._resample(samples, sample_rate, target_rate))
        frame_size = max(16, round(target_rate / float(self.config["sensory_frame_rate"])))
        complete = len(self._live_tail) // frame_size
        if complete < 1:
            return ()
        ready = self._live_tail[:complete * frame_size]
        self._live_tail = self._live_tail[complete * frame_size:]
        frames: list[SensoryFrame] = []
        for offset in range(0, len(ready), frame_size):
            features = self._features(ready[offset:offset + frame_size], target_rate)
            channels: dict[int, float] = {}
            for index, value in enumerate(features):
                if self.config["level_enabled"] and value > 0.0:
                    channels[self._channels.channel(f"feature:{index}:level")] = value
                if self.config["change_enabled"] and self._previous is not None:
                    delta = value - self._previous[index]
                    if delta > 0.0: channels[self._channels.channel(f"feature:{index}:rise")] = _bounded(delta)
                    elif delta < 0.0: channels[self._channels.channel(f"feature:{index}:fall")] = _bounded(-delta)
            self._previous = features
            if channels:
                frames.append(SensoryFrame(
                    source=source, channels=channels,
                    intensity=_bounded(intensity, 0.0, 2.0), bypass_filter=bool(bypass_filter),
                ))
        return tuple(frames)


DEFAULT_VISUAL_CONFIG: dict[str, Any] = {
    "target_width": 24,
    "target_height": 16,
    "sensory_frame_rate": 6.0,
    "patch_width": 4,
    "patch_height": 4,
    "filter_mode": "luminance",
    "threshold": 0.5,
    "level_enabled": True,
    "change_enabled": True,
    "gain": 1.0,
    "inter_patch_epochs": 1,
    "upload_limit_mb": 128,
    "live_enabled": False,
}


class VisualSensorAdapter:
    """Encode decoded pixels as a local retinal scan of anonymous frames."""

    def __init__(self, seed: int, config: dict[str, Any] | None = None) -> None:
        self.seed = int(seed)
        self._channels = _AnonymousChannels(seed, "visual-sensor")
        self.config = dict(DEFAULT_VISUAL_CONFIG)
        self._previous: list[float] | None = None
        self.configure(config or {})

    def configure(self, values: dict[str, Any]) -> None:
        merged = {**self.config, **dict(values)}
        mode = str(merged.get("filter_mode", "luminance"))
        if mode not in {"luminance", "edges", "threshold"}:
            raise ValueError("visual filter_mode must be luminance, edges or threshold")
        merged["filter_mode"] = mode
        merged["target_width"] = max(2, min(256, int(merged["target_width"])))
        merged["target_height"] = max(2, min(256, int(merged["target_height"])))
        merged["sensory_frame_rate"] = max(0.2, min(60.0, float(merged["sensory_frame_rate"])))
        merged["patch_width"] = max(1, min(32, int(merged["patch_width"])))
        merged["patch_height"] = max(1, min(32, int(merged["patch_height"])))
        merged["threshold"] = _bounded(merged["threshold"])
        merged["gain"] = max(0.0, min(100.0, float(merged["gain"])))
        merged["inter_patch_epochs"] = max(1, min(10000, int(merged["inter_patch_epochs"])))
        merged["upload_limit_mb"] = max(1, min(4096, int(merged["upload_limit_mb"])))
        merged["level_enabled"] = bool(merged["level_enabled"])
        merged["change_enabled"] = bool(merged["change_enabled"])
        merged["live_enabled"] = bool(merged["live_enabled"])
        self.config = merged

    @property
    def inter_patch_epochs(self) -> int:
        return int(self.config["inter_patch_epochs"])

    def reset_baseline(self) -> None:
        self._previous = None

    @staticmethod
    def _gray(raw: Sequence[int] | bytes, width: int, height: int, components: int) -> list[float]:
        expected = max(0, int(width) * int(height) * int(components))
        if len(raw) < expected or components not in {1, 2, 3, 4}:
            raise ValueError("pixel buffer does not match width, height and components")
        result: list[float] = []
        for index in range(width * height):
            offset = index * components
            if components <= 2:
                level = int(raw[offset])
            else:
                level = round(.2126 * int(raw[offset]) + .7152 * int(raw[offset + 1]) + .0722 * int(raw[offset + 2]))
            result.append(_bounded(level / 255.0))
        return result

    @staticmethod
    def _resize(values: Sequence[float], width: int, height: int, target_width: int, target_height: int) -> list[float]:
        result: list[float] = []
        for y in range(target_height):
            source_y = min(height - 1, int((y + .5) * height / target_height))
            for x in range(target_width):
                source_x = min(width - 1, int((x + .5) * width / target_width))
                result.append(float(values[source_y * width + source_x]))
        return result

    @staticmethod
    def _edges(values: Sequence[float], width: int, height: int) -> list[float]:
        result = [0.0] * (width * height)
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                def at(dx: int, dy: int) -> float: return float(values[(y + dy) * width + x + dx])
                gx = -at(-1, -1) + at(1, -1) - 2 * at(-1, 0) + 2 * at(1, 0) - at(-1, 1) + at(1, 1)
                gy = -at(-1, -1) - 2 * at(0, -1) - at(1, -1) + at(-1, 1) + 2 * at(0, 1) + at(1, 1)
                result[y * width + x] = _bounded(math.sqrt(gx * gx + gy * gy) / 4.0)
        return result

    def encode_pixels(
        self,
        pixels: Sequence[int] | bytes,
        width: int,
        height: int,
        *,
        components: int = 1,
        intensity: float = 1.0,
        source: str = "manual-visual",
        bypass_filter: bool = False,
    ) -> tuple[SensoryFrame, ...]:
        width = int(width); height = int(height); components = int(components)
        if width < 1 or height < 1:
            raise ValueError("visual frame dimensions must be positive")
        target_width = int(self.config["target_width"]); target_height = int(self.config["target_height"])
        values = self._resize(self._gray(pixels, width, height, components), width, height, target_width, target_height)
        mode = self.config["filter_mode"]
        if mode == "edges":
            values = self._edges(values, target_width, target_height)
        elif mode == "threshold":
            threshold = float(self.config["threshold"])
            values = [1.0 if value >= threshold else 0.0 for value in values]
        gain = float(self.config["gain"])
        values = [_bounded(value * gain) for value in values]
        patch_width = int(self.config["patch_width"]); patch_height = int(self.config["patch_height"])
        previous = self._previous
        frames: list[SensoryFrame] = []
        for top in range(0, target_height, patch_height):
            for left in range(0, target_width, patch_width):
                channels: dict[int, float] = {}
                for y in range(top, min(target_height, top + patch_height)):
                    for x in range(left, min(target_width, left + patch_width)):
                        index = y * target_width + x; value = values[index]
                        if self.config["level_enabled"] and value > 0.0:
                            channels[self._channels.channel(f"pixel:{x}:{y}:level")] = value
                        if self.config["change_enabled"] and previous is not None:
                            delta = value - previous[index]
                            if delta > 0:
                                channels[self._channels.channel(f"pixel:{x}:{y}:rise")] = _bounded(delta)
                            elif delta < 0:
                                channels[self._channels.channel(f"pixel:{x}:{y}:fall")] = _bounded(-delta)
                if channels:
                    frames.append(SensoryFrame(
                        source=source,
                        channels=channels,
                        intensity=_bounded(intensity, 0.0, 2.0),
                        bypass_filter=bool(bypass_filter),
                    ))
        self._previous = values
        return tuple(frames)


@dataclass(slots=True, frozen=True)
class AcousticControlFrame:
    consciousness_id: str
    tick: int
    voices: tuple[tuple[float, float], ...]


class AcousticOutputOrgan:
    """Bounded, non-blocking activation sonification output adapter.

    It maps anonymous node identities and activation levels to oscillator
    controls.  It does not use observation labels and therefore cannot turn a
    readable debug annotation into speech by accident.
    """

    def __init__(self, *, maximum_voices: int = 12, minimum_activation: float = .08, queue_size: int = 8) -> None:
        self.maximum_voices = max(1, min(128, int(maximum_voices)))
        self.minimum_activation = _bounded(minimum_activation)
        self._queue: deque[OutputFrame] = deque(maxlen=max(1, int(queue_size)))
        self._lock = Lock()

    def observe(self, frame: OutputFrame) -> None:
        # Called synchronously by OutputBus: retaining a reference is O(1).
        with self._lock:
            self._queue.append(frame)

    def latest(self) -> AcousticControlFrame | None:
        with self._lock:
            if not self._queue:
                return None
            frame = self._queue[-1]
            self._queue.clear()
        active = sorted(
            (
                (int(node.get("id", 0)), _bounded(node.get("activation", 0.0)))
                for node in frame.nodes
                if float(node.get("activation", 0.0)) >= self.minimum_activation
            ),
            key=lambda item: item[1], reverse=True,
        )[:self.maximum_voices]
        voices = tuple((110.0 * 2.0 ** ((node_id % 48) / 12.0), level) for node_id, level in active)
        return AcousticControlFrame(frame.consciousness_id, frame.tick, voices)


@dataclass(slots=True, frozen=True)
class ActivationImageFrame:
    consciousness_id: str
    tick: int
    width: int
    height: int
    pixels: bytes


class ActivationImageProjector:
    """Project anonymous activation into a deterministic grayscale image."""

    def __init__(self, *, width: int = 48, height: int = 32, queue_size: int = 4) -> None:
        self.width = max(8, min(512, int(width))); self.height = max(8, min(512, int(height)))
        self._queue: deque[OutputFrame] = deque(maxlen=max(1, int(queue_size)))
        self._lock = Lock()

    def observe(self, frame: OutputFrame) -> None:
        with self._lock:
            self._queue.append(frame)

    def latest(self) -> ActivationImageFrame | None:
        with self._lock:
            if not self._queue:
                return None
            frame = self._queue[-1]
            self._queue.clear()
        pixels = bytearray(self.width * self.height)
        for node in frame.nodes:
            node_id = int(node.get("id", 0)); level = _bounded(node.get("activation", 0.0))
            digest = hashlib.blake2b(str(node_id).encode(), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % len(pixels)
            pixels[index] = max(pixels[index], round(level * 255.0))
        return ActivationImageFrame(frame.consciousness_id, frame.tick, self.width, self.height, bytes(pixels))
