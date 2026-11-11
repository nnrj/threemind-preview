"""Observe the exact R46b host and perform read-only verification once."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import psutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/stimulus-v1')

def read(path):return json.loads(path.read_text('utf-8'))

def main():
    host=read(WORK/'host.json');folder=WORK/'postprocessing'
    folder.mkdir(exist_ok=True)
    marker=folder/'automatic-analysis.json'
    assert not marker.exists(),'an earlier attempt exists; inspect it'
    claim=folder/'automatic-analysis-claim.json'
    with claim.open('x',encoding='utf-8') as f:
        json.dump(dict(pid=psutil.Process().pid,created_at=psutil.Process().create_time(),host=host,
                       source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),f)
    while True:
        try:
            process=psutil.Process(host['pid'])
            if process.create_time()!=host['created_at']:break
            assert process.cmdline()==host['command'],'host command changed'
        except psutil.NoSuchProcess:break
        time.sleep(10)
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=960)
    assert not any((WORK/n).exists() for n in ('STOP','in-flight.json'))
    records=[]
    for name in ('analyze_stimulus.py','audit_stimulus.py','inventory_stimulus.py'):
        script=HERE/name
        with (folder/(name+'.out.log')).open('xb') as stdout,(folder/(name+'.err.log')).open('xb') as stderr:
            result=subprocess.run([sys.executable,'-X','utf8',str(script)],cwd=ROOT,stdout=stdout,stderr=stderr,check=False)
        records.append(dict(script=name,returncode=result.returncode,sha256=hashlib.sha256(script.read_bytes()).hexdigest()))
        if result.returncode:break
    success=len(records)==3 and all(x['returncode']==0 for x in records)
    with marker.open('x',encoding='utf-8') as f:
        json.dump(dict(host=host,steps=records,state='awaiting-report-review' if success else 'analysis-error',epoch=time.time()),f)
    print(json.dumps(dict(state='awaiting-report-review' if success else 'analysis-error',steps=records)))

if __name__=='__main__':main()
