"""Post-result audit prompted by zero output activation in the mean projection."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

PORTS=('S0','S1','V0','V1','A0','A1','AO')
FIELDS=('activation','inhibition','direct','associative')
def read(p):
    raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def output(window):return [[frame[n][f] for n in PORTS for f in FIELDS] for frame in window['raw']]


def main(work):
    assert read(work/'status.json')==dict(state='awaiting-analysis',origins_completed=8)
    counts={};comparisons={arm:dict(equal_windows=0,windows=0,identical_predictions=0) for arm in ('target','matched')}
    reverses=[]
    for i in range(8):
        for h in (0,1):
            root=work/f'origins/o{i}/h{h}';parent=read(root/'test-parent.json.gz')
            edges={(e['source'],e['target']):e for e in parent['core']['edges']}
            mask=read(root/'target/intervention/result.json.gz')
            for kind in ('target','matched'):
                selected=mask[kind];rows=[]
                for edge in selected:
                    key=(edge['source'],edge['target']);reverse=edges.get((key[1],key[0]))
                    rows.append(dict(edge=list(key),reverse_present=reverse is not None,
                        reverse_awake=reverse is not None and not reverse['sleeping']))
                reverses.append(dict(origin=i,history=h,kind=kind,connections=rows))
            for j in range(24):
                r=read(root/f'intact/trial-{j:03d}/result.json.gz')
                for phase in ('first','second'):
                    values={f:[frame[n][f] for frame in r[phase]['raw'] for n in PORTS] for f in FIELDS}
                    key=r['case']['kind']+'|'+phase
                    d=counts.setdefault(key,dict(windows=0,all_activation_zero=0,only_inhibition_varies=0,inhibition_nonzero=0))
                    d['windows']+=1
                    d['all_activation_zero']+=int(all(v==0 for v in values['activation']))
                    positive_zero=all(v==0 for f in ('activation','direct','associative') for v in values[f])
                    inhib=any(v!=0 for v in values['inhibition'])
                    d['only_inhibition_varies']+=int(positive_zero and inhib)
                    d['inhibition_nonzero']+=int(inhib)
                for arm,d in comparisons.items():
                    other=read(root/f'{arm}/trial-{j:03d}/result.json.gz')
                    for phase in ('first','second'):
                        d['windows']+=1
                        d['equal_windows']+=int(output(r[phase])==output(other[phase]))
                        d['identical_predictions']+=int(r[phase]['predictions']==other[phase]['predictions'])
    source=Path(__file__).resolve().parents[3]/'crates/threemind-core/src/local_shared.rs'
    out=dict(schema='threemind.context-signal-audit/1',classification='post-result descriptive and implementation audit; prompted by zero-activation projection; no primary criterion changes',
        counts=counts,comparisons=comparisons,reverse_connections=reverses,
        implementation_source='crates/threemind-core/src/local_shared.rs',implementation_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        interpretation_boundary='Nonzero inhibitory inputs are measured. Reverse-edge availability and the incident-edge diffusion rule are implementation facts; the contribution of a particular surviving route requires its own intervention.')
    raw=json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2).encode();path=work/'signal-audit-v1.json'
    if path.exists():assert path.read_bytes()==raw
    else:
        with path.open('xb') as f:f.write(raw)
    print(json.dumps({k:v for k,v in out.items() if k!='reverse_connections'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();main(a.work.resolve())
