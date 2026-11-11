"""Read-only logical and allocated-size inventory, accounting for hard links."""
import argparse
import ctypes
from ctypes import wintypes
import gzip
import json
from pathlib import Path

DEFAULT=Path('E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1')
class StandardInfo(ctypes.Structure):
    _fields_=[('AllocationSize',ctypes.c_longlong),('EndOfFile',ctypes.c_longlong),
        ('NumberOfLinks',wintypes.DWORD),('DeletePending',ctypes.c_ubyte),('Directory',ctypes.c_ubyte)]

kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
kernel.CreateFileW.restype=wintypes.HANDLE
kernel.GetFileInformationByHandleEx.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
kernel.GetFileInformationByHandleEx.restype=wintypes.BOOL
kernel.CloseHandle.argtypes=[wintypes.HANDLE]

def allocated(p):
    handle=kernel.CreateFileW(str(p),0x80,7,None,3,0,None)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    info=StandardInfo()
    try:
        if not kernel.GetFileInformationByHandleEx(handle,1,ctypes.byref(info),ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.AllocationSize
    finally:kernel.CloseHandle(handle)

def sum_files(files):
    unique={};logical=0
    for p in files:
        st=p.stat();logical+=st.st_size;unique.setdefault((st.st_dev,st.st_ino),p)
    return dict(files=len(files),unique_file_ids=len(unique),logical_bytes=logical,
                unique_logical_bytes=sum(p.stat().st_size for p in unique.values()),
                allocated_unique_bytes=sum(allocated(p) for p in unique.values()))

def main(work):
    target=work/'storage-inventory-v1.json';assert not target.exists()
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    assert json.loads((work/'status.json').read_text('utf-8'))['state']=='awaiting-analysis'
    files=[p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&{'.research-records','publication','readback'}
        and not p.name.startswith('originals-v1') and not p.name.endswith('.lock')]
    states=[p for phase in ('late','early','origins') for p in (work/phase).rglob('whole.json.gz')]
    largest=max(states,key=lambda p:p.stat().st_size)
    s=json.loads(gzip.decompress(largest.read_bytes()))
    dependencies={work/ref['path']/name for ref in s['adapter_refs'].values() for name in ref['files']}
    out=dict(measurement='before publication; allocated file-stream bytes via Windows FileStandardInfo; hard links counted once by file identity; directory/MFT/database overhead excluded',
        study=sum_files(files),largest_state=dict(path=largest.relative_to(work).as_posix(),compressed_bytes=largest.stat().st_size,
        nodes=len(s['core']['nodes']),directed_connections=len(s['core']['edges'])),
        one_complete_individual=sum_files([largest,*sorted(dependencies)]),adapter_dependencies=sum_files(sorted(dependencies)))
    with target.open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,sort_keys=True)
    print(json.dumps(out,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=DEFAULT);a=p.parse_args();main(a.work.resolve())
