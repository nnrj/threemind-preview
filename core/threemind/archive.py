"""Indexed, asynchronous catalogue for portable ThreeMind package artifacts.

The Core's associative dynamics deliberately do not depend on a database.
This module belongs to the host/application layer: it indexes immutable
``.tmind`` package files in SQLite so management endpoints never deserialize
every historical graph merely to list a consciousness or its snapshots.
"""

from __future__ import annotations

import hashlib
import json
import queue
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .model import ModelPackage, READABLE_MODEL_PACKAGE_SUFFIXES


def _legacy_kind(path: Path) -> str:
    stem = path.stem.casefold()
    if "portrait" in stem:
        return "portrait"
    if "snapshot" in stem or "-auto" in stem:
        return "snapshot"
    return "package"


class ArchiveRepository:
    """SQLite index of package artifacts; package payloads remain portable files."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=NORMAL")
            self._connection.execute("PRAGMA busy_timeout=5000")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS archive_artifacts (
                    path TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL,
                    consciousness_id TEXT NOT NULL,
                    consciousness_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    automatic INTEGER,
                    reason TEXT,
                    provenance TEXT NOT NULL,
                    tick INTEGER NOT NULL DEFAULT 0,
                    node_count INTEGER NOT NULL DEFAULT 0,
                    edge_count INTEGER NOT NULL DEFAULT 0,
                    life_state TEXT NOT NULL DEFAULT 'active',
                    parent_id TEXT,
                    kernel_id TEXT,
                    manifest_json TEXT NOT NULL DEFAULT '{}',
                    file_size INTEGER NOT NULL DEFAULT 0,
                    file_mtime REAL NOT NULL DEFAULT 0,
                    checksum TEXT,
                    state TEXT NOT NULL DEFAULT 'ready',
                    error TEXT,
                    indexed_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_archive_consciousness_created
                    ON archive_artifacts(consciousness_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_archive_kind_created
                    ON archive_artifacts(kind, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_archive_state
                    ON archive_artifacts(state);
                """
            )
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _path(path: Path | str) -> str:
        return str(Path(path).resolve())

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["artifact_id"]),
            "name": Path(str(row["path"])).stem,
            "label": str(row["label"]),
            "path": str(row["path"]),
            "kind": str(row["kind"]),
            "saved_at": float(row["created_at"]),
            "consciousness_id": str(row["consciousness_id"]),
            "consciousness_name": str(row["consciousness_name"]),
            "automatic": None if row["automatic"] is None else bool(row["automatic"]),
            "reason": str(row["reason"] or ""),
            "provenance": str(row["provenance"]),
            "metrics": {
                "tick": int(row["tick"]),
                "nodes": int(row["node_count"]),
                "edges": int(row["edge_count"]),
                "life_state": str(row["life_state"]),
            },
        }

    def index_metadata(self, path: Path | str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Upsert an artifact from its compact package header.

        This method never opens or deserializes the large consciousness state.
        It is suitable immediately after a package has been written.
        """
        target = Path(path)
        resolved = self._path(target)
        stat = target.stat()
        archive = metadata.get("archive") if isinstance(metadata.get("archive"), dict) else {}
        state = metadata.get("state") if isinstance(metadata.get("state"), dict) else {}
        manifest = metadata.get("manifest") if isinstance(metadata.get("manifest"), dict) else {}
        has_provenance = bool(archive)
        kind = str(archive.get("kind") or _legacy_kind(target))
        if kind not in {"package", "snapshot", "portrait"}:
            kind = "package"
        if has_provenance:
            automatic: bool | None = bool(archive.get("automatic", False))
            reason = str(archive.get("reason") or ("automatic" if automatic else "manual"))
            provenance = "automatic" if automatic else "manual"
        elif "-auto" in target.stem.casefold():
            automatic = True
            reason = "legacy_automatic"
            provenance = "legacy-automatic"
        else:
            automatic = None
            reason = "legacy_unknown" if kind in {"snapshot", "portrait"} else "package_save"
            provenance = "legacy" if kind in {"snapshot", "portrait"} else "manual"
        raw_id = str(archive.get("id") or "")
        artifact_id = raw_id or f"{kind}:{hashlib.sha256(resolved.encode('utf-8')).hexdigest()[:24]}"
        created_at_value = archive.get("created_at", stat.st_mtime)
        try:
            created_at = float(created_at_value)
        except (TypeError, ValueError):
            created_at = stat.st_mtime
        consciousness_id = str(metadata.get("consciousness_id") or "")
        if not consciousness_id:
            raise ValueError("package metadata has no consciousness id")
        consciousness_name = str(metadata.get("consciousness_name") or "Unnamed consciousness")
        label = str(archive.get("label") or target.stem)
        tick = int(state.get("tick", 0))
        node_count = int(state.get("node_count", 0))
        edge_count = int(state.get("edge_count", 0))
        life_state = str(state.get("life_state") or "active")
        parent_id = state.get("parent_id")
        payload = (
            resolved, artifact_id, consciousness_id, consciousness_name, kind, label,
            created_at, None if automatic is None else int(automatic), reason, provenance,
            tick, node_count, edge_count, life_state,
            str(parent_id) if parent_id is not None else None,
            str(manifest.get("kernel_id") or ""), json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            int(stat.st_size), float(stat.st_mtime), time.time(),
        )
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO archive_artifacts(
                    path, artifact_id, consciousness_id, consciousness_name, kind, label,
                    created_at, automatic, reason, provenance, tick, node_count, edge_count,
                    life_state, parent_id, kernel_id, manifest_json, file_size, file_mtime,
                    indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    artifact_id=excluded.artifact_id,
                    consciousness_id=excluded.consciousness_id,
                    consciousness_name=excluded.consciousness_name,
                    kind=excluded.kind,
                    label=excluded.label,
                    created_at=excluded.created_at,
                    automatic=excluded.automatic,
                    reason=excluded.reason,
                    provenance=excluded.provenance,
                    tick=excluded.tick,
                    node_count=excluded.node_count,
                    edge_count=excluded.edge_count,
                    life_state=excluded.life_state,
                    parent_id=excluded.parent_id,
                    kernel_id=excluded.kernel_id,
                    manifest_json=excluded.manifest_json,
                    file_size=excluded.file_size,
                    file_mtime=excluded.file_mtime,
                    state='ready',
                    error=NULL,
                    indexed_at=excluded.indexed_at
                """,
                payload,
            )
            self._connection.commit()
            row = self._connection.execute("SELECT * FROM archive_artifacts WHERE path=?", (resolved,)).fetchone()
        if row is None:
            raise RuntimeError("failed to index archive artifact")
        return self._row_to_item(row)

    def index_file(self, path: Path | str) -> dict[str, Any]:
        target = Path(path)
        return self.index_metadata(target, ModelPackage.read_catalog_metadata(target))

    def is_current(self, path: Path | str) -> bool:
        target = Path(path)
        try:
            stat = target.stat()
        except OSError:
            return False
        with self._lock:
            row = self._connection.execute(
                "SELECT file_size, file_mtime, state FROM archive_artifacts WHERE path=?",
                (self._path(target),),
            ).fetchone()
        return bool(row and row["state"] == "ready" and int(row["file_size"]) == stat.st_size and abs(float(row["file_mtime"]) - stat.st_mtime) < 0.0001)

    def list_archives(self, consciousness_id: str | None = None, *, limit: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM archive_artifacts WHERE state='ready' AND kind IN ('snapshot', 'portrait')"
        values: list[Any] = []
        if consciousness_id is not None:
            query += " AND consciousness_id=?"
            values.append(consciousness_id)
        query += " ORDER BY created_at DESC, path DESC"
        if limit is not None:
            query += " LIMIT ?"
            values.append(max(1, int(limit)))
        with self._lock:
            rows = self._connection.execute(query, values).fetchall()
        return [self._row_to_item(row) for row in rows]

    def get_archive(self, consciousness_id: str, path: str | None = None) -> dict[str, Any] | None:
        if path:
            query = "SELECT * FROM archive_artifacts WHERE state='ready' AND consciousness_id=? AND path=? AND kind IN ('snapshot', 'portrait')"
            values: tuple[Any, ...] = (consciousness_id, self._path(path))
        else:
            query = """
                SELECT * FROM archive_artifacts
                WHERE state='ready' AND consciousness_id=? AND kind IN ('snapshot', 'portrait')
                ORDER BY CASE kind WHEN 'snapshot' THEN 0 ELSE 1 END, created_at DESC, path DESC LIMIT 1
            """
            values = (consciousness_id,)
        with self._lock:
            row = self._connection.execute(query, values).fetchone()
        return self._row_to_item(row) if row else None

    def latest_package_path(self, consciousness_id: str) -> Path | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT path FROM archive_artifacts
                WHERE state='ready' AND consciousness_id=?
                ORDER BY CASE kind WHEN 'package' THEN 0 ELSE 1 END, created_at DESC, path DESC LIMIT 1
                """,
                (consciousness_id,),
            ).fetchone()
        return Path(str(row["path"])) if row else None

    def list_packages(self) -> list[dict[str, Any]]:
        """List indexed package files without opening their graph payloads."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM archive_artifacts WHERE state='ready' ORDER BY created_at DESC, path DESC"
            ).fetchall()
            counts = self._connection.execute(
                """
                SELECT consciousness_id,
                    SUM(CASE WHEN kind='snapshot' THEN 1 ELSE 0 END) AS snapshots,
                    SUM(CASE WHEN kind='portrait' THEN 1 ELSE 0 END) AS portraits
                FROM archive_artifacts WHERE state='ready' GROUP BY consciousness_id
                """
            ).fetchall()
        count_by_id = {str(row["consciousness_id"]): (int(row["snapshots"] or 0), int(row["portraits"] or 0)) for row in counts}
        output: list[dict[str, Any]] = []
        for row in rows:
            try:
                manifest = json.loads(str(row["manifest_json"]))
            except json.JSONDecodeError:
                manifest = {}
            snapshots, portraits = count_by_id.get(str(row["consciousness_id"]), (0, 0))
            output.append({
                "path": str(row["path"]),
                "name": str(row["consciousness_name"]),
                "consciousness_id": str(row["consciousness_id"]),
                "manifest": manifest,
                "kind": str(row["kind"]),
                "snapshots": snapshots,
                "portraits": portraits,
                "size": int(row["file_size"]),
                "saved_at": float(row["created_at"]),
            })
        return output

    def list_consciousnesses(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM archive_artifacts WHERE state='ready' ORDER BY created_at DESC, path DESC"
            ).fetchall()
            counts = self._connection.execute(
                """
                SELECT consciousness_id,
                    SUM(CASE WHEN kind='snapshot' THEN 1 ELSE 0 END) AS snapshots,
                    SUM(CASE WHEN kind='portrait' THEN 1 ELSE 0 END) AS portraits
                FROM archive_artifacts WHERE state='ready' GROUP BY consciousness_id
                """
            ).fetchall()
        count_by_id = {str(row["consciousness_id"]): (int(row["snapshots"] or 0), int(row["portraits"] or 0)) for row in counts}
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            consciousness_id = str(row["consciousness_id"])
            if consciousness_id in seen:
                continue
            seen.add(consciousness_id)
            snapshots, portraits = count_by_id.get(consciousness_id, (0, 0))
            items.append({
                "id": consciousness_id,
                "name": str(row["consciousness_name"]),
                "status": str(row["life_state"] or "stored"),
                "running": False,
                "active": False,
                "kernel": str(row["kernel_id"] or "unified-associative"),
                "parent_id": row["parent_id"],
                "snapshots": snapshots,
                "portraits": portraits,
                "package_path": str(row["path"]),
                "persisted": True,
                "saved_at": float(row["created_at"]),
                "metrics": {
                    "tick": int(row["tick"]),
                    "node_count": int(row["node_count"]),
                    "edge_count": int(row["edge_count"]),
                },
            })
        return items

    def archive_counts(self) -> dict[str, dict[str, int]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT consciousness_id,
                    SUM(CASE WHEN kind='snapshot' THEN 1 ELSE 0 END) AS snapshots,
                    SUM(CASE WHEN kind='portrait' THEN 1 ELSE 0 END) AS portraits
                FROM archive_artifacts WHERE state='ready' GROUP BY consciousness_id
                """
            ).fetchall()
        return {
            str(row["consciousness_id"]): {"snapshot": int(row["snapshots"] or 0), "portrait": int(row["portraits"] or 0)}
            for row in rows
        }

    def remove_path(self, path: Path | str) -> None:
        with self._lock:
            self._connection.execute("DELETE FROM archive_artifacts WHERE path=?", (self._path(path),))
            self._connection.commit()

    def prune_missing(self, directory: Path | str) -> int:
        """Remove stale entries for files deleted outside the HTTP API.

        It intentionally runs only from the background indexer, never on a
        catalogue request.  A stale row is less harmful than turning a simple
        UI listing into a filesystem walk.
        """
        root = Path(directory).resolve()
        with self._lock:
            rows = self._connection.execute("SELECT path FROM archive_artifacts").fetchall()
        stale = [str(row["path"]) for row in rows if Path(str(row["path"])).parent == root and not Path(str(row["path"])).exists()]
        if not stale:
            return 0
        with self._lock:
            self._connection.executemany("DELETE FROM archive_artifacts WHERE path=?", [(path,) for path in stale])
            self._connection.commit()
        return len(stale)

    def status(self) -> dict[str, Any]:
        with self._lock:
            count = int(self._connection.execute("SELECT COUNT(*) FROM archive_artifacts WHERE state='ready'").fetchone()[0])
        return {"backend": "sqlite", "path": str(self.path), "indexed_artifacts": count}


class ArchiveIndexer:
    """Low-priority legacy/file importer that never runs on an API request.

    Legacy packages do not have the compact metadata header.  Reading one can
    involve decompression and JSON parsing, so the worker deliberately yields
    between files.  The index therefore converges progressively instead of
    competing continuously with the live associative runtime.
    """

    def __init__(self, repository: ArchiveRepository, data_dir: Path | str) -> None:
        self.repository = repository
        self.data_dir = Path(data_dir)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._status: dict[str, Any] = {
            "running": False,
            "phase": "idle",
            "total": 0,
            "processed": 0,
            "indexed": 0,
            "skipped": 0,
            "failed": 0,
            "last_error": None,
            "started_at": None,
            "finished_at": None,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def start(self, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return dict(self._status)
            self._stop.clear()
            self._status = {
                "running": True,
                "phase": "scanning",
                "total": 0,
                "processed": 0,
                "indexed": 0,
                "skipped": 0,
                "failed": 0,
                "last_error": None,
                "started_at": time.time(),
                "finished_at": None,
            }
            self._thread = threading.Thread(target=self._run, args=(force,), name="threemind-archive-indexer", daemon=True)
            self._thread.start()
            return dict(self._status)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def _run(self, force: bool) -> None:
        try:
            self.repository.prune_missing(self.data_dir)
            paths = sorted(
                (
                    item
                    for item in self.data_dir.iterdir()
                    if item.is_file() and item.suffix.casefold() in READABLE_MODEL_PACKAGE_SUFFIXES
                ),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            with self._lock:
                self._status["total"] = len(paths)
            for path in paths:
                if self._stop.is_set():
                    break
                try:
                    if not force and self.repository.is_current(path):
                        outcome = "skipped"
                    else:
                        self.repository.index_file(path)
                        outcome = "indexed"
                except (OSError, ValueError, sqlite3.Error) as error:
                    outcome = "failed"
                    with self._lock:
                        self._status["last_error"] = str(error)
                with self._lock:
                    self._status["processed"] += 1
                    self._status[outcome] += 1
                # ``ModelPackage.read_catalog_metadata`` may need a legacy
                # fallback full load.  This tiny wait makes the migration a
                # low-priority maintenance task rather than a second busy
                # loop inside the Core process.
                self._stop.wait(.02)
        finally:
            with self._lock:
                self._status["running"] = False
                self._status["phase"] = "stopped" if self._stop.is_set() else "ready"
                self._status["finished_at"] = time.time()


class ArchiveWriteTicket:
    """Observable completion token for a queued immutable package write."""

    def __init__(self, path: Path, package: ModelPackage) -> None:
        self.path = path
        self.package = package
        self.done = threading.Event()
        self.item: dict[str, Any] | None = None
        self.error: Exception | None = None

    def result(self, timeout: float | None = None) -> dict[str, Any]:
        if not self.done.wait(timeout):
            raise TimeoutError("archive write is still pending")
        if self.error is not None:
            raise self.error
        if self.item is None:
            raise RuntimeError("archive write completed without an index entry")
        return self.item


class ArchiveWriter:
    """Single background writer for immutable snapshot package payloads.

    Runtime code captures an immutable package while holding its own lock, then
    releases that lock before compression, file I/O, checksumming, and SQLite
    indexing happen here.  This keeps automatic archival outside the tick
    path and provides ordered writes to SQLite.
    """

    def __init__(self, repository: ArchiveRepository) -> None:
        self.repository = repository
        self._queue: queue.Queue[ArchiveWriteTicket | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._status: dict[str, Any] = {"running": False, "queued": 0, "written": 0, "failed": 0, "last_error": None}

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._status["running"] = True
            self._thread = threading.Thread(target=self._run, name="threemind-archive-writer", daemon=True)
            self._thread.start()

    def submit(self, path: Path | str, package: ModelPackage) -> ArchiveWriteTicket:
        self.start()
        ticket = ArchiveWriteTicket(Path(path), package)
        with self._lock:
            self._status["queued"] += 1
        self._queue.put(ticket)
        return ticket

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {**self._status, "pending": self._queue.qsize()}

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        with self._lock:
            self._status["running"] = False

    def _run(self) -> None:
        while True:
            ticket = self._queue.get()
            if ticket is None:
                return
            try:
                ticket.package.save(ticket.path)
                ticket.item = self.repository.index_metadata(ticket.path, ticket.package.catalog_metadata())
                with self._lock:
                    self._status["written"] += 1
            except (OSError, ValueError, sqlite3.Error) as error:
                ticket.error = error
                with self._lock:
                    self._status["failed"] += 1
                    self._status["last_error"] = str(error)
            finally:
                with self._lock:
                    self._status["queued"] = max(0, int(self._status["queued"]) - 1)
                ticket.done.set()
