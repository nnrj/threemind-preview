"""Portable inventories of experiment trees and verified copying with native file times."""

import ctypes
import gzip
import hashlib
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from .storage_files import StorageConflict, checked_path, relative_key, under_root
from .storage_volumes import _allocation_api

BLOCK = 4 * 1024**2


def member(root, key):
    return checked_path(root) if key == "." else under_root(root, key)


def times(info):
    result = {"mtime_ns": info.st_mtime_ns}
    if hasattr(info, "st_birthtime_ns"):
        result["birth_ns"] = info.st_birthtime_ns
    elif os.name == "nt":  # Before Python 3.12 Windows exposed creation time as st_ctime.
        result["birth_ns"] = info.st_ctime_ns
    return result


def set_times(path, entry):
    if os.name == "nt":
        kernel = _allocation_api()
        kernel.SetFileTime.argtypes = [ctypes.c_void_p] * 4
        handle = kernel.CreateFileW(str(path), 0x100, 7, None, 3, 0x02000000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:

            def filetime(key):
                return ctypes.c_uint64(entry[key] // 100 + 116444736000000000)

            birth, modified = filetime("birth_ns"), filetime("mtime_ns")
            if not kernel.SetFileTime(handle, ctypes.byref(birth), None, ctypes.byref(modified)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)
    else:
        os.utime(path, ns=(path.stat().st_atime_ns, entry["mtime_ns"]))
    if times(path.stat()) != {k: entry[k] for k in ("mtime_ns", "birth_ns") if k in entry}:
        raise StorageConflict(f"destination cannot preserve the recorded timestamps: {path}")


class _Stream(ctypes.Structure):
    _fields_ = [("size", ctypes.c_int64), ("name", ctypes.c_wchar * 296)]


@lru_cache(maxsize=1)
def _stream_api():
    kernel = _allocation_api()
    kernel.FindFirstStreamW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    kernel.FindFirstStreamW.restype = ctypes.c_void_p
    kernel.FindNextStreamW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.FindClose.argtypes = [ctypes.c_void_p]
    return kernel


def no_named_streams(path):
    """A plain byte copy cannot reproduce NTFS alternate data streams."""
    if os.name != "nt":
        return
    kernel = _stream_api()
    info = _Stream()
    handle = kernel.FindFirstStreamW(str(path), 0, ctypes.byref(info), 0)
    if handle == ctypes.c_void_p(-1).value:
        if ctypes.get_last_error() in (38, 1):  # EOF or a filesystem without streams
            return
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        while True:
            if info.name != "::$DATA":
                raise StorageConflict(f"named filesystem stream requires a native backup: {path}")
            if not kernel.FindNextStreamW(handle, ctypes.byref(info)):
                if ctypes.get_last_error() != 38:
                    raise ctypes.WinError(ctypes.get_last_error())
                break
    finally:
        kernel.FindClose(handle)


@contextmanager
def opened(path, guards):
    stream = guards.get(path)
    if stream is None:
        with path.open("rb") as stream:
            yield stream
    else:
        stream.seek(0)
        yield stream


def digest(path, guards):
    with opened(path, guards) as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(roots, guards=None, *, hashes=True):
    """Include empty directories, the part root and exact timestamps. Missing optional parts stay absent."""
    result = {}
    for name, root in roots.items():
        if not root.is_dir():
            raise StorageConflict(f"missing experiment part: {root}")
        pending = [(root, ".")]
        while pending:
            path, key = pending.pop()
            checked_path(path)
            before = path.stat()
            entry = times(before)
            if stat.S_ISDIR(before.st_mode):
                entry["kind"] = "directory"
                for child in sorted(path.iterdir(), reverse=True):
                    relative_key(child.name)
                    pending.append((child, child.relative_to(root).as_posix()))
            elif stat.S_ISREG(before.st_mode):
                entry.update(kind="file", bytes=before.st_size)
                if hashes:
                    no_named_streams(path)
                    entry["sha256"] = digest(path, guards or {})
            else:
                raise StorageConflict(f"unsupported experiment file type: {path}")
            if hashes and entry["kind"] == "directory":
                no_named_streams(path)
            if times(path.stat()) != times(before):
                raise StorageConflict(f"experiment changed while reading: {path}")
            result[(name, key)] = entry
    return result


def write_inventory(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        tmp = Path(stream.name)
    try:
        with gzip.open(tmp, "wt", encoding="utf-8", newline="\n") as out:
            for (part, key), entry in sorted(entries.items()):
                out.write(json.dumps([part, key, entry], ensure_ascii=False, separators=(",", ":")) + "\n")
        with tmp.open("rb+") as stream:
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def read_inventory(path):
    entries = {}
    with gzip.open(checked_path(path), "rt", encoding="utf-8") as stream:
        for line in stream:
            part, key, entry = json.loads(line)
            relative_key(part)
            if key != ".":
                relative_key(key)
            entries[part, key] = entry
    return entries


def copy_file(source, destination, temporary, entry, guards, check):
    """Only the job's private temporary file is discarded on failure."""
    writer = hashlib.sha256()
    with opened(source, guards) as src, temporary.open("xb") as out:
        until_check = 0
        while block := src.read(BLOCK):
            if until_check <= 0:
                check(min(64 * 1024**2, entry["bytes"] - out.tell()))
                until_check = 64 * 1024**2
            out.write(block)
            writer.update(block)
            until_check -= len(block)
        out.flush()
        os.fsync(out.fileno())
    if writer.hexdigest() != entry["sha256"]:
        raise StorageConflict(f"source content changed during copy: {source}")
    if os.name != "nt":
        os.chmod(temporary, stat.S_IMODE(source.stat().st_mode))
    os.replace(temporary, destination)
    set_times(destination, entry)
