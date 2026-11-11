"""File-only apparatus storage and cost summary; no engine or learning."""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import statistics

import pilot_m2 as m
from m5_confirm_summary import StandardInfo


def inventory(work):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    files = [p for p in work.rglob('*') if p.is_file() and p.name != 'storage-inventory-v1.json']
    seen = set(); logical = unique_logical = allocated = 0
    for path in files:
        st = path.stat(); logical += st.st_size
        key = (st.st_dev, st.st_ino)
        if key in seen:
            continue
        handle = kernel.CreateFileW(str(path), 0x80, 7, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        info = StandardInfo()
        try:
            if not kernel.GetFileInformationByHandleEx(handle, 1, ctypes.byref(info), ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)
        assert info.EndOfFile == st.st_size
        seen.add(key); unique_logical += st.st_size; allocated += info.AllocationSize
    wholes = []
    for receipt in [work/'birth/complete.json', *sorted((work/'paths').glob('*/*/complete.json'))]:
        assert receipt.is_file()
        members = m.read(receipt)['files']
        paths = [receipt, *(receipt.parent/n for n in members)]
        wholes.append({'path': receipt.parent.relative_to(work).as_posix(),
                       'files': len(paths), 'logical_bytes': sum(p.stat().st_size for p in paths)})
    assert len(wholes) == 9
    return {'schema': 'threemind.file-storage-inventory/1', 'phase': 'before publication archive and API readback',
            'files': len(files), 'logical_bytes': logical, 'unique_files': len(seen),
            'hardlink_deduplicated_logical_bytes': unique_logical, 'allocated_file_stream_bytes': allocated,
            'duplicate_hardlink_entries': len(files)-len(seen), 'scientific_origins': 0,
            'instrument_whole_states': wholes,
            'whole_state_bytes': {'min': min(x['logical_bytes'] for x in wholes),
                                 'median': statistics.median(x['logical_bytes'] for x in wholes),
                                 'max': max(x['logical_bytes'] for x in wholes)},
            'exclusions': 'Inventory itself, later publication copies/archive/readback and directory/MFT/database overhead. Allocation is Windows FileStandardInfo with hardlink deduplication.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    work = p.parse_args().work.resolve()
    assert m.read(work/'audit-v1.json')['passed']
    a = m.read(work/'analysis-v1.json'); assert a['verdict'] == 'PASS' and a['scientific_origins'] == 0
    rows = inventory(work)
    m.original(work/'storage-inventory-v1.json', rows)
    print(json.dumps(rows))
