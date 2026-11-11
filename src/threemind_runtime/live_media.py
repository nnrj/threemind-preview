"""Transport-independent, bounded physical media packets and stream encoding."""

from __future__ import annotations

import math
import struct
from dataclasses import asdict, dataclass

from threemind_core import Stimulus

from .media import AuditoryConfig, AuditorySensor, VisualConfig, VisualSensor, parameter, validate_parameters

LIVE_VERSION = "threemind.live-media/2"
HEADER = struct.Struct("<4sBBIQQB")
AUDIO = struct.Struct("<IH")
VIDEO = struct.Struct("<HHBI")


@dataclass(frozen=True)
class LiveCaptureConfig:
    microphone_enabled: bool = parameter(
        False, "允许连续麦克风", hint="还需启用听觉感官；浏览器只能在明确点击并取得设备权限后开始。"
    )
    camera_enabled: bool = parameter(False, "允许连续摄像头", hint="还需启用视觉感官；不会自动打开设备。")
    audio_packet_us: int = parameter(
        200000, "音频传输块时长", 20000, 1000000, unit="μs", hint="按实际样本累计，结束时保留短尾块。"
    )
    delivery_buffer_us: int = parameter(
        1000000,
        "连续采集递送缓冲",
        100000,
        10000000,
        unit="μs",
        hint="为传输和处理留出时间；音画共享会话的模拟时间锚点。",
    )
    max_packet_bytes: int = parameter(1048576, "单个采集块上限", 4096, 8388608, unit="字节")
    max_pending_packets: int = parameter(
        16, "客户端待确认块上限", 1, 256, hint="达到上限停止采集并标记中断，不静默丢块。"
    )
    max_session_bytes: int = parameter(268435456, "单会话原始数据预算", 1048576, 1099511627776, unit="字节")
    max_session_s: int = parameter(3600, "单会话采集时长上限", 1, 86400, unit="s")

    def __post_init__(self):
        validate_parameters(self)
        if self.audio_packet_us >= self.delivery_buffer_us:
            raise ValueError("传输块时长必须小于递送缓冲。")
        if self.max_packet_bytes > self.max_session_bytes:
            raise ValueError("单个采集块上限不能超过会话原始数据预算。")


@dataclass(frozen=True)
class LivePacket:
    kind: str
    sequence: int
    capture_us: int
    final: bool
    sample_rate: int = 0
    channels: int = 0
    samples: tuple[float, ...] = ()
    width: int = 0
    height: int = 0
    components: int = 0
    pixels: bytes = b""
    source_index: int = 0
    skipped_before: int = 0
    timestamp_kind: int = 0

    @property
    def sample_count(self):
        return len(self.samples) // self.channels if self.channels else 0

    def metadata(self):
        return {
            "protocol": LIVE_VERSION,
            "kind": self.kind,
            "sequence": self.sequence,
            "capture_us": str(self.capture_us),
            "final": self.final,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sample_count": self.sample_count,
            "width": self.width,
            "height": self.height,
            "components": self.components,
            "source_index": str(self.source_index),
            "skipped_before": self.skipped_before,
            "timestamp_kind": {
                0: "source-declared",
                1: "audio-render-frame",
                2: "video-capture",
                3: "video-presentation",
            }[self.timestamp_kind],
            "raw_pcm_peak": max((abs(v) for v in self.samples), default=0),
            "clipped_mono_samples": sum(
                abs(sum(self.samples[i : i + self.channels]) / self.channels) > 1
                for i in range(0, len(self.samples), self.channels)
            )
            if self.kind == "audio"
            else 0,
        }


def decode_packet(raw: bytes, *, max_bytes=1048576) -> LivePacket:
    if len(raw) < HEADER.size or len(raw) > max_bytes:
        raise ValueError("采集块为空、过短或超出字节预算。")
    magic, kind, flags, sequence, capture_us, source_index, timestamp_kind = HEADER.unpack_from(raw)
    if (
        magic != b"TMV2"
        or kind not in (1, 2)
        or flags not in (0, 1)
        or capture_us > 2**53 - 1
        or source_index > 2**53 - 1
        or timestamp_kind not in (0, 1, 2, 3)
    ):
        raise ValueError("采集块协议、类型、标志或时间无效。")
    body = raw[HEADER.size :]
    if kind == 1 and timestamp_kind not in (0, 1) or kind == 2 and timestamp_kind not in (0, 2, 3):
        raise ValueError("时间来源与采集块类型不匹配。")
    if kind == 1:
        if len(body) < AUDIO.size or (len(body) - AUDIO.size) % 4:
            raise ValueError("PCM 数据长度无效。")
        rate, channels = AUDIO.unpack_from(body)
        if not 4000 <= rate <= 384000 or not 1 <= channels <= 8:
            raise ValueError("PCM 采样率或声道数无效。")
        samples = struct.unpack(f"<{(len(body) - AUDIO.size) // 4}f", body[AUDIO.size :])
        if len(samples) % channels or not samples and not flags:
            raise ValueError("PCM 数据必须由完整声道帧组成；仅结束块可为空。")
        if any(not math.isfinite(v) for v in samples):
            raise ValueError("PCM 幅度必须为有限数值。")
        return LivePacket(
            "audio",
            sequence,
            capture_us,
            bool(flags),
            sample_rate=rate,
            channels=channels,
            samples=samples,
            source_index=source_index,
            timestamp_kind=timestamp_kind,
        )
    if flags or len(body) < VIDEO.size:
        raise ValueError("图像采集块不支持结束标志，或元数据缺失。")
    width, height, components, skipped_before = VIDEO.unpack_from(body)
    pixels = body[VIDEO.size :]
    if (
        not 1 <= width <= 2048
        or not 1 <= height <= 2048
        or components not in (1, 3, 4)
        or len(pixels) != width * height * components
    ):
        raise ValueError("图像采集尺寸、组件数或字节长度无效。")
    return LivePacket(
        "video",
        sequence,
        capture_us,
        False,
        width=width,
        height=height,
        components=components,
        pixels=pixels,
        source_index=source_index,
        skipped_before=skipped_before,
        timestamp_kind=timestamp_kind,
    )


def encode_packet(packet: LivePacket) -> bytes:
    if packet.kind not in ("audio", "video"):
        raise ValueError("unknown physical media kind")
    body = (
        AUDIO.pack(packet.sample_rate, packet.channels) + struct.pack(f"<{len(packet.samples)}f", *packet.samples)
        if packet.kind == "audio"
        else VIDEO.pack(packet.width, packet.height, packet.components, packet.skipped_before) + packet.pixels
    )
    raw = (
        HEADER.pack(
            b"TMV2",
            1 if packet.kind == "audio" else 2,
            int(packet.final),
            packet.sequence,
            packet.capture_us,
            packet.source_index,
            packet.timestamp_kind,
        )
        + body
    )
    decode_packet(raw, max_bytes=8388608)
    return raw


class LiveMediaEncoder:
    """Preserve sample continuity, resampler tails and sensory adaptation.

    capture_us belongs to the source session clock. Mapping it to simulation
    is an explicit host operation; this encoder never substitutes arrival time.
    """

    def __init__(self, seed, auditory: AuditoryConfig, visual: VisualConfig, state=None):
        self.seed = seed
        self.audio = AuditorySensor(seed, auditory)
        self.video = VisualSensor(seed, visual)
        self.audio_start_us = None
        self.audio_channels = None
        self.audio_first_source_index = None
        self.audio_timestamp_kind = None
        self.next_sequence = 0
        self.video_last_us = None
        if state:
            if state["schema"] != LIVE_VERSION or state["seed"] != seed:
                raise ValueError("连续感官状态版本或接线种子不匹配。")
            if state["audio"]["config"] != asdict(auditory) or state["video"]["config"] != asdict(visual):
                raise ValueError("连续会话的感官配置已变更，请开始新会话。")
            self.audio = AuditorySensor.restore(state["audio"])
            self.video = VisualSensor.restore(state["video"])
            self.audio_start_us = state["audio_start_us"]
            self.audio_channels = state["audio_channels"]
            self.audio_first_source_index = state["audio_first_source_index"]
            self.audio_timestamp_kind = state["audio_timestamp_kind"]
            self.next_sequence = state["next_sequence"]
            self.video_last_us = state["video_last_us"]

    def capture(self):
        return {
            "schema": LIVE_VERSION,
            "seed": self.seed,
            "audio": self.audio.capture(),
            "video": self.video.capture(),
            "audio_start_us": self.audio_start_us,
            "audio_channels": self.audio_channels,
            "audio_first_source_index": self.audio_first_source_index,
            "audio_timestamp_kind": self.audio_timestamp_kind,
            "next_sequence": self.next_sequence,
            "video_last_us": self.video_last_us,
        }

    def consume(self, packet: LivePacket):
        if packet.sequence != self.next_sequence:
            raise ValueError("采集块序号不连续；不能悄悄跳过、重复或重排。")
        if packet.kind == "audio":
            if not self.audio.config.enabled:
                raise ValueError("听觉感官未开启。")
            if self.audio_channels is not None and self.audio_channels != packet.channels:
                raise ValueError("连续音频声道数改变，请开始新会话。")
            if self.audio_timestamp_kind is not None and self.audio_timestamp_kind != packet.timestamp_kind:
                raise ValueError("连续音频时钟类型改变，请开始新会话。")
            if (
                packet.timestamp_kind == 1
                and self.audio_first_source_index is not None
                and packet.source_index != self.audio_first_source_index + self.audio.source_count
            ):
                raise ValueError("音频源帧计数不连续，不能仅重写时间戳掩盖缺失采样。")
            if self.audio.source_rate is not None:
                expected = self.audio_start_us + round(self.audio.source_count * 1e6 / self.audio.source_rate)
                if abs(packet.capture_us - expected) > max(1, math.ceil(1e6 / packet.sample_rate)):
                    raise ValueError("音频采集时间存在缺口或重叠，请结束当前会话后重新采集。")
            origin = self.audio_start_us if self.audio_start_us is not None else packet.capture_us
            values = [
                max(-1.0, min(1.0, sum(packet.samples[i : i + packet.channels]) / packet.channels))
                for i in range(0, len(packet.samples), packet.channels)
            ]
            frames = self.audio.feed(values, packet.sample_rate, final=packet.final, enforce_duration_limit=False)
            self.audio_start_us, self.audio_channels = origin, packet.channels
            if self.audio_first_source_index is None:
                self.audio_first_source_index = packet.source_index
                self.audio_timestamp_kind = packet.timestamp_kind
            frames = [
                {"stimulus": Stimulus(origin + f["stimulus"].time_us, f["stimulus"].channels, f["stimulus"].intensity)}
                for f in frames
            ]
        else:
            if not self.video.config.enabled:
                raise ValueError("视觉感官未开启。")
            if self.video_last_us is not None and packet.capture_us <= self.video_last_us:
                raise ValueError("图像采集时间必须严格递增。")
            frames = self.video.feed(
                packet.pixels, packet.width, packet.height, components=packet.components, time_us=packet.capture_us
            )
            self.video_last_us = packet.capture_us
        self.next_sequence += 1
        return frames
