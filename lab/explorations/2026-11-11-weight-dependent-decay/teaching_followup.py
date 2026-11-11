"""Retrospective course diagnostics from completed R48a originals, without Core."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def load(p):
    raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)


def run(work):
    completion=load(work/'publication/completion.json')
    assert completion['execution_status']=='completed' and completion['pending']==0
    details=[]
    for case in load(work/'cases.json'):
        if case['course']!='spaced' or case['delay']!=1 or not case['cue']:
            continue
        path=work/'subjects'/case['key']/'teaching/result.json.gz'
        data=load(path); rows=[]
        for sample in data['samples']:
            edges=[e for e in sample['edges'] if e['source_symbol']=='cue' and e['target_symbol']==f"out{case['history']}" ]
            assert len(edges)==1
            e=edges[0]
            rows.append(dict(weight=e['weight'],birth_us=e['birth_us'],state_us=e['state_us'],touches=e['touches']))
        assert len(rows)==8
        changed=sum(a['birth_us']!=b['birth_us'] for a,b in zip(rows,rows[1:]))
        details.append(dict(origin=case['origin'],rule=case['curve'],history=case['history'],recreations_observed=changed,samples=rows,source=path.relative_to(work).as_posix(),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    summary=[]
    for rule in ('inverse-logarithmic','weight-fast','weight-slow','matched-fast','matched-slow'):
        found=[r for r in details if r['rule']==rule]
        assert len(found)==16
        counts=[sum(r['recreations_observed'] for r in found if r['origin']==o) for o in range(8)]
        summary.append(dict(rule=rule,independent_origins=8,origins_with_observed_recreation=sum(x>0 for x in counts),paired_history_recreation_counts=counts,last_weight_range=[min(r['samples'][-1]['weight'] for r in found),max(r['samples'][-1]['weight'] for r in found)],teaching_peak_weight_range=[min(max(s['weight'] for s in r['samples']) for r in found),max(max(s['weight'] for s in r['samples']) for r in found)]))
    return dict(schema='threemind.r48-teaching-followup/1',post_result=True,parent_record=completion['record'],parent_archive_sha256=completion['archive_sha256'],question='Did successive spaced lessons strengthen a persisting connection, or were target connections naturally deleted and recreated?',method='Compare directed cue-to-target birth timestamps at eight post-lesson snapshots; two opposing teaching histories per origin; no new simulation, no score change.',summary=summary,details=details)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=run(args.work)
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result['summary']))
