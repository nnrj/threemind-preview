"""Versioned binary packets used by browser microphone/camera sessions."""
from __future__ import annotations

import struct
from dataclasses import dataclass


PROTOCOL_NAME = "threemind-media/1"
KIND_AUDIO_F32 = 1
KIND_VIDEO_GRAY8 = 2


class MediaProtocolError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class LiveAudioPacket:
    sequence: int
    timestamp_ms: float
    sample_rate: int
    channels: int
    samples: tuple[float, ...]


@dataclass(slots=True, frozen=True)
class LiveVideoPacket:
    sequence: int
    timestamp_ms: float
    width: int
    height: int
    components: int
    pixels: bytes


def decode_live_packet(payload: bytes) -> LiveAudioPacket | LiveVideoPacket:
    """Decode one browser packet without guessing missing metadata.

    Common header: ``kind:u8, sequence:u32, timestamp_ms:f64`` (little
    endian).  Audio then carries ``sample_rate:u32, channels:u16`` followed by
    interleaved float32 PCM.  Video carries ``width:u16, height:u16,
    components:u8`` followed by unsigned pixel bytes.
    """
    if len(payload) < 13:
        raise MediaProtocolError("media packet is shorter than the common header")
    kind, sequence, timestamp_ms = struct.unpack_from("<BId", payload, 0)
    if kind == KIND_AUDIO_F32:
        if len(payload) < 19:
            raise MediaProtocolError("audio packet is shorter than its header")
        sample_rate, channels = struct.unpack_from("<IH", payload, 13)
        if sample_rate < 1000 or sample_rate > 384000 or channels < 1 or channels > 32:
            raise MediaProtocolError("audio packet declares invalid sample metadata")
        body = payload[19:]
        if len(body) % 4:
            raise MediaProtocolError("audio payload is not aligned to float32")
        samples = struct.unpack(f"<{len(body) // 4}f", body)
        if len(samples) % channels:
            raise MediaProtocolError("audio sample count is not divisible by channel count")
        return LiveAudioPacket(int(sequence), float(timestamp_ms), int(sample_rate), int(channels), tuple(float(value) for value in samples))
    if kind == KIND_VIDEO_GRAY8:
        if len(payload) < 18:
            raise MediaProtocolError("video packet is shorter than its header")
        width, height, components = struct.unpack_from("<HHB", payload, 13)
        if width < 1 or height < 1 or width > 4096 or height > 4096 or components not in {1, 3, 4}:
            raise MediaProtocolError("video packet declares invalid frame metadata")
        pixels = payload[18:]
        expected = int(width) * int(height) * int(components)
        if len(pixels) != expected:
            raise MediaProtocolError("video pixel payload does not match its dimensions")
        return LiveVideoPacket(int(sequence), float(timestamp_ms), int(width), int(height), int(components), bytes(pixels))
    raise MediaProtocolError(f"unsupported media packet kind: {kind}")
