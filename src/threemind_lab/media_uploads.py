"""Resumable database carriers, cooperative decoding and atomic input admission."""

import hashlib
import io
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from psycopg.types.json import Jsonb

from threemind_runtime.media import MEDIA_VERSION

from .database import Conflict, Forbidden, NotFound
from .inputs import digest, submit
from .media_codec import decode_stream
from .media_store import CHUNK
from .protocols import RunSpec

ACTIVE = ("uploading", "failed", "processing", "cancel_requested")


class Cancelled(ValueError):
    pass


def lock_key(upload):
    return (
        int.from_bytes(hashlib.blake2b(b"tm.media-upload/1\0" + UUID(str(upload)).bytes, digest_size=8).digest(), "big")
        >> 1
    )


def public(row):
    return {
        k: str(v) if k in ("byte_length", "received_bytes", "progress_bytes", "progress_frames") else v
        for k, v in row.items()
        if k != "request_hash"
    } | {"chunk_bytes": CHUNK}


def find(db, run, upload, *, lock=False):
    row = db.execute(
        "SELECT * FROM media_uploads WHERE run_id=%s AND id=%s" + (" FOR UPDATE" if lock else ""), (run, upload)
    ).fetchone()
    if row is None:
        raise NotFound("上传会话不存在。")
    return row


def writable_actor(db, project, actor):
    from . import permissions
    permissions.connection_access(db, actor, project, action="runs.stimulate", write=True)


def eligible(row, metadata, byte_length):
    spec = RunSpec(**row["spec"])
    if spec.study_id or row["status"] not in ("running", "queued", "paused", "blocked") or row["life"] == "dead":
        raise Conflict("该实例不能添加人工媒体，请分叉为独立运行后接收。")
    cfg = spec.auditory_sensor if metadata["kind"] == "audio" else spec.visual_sensor
    if not spec.source_policies.resolve(f"upload-{metadata['kind']}")["enabled"]:
        raise Conflict("该媒体来源已关闭，请暂停后在来源策略中开启。")
    if not cfg.enabled or byte_length > cfg.upload_limit_mb * CHUNK:
        raise Conflict("感官未启用或原件超出当前接收上限，请检查意识参数。")
    return spec


def expire(db, project):
    rows = db.execute(
        """SELECT id FROM media_uploads WHERE project_id=%s AND expires_at<=now()
                         AND status IN ('uploading','failed','processing','cancel_requested')
                         ORDER BY expires_at LIMIT 100 FOR UPDATE SKIP LOCKED""",
        (project,),
    ).fetchall()
    for row in rows:
        if db.execute("SELECT pg_try_advisory_xact_lock(%s) AS locked", (lock_key(row["id"]),)).fetchone()["locked"]:
            db.execute("DELETE FROM media_upload_chunks WHERE upload_id=%s", (row["id"],))
            db.execute(
                "UPDATE media_uploads SET status='expired',stage='expired',error='暂存有效期已过',updated_at=now() WHERE id=%s",
                (row["id"],),
            )


def begin(database, settings, project, run, actor, upload, metadata, byte_length):
    if "\0" in metadata["filename"]:
        raise ValueError("文件名不能包含空字符。")
    fingerprint = digest([metadata, byte_length])
    storage_policy = database.blobs.freeze("media-original")
    with database.tx(project) as db:
        # Serialize reservation accounting per project, not per decoded frame.
        db.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project,)).fetchone()
        writable_actor(db, project, actor)
        old = db.execute("SELECT * FROM media_uploads WHERE id=%s", (upload,)).fetchone()
        if old:
            if str(old["run_id"]) != str(run) or old["request_hash"] != fingerprint:
                raise Conflict("该上传标识已用于其他文件或参数。")
            return public(old)
        row = db.execute("SELECT * FROM runs WHERE id=%s", (run,)).fetchone()
        if row is None:
            raise NotFound()
        eligible(row, metadata, byte_length)
        expire(db, project)
        budget = db.execute("""SELECT count(*) AS count,COALESCE(sum(byte_length),0) AS bytes FROM media_uploads
                              WHERE status IN ('uploading','failed','processing','cancel_requested')""").fetchone()
        if (
            budget["count"] >= settings.max_media_uploads
            or int(budget["bytes"]) + byte_length > settings.max_staged_media_bytes
        ):
            raise Conflict("项目媒体暂存配额已满，请完成或取消现有上传。")
        result = db.execute(
            """INSERT INTO media_uploads(id,project_id,run_id,actor_id,metadata,request_hash,byte_length,storage_policy)
                               VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING RETURNING *""",
            (upload, project, run, actor["id"], Jsonb(metadata), fingerprint, byte_length, Jsonb(storage_policy)),
        ).fetchone()
        if result is None:
            raise Conflict("该上传标识不可用，请重新创建。")
        return public(result)


def status(database, project, run, upload):
    with database.tx(project) as db:
        return public(find(db, run, upload))


def put(database, project, run, upload, actor, index, raw, sha):
    if not raw or len(raw) > CHUNK or hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("分块长度或 SHA-256 校验失败。")
    with database.tx(project) as db:
        writable_actor(db, project, actor)
        row = find(db, run, upload, lock=True)
        if row["expires_at"] <= datetime.now(UTC) or row["status"] not in ("uploading", "failed"):
            raise Conflict("上传当前不可写；请查看状态、等待解码结束或重新创建。")
        if index < row["next_chunk"]:
            old = db.execute(
                "SELECT sha256,octet_length(body) AS bytes FROM media_upload_chunks WHERE upload_id=%s AND chunk_index=%s",
                (upload, index),
            ).fetchone()
            if old and old["sha256"] == sha and old["bytes"] == len(raw):
                return public(row)
            raise Conflict("同一块已存在不同内容；不能拼接成另一份原件。")
        if index != row["next_chunk"] or len(raw) != min(CHUNK, row["byte_length"] - row["received_bytes"]):
            raise Conflict("分块序号不连续或长度不符合声明；当前块未写入。")
        db.execute("INSERT INTO media_upload_chunks VALUES(%s,%s,%s,%s,%s,%s)", (project, run, upload, index, sha, raw))
        return public(
            db.execute(
                """UPDATE media_uploads SET received_bytes=received_bytes+%s,next_chunk=next_chunk+1,
                                  status='uploading',stage='uploading',error=NULL,updated_at=now() WHERE id=%s RETURNING *""",
                (len(raw), upload),
            ).fetchone()
        )


def cancel(database, project, run, upload, actor):
    with database.tx(project) as db:
        writable_actor(db, project, actor)
        row = find(db, run, upload, lock=True)
        if row["status"] == "accepted":
            raise Conflict("媒体已进入输入账本；不能通过取消上传删除研究证据。")
        active = not db.execute("SELECT pg_try_advisory_xact_lock(%s) AS locked", (lock_key(upload),)).fetchone()[
            "locked"
        ]
        if not active:
            db.execute("DELETE FROM media_upload_chunks WHERE upload_id=%s", (upload,))
        return public(
            db.execute(
                "UPDATE media_uploads SET status=%s,stage=%s,updated_at=now() WHERE id=%s RETURNING *",
                ("cancel_requested" if active else "cancelled", "cancelling" if active else "cancelled", upload),
            ).fetchone()
        )


@contextmanager
def decoding_lock(database, upload):
    # Session lock survives short commits; a lost process releases it automatically.
    with database.pool.connection() as db:
        locked = db.execute("SELECT pg_try_advisory_lock(%s) AS locked", (lock_key(upload),)).fetchone()["locked"]
        db.commit()
        if not locked:
            raise Conflict("此上传正在解码，可查看进度，无需重复提交。")
        try:
            yield
        finally:
            db.execute("SELECT pg_advisory_unlock(%s)", (lock_key(upload),))
            db.commit()


class Progress:
    def __init__(self, database, project, run, upload):
        self.database, self.project, self.run, self.upload = database, project, run, upload
        self.at, self.stage, self.bytes, self.frames = 0, "hashing", 0, 0

    def __call__(self, stage=None, position=0, frames=0, *, force=False):
        if stage:
            self.stage, self.frames = stage, frames
            if stage == "hashing":
                self.bytes = position
        if not force and time.monotonic() - self.at < 0.25:
            return
        with self.database.tx(self.project) as db:
            row = find(db, self.run, self.upload, lock=True)
            if row["status"] == "cancel_requested":
                raise Cancelled("用户取消媒体处理。")
            if row["expires_at"] <= datetime.now(UTC):
                raise Cancelled("媒体暂存已过期，请重新创建上传。")
            db.execute(
                "UPDATE media_uploads SET stage=%s,progress_bytes=%s,progress_frames=%s,updated_at=now() WHERE id=%s",
                (self.stage, self.bytes, self.frames, self.upload),
            )
        self.at = time.monotonic()


class DatabaseCarrier(io.RawIOBase):
    """Seekable one-chunk cache; never materializes the complete original."""

    max_read = 8 * CHUNK

    def __init__(self, database, project, upload, byte_length, progress=None):
        self.database, self.project, self.upload, self.length = database, project, upload, byte_length
        self.position, self.index, self.cache = 0, -1, b""
        self.progress = progress
        self.largest_read = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        if whence not in (io.SEEK_SET, io.SEEK_CUR, io.SEEK_END):
            raise ValueError("invalid carrier seek mode")
        position = offset + (0 if whence == io.SEEK_SET else self.position if whence == io.SEEK_CUR else self.length)
        if position < 0:
            raise ValueError("negative carrier position")
        self.position = position
        return position

    def read(self, size=-1):
        if self.closed:
            raise ValueError("carrier reader is closed")
        size = max(0, min(self.length - self.position, size if size >= 0 else self.length))
        if size > self.max_read:
            raise ValueError("解码器请求超过 8 MiB 的单次读取，请使用支持分段解码的媒体格式。")
        self.largest_read = max(self.largest_read, size)
        result = bytearray()
        while len(result) < size:
            index, offset = divmod(self.position, CHUNK)
            if index != self.index:
                if self.progress:
                    self.progress()
                with self.database.tx(self.project) as db:
                    row = db.execute(
                        "SELECT body,sha256 FROM media_upload_chunks WHERE upload_id=%s AND chunk_index=%s",
                        (self.upload, index),
                    ).fetchone()
                if row is None:
                    raise ValueError("原件分块缺失。")
                self.cache = bytes(row["body"])
                if (
                    len(self.cache) != min(CHUNK, self.length - index * CHUNK)
                    or hashlib.sha256(self.cache).hexdigest() != row["sha256"]
                ):
                    raise ValueError("数据库原件分块校验失败。")
                self.index = index
            n = min(size - len(result), len(self.cache) - offset)
            result.extend(self.cache[offset : offset + n])
            self.position += n
        return bytes(result)

    def readinto(self, buffer):
        value = self.read(len(buffer))
        buffer[: len(value)] = value
        return len(value)


def finalize(database, project, run, upload, actor):
    with decoding_lock(database, upload):
        with database.tx(project) as db:
            writable_actor(db, project, actor)
            row = find(db, run, upload, lock=True)
            if row["status"] == "accepted":
                return row["receipt"]
            if row["status"] not in ("uploading", "failed", "processing") or row["expires_at"] <= datetime.now(UTC):
                raise Conflict("此暂存已取消或过期，请重新上传。")
            if row["received_bytes"] != row["byte_length"]:
                raise Conflict("原件尚未传输完整。")
            spec = eligible(database.get_run(project, run), row["metadata"], row["byte_length"])
            db.execute(
                "UPDATE media_uploads SET status='processing',stage='hashing',progress_bytes=0,progress_frames=0,error=NULL,updated_at=now() WHERE id=%s",
                (upload,),
            )
        progress = Progress(database, project, run, upload)
        try:
            with DatabaseCarrier(database, project, upload, row["byte_length"], progress) as carrier:
                checksum = hashlib.sha256()
                while part := carrier.read(CHUNK):
                    checksum.update(part)
                    progress("hashing", carrier.tell())
                sha = checksum.hexdigest()
                carrier.seek(0)
                metadata = row["metadata"]
                frames, evidence = decode_stream(
                    carrier, row["byte_length"], metadata["kind"], spec, metadata["intensity"], progress=progress
                )
                evidence["upload"] = {
                    "id": str(upload),
                    "actor_id": str(row["actor_id"]),
                    "chunk_bytes": CHUNK,
                    "largest_read_bytes": carrier.largest_read,
                }
                carrier.seek(0)
                blob = database.blobs.prepare(
                    project, "media-original", iter(lambda: carrier.read(CHUNK), b""), frozen=row["storage_policy"]
                )
            payload = {
                "kind": metadata["kind"],
                "asset_sha256": sha,
                "byte_length": row["byte_length"],
                "filename": metadata["filename"],
                "intensity": metadata["intensity"],
            }
            prepared = {
                "frames": frames,
                "metadata": evidence,
                "upload_id": upload,
                "seed": spec.seed,
                "version": MEDIA_VERSION,
                "config": asdict(spec.auditory_sensor if metadata["kind"] == "audio" else spec.visual_sensor),
                "blob": blob,
            }
            progress("admitting", 0, len(frames), force=True)
            with database.tx(project) as db:
                current = db.execute("SELECT * FROM runs WHERE id=%s FOR UPDATE", (run,)).fetchone()
                writable_actor(db, project, actor)
                eligible(current, metadata, row["byte_length"])
                current_upload = find(db, run, upload, lock=True)
                if current_upload["status"] == "cancel_requested":
                    raise Cancelled("用户取消媒体处理。")
                receipt = submit(
                    database,
                    project,
                    run,
                    actor,
                    adapter_id="auditory-sensor" if metadata["kind"] == "audio" else "visual-sensor",
                    payload=payload,
                    request_id=upload,
                    delay_us=metadata["delay_us"],
                    prepared=prepared,
                    transaction=db,
                )
                db.execute("DELETE FROM media_upload_chunks WHERE upload_id=%s", (upload,))
                db.execute(
                    "UPDATE media_uploads SET status='accepted',stage='accepted',sha256=%s,receipt=%s,updated_at=now() WHERE id=%s",
                    (
                        sha,
                        Jsonb(
                            {
                                k: v.isoformat() if isinstance(v, datetime) else str(v) if isinstance(v, UUID) else v
                                for k, v in receipt.items()
                            }
                        ),
                        upload,
                    ),
                )
                return receipt
        except Exception as error:
            with database.tx(project) as db:
                state = find(db, run, upload, lock=True)
                cancelled = isinstance(error, Cancelled) or state["status"] == "cancel_requested"
                if cancelled:
                    db.execute("DELETE FROM media_upload_chunks WHERE upload_id=%s", (upload,))
                reason = (
                    str(error)[:500]
                    if isinstance(error, (ValueError, Conflict, Forbidden))
                    else f"媒体处理失败：{type(error).__name__}。"
                )
                db.execute(
                    "UPDATE media_uploads SET status=%s,stage=%s,error=%s,updated_at=now() WHERE id=%s",
                    ("cancelled" if cancelled else "failed", "cancelled" if cancelled else "failed", reason, upload),
                )
            raise
