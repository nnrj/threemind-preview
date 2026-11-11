"""Post-design description of saved temporal signals, without Core execution.

This complements the frozen behavioral analysis. It neither changes its scores
nor assigns a new pass criterion. It is not a substitute readout.
"""
from collections import Counter
import gzip
import json
from pathlib import Path

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1')
ARMS={'late':('baseline','target','matched','all'),'early':('baseline','target','all')}
PORTS=('S0','S1','V0','V1','A0','A1','AO')
FIELDS=('activation','inhibition','direct','associative')


def read(p):
    raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)


def main():
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',branches_completed=112)
    assert not (WORK/'in-flight.json').exists() and not (WORK/'STOP').exists()
    summary={}
    for phase,arms in ARMS.items():
        for arm in arms:
            windows=Counter();nonzero=Counter();maxima={};sums=Counter();comparisons=Counter()
            predictions=Counter();origins=[]
            for i in range(8):
                local=Counter()
                for h in (0,1):
                    for j in range(24):
                        leaf=f'trial-{j:03d}/result.json.gz'
                        r=read(WORK/f'{phase}/o{i}/h{h}/{arm}'/leaf)
                        b=read(WORK/f'{phase}/o{i}/h{h}/baseline'/leaf)
                        kind=r['case']['kind'];assert r['case']==b['case']
                        for window in ('first','second'):
                            group=f'{kind}:{window}';windows[group]+=1
                            for field in FIELDS:
                                key=f'{group}:{field}'
                                values=[frame[node][field] for frame in r[window]['raw'] for node in PORTS]
                                assert len(values)==140
                                nonzero[key]+=sum(v!=0 for v in values)
                                nonzero[key+':windows']+=any(v!=0 for v in values)
                                maxima[key]=max(maxima.get(key,0.),max(values))
                                sums[key]+=sum(values)
                            changed=r[window]['predictions']!=b[window]['predictions']
                            comparisons[group+':category_changed']+=changed
                            comparisons[group+':raw_changed']+=r[window]['raw']!=b[window]['raw']
                            comparisons[group+':logits_changed']+=r[window]['logits']!=b[window]['logits']
                            predictions[group+':'+str(tuple(r[window]['predictions'][x] for x in ('sound','vision','action')))]+=1
                            local[group+':category_changed']+=changed
                            local[group+':n']+=1
                origins.append(dict(origin=i,counts=dict(local)))
            summary[phase+':'+arm]=dict(windows=dict(windows),nonzero_samples_and_windows=dict(nonzero),
                maxima=maxima,sample_sum=dict(sums),comparisons_to_baseline=dict(comparisons),
                prediction_combinations=dict(predictions),origins=origins)
    out=dict(classification='post-design read-only description; no new success criteria or causal isolation claim',
        source='all stored 20-frame first and second answer windows; seven declared output channels',
        notes='Formal readout remains the original 8-frame Transformer. Closed-loop histories can differ after interventions. Exact float changes are not necessarily behavioral changes.',
        summary=summary)
    with (WORK/'activity-diagnostic-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,sort_keys=True)
    print(json.dumps({k:dict(new_first_nonzero_activation_windows=v['nonzero_samples_and_windows']['clear:first:activation:windows'],
        new_first_windows=v['windows']['clear:first'],new_first_category_changed=v['comparisons_to_baseline']['clear:first:category_changed']) for k,v in summary.items()}))


if __name__=='__main__':main()
