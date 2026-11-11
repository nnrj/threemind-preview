"""Dated post-run diagnostic of the registered default-API comparisons."""
import gzip,json,math
from pathlib import Path

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-relaxation/v1')
OLD=Path('E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1')

def read(p):
    raw=p.read_bytes();return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)

def leaves(a,b):
    assert type(a) is type(b)
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a:yield from leaves(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):yield from leaves(x,y)
    elif isinstance(a,(int,float)):
        assert math.isfinite(a) and math.isfinite(b)
        yield abs(a-b)
    else:assert a==b

def main():
    analysis=read(WORK/'analysis-v1.json');maximum=0.;compared=changed=0;count=0
    for row in analysis['api_default_comparison']:
        i,h,arm,unit=(row[k] for k in ('origin','history','arm','unit'))
        now=read(WORK/f'origins/o{i}/h{h}/{arm}/{unit}/result.json.gz')
        before=read(OLD/f'early/o{i}/h{h}/{"baseline" if arm.startswith("natural") else "target"}/{unit}/result.json.gz')
        for window in ('first','second'):
            assert now[window]['predictions']==before[window]['predictions']
            for error in leaves(now[window]['raw'],before[window]['raw']):
                maximum=max(maximum,error);compared+=1;changed+=error!=0
        count+=1
    out=dict(interpretation='Post-run numerical diagnostic, not a new registered success criterion',
        trials=count,windows=count*2,all_categories_equal=True,
        trials_with_exact_raw_equality=sum(x['raw_equal'] for x in analysis['api_default_comparison']),
        scalar_values_compared=compared,scalar_values_changed=changed,max_absolute_raw_difference=maximum)
    with (WORK/'api-control-diagnostic-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps(out))

if __name__=='__main__':main()
