"""Read-only Windows allocated-byte measurement, deduplicating hardlinks."""
import argparse,ctypes,gzip,json,os
from pathlib import Path
from ctypes import wintypes as W
class Standard(ctypes.Structure):
    _fields_=[('AllocationSize',ctypes.c_longlong),('EndOfFile',ctypes.c_longlong),('NumberOfLinks',W.DWORD),('DeletePending',ctypes.c_ubyte),('Directory',ctypes.c_ubyte)]
def measure(root):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
    kernel.CreateFileW.restype=W.HANDLE
    kernel.GetFileInformationByHandleEx.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD]
    kernel.GetFileInformationByHandleEx.restype=W.BOOL
    kernel.CloseHandle.argtypes=[W.HANDLE]
    groups={};seen=set();link_files=0;count=0;individuals=[];compressed_or_sparse=0
    for p in sorted(root.rglob('*')):
        if not p.is_file():continue
        s=p.stat();key=(s.st_dev,s.st_ino)
        h=kernel.CreateFileW(str(p),0x80,7,None,3,0,None)
        if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        info=Standard()
        try:
            if not kernel.GetFileInformationByHandleEx(h,1,ctypes.byref(info),ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:kernel.CloseHandle(h)
        assert info.EndOfFile==s.st_size
        rel=p.relative_to(root)
        name='api_readback' if rel.parts[0]=='readback' else 'archive' if rel.name=='originals-v1.zip' else 'other_originals_and_metadata'
        g=groups.setdefault(name,dict(files=0,logical_bytes=0,allocated_unique_bytes=0))
        g['files']+=1;g['logical_bytes']+=s.st_size
        if key not in seen:g['allocated_unique_bytes']+=info.AllocationSize;seen.add(key)
        link_files+=info.NumberOfLinks>1;count+=1
        compressed_or_sparse+=bool(getattr(s,'st_file_attributes',0)&(0x800|0x200))
        if p.name=='whole-026.json.gz':
            individuals.append(dict(compressed_bytes=s.st_size,decoded_json_bytes=len(gzip.decompress(p.read_bytes())),allocated_bytes=info.AllocationSize))
    return dict(schema='threemind.storage-snapshot/1',root=str(root),method='Win32 FileStandardInfo.AllocationSize; unique volume/file IDs',
                excludes='Directory and NTFS metadata overhead; this measurement file itself if written later',
                files=count,paths_with_multiple_links=link_files,unique_files=len(seen),compressed_or_sparse_paths=compressed_or_sparse,groups=groups,
                final_whole_subject_snapshots=dict(count=len(individuals),ranges={k:[min(r[k] for r in individuals),max(r[k] for r in individuals)] for k in ('compressed_bytes','decoded_json_bytes','allocated_bytes')}),
                logical_bytes=sum(g['logical_bytes'] for g in groups.values()),
                allocated_unique_bytes=sum(g['allocated_unique_bytes'] for g in groups.values()))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();print(json.dumps(measure(a.work.resolve()),ensure_ascii=False,indent=2))
