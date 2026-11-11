"""Dated post-result explanation from committed originals; no Core import."""
import argparse
import gzip
import json
from pathlib import Path


def load(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)


def target(graph, history):
    pair={'cue',f'out{history}'}
    return [e['weight'] for e in graph['edges'] if {e['source_symbol'],e['target_symbol']}==pair]


def diagnostics(work):
    assert load(work/'status.json')==dict(state='awaiting-analysis',sequences_completed=1280)
    groups={}
    for c in load(work/'cases.json'):
        if not c['cue']:
            continue
        folder=work/'subjects'/c['key']
        lesson=load(folder/'teaching/result.json.gz')
        probe=load(folder/'probe/result.json.gz')
        row=groups.setdefault(f"{c['curve']}/{c['course']}/{c['delay']}",dict(formed=[],before_probe=[],empty_target_pairs=0,cohorts=0))
        row['formed'].extend(target(lesson['samples'][-1],c['history']))
        weights=target(probe['before'],c['history'])
        row['before_probe'].extend(weights)
        row['empty_target_pairs']+=not weights
        row['cohorts']+=1
    for row in groups.values():
        for key in ('formed','before_probe'):
            values=row.pop(key)
            row[key+'_range']=[min(values),max(values)] if values else None
    a=load(work/'analysis-v1.json')
    reasons={}
    for c in ('inverse-logarithmic','weight-fast','weight-slow','matched-fast','matched-slow'):
        reasons[c]={}
        for course in ('spaced','strong','novelty'):
            rows=[r['measurements'][course]['expression'] for r in a['details'] if r['curve']==c]
            reasons[c][course]={
                'early_below_floor':sum(r['early_rms']<=1e-4 for r in rows),
                'late_zero':sum(r['late_rms']==0 for r in rows),
                'cosine_below_08':sum(r['cosine']<.8 for r in rows),
                'early_range':[min(r['early_rms'] for r in rows),max(r['early_rms'] for r in rows)],
                'late_range':[min(r['late_rms'] for r in rows),max(r['late_rms'] for r in rows)],
                'cosine_range':[min(r['cosine'] for r in rows),max(r['cosine'] for r in rows)],
            }
    return dict(schema='threemind.r48a-retrospective-diagnostics/1',post_result=True,groups=groups,expression_reasons=reasons,scope='Explanation only; preregistered scores remain unchanged.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
    result=diagnostics(w)
    with (w/'retrospective-diagnostics-v1.json').open('x',encoding='utf-8') as f: json.dump(result,f,indent=2)
    print(json.dumps(result))
