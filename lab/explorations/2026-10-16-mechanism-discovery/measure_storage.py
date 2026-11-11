"""Windows file allocation inventory, separate from logical and hard-link size."""
import argparse
import ctypes
import json
from ctypes import wintypes
from pathlib import Path


class StandardInfo(ctypes.Structure):
    _fields_ = [('allocation', ctypes.c_longlong), ('end', ctypes.c_longlong),
                ('links', wintypes.DWORD), ('delete_pending', ctypes.c_ubyte), ('directory', ctypes.c_ubyte)]


def measure(work):
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                               wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    api.CreateFileW.restype = wintypes.HANDLE
    api.GetFileInformationByHandleEx.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    api.GetFileInformationByHandleEx.restype = wintypes.BOOL
    api.CloseHandle.argtypes = (wintypes.HANDLE,)
    seen, logical, unique, allocation, links, count = set(), 0, 0, 0, 0, 0
    for path in work.rglob('*'):
        if not path.is_file():
            continue
        st = path.stat()
        count += 1
        logical += st.st_size
        key = (st.st_dev, st.st_ino)
        if key in seen:
            continue
        seen.add(key)
        handle = api.CreateFileW(str(path), 0x80, 7, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            info = StandardInfo()
            if not api.GetFileInformationByHandleEx(handle, 1, ctypes.byref(info), ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            if info.end != st.st_size:
                raise ValueError('file changed while observing')
            allocation += info.allocation
            unique += info.end
            links += info.links > 1
        finally:
            api.CloseHandle(handle)
    return {'schema': 'threemind.storage-inventory/2', 'files': count, 'unique_files': len(seen),
            'logical_bytes': logical, 'unique_logical_bytes': unique, 'file_allocation_bytes': allocation,
            'unique_files_with_multiple_links': links,
            'method': 'GetFileInformationByHandleEx(FileStandardInfo).AllocationSize; de-duplicate st_dev/st_ino',
            'scope': 'current work tree before this inventory; file-stream allocation excludes directory/MFT and database overhead; archive/readback may not yet exist',
            'correction': 'v1 GetCompressedFileSizeW returns logical size for ordinary noncompressed files; its unique_allocated_bytes must not be interpreted as allocation. v1 retained.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = measure(args.work)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps(value, ensure_ascii=False))
