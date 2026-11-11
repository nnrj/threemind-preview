"""Nonsemantic PCM/retina transducers and passive output organs (stdlib only).

Codecs and storage are host services. No labels, ASR, OCR or semantic models
participate in these algorithms. Each returned Stimulus remains a separate event.
"""

from __future__ import annotations

import hashlib
import heapq
import io
import math
import struct
import wave
from dataclasses import asdict, dataclass, field, fields

from threemind_core import Stimulus

from .receptors import ReceptorWiring

MEDIA_VERSION = "physical-media/1"
OUTPUT_VERSION = "activation-organs/1"


def parameter(default, label, lo=None, hi=None, *, choices=None, hint="", immutable=False, unit=""):
    return field(
        default=default,
        metadata={
            "label": label,
            "minimum": lo,
            "maximum": hi,
            "choices": choices,
            "hint": hint,
            "immutable": immutable,
            "unit": unit,
        },
    )


def validate_parameters(config):
    for f in fields(config):
        value, rule = getattr(config, f.name), f.metadata
        kind = type(f.default)
        valid_type = type(value) is kind if kind is not float else type(value) in (int, float)
        if not valid_type or (kind in (float, int) and not math.isfinite(value)):
            raise ValueError(f"{type(config).__name__}.{f.name}: invalid {kind.__name__}")
        if rule["choices"] and value not in [c[0] for c in rule["choices"]]:
            raise ValueError(f"{f.name}: unsupported mode")
        if rule["minimum"] is not None and not rule["minimum"] <= value <= rule["maximum"]:
            raise ValueError(f"{f.name}: must lie in [{rule['minimum']}, {rule['maximum']}]")


@dataclass(frozen=True)
class AuditoryConfig:
    enabled: bool = parameter(False, "启用听觉感官", hint="接收音频文件。已接收的载体保留原配置。")
    target_sample_rate: int = parameter(16000, "听觉目标采样率", 4000, 96000, unit="Hz", immutable=True)
    window_us: int = parameter(
        50000,
        "听觉分析窗口",
        5000,
        1000000,
        unit="μs",
        immutable=True,
        hint="完整窗口结束时递送；末尾短窗口按实际样本计算，不补零。",
    )
    encoding: str = parameter(
        "band-energy", "听觉编码", choices=[("band-energy", "频带幅度"), ("waveform", "波形正负通道")], immutable=True
    )
    band_count: int = parameter(12, "频带数", 3, 64, immutable=True)
    minimum_frequency: float = parameter(80.0, "频带最低频率", 1, 47000, unit="Hz", immutable=True)
    maximum_frequency: float = parameter(7600.0, "频带最高频率", 1, 47000, unit="Hz", immutable=True)
    waveform_bins: int = parameter(24, "波形分箱数", 4, 256, immutable=True)
    level_enabled: bool = parameter(True, "听觉电平通道", hint="零幅度表示无刺激。")
    change_enabled: bool = parameter(True, "听觉升降变化通道", hint="首窗口只建立基线；上升、下降为独立的非负通道。")
    gain: float = parameter(1.0, "听觉增益", 0, 100)
    upload_limit_mb: int = parameter(
        32, "单次音频原件上限", 1, 8192, unit="MiB", hint="大文件按数据库分块上传；另受部署暂存配额限制。"
    )
    max_duration_s: int = parameter(
        120, "音频解码时长上限", 1, 600, unit="s", hint="超出上限整条拒绝，不截取。另受输入总线预算约束。"
    )

    def __post_init__(self):
        validate_parameters(self)
        if not self.minimum_frequency <= self.maximum_frequency < self.target_sample_rate / 2:
            raise ValueError("听觉频带须满足 最低频率 ≤ 最高频率 < 目标采样率 / 2。")
        if self.encoding == "waveform" and self.waveform_bins > round(self.target_sample_rate * self.window_us / 1e6):
            raise ValueError("波形分箱数不能超过完整分析窗口的样本数。")


@dataclass(frozen=True)
class VisualConfig:
    enabled: bool = parameter(False, "启用视觉感官", hint="接收图片和视频。视频中的音轨不会自动递送。")
    target_width: int = parameter(24, "视网膜宽度", 2, 256, unit="像素", immutable=True)
    target_height: int = parameter(16, "视网膜高度", 2, 256, unit="像素", immutable=True)
    frame_interval_us: int = parameter(
        166667, "视频采样间隔", 16667, 5000000, unit="μs", hint="保留被采样画面的实际 PTS；被跳过的画面数量记入审计。"
    )
    patch_width: int = parameter(4, "视网膜块宽", 1, 32, unit="像素")
    patch_height: int = parameter(4, "视网膜块高", 1, 32, unit="像素")
    patch_interval_us: int = parameter(
        1000, "块递送间隔", 1, 100000, unit="μs", hint="从左到右、从上到下递送各块，保留空白块对应的时间间隙。"
    )
    filter_mode: str = parameter(
        "luminance", "视觉滤波", choices=[("luminance", "亮度"), ("edges", "Sobel 局部边缘"), ("threshold", "阈值对照")]
    )
    threshold: float = parameter(0.5, "视觉阈值", 0, 1, hint="仅用于阈值滤波。")
    level_enabled: bool = parameter(True, "视觉电平通道")
    change_enabled: bool = parameter(True, "视觉升降变化通道", hint="首画面只建立变化基线；每个独立文件重新建立基线。")
    gain: float = parameter(1.0, "视觉增益", 0, 100)
    upload_limit_mb: int = parameter(
        128, "单次图片／视频原件上限", 1, 8192, unit="MiB", hint="大文件按数据库分块上传；另受部署暂存配额限制。"
    )
    max_duration_s: int = parameter(120, "视频时长上限", 1, 600, unit="s")

    def __post_init__(self):
        validate_parameters(self)
        count = math.ceil(self.target_width / self.patch_width) * math.ceil(self.target_height / self.patch_height)
        if (count - 1) * self.patch_interval_us >= self.frame_interval_us:
            raise ValueError("一次视网膜扫描必须短于视频采样间隔，请调整块大小、块间隔或采样间隔。")


@dataclass(frozen=True)
class AcousticConfig:
    enabled: bool = parameter(False, "启用发声器", hint="被动记录匿名活动的振荡器控制值；页面试听须另行点击。")
    maximum_voices: int = parameter(12, "最大发声音数", 1, 128)
    minimum_activation: float = parameter(0.08, "发声激活下限", 0, 1)
    output_interval_us: int = parameter(100000, "发声控制采样间隔", 20000, 10000000, unit="μs")
    minimum_frequency: float = parameter(110.0, "发声频率下界", 20, 20000, unit="Hz")
    maximum_frequency: float = parameter(
        1760.0, "发声频率上界", 20, 20000, unit="Hz", hint="不含上界；按匿名身份映射到 48 个等比频点。"
    )
    gain: float = parameter(1.0, "发声输出增益", 0, 100, hint="只作用于器官幅值，超过 1 时显式饱和；不改变核心活动。")

    def __post_init__(self):
        validate_parameters(self)
        if self.maximum_frequency <= self.minimum_frequency:
            raise ValueError("发声频率上界必须大于下界。")


@dataclass(frozen=True)
class ProjectorConfig:
    enabled: bool = parameter(
        False, "启用激活图像投影器", hint="将节点活动投射为灰度图，属于观测，不代表内核看见的图像。"
    )
    width: int = parameter(48, "投影图像宽度", 8, 512, unit="像素")
    height: int = parameter(32, "投影图像高度", 8, 512, unit="像素")
    output_interval_us: int = parameter(100000, "投影控制采样间隔", 20000, 10000000, unit="μs")
    gain: float = parameter(1.0, "投影亮度增益", 0, 100, hint="仅改变读出像素；不会改变节点激活。")

    def __post_init__(self):
        validate_parameters(self)


MEDIA_CONFIGS = {
    "auditory_sensor": AuditoryConfig,
    "visual_sensor": VisualConfig,
    "acoustic_output": AcousticConfig,
    "activation_projector": ProjectorConfig,
}


def bounded(value):
    return min(1.0, max(0.0, value))


def feature_channels(wiring, features, previous, config, domain):
    channels = []
    for index, value in enumerate(features):
        if config.level_enabled and value > 0:
            channels.append((wiring.identity(domain + index * 3), value))
        if config.change_enabled and previous is not None:
            delta = value - previous[index]
            if delta:
                channels.append((wiring.identity(domain + index * 3 + (1 if delta > 0 else 2)), bounded(abs(delta))))
    return tuple(sorted(channels))


class AuditorySensor:
    """Continuous rational-phase linear resampling; window timestamps are causal.

    A tail belongs to this sensor stream, not to a transport packet. capture()
    and restore() preserve that tail, resampling phase and change baseline.
    """

    def __init__(self, seed: int, config: AuditoryConfig | None = None):
        self.seed, self.config = seed, config or AuditoryConfig()
        self.wiring = ReceptorWiring(seed)
        self.source_rate = None
        self.source_tail, self.window, self.previous = [], [], None
        self.base = self.source_count = self.resampled_count = 0
        self.finished = False

    def capture(self):
        return {
            "schema": MEDIA_VERSION,
            "seed": self.seed,
            "config": asdict(self.config),
            **{
                k: getattr(self, k).copy() if isinstance(getattr(self, k), list) else getattr(self, k)
                for k in (
                    "source_rate",
                    "source_tail",
                    "window",
                    "previous",
                    "base",
                    "source_count",
                    "resampled_count",
                    "finished",
                )
            },
        }

    @classmethod
    def restore(cls, state):
        if state["schema"] != MEDIA_VERSION:
            raise ValueError("unsupported auditory stream state")
        sensor = cls(state["seed"], AuditoryConfig(**state["config"]))
        for key in (
            "source_rate",
            "source_tail",
            "window",
            "previous",
            "base",
            "source_count",
            "resampled_count",
            "finished",
        ):
            setattr(sensor, key, state[key].copy() if isinstance(state[key], list) else state[key])
        return sensor

    def features(self, samples):
        cfg = self.config
        if cfg.encoding == "waveform":
            result = []
            for index in range(cfg.waveform_bins):
                # Empty bins in a final short window remain zero, not repeated samples.
                part = samples[
                    index * len(samples) // cfg.waveform_bins : (index + 1) * len(samples) // cfg.waveform_bins
                ]
                mean = sum(part) / len(part) * cfg.gain if part else 0
                result.extend((bounded(mean), bounded(-mean)))
            return result
        windowed = (
            [v * (0.5 - 0.5 * math.cos(math.tau * i / (len(samples) - 1))) for i, v in enumerate(samples)]
            if len(samples) > 1
            else samples
        )
        result = []
        for i in range(cfg.band_count):
            frequency = cfg.minimum_frequency * (cfg.maximum_frequency / cfg.minimum_frequency) ** (
                i / (cfg.band_count - 1)
            )
            coefficient = 2 * math.cos(math.tau * frequency / cfg.target_sample_rate)
            previous = previous2 = 0.0
            for value in windowed:
                current = value + coefficient * previous - previous2
                previous2, previous = previous, current
            power = max(0, previous2**2 + previous**2 - coefficient * previous * previous2)
            amplitude = min(1, 2 * math.sqrt(power) / len(samples))
            result.append(bounded(math.log1p(9 * amplitude * cfg.gain) / math.log(10)))
        return result

    def feed(self, samples, sample_rate: int, *, final=False, intensity=1.0, enforce_duration_limit=True):
        if self.finished or type(sample_rate) is not int or not 1 <= sample_rate <= 384000:
            raise ValueError("invalid or finished PCM stream")
        if self.source_rate not in (None, sample_rate):
            raise ValueError("PCM rate changed within one stream")
        if type(intensity) not in (int, float) or not math.isfinite(intensity) or not 0 <= intensity <= 100:
            raise ValueError("invalid stimulus intensity")
        values = list(samples)
        if any(type(v) not in (int, float) or not math.isfinite(v) or not -1 <= v <= 1 for v in values):
            raise ValueError("PCM samples must be finite physical amplitudes in [-1, 1]")
        if enforce_duration_limit and self.source_count + len(values) > self.config.max_duration_s * sample_rate:
            raise ValueError("音频超过解码时长上限，未接收。")
        self.source_rate = sample_rate
        self.source_count += len(values)
        self.source_tail.extend(values)
        rate = self.config.target_sample_rate
        size = max(1, round(rate * self.config.window_us / 1e6))
        frames = []

        def emit(at):
            features = self.features(self.window)
            channels = feature_channels(self.wiring, features, self.previous, self.config, 0x1000000)
            self.previous, self.window = features, []
            if channels and intensity > 0:
                frames.append({"stimulus": Stimulus(at, channels, intensity)})

        while True:
            left, remainder = divmod(self.resampled_count * sample_rate, rate)
            if left >= self.source_count or (remainder and left + 1 >= self.source_count and not final):
                break
            a = self.source_tail[left - self.base]
            b = self.source_tail[min(left + 1, self.source_count - 1) - self.base]
            self.window.append(a + (b - a) * remainder / rate)
            self.resampled_count += 1
            if len(self.window) == size:
                emit(min(round(self.resampled_count * 1e6 / rate), round(self.source_count * 1e6 / sample_rate)))
        retain = min(self.resampled_count * sample_rate // rate, self.source_count)
        self.source_tail = self.source_tail[retain - self.base :]
        self.base = retain
        if final:
            if self.window:
                emit(round(self.source_count * 1e6 / sample_rate))
            self.finished = True
        return frames


class VisualSensor:
    def __init__(self, seed: int, config: VisualConfig | None = None):
        self.seed, self.config = seed, config or VisualConfig()
        self.wiring, self.previous, self.last_time_us = ReceptorWiring(seed), None, None

    def capture(self):
        return {
            "schema": MEDIA_VERSION,
            "seed": self.seed,
            "config": asdict(self.config),
            "previous": self.previous.copy() if self.previous is not None else None,
            "last_time_us": self.last_time_us,
        }

    @classmethod
    def restore(cls, state):
        if state["schema"] != MEDIA_VERSION:
            raise ValueError("unsupported visual stream state")
        sensor = cls(state["seed"], VisualConfig(**state["config"]))
        sensor.previous = state["previous"].copy() if state["previous"] is not None else None
        sensor.last_time_us = state["last_time_us"]
        return sensor

    def feed(self, pixels: bytes, width: int, height: int, *, components=1, time_us=0, intensity=1.0):
        cfg = self.config
        if (
            type(width) is not int
            or type(height) is not int
            or min(width, height) < 1
            or components not in (1, 3, 4)
            or len(pixels) != width * height * components
        ):
            raise ValueError("pixel buffer does not match dimensions")
        if (
            type(time_us) is not int
            or time_us < 0
            or (self.last_time_us is not None and time_us - self.last_time_us < cfg.frame_interval_us)
        ):
            raise ValueError("visual frames must respect their physical sampling interval")
        if type(intensity) not in (int, float) or not math.isfinite(intensity) or not 0 <= intensity <= 100:
            raise ValueError("invalid stimulus intensity")
        w, h = cfg.target_width, cfg.target_height
        values = []
        for y in range(h):
            sy = min(height - 1, int((y + 0.5) * height / h))
            for x in range(w):
                sx = min(width - 1, int((x + 0.5) * width / w))
                index = (sy * width + sx) * components
                values.append(
                    (
                        pixels[index]
                        if components == 1
                        else round(0.2126 * pixels[index] + 0.7152 * pixels[index + 1] + 0.0722 * pixels[index + 2])
                    )
                    / 255
                )
        if cfg.filter_mode == "edges":
            result = [0.0] * len(values)
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    i = y * w + x
                    gx = (
                        -values[i - w - 1]
                        + values[i - w + 1]
                        - 2 * values[i - 1]
                        + 2 * values[i + 1]
                        - values[i + w - 1]
                        + values[i + w + 1]
                    )
                    gy = (
                        -values[i - w - 1]
                        - 2 * values[i - w]
                        - values[i - w + 1]
                        + values[i + w - 1]
                        + 2 * values[i + w]
                        + values[i + w + 1]
                    )
                    result[i] = bounded(math.hypot(gx, gy) / 4)
            values = result
        elif cfg.filter_mode == "threshold":
            values = [1.0 if v >= cfg.threshold else 0.0 for v in values]
        values = [bounded(v * cfg.gain) for v in values]
        frames, scan = [], 0
        for top in range(0, h, cfg.patch_height):
            for left in range(0, w, cfg.patch_width):
                channels = []
                for y in range(top, min(h, top + cfg.patch_height)):
                    for x in range(left, min(w, left + cfg.patch_width)):
                        i = y * w + x
                        # A fixed 256-wide address domain preserves pixel identity across sizes.
                        channels.extend(
                            feature_channels(
                                self.wiring,
                                [values[i]],
                                [self.previous[i]] if self.previous is not None else None,
                                cfg,
                                0x2000000 + (y * 256 + x) * 3,
                            )
                        )
                if channels and intensity > 0:
                    frames.append(
                        {
                            "stimulus": Stimulus(
                                time_us + scan * cfg.patch_interval_us, tuple(sorted(channels)), intensity
                            )
                        }
                    )
                scan += 1
        self.previous, self.last_time_us = values, time_us
        return frames


def organ_output(time_us, activations, acoustic: AcousticConfig, projector: ProjectorConfig, *, audio=True, image=True):
    """Read-only, bounded output projection. Does not read or modify a Core."""
    result = {
        "schema": OUTPUT_VERSION,
        "time_us": str(time_us),
        "configuration": {"acoustic_output": asdict(acoustic), "activation_projector": asdict(projector)},
    }
    if acoustic.enabled and audio:
        active = heapq.nsmallest(
            acoustic.maximum_voices,
            ((int(i), bounded(a)) for i, a in activations if a > 0 and a >= acoustic.minimum_activation),
            key=lambda v: (-v[1], v[0]),
        )
        result["voices"] = [
            {
                "node_id": i,
                "frequency_hz": acoustic.minimum_frequency
                * (acoustic.maximum_frequency / acoustic.minimum_frequency) ** ((i % 48) / 48),
                "amplitude": bounded(a * acoustic.gain),
            }
            for i, a in active
        ]
    if projector.enabled and image:
        pixels = bytearray(projector.width * projector.height)
        for i, a in activations:
            index = int.from_bytes(hashlib.blake2b(str(int(i)).encode(), digest_size=8).digest(), "big") % len(pixels)
            pixels[index] = max(pixels[index], round(bounded(a * projector.gain) * 255))
        # Hex is deterministic and portable; the database can compress the repeated zero bytes.
        result["image"] = {"width": projector.width, "height": projector.height, "gray8_hex": pixels.hex()}
    return result


def render_wav(output, *, sample_rate=16000):
    """Half-second sonification of ONE observation, not a recording or speech."""
    if output.get("schema") != OUTPUT_VERSION or "voices" not in output:
        raise ValueError("此采样未启用发声器。")
    voices, count = output["voices"], sample_rate // 2
    if any(v["frequency_hz"] >= sample_rate / 2 for v in voices):
        if sample_rate >= 48000:
            raise ValueError("输出频率超过合成采样率的 Nyquist 上限。")
        return render_wav(output, sample_rate=48000)
    if len(voices) > 128:
        raise ValueError("invalid organ voice count")
    raw = bytearray()
    for index in range(count):
        t = index / sample_rate
        envelope = min(1, t / 0.01, (0.5 - t) / 0.01)
        value = sum(math.sin(math.tau * v["frequency_hz"] * t) * v["amplitude"] for v in voices)
        raw.extend(struct.pack("<h", round(max(-1, min(1, value * envelope * 0.16 / max(1, len(voices)))) * 32767)))
    stream = io.BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setparams((1, 2, sample_rate, count, "NONE", "not compressed"))
        writer.writeframes(raw)
    return stream.getvalue()
