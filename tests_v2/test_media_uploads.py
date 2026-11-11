import hashlib
import io
import os
import struct
import subprocess
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb
from test_api import client_for
from test_media_v2 import png, protocol, wav

from threemind_lab import auth, media_store, media_uploads
from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.media_codec import decode, decode_stream
from threemind_lab.media_store import CHUNK
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime import ArtifactCodec, create_engine
from threemind_runtime.profile import profile_from_spec


class PaddedWav:
    """Generate an original on demand: RIFF JUNK plus a real short audio signal."""

    def __init__(self, padding):
        raw = wav([0.2] * 321)
        self.length = len(raw) + padding + 8
        self.segments = [
            (0, b"RIFF" + struct.pack("<I", self.length - 8) + b"WAVEJUNK" + struct.pack("<I", padding)),
            (20 + padding, raw[12:]),
        ]

    def part(self, offset, count=CHUNK):
        out = bytearray(min(count, self.length - offset))
        for start, data in self.segments:
            lo, hi = max(offset, start), min(offset + len(out), start + len(data))
            if hi > lo:
                out[lo - offset : hi - offset] = data[lo - start : hi - start]
        return bytes(out)


def fixture(client):
    project = client.post("/api/v2/projects", json={"name": "Chunked media"}).json()["id"]
    spec = protocol()
    spec["auditory_sensor"]["upload_limit_mb"] = 512
    run = client.post(f"/api/v2/projects/{project}/runs", json={"name": "Resumable carrier", "spec": spec}).json()["id"]
    return project, run, f"/api/v2/projects/{project}/runs/{run}"


def start(client, base, size, *, kind="audio", identifier=None):
    body = {"request_id": identifier or str(uuid4()), "filename": "instrument.wav", "kind": kind, "byte_length": size}
    response = client.post(base + "/media-uploads", json=body)
    assert response.status_code == 201, response.text
    return body, response.json(), base + "/media-uploads/" + body["request_id"]


def put(client, url, index, data):
    return client.put(f"{url}/chunks/{index}", params={"sha256": hashlib.sha256(data).hexdigest()}, content=data)


def test_seekable_decoder_retains_exact_signal_and_metadata():
    spec = RunSpec(**protocol())
    for kind, raw in (("audio", wav([0.4] * 321)), ("image", png())):
        assert decode_stream(io.BytesIO(raw), len(raw), kind, spec, 0.75) == decode(raw, kind, spec, 0.75)
    huge = PaddedWav(CHUNK * 2)
    raw = b"".join(huge.part(at) for at in range(0, huge.length, CHUNK))
    assert decode(raw, "audio", spec, 1) == decode(wav([0.2] * 321), "audio", spec, 1)


def test_large_upload_configuration_survives_independent_rust_model_and_sqlite(tmp_path):
    spec = protocol()
    spec["auditory_sensor"]["upload_limit_mb"] = 8192
    spec["visual_sensor"]["upload_limit_mb"] = 8192
    profile = profile_from_spec(spec)
    source, target = tmp_path / "large-media.tmind", tmp_path / "continued.tmind"
    source.write_bytes(ArtifactCodec.encode(create_engine().capture_state(), profile=profile))
    binary = Path("target/release/threemind-runtime" + (".exe" if os.name == "nt" else "")).resolve()
    assert binary.is_file(), "Build the standalone Runtime before running its integration tests"
    result = subprocess.run(
        [
            str(binary),
            "--model",
            str(source),
            "--clock",
            "unbounded",
            "--until-us",
            "1000",
            "--store",
            str(tmp_path / "runtime.sqlite"),
            "--export",
            str(target),
        ],
        capture_output=True,
        check=False,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    _, restored = ArtifactCodec.decode(target.read_bytes(), with_profile=True)
    assert restored == profile


def test_chunk_order_retries_receipts_originals_delivery_and_project_boundaries(database):
    with client_for(database) as client:
        project, _run, base = fixture(client)
        carrier = PaddedWav(CHUNK * 2)
        body, session, url = start(client, base, carrier.length)
        assert client.post(base + "/media-uploads", json=body).json() == session
        assert client.post(base + "/media-uploads", json=body | {"intensity": 1.0}).json() == session
        assert client.post(base + "/media-uploads", json=body | {"intensity": 0.3}).status_code == 409
        assert client.post(url + "/finalize").status_code == 409
        part = carrier.part(0)
        assert put(client, url, 1, part).status_code == 409
        assert client.put(url + "/chunks/0", params={"sha256": "0" * 64}, content=part).status_code == 422
        assert put(client, url, 0, part[:-1]).status_code == 409
        assert put(client, url, 0, part + b"x").status_code == 413
        assert put(client, url, 0, part).status_code == 200
        assert put(client, url, 0, part).json()["next_chunk"] == 1
        assert put(client, url, 0, b"x" * CHUNK).status_code == 409
        hashes = client.get(url + "/chunks?limit=1").json()
        assert hashes["rows"][0]["sha256"] == hashlib.sha256(part).hexdigest()
        for index in range(1, (carrier.length + CHUNK - 1) // CHUNK):
            assert put(client, url, index, carrier.part(index * CHUNK)).status_code == 200
        assert client.get(url + "/chunks?limit=1").json()["next"] == 0
        assert client.get(url + "/chunks?after=0&limit=1").json()["rows"][0]["chunk_index"] == 1
        with media_uploads.DatabaseCarrier(database, project, body["request_id"], carrier.length) as source:
            source.seek(CHUNK - 7)
            assert source.read(20) == carrier.part(CHUNK - 7, 20)
            source.seek(-10, io.SEEK_END)
            assert source.read() == carrier.part(carrier.length - 10)
            source.seek(carrier.length + 100)
            assert source.read(100) == b""
        with media_uploads.decoding_lock(database, body["request_id"]):
            assert client.post(url + "/finalize").status_code == 409
        accepted = client.post(url + "/finalize")
        assert accepted.status_code == 202, accepted.text
        assert client.post(url + "/finalize").json() == accepted.json()
        assert client.get(url).json()["status"] == "accepted"
        assert client.get(url + "/chunks").json()["rows"] == []
        assert client.delete(url).status_code == 409
        raw = b"".join(carrier.part(at) for at in range(0, carrier.length, CHUNK))
        assert client.get(base + f"/media/{body['request_id']}/original").content == raw
        expected, _ = decode(raw, "audio", RunSpec(**protocol()), 1)
        with database.tx(project) as db:
            actual = db.execute("SELECT stimulus FROM media_prepared_frames ORDER BY frame_index").fetchall()
            assert [r["stimulus"] for r in actual] == [f["stimulus"].to_dict() for f in expected]
        assert Worker(database).once()
        assert client.get(base + f"/inputs/{body['request_id']}").json()["envelope"]["status"] == "completed"
        foreign = client.post("/api/v2/projects", json={"name": "Unrelated media"}).json()["id"]
        assert client.get(url.replace(project, foreign)).status_code == 404
        with database.tx(foreign) as db:
            assert db.execute("SELECT count(*) AS n FROM media_upload_chunks").fetchone()["n"] == 0
        viewer = auth.create_user(database, "media-viewer", "media viewer test password")
        with database.tx() as db:
            db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, viewer["id"]))
    with client_for(database, "server") as client:
        assert client.get(url).status_code == 401
        client.post("/api/v2/login", json={"username": "media-viewer", "password": "media viewer test password"})
        assert client.get(url).status_code == 200
        assert client.post(url + "/finalize").status_code == 403
        assert client.delete(url).status_code == 403


def test_large_carrier_exceeds_old_limit_with_bounded_database_reads(database):
    with client_for(database) as client:
        project, run, base = fixture(client)
        carrier = PaddedWav(257 * CHUNK)
        body, _, url = start(client, base, carrier.length)
        checksum = hashlib.sha256()
        for index, at in enumerate(range(0, carrier.length, CHUNK)):
            part = carrier.part(at)
            checksum.update(part)
            assert put(client, url, index, part).status_code == 200
        with (
            media_uploads.DatabaseCarrier(database, project, body["request_id"], carrier.length) as source,
            pytest.raises(ValueError, match="8 MiB"),
        ):
            source.read()
        result = client.post(url + "/finalize")
        assert result.status_code == 202, result.text
        assert client.get(url).json()["sha256"] == checksum.hexdigest()
        metadata = result.json()["configuration"]["transduction"]
        assert metadata["source_samples"] == 321 and metadata["upload"]["largest_read_bytes"] <= CHUNK
        downloaded = hashlib.sha256()
        for part in media_store.chunks(
            database, project, media_store.asset_for(database, project, run, body["request_id"])
        ):
            assert len(part) <= CHUNK
            downloaded.update(part)
        assert downloaded.hexdigest() == checksum.hexdigest()
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM media_upload_chunks").fetchone()["n"] == 0


def test_failed_atomic_admission_can_retry_without_reupload_and_cancel_is_cooperative(database, monkeypatch):
    with client_for(database) as client:
        project, run, base = fixture(client)
        raw = wav([0.2] * 321)
        body, _, url = start(client, base, len(raw))
        assert put(client, url, 0, raw).status_code == 200
        persist = media_store.persist

        def fail(*args):
            persist(*args)
            raise ValueError("injected post-binary transaction failure")

        with monkeypatch.context() as patch:
            patch.setattr(media_store, "persist", fail)
            assert client.post(url + "/finalize").status_code == 422
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM input_envelopes").fetchone()["n"] == 0
            assert db.execute("SELECT count(*) AS n FROM media_assets").fetchone()["n"] == 0
            assert db.execute("SELECT count(*) AS n FROM media_upload_chunks").fetchone()["n"] == 1
            # Simulate the durable state left by a lost decoder process; its session lock is gone.
            db.execute("UPDATE media_uploads SET status='processing' WHERE id=%s", (body["request_id"],))
        assert client.post(url + "/finalize").status_code == 202
        other, _, cancel_url = start(client, base, len(raw))
        assert put(client, cancel_url, 0, raw).status_code == 200
        original = media_uploads.decode_stream

        def cancel_while_decoding(*args, **kwargs):
            state = media_uploads.cancel(database, project, run, other["request_id"], {"id": LOCAL_USER})
            assert state["status"] == "cancel_requested"
            kwargs["progress"](force=True)
            return original(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(media_uploads, "decode_stream", cancel_while_decoding)
            assert client.post(cancel_url + "/finalize").status_code == 422
        assert client.get(cancel_url).json()["status"] == "cancelled"
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM input_envelopes").fetchone()["n"] == 1
            assert db.execute("SELECT count(*) AS n FROM media_upload_chunks").fetchone()["n"] == 0


def test_reservations_expiry_and_final_permission_and_configuration_rechecks(database, monkeypatch):
    # This case revokes project membership, so use the ordinary role. The
    # newly explicit superadministrator intentionally retains all-project access.
    with database.tx() as db:
        db.execute("DELETE FROM platform_user_roles WHERE user_id=%s", (LOCAL_USER,))
        db.execute("INSERT INTO platform_user_roles(user_id,role_id) SELECT %s,id FROM platform_roles WHERE key='user'", (LOCAL_USER,))
    with client_for(database) as client:
        project, run, base = fixture(client)
        raw = wav([0.2] * 321)
        body, _, url = start(client, base, len(raw))
        settings = replace(client.app.state.settings, max_media_uploads=1)
        with pytest.raises(Conflict, match="配额"):
            media_uploads.begin(
                database,
                settings,
                project,
                run,
                {"id": LOCAL_USER},
                uuid4(),
                {"kind": "audio", "filename": "new.wav", "intensity": 1, "delay_us": 0},
                len(raw),
            )
        assert put(client, url, 0, raw).status_code == 200
        original = media_uploads.decode_stream

        def revoked(*args, **kwargs):
            result = original(*args, **kwargs)
            with database.tx(project) as db:
                db.execute("UPDATE members SET role='viewer' WHERE project_id=%s AND user_id=%s", (project, LOCAL_USER))
            return result

        with monkeypatch.context() as patch:
            patch.setattr(media_uploads, "decode_stream", revoked)
            assert client.post(url + "/finalize").status_code == 403
        with database.tx(project) as db:
            db.execute("UPDATE members SET role='owner' WHERE project_id=%s AND user_id=%s", (project, LOCAL_USER))

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            spec = database.get_run(project, run)["spec"]
            spec["auditory_sensor"]["gain"] = 0.5
            with database.tx(project) as db:
                db.execute("UPDATE runs SET spec=%s WHERE id=%s", (Jsonb(spec), run))
            return result

        with monkeypatch.context() as patch:
            patch.setattr(media_uploads, "decode_stream", changed)
            assert client.post(url + "/finalize").status_code == 409
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM input_envelopes").fetchone()["n"] == 0
            db.execute(
                "UPDATE media_uploads SET expires_at=now()-interval '1 second' WHERE id=%s", (body["request_id"],)
            )
        assert client.get(base + "/media-uploads").json()["rows"] == []
        assert client.get(url).json()["status"] == "expired"
        assert client.post(url + "/finalize").status_code == 409
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM media_upload_chunks").fetchone()["n"] == 0


def test_database_chunk_corruption_and_closed_sources_never_admit_partial_carriers(database):
    with client_for(database) as client:
        project, _run, base = fixture(client)
        raw = wav([0.2] * 321)
        body, _, url = start(client, base, len(raw))
        assert put(client, url, 0, raw).status_code == 200
        with database.tx(project) as db:
            db.execute(
                "UPDATE media_upload_chunks SET body=%s WHERE upload_id=%s", (b"x" * len(raw), body["request_id"])
            )
        response = client.post(url + "/finalize")
        assert response.status_code == 422 and "分块校验失败" in response.text
        with database.tx(project) as db:
            db.execute("UPDATE media_upload_chunks SET body=%s WHERE upload_id=%s", (raw, body["request_id"]))
        assert client.post(base + "/commands", json={"kind": "close_inputs"}).status_code == 200
        assert client.post(url + "/finalize").status_code == 409
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM input_envelopes").fetchone()["n"] == 0
            assert db.execute("SELECT count(*) AS n FROM media_upload_chunks").fetchone()["n"] == 1
        assert client.delete(url).json()["status"] == "cancelled"
