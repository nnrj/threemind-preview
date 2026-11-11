import hashlib
import io
import json
import math
import struct
import wave
import zipfile
from dataclasses import asdict, fields, replace
from pathlib import Path
from uuid import uuid4

import pytest
from test_api import client_for

from threemind_core import Engine
from threemind_lab.configuration import catalogue, default_spec, validate_configuration
from threemind_lab.media_codec import decode
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.media import (
    MEDIA_CONFIGS,
    AcousticConfig,
    AuditoryConfig,
    AuditorySensor,
    ProjectorConfig,
    VisualConfig,
    VisualSensor,
    organ_output,
    render_wav,
)
from threemind_runtime.profile import profile_from_spec, validate_profile
from threemind_runtime.receptors import ReceptorWiring
from threemind_runtime.sensory import TextSensor, TextSensorConfig


def wav(samples, rate=16000):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as writer:
        writer.setparams((1, 2, rate, len(samples), "NONE", "not compressed"))
        writer.writeframes(struct.pack(f"<{len(samples)}h", *[round(v * 32767) for v in samples]))
    return stream.getvalue()


def png():
    from PIL import Image

    image = Image.new("RGB", (4, 4), "black")
    image.putpixel((3, 3), (255, 255, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def protocol():
    return default_spec() | {
        "environment": "manual",
        "clock": "unbounded",
        "duration_s": 0.3,
        "sample_us": 20000,
        "auditory_sensor": asdict(AuditoryConfig(enabled=True, encoding="waveform", waveform_bins=4, window_us=20000)),
        "visual_sensor": asdict(
            VisualConfig(enabled=True, target_width=4, target_height=4, patch_width=2, patch_height=2)
        ),
        "acoustic_output": asdict(AcousticConfig(enabled=True, minimum_activation=0.0)),
        "activation_projector": asdict(ProjectorConfig(enabled=True, width=8, height=8)),
    }


def test_pcm_stream_packetization_restore_silence_and_actual_tail():
    rate = 11025
    values = [0.7 * math.sin(math.tau * 440 * i / rate) for i in range(1429)]
    cfg = AuditoryConfig(window_us=20000)
    whole = AuditorySensor(31, cfg)
    expected = whole.feed(values, rate, final=True)
    fragmented = AuditorySensor(31, cfg)
    actual = []
    for offset in range(0, len(values), 17):
        actual.extend(fragmented.feed(values[offset : offset + 17], rate))
        fragmented = AuditorySensor.restore(json.loads(json.dumps(fragmented.capture())))
    actual.extend(fragmented.feed([], rate, final=True))
    assert actual == expected
    snapshot = AuditorySensor(31, cfg)
    snapshot.feed([0.2] * 17, rate)
    frozen = snapshot.capture()
    material = json.dumps(frozen)
    snapshot.feed([0.8] * 41, rate)
    assert json.dumps(frozen) == material
    assert [f["stimulus"].time_us for f in expected] == [
        20000,
        40000,
        60000,
        80000,
        100000,
        120000,
        round(len(values) * 1e6 / rate),
    ]
    assert len(fragmented.source_tail) <= 1
    assert AuditorySensor(31, cfg).feed([0.0] * 320, 16000, final=True) == []
    cfg = replace(cfg, encoding="waveform", waveform_bins=4)
    sound = AuditorySensor(31, cfg)
    frames = sound.feed([0.8] * 320 + [0.0] * 640, 16000, final=True)
    assert [f["stimulus"].time_us for f in frames] == [20000, 40000]  # fall retained; later silence absent
    change = AuditorySensor(31, replace(cfg, level_enabled=False))
    assert change.feed([0.8] * 320, 16000, final=True) == []
    with pytest.raises(ValueError):
        AuditorySensor(31).feed([float("nan")], 16000)


def test_retinal_locality_timing_namespaces_and_recovery():
    cfg = VisualConfig(target_width=4, target_height=4, patch_width=2, patch_height=2)
    sensor = VisualSensor(31, cfg)
    image = bytes([0] * 15 + [255])
    frames = sensor.feed(image, 4, 4, time_us=0)
    assert len(frames) == 1 and frames[0]["stimulus"].time_us == 3000  # empty patches retain their slots
    cloned = VisualSensor.restore(json.loads(json.dumps(sensor.capture())))
    assert sensor.feed(bytes(16), 4, 4, time_us=200000) == cloned.feed(bytes(16), 4, 4, time_us=200000)
    assert len(cloned.feed(bytes([255] * 16), 4, 4, time_us=400000)) == 4
    with pytest.raises(ValueError):
        cloned.feed(image, 4, 4, time_us=400001)
    # The affine mapping is a bijection: entire receptor domains remain disjoint.
    wiring = ReceptorWiring(31)
    domains = [
        {wiring.identity(base + i) for i in range(size)}
        for base, size in ((0x1000000, 1536), (0x2000000, 256 * 256 * 3))
    ]
    text = TextSensor(31, TextSensorConfig(encoding="literal-character"))
    assert not domains[0].intersection(domains[1])
    for f in text.frames("Aa汉字👁"):
        assert not {c for c, _ in f["stimulus"].channels}.intersection(domains[0] | domains[1])
    local = Engine()
    for f in VisualSensor(31, cfg).feed(bytes([255] * 16), 4, 4):
        local.inject(f["stimulus"])
    local.advance_to(3000)
    assert len(local.capture_state().to_dict()["edges"]) == 4 * 4 * 3  # only four independent 2x2 blocks


def test_media_catalogue_profile_contract_and_immutable_wiring():
    contract = json.loads(Path("crates/threemind-runtime/src/media-profile-contract.json").read_text(encoding="utf-8"))
    for root, cls in MEDIA_CONFIGS.items():
        assert contract[root] == json.loads(
            json.dumps(
                {
                    f.name: {
                        "type": type(f.default).__name__,
                        **{k: v for k, v in f.metadata.items() if k in ("minimum", "maximum", "choices")},
                    }
                    for f in fields(cls)
                }
            )
        )
    available = {f["path"] for f in catalogue()["fields"]}
    assert {f"{root}.{f.name}" for root, cls in MEDIA_CONFIGS.items() for f in fields(cls)} <= available
    original = protocol()
    changed = original | {"visual_sensor": original["visual_sensor"] | {"target_width": 8}}
    assert any(
        e["path"] == "visual_sensor.target_width" for e in validate_configuration(changed, current=original)["errors"]
    )
    assert not validate_configuration(original | {"auditory_sensor": {"gain": "1"}})["valid"]
    with pytest.raises(ValueError):
        AuditoryConfig(target_sample_rate=4000)
    with pytest.raises(ValueError):
        VisualConfig(frame_interval_us=16667)
    profile = profile_from_spec(original)
    _, restored = ArtifactCodec.decode(
        ArtifactCodec.encode(Engine().capture_state(), profile=profile), with_profile=True
    )
    assert profile == restored
    legacy = {"schema": "threemind.runtime-profile/1", "sensory_seed": 31, "text_sensor": asdict(TextSensorConfig())}
    assert validate_profile(legacy) == legacy


def test_decoded_carrier_limits_video_pts_and_visual_filters():
    spec = RunSpec(**protocol())
    audio = wav([0.5] * 643)
    frames, metadata = decode(audio, "audio", spec, 1)
    assert frames[-1]["stimulus"].time_us == round(643 * 1e6 / 16000)
    assert metadata["source_samples"] == 643
    with pytest.raises(ValueError):
        decode(audio[:-1], "audio", spec, 1)
    frames, metadata = decode(png(), "image", spec, 1)
    assert len(frames) == 1 and frames[0]["stimulus"].time_us == 3000
    for mode in ("edges", "threshold"):
        altered = spec.model_copy(update={"visual_sensor": replace(spec.visual_sensor, filter_mode=mode)})
        result, _ = decode(png(), "image", altered, 1)
        assert all(set(f) == {"stimulus"} for f in result)
    with pytest.raises(ValueError, match="预算"):
        decode(audio, "audio", RunSpec(**(protocol() | {"input_bus": {"max_pending_frames": 1}})), 1)
    import av
    import numpy as np

    stream = io.BytesIO()
    with av.open(stream, "w", format="matroska") as container:
        video = container.add_stream("ffv1", rate=10)
        video.width = video.height = 32
        video.pix_fmt = "gray"
        for i in range(6):
            frame = av.VideoFrame.from_ndarray(np.full((32, 32), 80 if i % 2 else 180, dtype=np.uint8), format="gray")
            for packet in video.encode(frame):
                container.mux(packet)
        for packet in video.encode():
            container.mux(packet)
    result, metadata = decode(stream.getvalue(), "video", spec, 1)
    assert metadata["decoded_frames"] == 6 and metadata["selected_frames"] == 3
    assert [f["stimulus"].time_us for f in result] == [
        t + offset for t in (0, 200000, 400000) for offset in (0, 1000, 2000, 3000)
    ]


def test_media_admission_is_atomic_auditable_and_restorable(database, monkeypatch):
    with client_for(database) as client:
        p = client.post("/api/v2/projects", json={"name": "Media restoration"}).json()["id"]
        root = f"/api/v2/projects/{p}"
        run = client.post(f"{root}/runs", json={"name": "Physical media", "spec": protocol()}).json()
        url = f"{root}/runs/{run['id']}"
        worker = Worker(database)
        client.post(f"{url}/commands", json={"kind": "pause"})
        assert worker.once()
        originals = [wav([0.5] * 643), png(), wav([0.0] * 320)]
        accepted = []
        for raw, kind in zip(originals, ("audio", "image", "audio")):
            identifier = str(uuid4())
            params = {"kind": kind, "filename": f"{kind}.bin", "request_id": identifier, "delay_us": 5000}
            response = client.post(f"{url}/media", params=params, content=raw)
            assert response.status_code == 202, response.text
            accepted.append(identifier)
            assert client.post(f"{url}/media", params=params, content=raw).json()["id"] == identifier
            assert client.post(f"{url}/media", params=params, content=raw + b"X").status_code == 409
            download = client.get(f"{url}/media/{identifier}/original")
            assert download.content == raw and download.headers["x-content-sha256"] == hashlib.sha256(raw).hexdigest()
        with database.tx(p) as db:
            assert db.execute("SELECT count(*) AS n FROM media_assets").fetchone()["n"] == 3
            prepared = db.execute(
                "SELECT envelope_id,stimulus FROM media_prepared_frames ORDER BY envelope_id,frame_index"
            ).fetchall()
        bundle = client.get(f"{url}/media/export")
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
            assert len(json.loads(archive.read("manifest.json"))["carriers"]) == 3
            assert {archive.read(f"originals/{hashlib.sha256(raw).hexdigest()}.bin") for raw in originals} == set(
                originals
            )
        # Project RLS, including binary routes and prepared frames.
        foreign = client.post("/api/v2/projects", json={"name": "Other project"}).json()["id"]
        assert (
            client.get(f"/api/v2/projects/{foreign}/runs/{run['id']}/media/{accepted[0]}/original").status_code == 404
        )
        with database.tx(foreign) as db:
            assert db.execute("SELECT count(*) AS n FROM media_chunks").fetchone()["n"] == 0
        bad = client.post(
            f"{url}/media",
            params={"kind": "image", "filename": "bad.png", "request_id": str(uuid4())},
            content=b"invalid",
        )
        assert bad.status_code == 422
        from threemind_lab import media_store

        persisted = media_store.persist

        def fail_after_binary_write(*args):
            persisted(*args)
            raise ValueError("injected storage failure")

        with monkeypatch.context() as patch:
            patch.setattr(media_store, "persist", fail_after_binary_write)
            failure = client.post(
                f"{url}/media",
                params={"kind": "audio", "filename": "rollback.wav", "request_id": str(uuid4())},
                content=wav([0.2] * 321),
            )
            assert failure.status_code == 422
        with database.tx(p) as db:
            assert db.execute("SELECT count(*) AS n FROM input_envelopes").fetchone()["n"] == 3
            assert db.execute("SELECT count(*) AS n FROM media_assets").fetchone()["n"] == 3
            assert db.execute("SELECT count(*) AS n FROM media_prepared_frames").fetchone()["n"] == 4
        # Schedule, pause with queue pending, then restore into a new worker.
        client.post(f"{url}/commands", json={"kind": "pause"})
        client.post(f"{url}/commands", json={"kind": "resume"})
        assert worker.once()
        paused = client.get(url).json()
        assert paused["status"] == "paused", paused.get("error")
        _cp, state = database.load_checkpoint(p, run["id"])
        expected = create_engine(state=state)
        expected.advance_to(300000)
        assert client.get(f"{url}/inputs/{accepted[2]}").json()["envelope"]["status"] == "completed"
        client.post(f"{url}/commands", json={"kind": "resume"})
        assert Worker(database).once()
        finished = client.get(url).json()
        assert finished["status"] == "completed", finished.get("error")
        assert finished["state_hash"] == expected.capture_state().digest  # outputs do not influence dynamics
        for identifier in accepted:
            record = client.get(f"{url}/inputs/{identifier}").json()
            assert record["envelope"]["status"] == "completed"
            assert record["envelope"]["delivered_count"] == record["envelope"]["frame_count"]
            assert all(f["scheduled_time_us"] == f["delivered_time_us"] for f in record["frames"])
        exported = [json.loads(line) for line in client.get(f"{url}/organs/export").text.splitlines()]
        assert any(e["payload"].get("voices") for e in exported)
        assert all(e["kind"] != "organ_output" for e in client.get(f"{url}/events").json())
        assert client.get(f"{url}/events?kind=organ_output").json()
        cursor, ids = None, []
        while True:
            page = client.get(f"{url}/organs", params={"limit": 2, **({"before_id": cursor} if cursor else {})}).json()
            ids += [r["sample_id"] for r in page["rows"]]
            if not page["more"]:
                break
            cursor = page["next"]
        assert len(ids) == len(set(ids)) == len(exported)
        sound = client.get(f"{url}/organs/{ids[-1]}/audio.wav")
        assert sound.status_code == 200 and sound.content[:4] == b"RIFF"
        export = database.enqueue(p, "export", {"format": "evidence"}, run["id"])
        assert Worker(database).once()
        with database.tx(p) as db:
            job = db.execute("SELECT * FROM jobs WHERE id=%s", (export["id"],)).fetchone()
        assert job["status"] == "done", job["error"]
        package = client.get(f"{root}/artifacts/{job['result']['artifact_id']}")
        assert package.status_code == 200, package.text
        with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
            assert len(archive.read("input-carriers.jsonl").splitlines()) == 3  # includes silent carrier
            assert archive.read("organ-outputs.jsonl")
        assert len(prepared) == 4


def test_output_organs_ignore_labels_and_bound_synthesis():
    cfg = AcousticConfig(enabled=True, maximum_voices=2)
    image = ProjectorConfig(enabled=True, width=8, height=8)
    output = organ_output(10000, [(1, 0.8), (3, 0.9), (2, 0)], cfg, image)
    assert [v["node_id"] for v in output["voices"]] == [3, 1]
    assert len(output["image"]["gray8_hex"]) == 128
    with wave.open(io.BytesIO(render_wav(output))) as reader:
        assert reader.getnframes() == 8000 and reader.getframerate() == 16000
        values = struct.unpack("<8000h", reader.readframes(8000))
        assert max(abs(v) for v in values) <= 5243


def test_compressed_audio_decode_preserves_physical_sample_duration():
    import av
    import numpy as np

    stream = io.BytesIO()
    with av.open(stream, "w", format="flac") as container:
        track = container.add_stream("flac", rate=48000)
        track.layout = "mono"
        frame = av.AudioFrame.from_ndarray(np.full((1, 4800), 16000, dtype=np.int16), format="s16", layout="mono")
        frame.sample_rate = 48000
        for packet in track.encode(frame):
            container.mux(packet)
        for packet in track.encode():
            container.mux(packet)
    frames, metadata = decode(stream.getvalue(), "audio", RunSpec(**protocol()), 1)
    assert metadata["source_samples"] == 4800 and metadata["duration_us"] == "100000"
    assert metadata["decoder"]["packages"]["av"]
    assert [f["stimulus"].time_us for f in frames] == [20000, 40000, 60000, 80000, 100000]
