"""Read-only storage and subject scale inventory after scientific completion."""
import argparse
import ctypes
from ctypes import wintypes
import statistics
import experiment as e


class StandardInfo(ctypes.Structure):
    _fields_=[('AllocationSize',ctypes.c_longlong),('EndOfFile',ctypes.c_longlong),
              ('NumberOfLinks',wintypes.DWORD),('DeletePending',ctypes.c_ubyte),('Directory',ctypes.c_ubyte)]


def main(work):
    assert e.load(work/'status.json')==dict(state='awaiting-analysis',origins_completed=8)
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    excluded={'.research-records','publication','readback'}
    files=sorted(p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&excluded
        and p.name not in ('storage-inventory-v1.json','originals-v1.zip','originals-manifest-v1.json')
        and not p.name.endswith('.lock') and not (p.parent==work and p.name.startswith('api-') and p.suffix=='.log'))
    logical=allocated=unique_logical=0;seen=set();sizes=[]
    for p in files:
        st=p.stat();logical+=st.st_size;key=(st.st_dev,st.st_ino)
        if key not in seen:
            handle=kernel.CreateFileW(str(p),0x80,7,None,3,0,None)
            if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
            info=StandardInfo()
            try:
                if not kernel.GetFileInformationByHandleEx(handle,1,ctypes.byref(info),ctypes.sizeof(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:kernel.CloseHandle(handle)
            seen.add(key);unique_logical+=st.st_size;allocated+=info.AllocationSize
        if p.name=='whole.json.gz':sizes.append(st.st_size)
    parents=[]
    for p in sorted((work/'origins').glob('o*/h*/test-parent.json.gz')):
        state=e.load(p)
        deps={work/ref['path']/name for ref in state['adapter_refs'].values() for name in ref['files']}
        parents.append(dict(path=p.relative_to(work).as_posix(),internal_seconds=int(state['core']['time_us'])/1e6,
            nodes=len(state['core']['nodes']),directed_connections=len(state['core']['edges']),
            compressed_state_bytes=p.stat().st_size,adapter_dependency_bytes=sum(q.stat().st_size for q in deps)))
    out=dict(schema='threemind.context-storage-inventory/1',files=len(files),logical_bytes=logical,
        hardlink_deduplicated_logical_bytes=unique_logical,allocated_file_stream_bytes=allocated,
        unique_files=len(seen),duplicate_hardlinks=len(files)-len(seen),
        compressed_whole_state_bytes=dict(min=min(sizes),median=statistics.median(sizes),max=max(sizes)),parents=parents,
        scope='Pre-publication scientific and apparatus files. Excludes live API logs, local request cache, locks, this inventory, later reports/archive/readback and directory/MFT/database overhead. Allocation measured by Windows FileStandardInfo.')
    e.save(work/'storage-inventory-v1.json',out)
    print(e.json.dumps({k:v for k,v in out.items() if k!='parents'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=e.Path,default=e.WORK);a=p.parse_args();main(a.work.resolve())
