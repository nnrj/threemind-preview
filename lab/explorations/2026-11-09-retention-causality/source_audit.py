"""Read-only source audit and prespecified mathematical decay comparison."""
import argparse
import math
from pathlib import Path
import study as e

def x_edges(state):
    ns=e.names(state);ports=set(sum(e.old.PORTS.values(),()))
    return [x for x in e.current_edge_measure(state) if
            (x['source'] in ('X0','X1') and x['target'] in ports) or
            (x['target'] in ('X0','X1') and x['source'] in ports)]

def main(work):
    rows=[]
    for i in range(e.N):
        for h in (0,1):
            root=e.SOURCE/f'origins/o{i}/h{h}'
            before=e.load(root/'test-parent.json.gz');initial=x_edges(before)
            keys={tuple(x['key']) for x in initial};series=[]
            for j in range(24):
                p=root/f'intact/trial-{j:03d}/whole.json.gz';s=e.load(p)
                remaining=[x for x in x_edges(s) if tuple(x['key']) in keys]
                series.append(dict(trial=j,elapsed_s=(int(s['core']['time_us'])-int(before['core']['time_us']))/1e6,
                    surviving=len(remaining),sha256=e.sha(p)))
            rows.append(dict(origin=i,history=h,parent_sha256=e.sha(root/'test-parent.json.gz'),initial=initial,series=series))
    e.save(work/'source-audit-v1.json',dict(classification='retrospective read-only R43 original-state audit',origins=rows,
        source_core_sha256=e.sha(e.ROOT/'crates/threemind-core/src/local_shared.rs'),
        source_retention_sha256=e.sha(e.ROOT/'crates/threemind-core/src/retention.rs')))
    # Match half-value time for curve-shape comparisons; the 300-second arm explicitly changes it.
    slow=.2;slow_half=300.;fast_half=30./(-math.log2((.5-slow*2**(-30/slow_half))/(1-slow)))
    curves={
        'exponential30':(lambda t:2**(-t/30),'2^(-t/30)'),
        'exponential300':(lambda t:2**(-t/300),'2^(-t/300)'),
        'power30':(lambda t:1/(1+t/30),'(1+t/30)^(-1)'),
        'inverse_log30':(lambda t:1/(1+math.log1p(t/(30/(math.e-1)))),'1/[1+ln(1+t/(30/(e-1)))]'),
        'two_exponentials30':(lambda t:(1-slow)*2**(-t/fast_half)+slow*2**(-t/slow_half),f'0.8*2^(-t/{fast_half})+0.2*2^(-t/300)')}
    initial=[x['weight'] for r in rows for x in r['initial']]
    items={}
    for name,(fn,formula) in curves.items():
        assert abs(fn(0)-1)<1e-12
        assert abs(fn(300 if name=='exponential300' else 30)-.5)<1e-12
        crossing=[]
        for w in initial:
            lo,hi=0.,1.
            while w*fn(hi)>.008:hi*=2
            for _ in range(70):
                mid=(lo+hi)/2
                if w*fn(mid)>.008:lo=mid
                else:hi=mid
            crossing.append(hi)
        items[name]=dict(formula=formula,remaining_fraction={str(t):fn(t) for t in (1,30,60,300,1000)},
            threshold_crossing_seconds=dict(min=min(crossing),median=sorted(crossing)[len(crossing)//2],max=max(crossing)))
    e.save(work/'curves-v1.json',dict(classification='mathematical candidates, not subject performance or adopted dynamics',
        assumptions='fixed initial weight and .008 deletion threshold; no reinforcement, interference, threshold adaptation or state dependence',
        initial_weights_n=len(initial),items=items))
    print({'histories':len(rows),'initial_x_edges':len(initial),'all_lost_at_end':all(r['series'][-1]['surviving']==0 for r in rows)})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=e.WORK);a=p.parse_args();main(a.work.resolve())
