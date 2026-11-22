"""Existing resource guard plus file allocation measurements; no Core import."""
import ctypes
import hashlib
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'lab/explorations/2026-10-16-mechanism-discovery'))
import pilot_m2 as base

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def allocated(path):
    high = ctypes.c_ulong(0)
    fn = ctypes.WinDLL('kernel32', use_last_error=True).GetCompressedFileSizeW
    fn.argtypes = (ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong))
    fn.restype = ctypes.c_ulong
    ctypes.set_last_error(0)
    low = fn(str(path), ctypes.byref(high))
    if low == 0xffffffff and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    return (high.value << 32) | low


def blob(path, data):
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    return {'sha256': sha(path), 'logical_bytes': len(data), 'allocated_bytes': allocated(path)}


