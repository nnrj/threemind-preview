"""Identify mounted volumes and measure file allocation without following links."""

import ctypes
import os
import shutil
import stat
import sys
from functools import lru_cache
from pathlib import Path

from .storage_files import StorageConflict, checked_path


class VolumeOffline(StorageConflict):
    """An explicitly identified disk or directory is currently unavailable."""


def volume(path):
    path = checked_path(path)
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        mount = ctypes.create_unicode_buffer(32768)
        guid = ctypes.create_unicode_buffer(128)
        if kernel.GetVolumePathNameW(str(path), mount, len(mount)) and kernel.GetVolumeNameForVolumeMountPointW(
            mount.value, guid, len(guid)
        ):
            return guid.value.casefold(), Path(mount.value)
    return str(path.stat().st_dev), Path(path.anchor)


def directory_identity(path):
    key, mount = volume(path)
    return {"volume": key, "relative": str(path.relative_to(mount)), "inode": str(path.stat().st_ino)}


def mounted_directory(entry):
    original = Path(entry["path"])
    candidates = [original]
    if os.name == "nt" and entry["volume"].startswith("\\\\?\\volume{"):
        drives = ctypes.windll.kernel32.GetLogicalDrives()
        candidates.extend(
            Path(f"{chr(65 + index)}:/") / entry["relative"] for index in range(26) if drives & (1 << index)
        )
    for candidate in dict.fromkeys(candidates):
        try:
            if (
                candidate.is_dir()
                and str(candidate.stat().st_ino) == entry["inode"]
                and volume(candidate)[0] == entry["volume"]
            ):
                return checked_path(candidate)
        except (OSError, ValueError):
            continue
    raise VolumeOffline(f"storage directory offline or replaced: {entry['path']}")


@lru_cache(maxsize=1)
def _allocation_api():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    return kernel


def allocation_size(path, info):
    if hasattr(info, "st_blocks"):
        return info.st_blocks * 512
    kernel = _allocation_api()
    handle = kernel.CreateFileW(str(path), 0x80, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        # FILE_STANDARD_INFO starts with the 64-bit allocation and end-of-file sizes.
        record = (ctypes.c_int64 * 3)()
        if not kernel.GetFileInformationByHandleEx(handle, 1, record, ctypes.sizeof(record)):
            raise ctypes.WinError(ctypes.get_last_error())
        return record[0]
    finally:
        kernel.CloseHandle(handle)


def allocation_unit(path):
    if os.name != "nt":
        return os.statvfs(path).f_frsize
    sectors, size, free, total = (ctypes.c_uint32() for _ in range(4))
    mount = volume(path)[1]
    if not ctypes.windll.kernel32.GetDiskFreeSpaceW(
        str(mount), *(ctypes.byref(v) for v in (sectors, size, free, total))
    ):
        raise ctypes.WinError()
    return sectors.value * size.value


def tree_usage(path):
    """Directory charges include existing files. Count a hard link only once within this tree."""
    if not path.exists():
        return 0
    total, pending, links = 0, [checked_path(path)], set()
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    pending.append(entry.path)
                elif stat.S_ISREG(info.st_mode):
                    if os.name == "nt" or info.st_nlink > 1:
                        info = os.stat(entry.path, follow_symlinks=False)
                        if info.st_nlink > 1:
                            identity = (info.st_dev, info.st_ino)
                            if identity in links:
                                continue
                            links.add(identity)
                    total += allocation_size(entry.path, info)
    return total


def free_bytes(path):
    return shutil.disk_usage(path).free


class _DiskExtent(ctypes.Structure):
    _fields_ = [("number", ctypes.c_uint32), ("offset", ctypes.c_int64), ("length", ctypes.c_int64)]


class _VolumeExtents(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32), ("first", _DiskExtent)]


def physical_disks(volume_id, root):
    """Return OS disk IDs for this mount right now. Unknown topology never blocks a transfer."""
    if os.name == "nt" and volume_id.startswith("\\\\?\\volume{"):
        kernel = _allocation_api()
        kernel.DeviceIoControl.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        handle = kernel.CreateFileW(volume_id.rstrip("\\"), 0, 7, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            return []
        try:
            size = ctypes.sizeof(_VolumeExtents)
            while size <= 1024**2:
                data, used = ctypes.create_string_buffer(size), ctypes.c_uint32()
                # IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, documented in winioctl.h.
                if kernel.DeviceIoControl(handle, 0x00560000, None, 0, data, size, ctypes.byref(used), None):
                    count = ctypes.c_uint32.from_buffer(data).value
                    start, step = _VolumeExtents.first.offset, ctypes.sizeof(_DiskExtent)
                    if start + count * step > used.value:
                        return []
                    return sorted({str(_DiskExtent.from_buffer(data, start + i * step).number) for i in range(count)})
                if ctypes.get_last_error() not in (122, 234):
                    return []
                size *= 2
        finally:
            kernel.CloseHandle(handle)
    elif sys.platform.startswith("linux"):
        try:
            device = root.stat().st_dev
            pending = [(Path("/sys/dev/block") / f"{os.major(device)}:{os.minor(device)}").resolve(strict=True)]
            numbers = set()
            while pending:
                path = pending.pop()
                if (path / "partition").exists():
                    path = path.parent
                slaves = list((path / "slaves").iterdir())
                if slaves:
                    pending.extend(p.resolve(strict=True) for p in slaves)
                elif (path / "device").exists():
                    numbers.add((path / "dev").read_text().strip())
                else:
                    return []
            return sorted(numbers)
        except OSError:
            return []
    return []
