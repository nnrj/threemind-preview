"""Bounded instrument checks; this source never enters scientific N."""
import argparse
import copy
import json
import math
from pathlib import Path
import time
import study as e

def main(work,attempt):
    source=e.SOURCE/'instrument/attempt-02';out=work/f'instrument/attempt-{attempt:02d}'
    out.mkdir(parents=True,exist_ok=False);e.old.deterministic();checks=[]
    original=e.load(source/'trained.json.gz')
    e.save(out/'source.json',dict(path=str(source/'trained.json.gz'),sha256=e.sha(source/'trained.json.gz'),classification='instrument only'))
    s=e.old.Student.restore(source,original);assert s.state()==original;checks.append('complete original restoration')
    before=s.state();before_graph=s.core.graph();before_observation=s.core.observation_nodes()
    same,receipt=e.patch_half_life(before,'baseline');assert same==before;checks.append('sham exact')
    changed,receipt=e.patch_half_life(before,'target')
    target=e.selected(before,'target');matched=e.selected(before,'matched')
    assert len(target)==len(matched)==28
    altered=e.base.create_engine(state=e.base.StateImage.from_dict(changed['core']),kernel_id=e.base.KERNEL,backend='native')
    assert altered.capture_state().to_dict()==changed['core']
    assert altered.observation_nodes()==before_observation
    def weights(graph):return {(x['source'],x['target']):x['weight'] for x in graph['edges']}
    a,b=weights(before_graph),weights(altered.graph())
    assert a.keys()==b.keys() and max(abs(a[k]-b[k]) for k in a)<1e-14
    assert changed['core']['nodes']==before['core']['nodes'] and changed['core']['queue']==before['core']['queue']
    selected=set(target)
    for x,y in zip(before['core']['edges'],changed['core']['edges']):
        changed_keys={k for k in x if x[k]!=y[k]}
        assert changed_keys<={'weight','half_life'}
        if (x['source'],x['target']) not in selected:assert x==y
    for k in before['core']:
        if k not in ('edges','timers'):assert before['core'][k]==changed['core'][k],k
    checks.append('native projected weights and observations unchanged at intervention; allowed fields only')
    assert all(abs(r['current_h']-300)<1e-10 for r in receipt['connections'])
    checks.append('current half-life target and selected bidirectional edges')
    undone=e.base.create_engine(state=e.base.StateImage.from_dict(before['core']),kernel_id=e.base.KERNEL,backend='native')
    assert undone.capture_state().to_dict()==before['core'];checks.append('immediate declared undo exact')
    snapshot=altered.capture_state().to_dict();altered.metrics();altered.graph();altered.observation_nodes();time.sleep(.02)
    assert altered.capture_state().to_dict()==snapshot;checks.append('observation and wall time do not advance state')
    for h in (30.,31.,300.,3000.):
        for a in (0.,.01,1.,15.,100.):
            for b in (.03,2.,50.):
                c=before['core']['config'];w1,h1=e.decay(.2,h,a,c);w2,h2=e.decay(w1,h1,b,c);w3,h3=e.decay(.2,h,a+b,c)
                assert abs(w2-w3)<1e-14 and abs(h2-h3)<1e-10
    checks.append('analytic retention composition across the lower bound')
    s.core=altered;initial=s.state();e.save(out/'patched.json.gz',initial)
    start=time.monotonic();q1=s.window({'X0':.76},observed=True);end=s.state()
    s2=e.old.Student.restore(source,initial);q2=s2.window({'X0':.76})
    assert q1==q2 and s2.state()==end;checks.append('patched whole restore and next window including dense observation')
    e.save(out/'window.json.gz',q1);e.save(out/'intervention.json',receipt)
    result=dict(passed=True,checks=checks,manifest=e.manifest(),window_wall_seconds=time.monotonic()-start,
                scientific_N=0,instrument_source=str(source/'trained.json.gz'))
    e.save(out/'summary.json',result);e.save(work/'instrument/verified.json',result)
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=e.WORK);p.add_argument('--attempt',type=int,default=1)
    a=p.parse_args();main(a.work.resolve(),a.attempt)
