"""Optional media decoding backends with a standard-library WAV fallback."""
from __future__ import annotations

import contextlib
import io
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class MediaDependencyError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class DecodedAudio:
    sample_rate: int
    samples: tuple[float, ...]
    duration_seconds: float


@dataclass(slots=True, frozen=True)
class DecodedVideoFrame:
    index: int
    timestamp_seconds: float
    width: int
    height: int
    components: int
    pixels: bytes


class MediaCodecService:
    """Decode carriers without interpreting their content."""

    @staticmethod
    def capabilities() -> dict[str, object]:
        try:
            import PIL  # noqa: F401
            pillow = True
        except Exception:
            pillow = False
        try:
            import av  # noqa: F401
            pyav = True
        except Exception:
            pyav = False
        return {
            "wav": True,
            "images": pillow,
            "audio_codecs": pyav,
            "video_codecs": pyav,
            "backend": "pyav+pillow" if pyav and pillow else "pyav" if pyav else "pillow+wave" if pillow else "wave-only",
        }

    @staticmethod
    def _pcm_to_float(raw: bytes, sample_width: int) -> list[float]:
        if sample_width == 1:
            return [(value - 128) / 128.0 for value in raw]
        if sample_width == 2:
            import struct
            return [value / 32768.0 for value in struct.unpack(f"<{len(raw) // 2}h", raw)]
        if sample_width == 3:
            values: list[float] = []
            for offset in range(0, len(raw), 3):
                value = int.from_bytes(raw[offset:offset + 3], "little", signed=False)
                if value & 0x800000: value -= 0x1000000
                values.append(value / 8388608.0)
            return values
        if sample_width == 4:
            import struct
            return [value / 2147483648.0 for value in struct.unpack(f"<{len(raw) // 4}i", raw)]
        raise MediaDependencyError(f"unsupported PCM sample width: {sample_width}")

    @classmethod
    def decode_audio(cls, path: Path | str) -> DecodedAudio:
        path = Path(path)
        if path.suffix.casefold() in {".wav", ".wave"}:
            with contextlib.closing(wave.open(str(path), "rb")) as reader:
                rate = reader.getframerate(); channels = reader.getnchannels(); frames = reader.getnframes()
                values = cls._pcm_to_float(reader.readframes(frames), reader.getsampwidth())
            mono = [sum(values[index:index + channels]) / channels for index in range(0, len(values), channels)]
            return DecodedAudio(rate, tuple(mono), len(mono) / max(1, rate))
        try:
            import av
        except Exception as error:
            raise MediaDependencyError("this audio codec requires the optional media dependency: pip install -e .[media]") from error
        samples: list[float] = []; sample_rate: int | None = None
        with av.open(str(path)) as container:
            stream = next((item for item in container.streams if item.type == "audio"), None)
            if stream is None: raise MediaDependencyError("uploaded file contains no audio stream")
            resampler = None

            def append_mono(frames) -> None:
                for mono_frame in frames or ():
                    array = mono_frame.to_ndarray()
                    # ``fltp`` mono frames are already physical floating-point
                    # samples in [-1, 1].  Resampling before flattening avoids
                    # confusing packed multi-channel array layouts with time.
                    samples.extend(max(-1.0, min(1.0, float(value))) for value in array.reshape(-1))

            for frame in container.decode(stream):
                sample_rate = int(frame.sample_rate or stream.rate or sample_rate or 16000)
                if resampler is None:
                    resampler = av.AudioResampler(format="fltp", layout="mono", rate=sample_rate)
                append_mono(resampler.resample(frame))
            if resampler is not None:
                append_mono(resampler.resample(None))
        rate = int(sample_rate or 16000)
        return DecodedAudio(rate, tuple(samples), len(samples) / max(1, rate))

    @staticmethod
    def decode_image(path: Path | str) -> DecodedVideoFrame:
        try:
            from PIL import Image
        except Exception as error:
            raise MediaDependencyError("image uploads require the optional media dependency: pip install -e .[media]") from error
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            return DecodedVideoFrame(0, 0.0, rgb.width, rgb.height, 3, rgb.tobytes())

    @staticmethod
    def iter_video(path: Path | str, *, maximum_frame_rate: float | None = None) -> Iterator[DecodedVideoFrame]:
        try:
            import av
        except Exception as error:
            raise MediaDependencyError("video uploads require the optional media dependency: pip install -e .[media]") from error
        last_timestamp = float("-inf")
        minimum_delta = 0.0 if not maximum_frame_rate else 1.0 / max(.01, float(maximum_frame_rate))
        with av.open(str(path)) as container:
            stream = next((item for item in container.streams if item.type == "video"), None)
            if stream is None: raise MediaDependencyError("uploaded file contains no video stream")
            emitted = 0
            nominal_rate = float(stream.average_rate) if stream.average_rate else 0.0
            for index, frame in enumerate(container.decode(stream)):
                if frame.time is not None:
                    timestamp = float(frame.time)
                elif frame.pts is not None and frame.time_base is not None:
                    timestamp = float(frame.pts * frame.time_base)
                elif nominal_rate > 0.0:
                    timestamp = index / nominal_rate
                else:
                    # No timing metadata means the carrier cannot support a
                    # trustworthy frame-rate conversion.  Preserve order and
                    # emit every frame instead of pretending they all occurred
                    # at timestamp zero.
                    timestamp = float(index)
                if timestamp - last_timestamp + 1e-9 < minimum_delta:
                    continue
                image = frame.to_image().convert("RGB")
                yield DecodedVideoFrame(emitted, timestamp, image.width, image.height, 3, image.tobytes())
                emitted += 1; last_timestamp = timestamp
