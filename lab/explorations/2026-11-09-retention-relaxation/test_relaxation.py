"""Disposable instrument validation; no formal study source is advanced."""
import argparse
import copy
import json
from pathlib import Path
import time
import relaxation_study as e


def numeric_difference(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        return max((numeric_difference(a[k],b[k]) for k in a),default=0.)
    if isinstance(a,list):
        assert len(a)==len(b)
        return max((numeric_difference(x,y) for x,y in zip(a,b)),default=0.)
    if isinstance(a,(int,float)) and not isinstance(a,bool):return abs(a-b)
    assert a==b
    return 0.


def main(work,attempt):
    source=e.rc.SOURCE/'instrument/attempt-02';out=work/f'instrument/attempt-{attempt:02d}'
    out.mkdir(parents=True,exist_ok=False);e.old.deterministic();before_impl=e.base.capture_implementation('native')
    original=e.load(source/'trained.json.gz');checks=[];rows=[]
    for arm in e.ARMS:
        s=e.old.Student.restore(source,original);assert s.state()==original
        before=s.state();receipt=e.intervene(s,arm,work);initial=s.state()
        assert initial['core']['config']['memory_half_life_decay_rate']==e.RATES[arm.split('-')[1]]
        assert initial['adapter_digest']==before['adapter_digest'] and initial['torch_rng']==before['torch_rng']
        check=s.state();s.core.metrics();s.core.graph();s.core.observation_nodes();time.sleep(.01);assert s.state()==check
        q=s.window({'X0':.76},observed=True);after=s.state()
        restored=e.old.Student.restore(source,initial);q2=restored.window({'X0':.76})
        assert q==q2 and after==restored.state()
        if arm=='natural-default':
            raw=e.old.Student.restore(source,original);unmodified=raw.window({'X0':.76})
            assert q['predictions']==unmodified['predictions']
            error=numeric_difference(q,unmodified);assert error<1e-12
            checks.append('same-configuration API control preserves the next temporal answer within 1e-12 and exactly preserves categories')
        rate=arm.split('-')[1]
        if rate=='off':
            old_edges={(v['source'],v['target']):v['half_life'] for v in e.rc.current_edge_measure(initial)}
            for v in e.rc.current_edge_measure(after):
                key=(v['source'],v['target'])
                if key in old_edges:assert v['half_life']>=old_edges[key]-1e-12
        e.save(out/(arm+'.json.gz'),dict(before=before,initial=initial,after=after,window=q,receipt=receipt))
        rows.append(dict(arm=arm,current_projection_error=receipt['max_current_physical_change_at_reconfigure'],restored_window_equal=True))
    checks+=['six arms preserve current physical quantities while applying only the declared rate and optional target H boost',
             'configuration, clocks, queue, personal adapters and RNG audited',
             'observations and wall time do not advance the subject',
             'all six complete restores reproduce the next temporal window with dense observation',
             'zero relaxation retains nondecreasing current H on surviving connections during the instrument window']
    cfg=copy.deepcopy(original['core']['config'])
    for r in e.RATES.values():
        cfg['memory_half_life_decay_rate']=r
        for h in (30.,31.,300.,3000.):
            for a,b in ((0.,1.),(.01,30.),(30.,300.),(100.,3000.)):
                w,h1=e.rc.decay(.2,h,a,cfg);w2,h2=e.rc.decay(w,h1,b,cfg);w3,h3=e.rc.decay(.2,h,a+b,cfg)
                assert abs(w2-w3)<1e-14 and abs(h2-h3)<1e-10
    checks.append('decay remains exponential with zero H relaxation; analytic composition holds for all three rates')
    assert before_impl==e.base.capture_implementation('native');checks.append('production implementation and defaults unchanged')
    result=dict(passed=True,checks=checks,arms=rows,scientific_N=0,manifest=e.manifest(),source_path=str(source/'trained.json.gz'),source_sha256=e.sha(source/'trained.json.gz'))
    e.save(out/'summary.json',result);e.save(work/'instrument/verified.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=e.WORK);p.add_argument('--attempt',type=int,default=1)
    a=p.parse_args();main(a.work.resolve(),a.attempt)
