"""Bounded transduction from a seekable carrier; raw storage belongs to the host."""

from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version

from threemind_runtime.media import AuditorySensor, VisualSensor


def capabilities():
    packages = {}
    for name in ("Pillow", "av"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {
        "wav": True,
        "images": bool(packages["Pillow"]),
        "audio_codecs": bool(packages["av"]),
        "video_codecs": bool(packages["av"] and packages["Pillow"]),
        "packages": packages,
    }


def pcm_values(raw, width):
    if width == 1:
        return [(v - 128) / 128 for v in raw]
    if width == 3:
        return [int.from_bytes(raw[i : i + 3], "little", signed=True) / 8388608 for i in range(0, len(raw), 3)]
    if width not in (2, 4):
        raise ValueError("不支持该 WAV 位宽。")
    return [v / 2 ** (width * 8 - 1) for v in struct.unpack(f"<{len(raw) // width}{'h' if width == 2 else 'i'}", raw)]


def decode(raw, kind, spec, intensity):
    return decode_stream(io.BytesIO(raw), len(raw), kind, spec, intensity)


def decode_stream(source, byte_length, kind, spec, intensity, *, progress=None):
    cfg = spec.auditory_sensor if kind == "audio" else spec.visual_sensor
    if not cfg.enabled:
        raise ValueError("该感官尚未启用，请先暂停并在参数配置中开启。")
    if not byte_length or byte_length > cfg.upload_limit_mb * 1024**2:
        raise ValueError("空媒体或原件超过当前感官接收上限。")
    if not math.isfinite(intensity) or not 0 <= intensity <= 100:
        raise ValueError("刺激强度必须是 0 至 100 的有限数值。")
    frames, channel_count = [], 0

    def append(batch):
        nonlocal channel_count
        channel_count += sum(len(f["stimulus"].channels) for f in batch)
        if (
            len(frames) + len(batch) > spec.input_bus.max_pending_frames
            or channel_count > spec.input_bus.max_pending_channels
        ):
            raise ValueError("媒体超出输入总线预算；整条未接收，请调整采样参数或总线预算。")
        frames.extend(batch)
        if progress:
            progress("decoding", source.tell(), len(frames))

    metadata = {"kind": kind, "decoder": capabilities(), "baseline": "reset-per-carrier", "config": asdict(cfg)}

    def float_pcm(array):
        values = []
        clipped = 0
        for raw_value in array.reshape(-1):
            value = float(raw_value)
            if not math.isfinite(value):
                raise ValueError("音频解码产生非有限样本，不能伪造替代幅值。")
            clipped += abs(value) > 1
            values.append(max(-1.0, min(1.0, value)))
        metadata["clipped_pcm_samples"] = metadata.get("clipped_pcm_samples", 0) + clipped
        return values

    try:
        if kind == "audio":
            sensor = AuditorySensor(spec.seed, cfg)
            header = source.read(12)
            source.seek(0)
            if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
                with wave.open(source, "rb") as reader:
                    rate, channels, width = reader.getframerate(), reader.getnchannels(), reader.getsampwidth()
                    if reader.getnframes() > rate * cfg.max_duration_s or channels > 32:
                        raise ValueError("WAV 超过解码时长或声道预算，未接收。")
                    count = 0
                    while chunk := reader.readframes(16384):
                        if len(chunk) % (width * channels):
                            raise ValueError("WAV 末尾样本不完整。")
                        values = pcm_values(chunk, width)
                        mono = [sum(values[i : i + channels]) / channels for i in range(0, len(values), channels)]
                        count += len(mono)
                        append(sensor.feed(mono, rate, intensity=intensity))
                    if count != reader.getnframes():
                        raise ValueError("WAV 声明样本数与实际数据不符，可能已截断。")
                    metadata.update(source_channels=channels, downmix="arithmetic-mean", codec="pcm-wav")
            else:
                try:
                    import av
                except ImportError as error:
                    raise ValueError("该音频格式需要 media 可选依赖；当前仍可使用 PCM WAV。") from error
                with av.open(source) as container:
                    stream = next((s for s in container.streams if s.type == "audio"), None)
                    if stream is None:
                        raise ValueError("文件没有音轨。")
                    resampler, rate, first_time, count = None, None, None, 0
                    for frame in container.decode(stream):
                        if rate is None:
                            rate = int(frame.sample_rate)
                            resampler = av.AudioResampler(format="fltp", layout="mono", rate=rate)
                            metadata.update(
                                codec=stream.codec_context.name,
                                downmix="ffmpeg-mono",
                                source_channels=len(frame.layout.channels),
                            )
                        if frame.sample_rate != rate:
                            raise ValueError("音轨中途改变采样率，当前不支持此载体。")
                        if frame.time is not None:
                            first_time = frame.time if first_time is None else first_time
                            if abs((frame.time - first_time) - count / rate) > 2 / rate:
                                raise ValueError("音轨时间戳包含间隙或重叠，不能静默压缩时间；当前未接收。")
                        count += frame.samples
                        for mono in resampler.resample(frame):
                            append(
                                sensor.feed(
                                    float_pcm(mono.to_ndarray()),
                                    rate,
                                    intensity=intensity,
                                )
                            )
                    if resampler is None:
                        raise ValueError("音轨为空。")
                    for mono in resampler.resample(None):
                        append(
                            sensor.feed(
                                float_pcm(mono.to_ndarray()),
                                rate,
                                intensity=intensity,
                            )
                        )
            if not sensor.source_count:
                raise ValueError("音频没有样本。")
            append(sensor.feed([], rate, final=True, intensity=intensity))
            metadata.update(
                sample_rate=rate,
                source_samples=sensor.source_count,
                duration_us=str(round(sensor.source_count * 1e6 / rate)),
                target_samples=sensor.resampled_count,
                tail_policy="actual-samples-no-zero-padding",
            )
        else:
            try:
                from PIL import Image, ImageOps
            except ImportError as error:
                raise ValueError("图片和视频需要 media 可选依赖（Pillow）。") from error
            sensor = VisualSensor(spec.seed, cfg)

            def picture(image, at):
                if image.width * image.height > 40_000_000:
                    raise ValueError("单画面超过 4,000 万像素解码预算。")
                # Match the runtime's nearest-neighbour retina sampler, before RGB expansion.
                retina = image.resize((cfg.target_width, cfg.target_height), Image.Resampling.NEAREST).convert("RGB")
                append(
                    sensor.feed(
                        retina.tobytes(), retina.width, retina.height, components=3, time_us=at, intensity=intensity
                    )
                )

            if kind == "image":
                with Image.open(source) as image:
                    if image.width * image.height > 40_000_000:
                        raise ValueError("图片超过 4,000 万像素解码预算。")
                    if getattr(image, "n_frames", 1) != 1:
                        raise ValueError("动画图片不能静默当作单帧；请转为带时间戳的视频后递送。")
                    oriented = ImageOps.exif_transpose(image)
                    picture(oriented, 0)
                    metadata.update(
                        width=image.width,
                        height=image.height,
                        exif_orientation="applied",
                        selected_frames=1,
                        decoded_frames=1,
                        duration_us="0",
                    )
            elif kind == "video":
                try:
                    import av
                except ImportError as error:
                    raise ValueError("视频解码需要 media 可选依赖（PyAV）。") from error
                with av.open(source) as container:
                    stream = next((s for s in container.streams if s.type == "video"), None)
                    if stream is None:
                        raise ValueError("文件没有视频轨道。")
                    first = last = selected = None
                    decoded_count = selected_count = 0
                    for frame in container.decode(stream):
                        if progress:
                            progress("decoding", source.tell(), len(frames))
                        if frame.pts is None or frame.time_base is None:
                            raise ValueError("视频缺少画面时间戳，不能伪造帧间时间。")
                        at = round(frame.pts * frame.time_base * 1_000_000)
                        first = at if first is None else first
                        at -= first
                        if last is not None and at <= last:
                            raise ValueError("视频画面时间戳未严格递增。")
                        if at > cfg.max_duration_s * 1e6:
                            raise ValueError("视频超过解码时长上限，整条未接收。")
                        decoded_count += 1
                        if decoded_count > 36000 or frame.width * frame.height > 40_000_000:
                            raise ValueError("视频超过 36,000 帧或单帧 4,000 万像素的解码预算。")
                        last = at
                        if selected is not None and at - selected < cfg.frame_interval_us:
                            continue
                        picture(frame.to_image(), at)
                        selected, selected_count = at, selected_count + 1
                    if first is None:
                        raise ValueError("视频没有画面。")
                    metadata.update(
                        decoded_frames=decoded_count,
                        selected_frames=selected_count,
                        skipped_frames=decoded_count - selected_count,
                        first_pts_us=str(first),
                        duration_us=str(last),
                        audio_track="not-submitted",
                        timing="original-pts-relative-to-first",
                    )
            else:
                raise ValueError("unsupported media kind")
    except (ValueError, ImportError):
        raise
    except Exception as error:
        raise ValueError(f"媒体解码失败，整条未接收：{type(error).__name__}。") from error
    metadata.update(
        sensory_frames=len(frames),
        channel_entries=channel_count,
        last_stimulus_us=str(frames[-1]["stimulus"].time_us) if frames else None,
    )
    return frames, metadata
