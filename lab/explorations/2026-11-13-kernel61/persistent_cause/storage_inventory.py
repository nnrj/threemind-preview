"""Measure current files and unique allocated bytes without loading a subject."""
import argparse
import ctypes
from datetime import datetime, timezone
import json
from pathlib import Path


class StandardInfo(ctypes.Structure):
    _fields_=[('AllocationSize',ctypes.c_longlong),('EndOfFile',ctypes.c_longlong),
              ('NumberOfLinks',ctypes.c_ulong),('DeletePending',ctypes.c_ubyte),('Directory',ctypes.c_ubyte)]


def measure(work):
    target=work/'storage-before-publication.json'
    if target.exists():
        print(target.read_text('utf8'));return
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p]
    create.restype=ctypes.c_void_p
    info=kernel.GetFileInformationByHandleEx
    info.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_ulong]
    info.restype=ctypes.c_int
    close=kernel.CloseHandle;close.argtypes=[ctypes.c_void_p];close.restype=ctypes.c_int
    paths=sorted(p for p in work.rglob('*') if p.is_file())
    logical=allocated=unique_logical=hardlinks=0;seen=set()
    for p in paths:
        stat=p.stat();logical+=stat.st_size
        identity=(stat.st_dev,stat.st_ino)
        if identity in seen:hardlinks+=1;continue
        seen.add(identity);unique_logical+=stat.st_size
        handle=create(str(p),0,7,None,3,0,None)
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        try:
            row=StandardInfo()
            if not info(handle,1,ctypes.byref(row),ctypes.sizeof(row)):raise ctypes.WinError(ctypes.get_last_error())
            assert row.EndOfFile==stat.st_size and row.AllocationSize>=0
            allocated+=row.AllocationSize
        finally:close(handle)
    result={'measured_at':datetime.now(timezone.utc).isoformat(),'scope':'All current files before publication; excludes this inventory and later archive/readback copies.',
            'files':len(paths),'unique_files':len(seen),'additional_hardlink_paths':hardlinks,
            'logical_bytes':logical,'unique_logical_bytes':unique_logical,'unique_allocated_bytes':allocated,
            'allocation_method':'Windows FileStandardInfo.AllocationSize; deduplicate by volume and file identity'}
    with target.open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);a=p.parse_args();measure(a.work.resolve())
