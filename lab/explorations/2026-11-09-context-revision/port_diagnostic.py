"""Exploratory mean-activation projection of committed windows; no subject loading."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

PORTS=dict(sound=('S0','S1'),vision=('V0','V1'),action=('A0','A1','AO'))
ARMS=('intact','sham','target','matched','restored','view-blocked','forced-view')
def read(p):
    b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)


def project(window):
    predictions={};means={}
    assert len(window['raw'])==20
    for head,names in PORTS.items():
        v=[sum(frame[n]['activation'] for frame in window['raw'])/20 for n in names]
        best=max(v);indices=[j for j,x in enumerate(v) if best-x<=1e-12]
        predictions[head]=indices[0] if best>1e-12 and len(indices)==1 else -1
        means[head]=v
    return predictions,means


def main(work):
    assert read(work/'status.json')==dict(state='awaiting-analysis',origins_completed=8)
    rows=[];tables={}
    for i in range(8):
        for h in range(2):
            for arm in ARMS:
                for j in range(24):
                    rel=f'origins/o{i}/h{h}/{arm}/trial-{j:03d}/result.json.gz';r=read(work/rel);c=r['case']
                    for phase in ('first','second'):
                        p,means=project(r[phase]);truth=c['expected' if phase=='first' else 'actual']
                        category=c['kind'] if phase=='first' or c['kind']!='clear' else ('conflict' if c['conflict'] else 'consistent')
                        heads=('action',) if phase=='first' and c['kind']=='ambiguous' else tuple(PORTS)
                        comparison=dict(projected={k:p[k]==truth for k in heads},actual={k:r[phase]['predictions'][k]==truth for k in heads})
                        for method,correct in comparison.items():
                            joint=[('joint',all(correct.values()))] if len(heads)==3 else []
                            for head,value in list(correct.items())+joint:
                                key='|'.join((arm,category,phase,method,head));d=tables.setdefault(key,dict(correct=0,n=0))
                                d['correct']+=int(value);d['n']+=1
                        rows.append(dict(origin=i,history=h,condition=arm,trial=j,phase=phase,category=category,
                            means=means,predictions=p,actual=r[phase]['predictions'],expected=truth))
    plan=Path(__file__).with_name('posthoc-projection-plan.md')
    result=dict(schema='threemind.context-port-diagnostic/1',classification='exploratory; selected after four sources; no primary score changes',
        independent_origins=8,plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),tables=tables,rows=rows)
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    path=work/'port-diagnostic-v1.json.gz';packed=gzip.compress(raw,mtime=0)
    if path.exists():assert path.read_bytes()==packed
    else:
        with path.open('xb') as f:f.write(packed)
    print(json.dumps({k:v for k,v in tables.items() if k.startswith('intact|')},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();main(a.work.resolve())
