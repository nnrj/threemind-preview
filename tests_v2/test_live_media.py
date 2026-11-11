import json
import math
import struct
from dataclasses import replace
from uuid import uuid4

import pytest
from test_api import client_for

from threemind_lab.protocols import RunSpec
from threemind_lab.readouts import ReadoutHost
from threemind_lab.worker import Worker
from threemind_runtime.host import NativeEngine
from threemind_runtime.live_media import LiveCaptureConfig, LiveMediaEncoder, LivePacket, decode_packet, encode_packet
from threemind_runtime.media import AuditoryConfig, AuditorySensor, VisualConfig


def packet(sequence, at, samples, final=False):
    return decode_packet(
        encode_packet(LivePacket("audio", sequence, at, final, sample_rate=16000, channels=1, samples=tuple(samples)))
    )


def test_capture_database_access_does_not_block_the_async_receiver(monkeypatch):
    import asyncio
    import threading
    from types import SimpleNamespace

    import httpx
    from fastapi import FastAPI

    from threemind_lab import live_capture
    from threemind_lab.live_capture_api import register_capture_routes

    async def scenario():
        main_thread = threading.get_ident()
        entered, release = threading.Event(), threading.Event()

        def access(*args, **kwargs):
            assert threading.get_ident() != main_thread
            entered.set()
            assert release.wait(3)
            return {"id": str(uuid4())}

        app = FastAPI()
        app.state.db = SimpleNamespace(get_run=lambda *args: {"spec": {}})
        register_capture_routes(app, access, asyncio.Semaphore(1))
        monkeypatch.setattr(live_capture, "accept_packet", lambda *args: {"accepted": True})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            url = f"/api/v2/projects/{uuid4()}/runs/{uuid4()}/capture/{uuid4()}/packets"
            receiving = asyncio.create_task(client.post(url, content=b"test"))
            try:
                assert await asyncio.to_thread(entered.wait, 1)
                # Still executing on the event loop while database access waits.
                assert not receiving.done()
            finally:
                release.set()
            assert (await receiving).status_code == 202

    asyncio.run(scenario())


def test_live_packets_use_periodic_checkpoint_without_losing_delivery_audit(database, monkeypatch):
    """Each packet used to force a synchronous whole-model checkpoint."""
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "capture checkpoint cadence"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = RunSpec(
            environment="manual",
            clock="realtime",
            duration_s=2.2,
            checkpoint_us=2000000,
            auditory_sensor=AuditoryConfig(enabled=True, encoding="waveform", waveform_bins=4),
            live_capture=LiveCaptureConfig(microphone_enabled=True),
            structural_readout={"enabled": False},
            temporal_readout={"enabled": False},
        )
        run = client.post(f"{root}/runs", json={"name": "continuous packets", "spec": spec.model_dump()}).json()["id"]
        url = f"{root}/runs/{run}"
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
        session = str(uuid4())
        assert (
            client.post(
                f"{url}/capture",
                json={
                    "session_id": session,
                    "kind": "audio",
                    "source_clock": {"kind": "synthetic-test-clock"},
                },
            ).status_code
            == 201
        )
        sent = []
        checkpoints = []
        original_observe, original_save = ReadoutHost.observe, database.save_checkpoint

        def observe(host, engine, **kwargs):
            original_observe(host, engine, **kwargs)
            if len(sent) < 4 and engine.time_us >= len(sent) * 200000:
                sequence = len(sent)
                raw = encode_packet(packet(sequence, sequence * 200000, [0.4] * 3200, sequence == 3))
                response = client.post(f"{url}/capture/{session}/packets", content=raw)
                assert response.status_code == 202, response.text
                sent.append(response.json()["envelope_id"])

        def save(*args, **kwargs):
            result = original_save(*args, **kwargs)
            checkpoints.append(int(result["time_us"]))
            return result

        monkeypatch.setattr(ReadoutHost, "observe", observe)
        monkeypatch.setattr(database, "save_checkpoint", save)
        assert Worker(database).once()
        assert len(sent) == 4
        assert checkpoints[0] >= 1800000, checkpoints
        assert len(checkpoints) <= 2, checkpoints
        rows = client.get(f"{url}/capture/{session}/packets").json()["rows"]
        assert all(r["status"] == "completed" and r["delivered_count"] == 4 for r in rows)
        cp, image = database.load_checkpoint(project, run)
        assert not any(event["kind"] == "stimulus" for event in image.to_dict()["queue"])
        assert cp["context"]["input_bus_run_id"] == run


def test_live_audio_partition_restore_and_final_tail_preserve_actual_samples():
    audio = AuditoryConfig(enabled=True)
    visual = VisualConfig(enabled=True)
    samples = [0.4 * math.sin(i * math.tau * 440 / 16000) for i in range(1900)]
    # Float32 bytes are the actual retained carrier, not the source's float64 list.
    samples = packet(0, 0, samples).samples
    whole = AuditorySensor(79, audio).feed(samples, 16000, final=True)
    live = LiveMediaEncoder(79, audio, visual)
    assert not live.consume(packet(0, 700000, samples[:100]))
    state = json.loads(json.dumps(live.capture()))
    resumed = LiveMediaEncoder(79, audio, visual, state)
    chunks = [packet(1, 706250, samples[100:900]), packet(2, 756250, samples[900:], True)]
    actual = []
    for p in chunks:
        emitted = resumed.consume(p)
        assert emitted == live.consume(p)
        actual += emitted
    assert [f["stimulus"].time_us - 700000 for f in actual] == [f["stimulus"].time_us for f in whole]
    assert [f["stimulus"].channels for f in actual] == [f["stimulus"].channels for f in whole]
    assert actual[-1]["stimulus"].time_us == 818750
    assert live.capture() == resumed.capture()
    frozen = live.capture()
    frozen["audio"]["previous"][0] = -999
    assert live.capture()["audio"]["previous"][0] >= 0


def test_exact_rate_window_does_not_wait_for_a_nonexistent_interpolation_dependency():
    sensor = AuditorySensor(1, AuditoryConfig(enabled=True))
    frames = sensor.feed([0.2] * 800, 16000)
    assert len(frames) == 1 and frames[0]["stimulus"].time_us == 50000
    assert sensor.feed([], 16000, final=True) == []


def test_live_audio_rejects_gaps_rate_changes_and_sequence_loss_before_state_changes():
    live = LiveMediaEncoder(1, AuditoryConfig(enabled=True), VisualConfig(enabled=True))
    live.consume(packet(0, 0, [0.2] * 160))
    state = live.capture()
    for bad in (
        packet(2, 10000, [0.2] * 160),
        packet(1, 100000, [0.2] * 160),
        replace(packet(1, 10000, [0.2] * 160), sample_rate=8000),
    ):
        with pytest.raises(ValueError):
            live.consume(bad)
        assert live.capture() == state


def test_interleaved_audio_video_uses_one_session_clock_without_merging_events():
    live = LiveMediaEncoder(
        1,
        AuditoryConfig(enabled=True),
        VisualConfig(enabled=True, target_width=4, target_height=4, patch_width=2, patch_height=2),
    )
    assert not live.consume(packet(0, 0, [0.2] * 160))
    image = LivePacket("video", 1, 20000, False, width=4, height=4, components=1, pixels=bytes([128] * 16))
    assert decode_packet(encode_packet(image)) == image
    frames = live.consume(image)
    assert [f["stimulus"].time_us for f in frames] == [20000, 21000, 22000, 23000]
    audio = live.consume(packet(2, 10000, [0.2] * 640, True))
    assert [f["stimulus"].time_us for f in audio] == [50000]
    assert not (
        {c for f in frames for c, _ in f["stimulus"].channels} & {c for f in audio for c, _ in f["stimulus"].channels}
    )


def test_audio_render_counter_detects_loss_even_when_timestamps_are_rewritten():
    live = LiveMediaEncoder(1, AuditoryConfig(enabled=True), VisualConfig())
    first = replace(packet(0, 0, [0.1] * 160), source_index=1000, timestamp_kind=1)
    live.consume(first)
    live = LiveMediaEncoder(1, AuditoryConfig(enabled=True), VisualConfig(), live.capture())
    before = live.capture()
    with pytest.raises(ValueError, match="帧计数"):
        live.consume(replace(packet(1, 10000, [0.1] * 160), source_index=1200, timestamp_kind=1))
    assert live.capture() == before
    live.consume(replace(packet(1, 10000, [0.1] * 160, True), source_index=1160, timestamp_kind=1))


def test_capture_incomplete_tail_abandoned_ownership_and_worker_failure(database, monkeypatch):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "capture interruption verification"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        run = client.post(
            f"{root}/runs",
            json={
                "name": "interruptions",
                "spec": {
                    "environment": "manual",
                    "clock": "realtime",
                    "duration_s": 2,
                    "auditory_sensor": {"enabled": True},
                    "live_capture": {"microphone_enabled": True},
                },
            },
        ).json()["id"]
        url = f"{root}/runs/{run}/capture"
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))

        def start():
            response = client.post(
                url,
                json={
                    "session_id": str(uuid4()),
                    "kind": "audio",
                    "source_clock": {"kind": "synthetic-test-clock", "physical_hardware": False},
                },
            )
            assert response.status_code == 201, response.text
            return response.json()["id"]

        first = start()
        assert (
            client.post(f"{url}/{first}/packets", content=encode_packet(packet(0, 0, [0.1] * 160))).status_code == 202
        )
        stopped = client.post(f"{url}/{first}/stop", json={}).json()
        assert stopped["status"] == "interrupted" and stopped["reason"] == "incomplete_audio_tail"
        # A pause before the first scheduling pass must not re-anchor the old
        # physical carrier when the model later resumes.
        from threemind_lab.input_cycle import RuntimeInputs

        with database.tx(project) as db:
            db.execute("UPDATE capture_sessions SET reason='paused' WHERE id=%s", (first,))
        envelope = client.get(f"{url}/{first}/packets").json()["rows"][0]["envelope_id"]
        engine = NativeEngine()
        spec = RunSpec(**client.get(f"{root}/runs/{run}").json()["spec"])
        inputs = RuntimeInputs(database, project, run, engine, spec, {}, 0)
        inputs.accepted(envelope)
        assert len(inputs.changes["rejected"]) == 1 and inputs.capture_streams == {}
        assert engine.capture_state().to_dict()["queue"] == []
        second = start()
        with database.tx(project) as db:
            db.execute("UPDATE capture_sessions SET updated_at=now()-interval '31 seconds' WHERE id=%s", (second,))
        third = start()
        rows = {r["id"]: r for r in client.get(url).json()["rows"]}
        assert rows[second]["reason"] == "idle_timeout" and rows[third]["status"] == "active"

        def fail(*args):
            raise ValueError("synthetic worker failure")

        monkeypatch.setattr(Worker, "run", fail)
        assert Worker(database).once()
        rows = {r["id"]: r for r in client.get(url).json()["rows"]}
        assert rows[third]["status"] == "interrupted" and rows[third]["reason"] == "worker_failed"


def test_protocol_rejects_invalid_physical_values_and_byte_budget():
    raw = encode_packet(LivePacket("audio", 0, 0, False, sample_rate=16000, channels=1, samples=(0.2,)))
    for bad in (
        raw[:10],
        raw[:-1],
        raw[:-4] + struct.pack("<f", math.nan),
        raw[:-4] + struct.pack("<f", math.inf),
        b"bad!" + raw[4:],
    ):
        with pytest.raises(ValueError):
            decode_packet(bad)
    with pytest.raises(ValueError):
        decode_packet(raw, max_bytes=8)
    with pytest.raises(ValueError):
        LiveCaptureConfig(audio_packet_us=1000000, delivery_buffer_us=100000)
    sensor = AuditorySensor(1, AuditoryConfig(max_duration_s=1))
    with pytest.raises(ValueError):
        sensor.feed([0.0] * 16001, 16000)
    # Long live acquisition is bounded by session budgets instead of file duration.
    assert sensor.feed([0.0] * 16001, 16000, enforce_duration_limit=False) == []


def test_float_pcm_overshoot_retained_with_explicit_sensory_saturation():
    raw = encode_packet(LivePacket("audio", 0, 0, True, sample_rate=16000, channels=1, samples=(1.25, -1.1)))
    decoded = decode_packet(raw)
    assert decoded.samples[0] == 1.25
    assert decoded.metadata()["clipped_mono_samples"] == 2
    assert decoded.metadata()["raw_pcm_peak"] == 1.25
    audio = AuditoryConfig(enabled=True, encoding="waveform", waveform_bins=4)
    frames = LiveMediaEncoder(1, audio, VisualConfig()).consume(decoded)
    expected = AuditorySensor(1, audio).feed([1.0, -1.0], 16000, final=True)
    assert frames == expected


def test_live_capture_atomic_admission_shared_clock_pause_resume_and_export(database, monkeypatch):
    with client_for(database) as client:
        project = client.post("/api/v2/projects", json={"name": "live capture verification"}).json()["id"]
        root = f"/api/v2/projects/{project}"
        spec = RunSpec(
            environment="manual",
            clock="realtime",
            duration_s=2,
            checkpoint_us=100000,
            auditory_sensor=AuditoryConfig(enabled=True),
            visual_sensor=VisualConfig(enabled=True, target_width=4, target_height=4),
            live_capture=LiveCaptureConfig(microphone_enabled=True, camera_enabled=True),
            structural_readout={"enabled": False},
            temporal_readout={"enabled": False},
        )
        run = client.post(f"{root}/runs", json={"name": "AV capture", "spec": spec.model_dump()}).json()["id"]
        url = f"{root}/runs/{run}"
        # Admission fixture represents the worker's running status; real execution follows.
        with database.tx(project) as db:
            db.execute("UPDATE runs SET status='running' WHERE id=%s", (run,))
        session = str(uuid4())
        body = {
            "session_id": session,
            "kind": "av",
            "source_clock": {"kind": "synthetic-test-clock", "physical_hardware": False},
        }
        response = client.post(f"{url}/capture", json=body)
        assert response.status_code == 201, response.text
        assert client.post(f"{url}/capture", json=body).json()["id"] == session
        raw = encode_packet(packet(0, 0, [0.2] * 3200))
        from threemind_lab import media_store

        original = media_store.persist

        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("injected raw-block transaction failure")

        with monkeypatch.context() as patch:
            patch.setattr(media_store, "persist", fail)
            result = client.post(
                f"{url}/capture/{session}/packets", content=raw, headers={"Content-Type": "application/octet-stream"}
            )
            assert result.status_code == 422
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM media_assets").fetchone()["n"] == 0
            assert db.execute("SELECT count(*) AS n FROM input_envelopes").fetchone()["n"] == 0
            saved = db.execute(
                "SELECT next_sequence,encoder_state FROM capture_sessions WHERE id=%s", (session,)
            ).fetchone()
            assert saved["next_sequence"] == 0 and saved["encoder_state"]["audio"]["source_count"] == 0
        # Model projection writes must not hold up live admission. Two identical
        # concurrent sends still reserve the input budget and packet sequence once.
        import threading
        from concurrent.futures import ThreadPoolExecutor

        pool = ThreadPoolExecutor(max_workers=2)
        done = threading.Event()
        responses = []

        def send_packet():
            response = client.post(f"{url}/capture/{session}/packets", content=raw)
            responses.append(response)
            if len(responses) == 2:
                done.set()

        try:
            with database.tx(project) as db:
                db.execute("SELECT id FROM runs WHERE id=%s FOR NO KEY UPDATE", (run,))
                tasks = [pool.submit(send_packet) for _ in range(2)]
                concurrent = done.wait(3)
            for task in tasks:
                task.result(timeout=5)
        finally:
            pool.shutdown()
        assert concurrent, "packet admission waited for an unrelated projection transaction"
        assert sorted(r.json()["duplicate"] for r in responses) == [False, True]
        first = responses[0]
        assert first.status_code == 202, first.text
        assert client.post(f"{url}/capture/{session}/packets", content=raw).json()["duplicate"]
        wrong = encode_packet(packet(0, 0, [0.3] * 3200))
        assert client.post(f"{url}/capture/{session}/packets", content=wrong).status_code == 409
        video = encode_packet(
            LivePacket("video", 1, 150000, False, width=4, height=4, components=1, pixels=bytes([128] * 16))
        )
        second = client.post(f"{url}/capture/{session}/packets", content=video)
        assert second.status_code == 202, second.text
        tail = encode_packet(packet(2, 200000, [0.2] * 1600, True))
        assert client.post(f"{url}/capture/{session}/packets", content=tail).status_code == 202
        rows = client.get(f"{url}/capture/{session}/packets?limit=2").json()
        assert rows["more"] and len(rows["rows"]) == 2 and rows["next"] == 1
        assert "encoder_state" not in rows["session"]
        worker = Worker(database)
        observe = ReadoutHost.observe

        def pause(host, engine, **kwargs):
            observe(host, engine, **kwargs)
            if engine.time_us >= 1100000:
                worker.stopping = True

        with monkeypatch.context() as patch:
            patch.setattr(ReadoutHost, "observe", pause)
            assert worker.once()
        paused = client.get(url).json()
        assert paused["status"] == "paused", paused.get("error")
        detail = client.get(f"{url}/capture/{session}/packets").json()
        assert detail["session"]["status"] == "interrupted" and detail["session"]["origin_sim_us"] == "1000000"
        cp, image = database.load_checkpoint(project, run)
        assert cp["context"]["capture_streams"][session]["closed"]
        expected = NativeEngine(state=image)
        expected.advance_to(2000000)
        client.post(f"{url}/commands", json={"kind": "resume"})
        assert Worker(database).once()
        finished = client.get(url).json()
        assert finished["status"] == "completed", finished.get("error")
        assert finished["state_hash"] == expected.capture_state().digest
        first_frames = client.get(f"{url}/inputs/{first.json()['envelope_id']}").json()["frames"]
        camera_frames = client.get(f"{url}/inputs/{second.json()['envelope_id']}").json()["frames"]
        assert [int(f["delivered_time_us"]) for f in first_frames] == [1050000, 1100000, 1150000, 1200000]
        assert camera_frames[0]["delivered_time_us"] == "1150000"
        assert all(r["status"] == "completed" for r in client.get(f"{url}/capture/{session}/packets").json()["rows"])
        original_packet = client.get(f"{url}/media/{first.json()['envelope_id']}/original")
        assert original_packet.status_code == 200 and original_packet.content == raw
        other = client.post("/api/v2/projects", json={"name": "Other captures"}).json()["id"]
        assert client.get(f"/api/v2/projects/{other}/runs/{run}/capture/{session}/packets").status_code == 404
