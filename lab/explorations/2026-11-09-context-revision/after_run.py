"""Finish read-only arithmetic after this exact scientific host, without replay."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
import psutil

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-context-revision/v1')
def read(p):return json.loads(p.read_bytes())


def alive(host):
    try:return abs(psutil.Process(host['pid']).create_time()-host['created_at'])<.01
    except psutil.NoSuchProcess:return False


def main(work):
    receipt=work/'postprocessing/automatic-analysis.json'
    if receipt.exists():
        print(json.dumps(read(receipt)));return
    host=read(work/'host.json')
    while alive(host):
        if (work/'STOP').exists():
            print(json.dumps(dict(state='boundary-pause-requested',action='retain; no continuation or replay')))
            return
        time.sleep(5)
    import experiment as e
    with e.base.worker_lock(work):
        state=e.load(work/'status.json')
        if (work/'STOP').exists() or (work/'in-flight.json').exists() or state!=dict(state='awaiting-analysis',origins_completed=e.N):
            print(json.dumps(dict(state='needs-inspection',scientific_status=state,in_flight=(work/'in-flight.json').exists())))
            return
        e.frozen(work);checks=[]
        for name,result in [('analyze.py','analysis-v1.json'),('audit_integrity.py','integrity-audit-v1.json'),('summarize.py','summary-v1.json')]:
            e.base.resource_check(work)
            if not (work/result).exists():
                command=[sys.executable,'-X','utf8',str(e.HERE/name),'--work',str(work)]
                p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',cwd=e.ROOT)
                e.save(work/f'postprocessing/{Path(name).stem}-execution.json',dict(command=command,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
                if p.returncode:
                    print(json.dumps(dict(state='analysis-failed',step=name,action='retain all subjects; do not rerun')))
                    return
            checks.append(dict(step=name,result=result,sha256=e.sha(work/result)))
        out=dict(state='awaiting-report-review',scientific_origins=e.N,checks=checks,
                 source_manifest=e.manifest(),automatic_publication=False,simulation_advanced=False)
        e.save(receipt,out);print(json.dumps(out))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=WORK);a=p.parse_args();main(a.work.resolve())
