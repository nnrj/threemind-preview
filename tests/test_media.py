from __future__ import annotations

import math
import struct
import wave
from io import BytesIO

from threemind.frames import OutputFrame
from threemind.model import ModelManifest, ModelPackage
from threemind.runtime import ConsciousnessRuntime
from threemind.manager import RuntimeManager
from threemind import api
from threemind_adapters import (
    AcousticOutputOrgan,
    ActivationImageProjector,
    AuditorySensorAdapter,
    VisualSensorAdapter,
    default_adapter_registry,
)
from threemind_media import LiveAudioPacket, LiveVideoPacket, MediaAuditStore, MediaCodecService, MediaSizeLimitError, decode_live_packet


def test_auditory_sensor_is_anonymous_temporal_and_non_negative() -> None:
    sensor = AuditorySensorAdapter(41, {"band_count": 6, "sensory_frame_rate": 10})
    samples = [math.sin(math.tau * 440 * index / 8000) * .5 for index in range(1600)]
    first = sensor.encode_samples(samples, 8000)
    assert len(first) == 2
    assert all(frame.source == "manual-audio" for frame in first)
    assert all(channel >= 0 and value >= 0 for frame in first for channel, value in frame.channels.items())
    # A fresh adapter with another sensory seed sees the same physical carrier
    # through a different anonymous receptor mapping.
    other = AuditorySensorAdapter(42, {"band_count": 6, "sensory_frame_rate": 10}).encode_samples(samples, 8000)
    assert set(first[0].channels) != set(other[0].channels)


def test_auditory_first_frame_establishes_change_baseline() -> None:
    sensor = AuditorySensorAdapter(9, {"band_count": 4, "sensory_frame_rate": 1, "level_enabled": False, "change_enabled": True})
    assert sensor.encode_samples([0.0] * 4000, 4000) == ()
    changed = sensor.encode_samples([.8] * 4000, 4000)
    assert changed and all(value >= 0 for value in changed[0].channels.values())


def test_live_audio_buffers_short_browser_blocks_without_inventing_silence() -> None:
    sensor = AuditorySensorAdapter(9, {"band_count": 4, "sensory_frame_rate": 20})
    assert sensor.encode_live_samples([.2] * 128, 16000) == ()
    assert sensor.encode_live_samples([.2] * 672, 16000)


def test_empty_and_waveform_silence_do_not_become_stimuli() -> None:
    sensor = AuditorySensorAdapter(9, {
        "encoding": "waveform", "waveform_bins": 4,
        "sensory_frame_rate": 1, "change_enabled": False,
    })
    assert sensor.encode_samples([], 4000) == ()
    assert sensor.encode_samples([0.0] * 4000, 4000) == ()
    frames = sensor.encode_samples([.5] * 4000, 4000)
    assert frames and all(value > 0.0 for value in frames[0].channels.values())


def test_visual_sensor_uses_local_retinal_patches() -> None:
    sensor = VisualSensorAdapter(7, {
        "target_width": 8, "target_height": 4,
        "patch_width": 2, "patch_height": 2,
        "change_enabled": False,
    })
    pixels = bytes(range(32))
    frames = sensor.encode_pixels(pixels, 8, 4)
    assert len(frames) == 8
    assert all(len(frame.channels) <= 4 for frame in frames)
    # Pixel value zero is absence of excitatory drive rather than a receptor
    # creation request.
    assert len(set().union(*(set(frame.channels) for frame in frames))) == 31
    assert all(value > 0.0 for frame in frames for value in frame.channels.values())


def test_visual_filter_modes_do_not_create_semantic_payloads() -> None:
    pixels = bytes([0, 0, 255, 255] * 4)
    for mode in ("luminance", "edges", "threshold"):
        sensor = VisualSensorAdapter(5, {"target_width": 4, "target_height": 4, "filter_mode": mode})
        frames = sensor.encode_pixels(pixels, 4, 4)
        assert frames
        assert all(isinstance(channel, int) and isinstance(value, float) for frame in frames for channel, value in frame.channels.items())


def test_live_binary_protocol_is_explicit_and_strict() -> None:
    audio_payload = struct.pack("<BIdIH4f", 1, 3, 125.5, 16000, 2, .1, .2, .3, .4)
    audio = decode_live_packet(audio_payload)
    assert isinstance(audio, LiveAudioPacket)
    assert audio.sequence == 3 and audio.channels == 2 and len(audio.samples) == 4
    video_payload = struct.pack("<BIdHHB", 2, 4, 250.0, 2, 2, 1) + bytes([0, 64, 128, 255])
    video = decode_live_packet(video_payload)
    assert isinstance(video, LiveVideoPacket)
    assert video.width == 2 and video.pixels[-1] == 255


def test_standard_library_wav_decode_preserves_physical_duration(tmp_path) -> None:
    path = tmp_path / "tone.wav"
    values = [round(math.sin(math.tau * 440 * index / 8000) * 8192) for index in range(800)]
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(8000)
        writer.writeframes(struct.pack(f"<{len(values)}h", *values))
    decoded = MediaCodecService.decode_audio(path)
    assert decoded.sample_rate == 8000
    assert len(decoded.samples) == 800
    assert abs(decoded.duration_seconds - .1) < 1e-9
    assert max(decoded.samples) <= 1.0 and min(decoded.samples) >= -1.0


def test_consciousness_media_bindings_accept_live_config_and_persist_it(tmp_path, monkeypatch) -> None:
    runtime = ConsciousnessRuntime(ModelPackage.empty(name="live-media-binding"))
    monkeypatch.setattr(api, "manager", RuntimeManager(runtime))
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api, "_record_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "_schedule_history_checkpoint", lambda *_args, **_kwargs: None)

    for adapter_id in ("auditory-sensor", "visual-sensor"):
        result = api.update_consciousness_adapter_binding(
            runtime.consciousness_id,
            adapter_id,
            api.AdapterBindingUpdateRequest(enabled=True, config={"live_enabled": True}),
        )
        assert result["binding"]["enabled"] is True
        assert result["binding"]["config"]["live_enabled"] is True
    assert (tmp_path / f"{runtime.consciousness_id}.tmind").exists()


def test_output_organs_ignore_labels_and_remain_bounded() -> None:
    frame = OutputFrame(
        consciousness_id="mind", tick=7, life_state="alive", metrics={},
        nodes=(
            {"id": 11, "activation": .9, "feature": "human debug label"},
            {"id": 12, "activation": .4, "feature": "another label"},
        ),
        edges=(), delta={},
    )
    mouth = AcousticOutputOrgan(maximum_voices=1); mouth.observe(frame)
    sound = mouth.latest()
    assert sound is not None and len(sound.voices) == 1
    image = ActivationImageProjector(width=8, height=8); image.observe(frame)
    projection = image.latest()
    assert projection is not None and len(projection.pixels) == 64 and max(projection.pixels) > 0


def test_media_audit_is_content_addressed_and_restart_safe(tmp_path) -> None:
    store = MediaAuditStore(tmp_path / "assets", tmp_path / "media.sqlite3")
    first = store.save_asset(b"physical carrier", filename="sample.wav", content_type="audio/wav")
    second = store.save_asset(b"physical carrier", filename="renamed.wav", content_type="audio/wav")
    assert first.asset_id == second.asset_id
    session = store.create_session(consciousness_id="mind", adapter_id="auditory-sensor", mode="upload", asset_id=first.asset_id, config={"gain": 1})
    store.record_delivery(session_id=session["session_id"], consciousness_id="mind", adapter_id="auditory-sensor", envelope_id="env", frame_start=0, frame_count=3, captured_at_ms=0, audit={"anonymous_channel_count": 12})
    store.record_delivery(session_id=session["session_id"], consciousness_id="mind", adapter_id="auditory-sensor", envelope_id="env-2", frame_start=3, frame_count=2, captured_at_ms=50, audit={"anonymous_channel_count": 8})
    reopened = MediaAuditStore(tmp_path / "assets", tmp_path / "media.sqlite3")
    assert reopened.session(session["session_id"])["state"] == "queued"
    assert reopened.list_deliveries(consciousness_id="mind")["total"] == 2
    streamed = list(reopened.iter_deliveries(consciousness_id="mind", page_size=1))
    assert [row["envelope_id"] for row in streamed] == ["env", "env-2"]
    assert reopened.status()["assets"] == 1


def test_media_stream_limit_removes_partial_upload(tmp_path) -> None:
    store = MediaAuditStore(tmp_path / "assets", tmp_path / "media.sqlite3")
    try:
        store.save_stream(BytesIO(b"12345"), filename="large.wav", content_type="audio/wav", byte_limit=4)
    except MediaSizeLimitError:
        pass
    else:
        raise AssertionError("oversized upload must be rejected")
    assert store.status()["assets"] == 0
    assert not list((tmp_path / "assets" / ".incoming").glob("*.tmp"))


def test_media_devices_are_registered_but_model_bindings_default_off() -> None:
    ids = set(default_adapter_registry().ids())
    assert {"auditory-sensor", "visual-sensor", "acoustic-output-organ", "activation-image-projector"} <= ids
    bindings = {item["adapter_id"]: item for item in ModelManifest().adapter_bindings}
    assert all(bindings[name]["enabled"] is False for name in ("auditory-sensor", "visual-sensor", "acoustic-output-organ", "activation-image-projector"))


def test_live_media_reservation_follows_concrete_runtime_on_snapshot_replacement(monkeypatch) -> None:
    """A restored runtime may reuse an id but must not inherit a stale socket."""

    original = ConsciousnessRuntime(ModelPackage.empty(name="media-original"))
    replacement = ConsciousnessRuntime(ModelPackage.empty(name="media-restored"))
    key = (original.consciousness_id, "auditory-sensor")
    monkeypatch.setattr(api, "_active_media_live_sessions", {})
    monkeypatch.setattr(api, "_auditory_adapters", {})
    monkeypatch.setattr(api, "_visual_adapters", {})
    monkeypatch.setattr(api, "_media_output_subscriptions", {})

    old = api._reserve_media_live_session(key, original)
    assert old is not None
    assert api._reserve_media_live_session(key, original) is None

    api._release_media_runtime(original)
    fresh = api._reserve_media_live_session(key, replacement)
    assert fresh is not None

    # The old WebSocket's delayed finally block cannot evict the new owner.
    assert api._release_media_live_session(key, old) is False
    assert api._active_media_live_sessions[key] is fresh
    assert api._release_media_live_session(key, fresh) is True
