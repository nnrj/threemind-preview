"""Wait for this exact host, then run read-only verification once; never restart it."""
import json
from pathlib import Path
import subprocess
import sys
import time
import psutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-relaxation/v1')

def read(p):return json.loads(p.read_text('utf-8'))

def main():
    host=read(WORK/'host.json');out=WORK/'postprocessing'
    out.mkdir(exist_ok=True)
    mark=out/'automatic-analysis.json'
    if mark.exists():raise RuntimeError('already attempted; inspect receipt')
    while psutil.pid_exists(host['pid']):
        p=psutil.Process(host['pid'])
        if p.create_time()!=host['created_at']:break
        if p.cmdline()!=host['command']:raise RuntimeError('host command changed')
        time.sleep(10)
    status=read(WORK/'status.json')
    assert status==dict(state='awaiting-analysis',branches_completed=96),status
    assert not (WORK/'STOP').exists() and not (WORK/'in-flight.json').exists()
    records=[]
    for script in ('analyze_relaxation.py','audit_independent.py'):
        with (out/(script+'.out.log')).open('xb') as stdout,(out/(script+'.err.log')).open('xb') as stderr:
            result=subprocess.run([sys.executable,'-X','utf8',str(HERE/script)],cwd=ROOT,stdout=stdout,stderr=stderr,check=False)
        records.append(dict(script=script,returncode=result.returncode))
        if result.returncode:break
    with mark.open('x',encoding='utf-8') as f:
        json.dump(dict(host=host,steps=records,state='awaiting-report-review' if len(records)==2 and all(x['returncode']==0 for x in records) else 'analysis-error'),f)

if __name__=='__main__':main()
