"""Bounded engineering cost probe on synthetic fixtures, not research subjects."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def case(curve, enabled):
    import psutil
    from threemind_core import Stimulus
    from local52_candidate import Local52Config, Local52Engine
    proc=psutil.Process();start=time.perf_counter()
    engine=Local52Engine(Local52Config(decay_curve=curve,
        retention_relaxation_enabled=enabled,quiescence_death_us=10**15))
    measurements=[]
    def capture(stage):
        before=engine.capture_state().payload
        state=engine.capture_state().to_dict()
        rows=state['nodes']+state['edges']
        observations=engine.graph()
        assert before==engine.capture_state().payload
        restored=Local52Engine(state=engine.capture_state())
        assert before==restored.capture_state().payload
        measurements.append(dict(stage=stage,time_us=engine.time_us,nodes=len(state['nodes']),
            edges=len(state['edges']),contributions=sum(len(r['decay_contributions']) for r in rows),
            state_bytes=len(before),state_sha256=hashlib.sha256(before).hexdigest(),
            wall_seconds=time.perf_counter()-start,private_bytes=proc.memory_info().private,
            weight_sum=sum(r['weight'] for r in observations['edges'])))
    capture('blank')
    for i,t in enumerate((0,.1,.2,.5,1,2,4,8)):
        us=round(t*1e6);engine.advance_to(us)
        engine.inject(Stimulus(us,((10,.8),(20+i%2,.8))))
        engine.advance_to(us+50000)
    capture('spaced-inputs')
    for seconds in (30,300,3600,86400,2592000):
        engine.advance_to(round(seconds*1e6));capture(f't-{seconds}')
    return dict(kind='synthetic-engineering-cost',curve=curve,relaxation=enabled,
                measurements=measurements,wall_seconds=time.perf_counter()-start)


def main():
    p=argparse.ArgumentParser();p.add_argument('--curve');p.add_argument('--enabled',type=int)
    p.add_argument('--output',type=Path);a=p.parse_args()
    if a.curve:
        print(json.dumps(case(a.curve,bool(a.enabled))));return
    from decay_reference import CURVES
    out=[]
    for curve in CURVES:
        for enabled in (True,False):
            cmd=[sys.executable,'-X','utf8',__file__,'--curve',curve,'--enabled',str(int(enabled))]
            try:
                r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=30)
                row=json.loads(r.stdout) if r.returncode==0 else dict(curve=curve,relaxation=enabled,
                    error=r.stderr[-3000:],returncode=r.returncode)
            except subprocess.TimeoutExpired:
                row=dict(curve=curve,relaxation=enabled,error='30-second engineering limit')
            out.append(row);print(json.dumps(row),flush=True)
    if a.output:
        with a.output.open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)


if __name__=='__main__':main()
