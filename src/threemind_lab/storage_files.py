"""Small local control-file primitives; importing this module creates no files."""

from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


class StorageConflict(ValueError):
    pass


class StorageBusy(StorageConflict):
    pass


def checked_path(path: str | Path) -> Path:
    """Reject links/reparse points in every existing component, before resolving."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("storage paths must be absolute and cannot contain '..'")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("storage paths cannot traverse symbolic links or reparse points")
    return path.resolve(strict=False)


def relative_key(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("a nonempty portable relative storage key is required")
    parts = value.split("/")
    if any(p in ("", ".", "..") or ":" in p for p in parts):
        raise ValueError("storage keys cannot contain empty, parent, drive or dot components")
    reserved = {"con", "prn", "aux", "nul"} | {f"{prefix}{i}" for prefix in ("com", "lpt") for i in range(1, 10)}
    if any(p[-1] in (" ", ".") or any(c in p for c in '<>"|?*') or p.split(".")[0].casefold() in reserved for p in parts):
        raise ValueError("storage keys cannot contain nonportable Windows path aliases")
    path = Path(*parts)
    if path.is_absolute():
        raise ValueError("storage keys must be relative")
    return path


def under_root(root: Path, key: str) -> Path:
    root = checked_path(root)
    path = checked_path(root / relative_key(key))
    if path == root or not path.is_relative_to(root):
        raise ValueError("storage key escapes its registered root")
    return path


def atomic_json(path: Path, value: dict) -> None:
    checked_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    checked_path(path.parent)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, *, maximum=32 * 1024**2) -> dict:
    checked_path(path)
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("storage control document exceeds its read budget")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("storage control document must be an object")  # noqa: TRY004 - Corrupt persisted control data uses the validation error contract.
    return result


def publish_directory(source: Path, destination: Path) -> None:
    """Atomically publish a complete directory without replacing a racing creator."""
    checked_path(source)
    checked_path(destination)
    if os.name == "nt":
        # Windows MoveFile (used by os.rename) refuses an existing destination.
        os.rename(source, destination)
    else:
        import ctypes
        import sys

        library = ctypes.CDLL(None, use_errno=True)
        if sys.platform.startswith("linux") and hasattr(library, "renameat2"):
            result = library.renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
        elif sys.platform == "darwin" and hasattr(library, "renamex_np"):
            result = library.renamex_np(os.fsencode(source), os.fsencode(destination), 4)
        else:
            raise StorageConflict("this host cannot atomically publish a directory without overwriting")
        if result != 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(destination))
        fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


@contextmanager
def file_lock(path: Path, *, create=True):
    checked_path(path)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
        checked_path(path.parent)
    stream = path.open("a+b" if create else "r+b")
    try:
        if stream.seek(0, 2) == 0:
            if not create:
                raise StorageBusy("an empty legacy lock cannot establish writer safety")
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise StorageBusy("another writer or storage operation holds this lock") from error
        try:
            yield stream
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()
