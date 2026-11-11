"""Content-addressed media retention and SQLite transport audit."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO


def _utc() -> str: return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True, frozen=True)
class MediaAsset:
    asset_id: str
    sha256: str
    path: str
    original_name: str
    content_type: str
    byte_size: int
    created_at_utc: str


class MediaSizeLimitError(ValueError):
    """Raised before an oversized carrier is committed to durable storage."""


class MediaAuditStore:
    def __init__(self, root: Path | str, database: Path | str) -> None:
        self.root = Path(root); self.database = Path(database)
        self.root.mkdir(parents=True, exist_ok=True); self.database.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS media_assets (
                    asset_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, path TEXT NOT NULL,
                    original_name TEXT NOT NULL, content_type TEXT NOT NULL, byte_size INTEGER NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS media_sessions (
                    session_id TEXT PRIMARY KEY, consciousness_id TEXT NOT NULL, adapter_id TEXT NOT NULL,
                    mode TEXT NOT NULL, asset_id TEXT, state TEXT NOT NULL, created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
                    frames_encoded INTEGER NOT NULL DEFAULT 0, error TEXT, config_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_media_sessions_mind ON media_sessions(consciousness_id, created_at_utc);
                CREATE TABLE IF NOT EXISTS media_deliveries (
                    delivery_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    consciousness_id TEXT NOT NULL, adapter_id TEXT NOT NULL, envelope_id TEXT,
                    frame_start INTEGER NOT NULL, frame_count INTEGER NOT NULL, captured_at_ms REAL,
                    created_at_utc TEXT NOT NULL, audit_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_media_delivery_mind ON media_deliveries(consciousness_id, delivery_id);
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _suffix(filename: str, content_type: str) -> str:
        typed = {
            "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3",
            "audio/ogg": ".ogg", "video/mp4": ".mp4", "video/webm": ".webm",
            "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        }.get(content_type.casefold())
        raw = Path(filename).suffix.casefold()
        return typed or (raw if re.fullmatch(r"\.[a-z0-9]{1,8}", raw) else ".bin")

    def save_stream(
        self,
        stream: BinaryIO,
        *,
        filename: str,
        content_type: str,
        byte_limit: int,
    ) -> MediaAsset:
        """Hash and retain one carrier without loading it all into memory."""
        byte_limit = max(1, int(byte_limit)); created = _utc()
        incoming = self.root / ".incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        temporary = incoming / f"{uuid.uuid4().hex}.tmp"
        digestor = hashlib.sha256(); byte_size = 0
        try:
            stream.seek(0)
            with temporary.open("xb") as output:
                while True:
                    chunk = stream.read(min(1024 * 1024, byte_limit + 1 - byte_size))
                    if not chunk:
                        break
                    byte_size += len(chunk)
                    if byte_size > byte_limit:
                        raise MediaSizeLimitError(
                            f"media upload exceeds the configured {byte_limit // (1024 * 1024)} MB limit"
                        )
                    digestor.update(chunk); output.write(chunk)
                output.flush(); os.fsync(output.fileno())
            if byte_size == 0:
                raise ValueError("media upload is empty")
            digest = digestor.hexdigest(); asset_id = digest
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        with self._lock, self._connect() as connection:
            existing = connection.execute("SELECT * FROM media_assets WHERE sha256=?", (digest,)).fetchone()
            if existing is not None and Path(str(existing["path"])).is_file():
                temporary.unlink(missing_ok=True)
                return MediaAsset(**dict(existing))
            suffix = self._suffix(filename, content_type)
            target_dir = self.root / digest[:2]; target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{digest}{suffix}"
            if target.exists(): temporary.unlink(missing_ok=True)
            else: os.replace(temporary, target)
            connection.execute(
                """INSERT INTO media_assets(asset_id,sha256,path,original_name,content_type,byte_size,created_at_utc)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(asset_id) DO UPDATE SET
                     path=excluded.path, original_name=excluded.original_name,
                     content_type=excluded.content_type, byte_size=excluded.byte_size""",
                (asset_id, digest, str(target), filename, content_type, byte_size, created),
            )
            row = connection.execute("SELECT * FROM media_assets WHERE asset_id=?", (asset_id,)).fetchone()
        return MediaAsset(**dict(row))

    def save_asset(self, payload: bytes, *, filename: str, content_type: str) -> MediaAsset:
        """Compatibility helper for tests and small programmatic carriers."""
        from io import BytesIO
        return self.save_stream(
            BytesIO(payload), filename=filename, content_type=content_type,
            byte_limit=max(1, len(payload)),
        )

    def status(self) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            assets = int(connection.execute("SELECT COUNT(*) FROM media_assets").fetchone()[0])
            sessions = int(connection.execute("SELECT COUNT(*) FROM media_sessions").fetchone()[0])
            deliveries = int(connection.execute("SELECT COUNT(*) FROM media_deliveries").fetchone()[0])
            active = int(connection.execute(
                "SELECT COUNT(*) FROM media_sessions WHERE state IN ('decoding','encoding','running')"
            ).fetchone()[0])
        return {
            "assets": assets,
            "sessions": sessions,
            "deliveries": deliveries,
            "active_sessions": active,
            "retention": "content-addressed uploads; ephemeral live raw carriers",
        }

    def create_session(self, *, consciousness_id: str, adapter_id: str, mode: str, asset_id: str | None, config: dict[str, Any]) -> dict[str, Any]:
        session_id = str(uuid.uuid4()); now = _utc()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO media_sessions(session_id,consciousness_id,adapter_id,mode,asset_id,state,created_at_utc,updated_at_utc,progress,frames_encoded,error,config_json) VALUES (?,?,?,?,?,'queued',?,?,0,0,NULL,?)",
                (session_id, consciousness_id, adapter_id, mode, asset_id, now, now, json.dumps(config, ensure_ascii=False)),
            )
        return self.session(session_id) or {}

    def update_session(self, session_id: str, *, state: str | None = None, progress: float | None = None, frames_encoded: int | None = None, error: str | None = None) -> dict[str, Any]:
        fields = ["updated_at_utc=?"]; values: list[Any] = [_utc()]
        if state is not None: fields.append("state=?"); values.append(state)
        if progress is not None: fields.append("progress=?"); values.append(max(0.0, min(1.0, float(progress))))
        if frames_encoded is not None: fields.append("frames_encoded=?"); values.append(max(0, int(frames_encoded)))
        if error is not None: fields.append("error=?"); values.append(str(error)[:4000])
        values.append(session_id)
        with self._lock, self._connect() as connection:
            connection.execute(f"UPDATE media_sessions SET {', '.join(fields)} WHERE session_id=?", values)
        return self.session(session_id) or {}

    def record_delivery(self, *, session_id: str, consciousness_id: str, adapter_id: str, envelope_id: str | None, frame_start: int, frame_count: int, captured_at_ms: float | None, audit: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO media_deliveries(session_id,consciousness_id,adapter_id,envelope_id,frame_start,frame_count,captured_at_ms,created_at_utc,audit_json) VALUES (?,?,?,?,?,?,?,?,?)",
                (session_id, consciousness_id, adapter_id, envelope_id, int(frame_start), int(frame_count), captured_at_ms, _utc(), json.dumps(audit, ensure_ascii=False)),
            )

    def session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM media_sessions WHERE session_id=?", (session_id,)).fetchone()
        if row is None: return None
        result = dict(row); result["config"] = json.loads(result.pop("config_json")); return result

    def list_sessions(self, *, consciousness_id: str | None = None, adapter_id: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        where: list[str] = []; values: list[Any] = []
        if consciousness_id: where.append("consciousness_id=?"); values.append(consciousness_id)
        if adapter_id: where.append("adapter_id=?"); values.append(adapter_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        with self._lock, self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM media_sessions" + clause, values).fetchone()[0])
            rows = connection.execute("SELECT * FROM media_sessions" + clause + " ORDER BY created_at_utc DESC LIMIT ? OFFSET ?", (*values, max(1, min(1000, int(limit))), max(0, int(offset)))).fetchall()
        items = []
        for row in rows:
            item = dict(row); item["config"] = json.loads(item.pop("config_json")); items.append(item)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def list_deliveries(self, *, consciousness_id: str | None = None, session_id: str | None = None, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        where: list[str] = []; values: list[Any] = []
        if consciousness_id: where.append("consciousness_id=?"); values.append(consciousness_id)
        if session_id: where.append("session_id=?"); values.append(session_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        with self._lock, self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM media_deliveries" + clause, values).fetchone()[0])
            rows = connection.execute("SELECT * FROM media_deliveries" + clause + " ORDER BY delivery_id DESC LIMIT ? OFFSET ?", (*values, max(1, min(5000, int(limit))), max(0, int(offset)))).fetchall()
        items = []
        for row in rows:
            item = dict(row); item["audit"] = json.loads(item.pop("audit_json")); items.append(item)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def iter_deliveries(self, *, consciousness_id: str | None = None, session_id: str | None = None, page_size: int = 1000):
        """Yield delivery audit rows oldest-first without materializing history.

        Pagination uses the monotonically increasing primary key rather than
        OFFSET, so exporting a large experiment does not progressively rescan
        the SQLite table or keep a read transaction open while a client is
        downloading it.
        """
        cursor = 0; page_size = max(1, min(5000, int(page_size)))
        while True:
            where = ["delivery_id>?"]; values: list[Any] = [cursor]
            if consciousness_id: where.append("consciousness_id=?"); values.append(consciousness_id)
            if session_id: where.append("session_id=?"); values.append(session_id)
            query = "SELECT * FROM media_deliveries WHERE " + " AND ".join(where) + " ORDER BY delivery_id ASC LIMIT ?"
            with self._lock, self._connect() as connection:
                rows = connection.execute(query, (*values, page_size)).fetchall()
            if not rows: return
            for row in rows:
                item = dict(row); item["audit"] = json.loads(item.pop("audit_json")); yield item
            cursor = int(rows[-1]["delivery_id"])
