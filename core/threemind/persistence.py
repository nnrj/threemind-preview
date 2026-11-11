from __future__ import annotations

import json
import os
import sqlite3
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


DEFAULT_FILE_BACKEND_MAX_EAGER_BYTES = 128 * 1024 * 1024


class FileBackendTooLarge(RuntimeError):
    """The JSON backend is intentionally limited to small, eagerly loaded data.

    File persistence is a compatibility option, not a scalable history store.
    Its document must be decoded as one Python object, so trying to load a
    multi-gigabyte document can make a local Core appear to hang before
    Uvicorn has had a chance to print its startup banner.
    """

    def __init__(self, path: Path, size: int, limit: int) -> None:
        self.path = path
        self.size = int(size)
        self.limit = int(limit)
        super().__init__(
            f"legacy file persistence at {path} is {self.size:,} bytes, above "
            f"the safe eager-load limit of {self.limit:,} bytes; select SQLite, "
            "MySQL, or D1 instead"
        )


def _file_backend_limit(config: dict[str, Any] | None = None) -> int | None:
    """Resolve the host-side safety limit without introducing a Core limit.

    ``0`` (or a negative value) explicitly disables the guard for a deliberate
    one-off legacy recovery attempt. Normal ThreeMind operation should use a
    database backend once history outgrows a small JSON document.
    """

    config = config or {}
    raw = config.get("max_eager_bytes", os.getenv("THREEMIND_FILE_BACKEND_MAX_BYTES", DEFAULT_FILE_BACKEND_MAX_EAGER_BYTES))
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        limit = DEFAULT_FILE_BACKEND_MAX_EAGER_BYTES
    return limit if limit > 0 else None


class PersistenceBackend(Protocol):
    name: str
    def put(self, key: str, value: dict[str, Any]) -> None: ...
    def get(self, key: str) -> dict[str, Any] | None: ...
    def all(self) -> list[dict[str, Any]]: ...
    def delete(self, key: str) -> None: ...
    def clear(self) -> None: ...
    def close(self) -> None: ...


class FileBackend:
    name = "file"
    def __init__(self, path: Path, *, max_eager_bytes: int | None = DEFAULT_FILE_BACKEND_MAX_EAGER_BYTES):
        self.path = path
        self.max_eager_bytes = max_eager_bytes if max_eager_bytes and max_eager_bytes > 0 else None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            size = self.path.stat().st_size
            if self.max_eager_bytes is not None and size > self.max_eager_bytes:
                raise FileBackendTooLarge(self.path, size, self.max_eager_bytes)
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                self.data = raw if isinstance(raw, dict) else {}
            except (OSError, ValueError):
                self.data = {}
    def _flush(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        # ``json.dump`` streams the JSON text to disk rather than constructing a
        # second full string in memory. This backend remains intentionally for
        # small compatibility records; database backends are the default for
        # long-running, append-heavy experimental history.
        with tmp.open("w", encoding="utf-8") as stream:
            json.dump(self.data, stream, ensure_ascii=False, indent=2)
        tmp_size = tmp.stat().st_size
        if self.max_eager_bytes is not None and tmp_size > self.max_eager_bytes:
            tmp.unlink(missing_ok=True)
            raise FileBackendTooLarge(self.path, tmp_size, self.max_eager_bytes)
        os.replace(tmp, self.path)
    def put(self, key: str, value: dict[str, Any]) -> None:
        self.data[key] = value; self._flush()
    def get(self, key: str) -> dict[str, Any] | None: return self.data.get(key)
    def all(self) -> list[dict[str, Any]]: return list(self.data.values())
    def delete(self, key: str) -> None: self.data.pop(key, None); self._flush()
    def clear(self) -> None: self.data.clear(); self._flush()
    def close(self) -> None: pass


class SQLiteBackend:
    name = "sqlite"
    def __init__(self, path: Path):
        self.path = path; self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("CREATE TABLE IF NOT EXISTS threemind_records (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.connection.commit()
    def put(self, key: str, value: dict[str, Any]) -> None:
        self.connection.execute("INSERT OR REPLACE INTO threemind_records(key,value) VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False))); self.connection.commit()
    def get(self, key: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT value FROM threemind_records WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None
    def all(self) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in self.connection.execute("SELECT value FROM threemind_records ORDER BY key")]
    def delete(self, key: str) -> None:
        self.connection.execute("DELETE FROM threemind_records WHERE key=?", (key,)); self.connection.commit()
    def clear(self) -> None:
        self.connection.execute("DELETE FROM threemind_records"); self.connection.commit()
        # Reclaim pages after an explicit user-requested purge.  This is a
        # host-history operation; it does not alter the in-memory consciousness
        # graph or its current activation state.
        self.connection.execute("VACUUM")
    def close(self) -> None: self.connection.close()


class MySQLBackend:
    name = "mysql"
    def __init__(self, url: str):
        try:
            import mysql.connector  # type: ignore
        except ImportError as exc:
            raise RuntimeError("MySQL backend requires mysql-connector-python") from exc
        from urllib.parse import urlparse
        parsed = urlparse(url)
        self.connection = mysql.connector.connect(host=parsed.hostname or "127.0.0.1", port=parsed.port or 3306, user=parsed.username, password=parsed.password, database=(parsed.path or "/").lstrip("/"))
        cursor = self.connection.cursor(); cursor.execute("CREATE TABLE IF NOT EXISTS threemind_records (record_key VARCHAR(255) PRIMARY KEY, record_value JSON NOT NULL)"); self.connection.commit()
    def put(self, key: str, value: dict[str, Any]) -> None:
        c=self.connection.cursor(); c.execute("INSERT INTO threemind_records(record_key,record_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE record_value=VALUES(record_value)",(key,json.dumps(value))); self.connection.commit()
    def get(self, key: str) -> dict[str, Any] | None:
        c=self.connection.cursor(); c.execute("SELECT record_value FROM threemind_records WHERE record_key=%s",(key,)); row=c.fetchone(); return json.loads(row[0]) if row else None
    def all(self) -> list[dict[str, Any]]:
        c=self.connection.cursor(); c.execute("SELECT record_value FROM threemind_records ORDER BY record_key"); return [json.loads(row[0]) for row in c.fetchall()]
    def delete(self, key: str) -> None:
        c=self.connection.cursor(); c.execute("DELETE FROM threemind_records WHERE record_key=%s",(key,)); self.connection.commit()
    def clear(self) -> None:
        c=self.connection.cursor(); c.execute("DELETE FROM threemind_records"); self.connection.commit()
    def close(self) -> None: self.connection.close()


class D1Backend:
    name = "d1"
    def __init__(self, endpoint: str, token: str): self.endpoint, self.token = endpoint.rstrip("/"), token
    def _request(self, payload: dict[str, Any]) -> Any:
        request = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(), headers={"content-type":"application/json","authorization":f"Bearer {self.token}"}, method="POST")
        with urllib.request.urlopen(request, timeout=15) as response: return json.loads(response.read())
    def put(self, key: str, value: dict[str, Any]) -> None: self._request({"sql":"INSERT OR REPLACE INTO threemind_records(record_key,record_value) VALUES (?,?)","params":[key,json.dumps(value)]})
    def get(self, key: str) -> dict[str, Any] | None:
        result = self._request({"sql":"SELECT record_value FROM threemind_records WHERE record_key=?","params":[key]})
        rows = result.get("result", result) if isinstance(result, dict) else result
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            value = rows[0].get("record_value") or rows[0].get("results", [{}])[0].get("record_value")
            return json.loads(value) if value else None
        return None
    def all(self) -> list[dict[str, Any]]:
        result = self._request({"sql":"SELECT record_value FROM threemind_records ORDER BY record_key"})
        rows = result.get("result", result) if isinstance(result, dict) else result
        output = []
        for row in rows if isinstance(rows, list) else []:
            value = row.get("record_value") if isinstance(row, dict) else None
            if value: output.append(json.loads(value))
        return output
    def delete(self, key: str) -> None: self._request({"sql":"DELETE FROM threemind_records WHERE record_key=?","params":[key]})
    def clear(self) -> None: self._request({"sql":"DELETE FROM threemind_records"})
    def close(self) -> None: pass


def build_backend(kind: str, data_dir: Path, config: dict[str, Any] | None = None) -> PersistenceBackend:
    config = config or {}
    if kind == "file": return FileBackend(data_dir / "records.json", max_eager_bytes=_file_backend_limit(config))
    if kind == "sqlite": return SQLiteBackend(Path(config.get("path") or data_dir / "threemind.sqlite3"))
    if kind == "mysql": return MySQLBackend(str(config.get("url") or os.getenv("THREEMIND_MYSQL_URL", "")))
    if kind == "d1": return D1Backend(str(config.get("endpoint") or os.getenv("THREEMIND_D1_ENDPOINT", "")), str(config.get("token") or os.getenv("THREEMIND_D1_TOKEN", "")))
    raise ValueError(f"unsupported persistence backend: {kind}")
