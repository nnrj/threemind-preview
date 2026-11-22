"""Read Windows allocation sizes without loading or advancing a subject."""
import argparse
import ctypes
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import statistics


class StandardInfo(ctypes.Structure):
    _fields_ = [('allocation', ctypes.c_longlong), ('end', ctypes.c_longlong),
                ('links', w.DWORD), ('deleted', w.BYTE), ('directory', w.BYTE)]


def allocation(path):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
    k.CreateFileW.restype = w.HANDLE
    k.GetFileInformationByHandleEx.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    k.GetFileInformationByHandleEx.restype = w.BOOL
    k.CloseHandle.argtypes = [w.HANDLE]
    handle = k.CreateFileW(str(path), 0, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = StandardInfo()
        if not k.GetFileInformationByHandleEx(handle, 1, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.allocation
    finally:
        k.CloseHandle(handle)


def audit(root):
    path = root / 'storage-allocation-audit.json'
    if path.exists():
        return json.loads(path.read_bytes())
    files = sorted(p for p in root.rglob('*') if p.is_file())
    rows = []
    unique = {}
    for p in files:
        st = p.stat()
        size = allocation(p)
        rows.append({'path': p.relative_to(root).as_posix(), 'logical_bytes': st.st_size,
                     'allocation_bytes': size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        unique.setdefault((st.st_dev, st.st_ino), size)
    finals = {version: [r for r in rows if r['path'].startswith('foundation-v2/n1024-active/confirm')
                       and r['path'].endswith('/' + version + '/final.tmind')] for version in ('5.1', '6.0')}
    assert all(len(value) == 5 for value in finals.values())
    medians = {version: statistics.median(r['allocation_bytes'] for r in values)
               for version, values in finals.items()}
    result = {'schema': 'threemind.r51a-allocation/1', 'method': 'GetFileInformationByHandleEx/FileStandardInfo',
              'scope': 'Snapshot before this allocation audit and its publication; includes originals and API readback.',
              'files': len(rows), 'unique_files': len(unique), 'logical_bytes': sum(r['logical_bytes'] for r in rows),
              'allocated_bytes': sum(unique.values()), 'median_final_allocation': medians,
              'final_allocation_ratio': medians['6.0'] / medians['5.1'], 'members': rows}
    with path.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True, type=Path)
    result = audit(parser.parse_args().work.resolve())
    print(json.dumps({k: v for k, v in result.items() if k != 'members'}, indent=2))
