"""Small read-only state/process query; never loads an experimental subject."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
import psutil
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from threemind_lab.config import load_env
from threemind_lab.research_storage import ResearchStorage
def read(p):return json.loads(p.read_bytes()) if p.exists() else None
def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path);args=p.parse_args();load_env()
    work=args.work or ResearchStorage().writable_root()/'experiments'/Path(__file__).resolve().parent.name
    out=dict(time_epoch=time.time(),free_GiB=shutil.disk_usage(work if work.exists() else work.parent).free/2**30,
        pipeline=read(work/'pipeline-status.json'),host=read(work/'host-status.json'),progress=read(work/'progress.json'),
        sync=read(work/'sync-status.json'),complete=read(work/'computation-complete.json'))
    out['processes']=[]
    for proc in psutil.process_iter(['name']):
        try:
            if not proc.info['name'] or 'python' not in proc.info['name'].lower():continue
            cmd=proc.cmdline()
            if any(Path(c).name in ('pipeline.py','experiment.py','analyze.py','replay.py','publish.py') and
                   '2026-10-13-continuous-shape-color' in c for c in cmd):
                out['processes'].append(dict(pid=proc.pid,cmd=cmd,cpu_s=sum(proc.cpu_times()[:2]),rss=proc.memory_info().rss))
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    out['arms']={}
    for arm in ('2','3.1'):
        base=work/'arms'/arm;latest=read(base/'latest.json')
        out['arms'][arm]=dict(born=bool(latest),latest={k:latest[k] for k in ('sequence','key','end_us','identity')} if latest else None,
            in_flight=read(base/'in-flight.json'),scores={p.parent.name:{k:read(p)[k] for k in ('n','correct','shape','color','pairs')}
                for p in sorted(base.glob('*/result.json')) if 'development' in p.parent.name or p.parent.name=='final'})
    out['pending']=len(list((work/'.research-records/pending').glob('*.json')))
    print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()
