"""Measure scientific files and complete subject dependency closures, Windows allocation aware."""
import argparse,ctypes,gzip,json
from pathlib import Path
from ctypes import wintypes as W
import study as d
from student import load
class Standard(ctypes.Structure):
 _fields_=[('AllocationSize',ctypes.c_longlong),('EndOfFile',ctypes.c_longlong),('NumberOfLinks',W.DWORD),('DeletePending',ctypes.c_ubyte),('Directory',ctypes.c_ubyte)]
def measure(root):
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
 k.GetFileInformationByHandleEx.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];k.GetFileInformationByHandleEx.restype=W.BOOL
 k.CloseHandle.argtypes=[W.HANDLE]
 seen=set();groups={};allocations={};sizes={};multi=0
 for p in sorted(root.rglob('*')):
  if not p.is_file():continue
  stat=p.stat();h=k.CreateFileW(str(p),0x80,7,None,3,0,None)
  if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
  info=Standard()
  try:
   if not k.GetFileInformationByHandleEx(h,1,ctypes.byref(info),ctypes.sizeof(info)):raise ctypes.WinError(ctypes.get_last_error())
  finally:k.CloseHandle(h)
  key=(stat.st_dev,stat.st_ino);rel=p.relative_to(root).as_posix()
  group='api_readback' if rel.startswith('readback/') else 'archive' if p.name=='originals-v1.zip' else 'originals_and_metadata'
  g=groups.setdefault(group,dict(files=0,logical_bytes=0,allocated_unique_bytes=0));g['files']+=1;g['logical_bytes']+=stat.st_size
  if key not in seen:g['allocated_unique_bytes']+=info.AllocationSize;seen.add(key)
  allocations[rel]=info.AllocationSize;sizes[rel]=stat.st_size;multi+=info.NumberOfLinks>1
 subjects=[]
 for p in root.glob('origins/o*/*/whole-test-026.json.gz'):
  state=load(p);folder=p.parent;refs=[p]+[folder/state['reader_ref']['path']/name for name in state['reader_ref']['files']]+[folder/r for r in state['samples']]
  if state['student']:refs += [folder/r for r in state['student']['sample_refs']]
  if state['mode']=='template-fixed':refs += [root/f"templates/o{state['origin']}.json.gz"]
  refs=list(dict.fromkeys(r.resolve() for r in refs))
  subjects.append(dict(identity=state['branch_id'],mode=state['mode'],checkpoint_bytes=p.stat().st_size,
   checkpoint_decoded_json_bytes=len(gzip.decompress(p.read_bytes())),closure_files=len(refs),
   closure_logical_bytes=sum(sizes[r.relative_to(root).as_posix()] for r in refs),
   closure_allocated_bytes=sum(allocations[r.relative_to(root).as_posix()] for r in refs)))
 return dict(schema='sat-core-exclusion-storage/1',method='Win32 FileStandardInfo allocation with volume/file identity hardlink deduplication',
  excludes='Directory and NTFS metadata overhead; the measurement file itself when saved afterward',groups=groups,
  logical_bytes=sum(x['logical_bytes'] for x in groups.values()),allocated_unique_bytes=sum(x['allocated_unique_bytes'] for x in groups.values()),
  paths_with_multiple_links=multi,branches=subjects,closure_note='Final state, reader and retained sample/template dependencies; shared dependencies overlap between branches. Code frozen separately.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=d.WORK);a=p.parse_args();print(json.dumps(measure(a.work.resolve()),ensure_ascii=False,indent=2))
