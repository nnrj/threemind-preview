"""Binary carrier and frozen transduction persistence in the existing project DB."""

import hashlib
import io
import json
import zipfile
from dataclasses import asdict

from psycopg.types.json import Jsonb

from threemind_runtime.media import MEDIA_VERSION

from .database import Conflict, NotFound
from .inputs import digest, public_envelope, submit
from .media_codec import decode
from .protocols import RunSpec

CHUNK = 1024 * 1024


def accept(database, project, run_id, actor, raw, *, kind, filename, request_id, intensity=1.0, delay_us=0):
    if "\0" in filename:
        raise ValueError("文件名不能包含空字符。")
    sha = hashlib.sha256(raw).hexdigest()
    payload = {"kind": kind, "asset_sha256": sha, "byte_length": len(raw), "filename": filename, "intensity": intensity}
    adapter_id = "auditory-sensor" if kind == "audio" else "visual-sensor"
    # Retry identity is independent of decoder versions and subsequent settings.
    with database.tx(project) as db:
        old = db.execute("SELECT * FROM input_envelopes WHERE id=%s", (request_id,)).fetchone()
        if old:
            if str(old["run_id"]) != str(run_id) or old["request_hash"] != digest(
                [adapter_id, payload, delay_us, None]
            ):
                raise Conflict("该请求标识已用于不同载体。")
            return public_envelope(old)
    row = database.get_run(project, run_id)
    spec = RunSpec(**row["spec"])
    if spec.study_id or row["status"] not in ("running", "queued", "paused", "blocked") or row["life"] == "dead":
        raise Conflict("该实例不能添加人工媒体，请分叉为独立运行后接收。")
    frames, metadata = decode(raw, kind, spec, intensity)
    prepared = {
        "frames": frames,
        "metadata": metadata,
        "raw": raw,
        "seed": spec.seed,
        "version": MEDIA_VERSION,
        "config": asdict(spec.auditory_sensor if kind == "audio" else spec.visual_sensor),
        "blob": database.blobs.prepare(
            project, "media-original", (raw[i : i + CHUNK] for i in range(0, len(raw), CHUNK))
        ),
    }
    return submit(
        database,
        project,
        run_id,
        actor,
        adapter_id=adapter_id,
        payload=payload,
        request_id=request_id,
        delay_us=delay_us,
        prepared=prepared,
    )


def persist(db, project, run_id, envelope_id, payload, prepared):
    from .blob_store import BlobStore

    sha, raw = payload["asset_sha256"], prepared.get("raw")
    blob_id = BlobStore.attach(db, prepared.get("blob"))
    inserted = db.execute(
        "INSERT INTO media_assets(project_id,sha256,byte_length,blob_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING sha256",
        (project, sha, payload["byte_length"], blob_id),
    ).fetchone()
    if inserted and blob_id is None:
        if prepared.get("upload_id"):
            db.execute(
                """INSERT INTO media_chunks(project_id,sha256,chunk_index,body)
                   SELECT project_id,%s,chunk_index,body FROM media_upload_chunks
                   WHERE run_id=%s AND upload_id=%s ORDER BY chunk_index""",
                (sha, run_id, prepared["upload_id"]),
            )
        else:
            with db.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO media_chunks(project_id,sha256,chunk_index,body) VALUES(%s,%s,%s,%s)",
                    ((project, sha, i // CHUNK, raw[i : i + CHUNK]) for i in range(0, len(raw), CHUNK)),
                )
    with db.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO media_prepared_frames(project_id,run_id,envelope_id,frame_index,stimulus) VALUES(%s,%s,%s,%s,%s)",
            (
                (project, run_id, envelope_id, i, Jsonb(f["stimulus"].to_dict()))
                for i, f in enumerate(prepared["frames"])
            ),
        )


def asset_for(database, project, run_id, envelope_id):
    with database.tx(project) as db:
        row = db.execute(
            "SELECT payload FROM input_envelopes WHERE run_id=%s AND id=%s AND adapter_id IN ('auditory-sensor','visual-sensor')",
            (run_id, envelope_id),
        ).fetchone()
    if row is None:
        raise NotFound()
    return row["payload"]


def chunks(database, project, payload):
    from .blob_store import object_chunks

    yield from object_chunks(database, project, "media", payload["asset_sha256"])


class ZipSink(io.RawIOBase):
    def __init__(self):
        self.parts, self.position = [], 0

    def writable(self):
        return True

    def write(self, value):
        self.parts.append(value)
        self.position += len(value)
        return len(value)

    def tell(self):
        return self.position

    def drain(self):
        parts, self.parts = self.parts, []
        return parts


def export_originals(database, project, run_id):
    # This is an on-demand evidence export, never an automatic model write.
    with database.tx(project) as db:
        rows = db.execute(
            "SELECT id,payload,payload_hash,configuration_hash FROM input_envelopes WHERE run_id=%s AND adapter_id IN ('auditory-sensor','visual-sensor') ORDER BY ordinal",
            (run_id,),
        ).fetchall()
    sink = ZipSink()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {"schema": "threemind.media-evidence/1", "run_id": str(run_id), "carriers": rows},
                default=str,
                ensure_ascii=False,
                indent=2,
            ),
        )
        yield from sink.drain()
        seen = set()
        for row in rows:
            payload = row["payload"]
            if payload["asset_sha256"] in seen:
                continue
            seen.add(payload["asset_sha256"])
            with archive.open(f"originals/{payload['asset_sha256']}.bin", "w", force_zip64=True) as entry:
                for chunk in chunks(database, project, payload):
                    entry.write(chunk)
                    yield from sink.drain()
            yield from sink.drain()
    yield from sink.drain()
