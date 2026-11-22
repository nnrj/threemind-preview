"""Retrospective development on already delivered R63g records; never a test cohort."""
import gzip
import json
from pathlib import Path
from predict_first import predict

WORK=Path('E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/transfer-63-rerun-v1')


def check():
    assert json.loads((WORK/'publication/completion.json').read_bytes())['pending']==0
    rows=[]
    for origin in range(8):
        folder=WORK/'units'/f'o{origin}'
        result=json.loads((folder/'result.json').read_bytes())
        for h in (0,1):
            parent=json.loads(gzip.decompress((folder/f'parent-h{h}.json.gz').read_bytes()))
            for cue in ('X','Y','Z','W'):
                predicted=predict(parent,cue,.8)
                trial=next(t for t in result['trials'] if t['history']==h and t['arm']=='intact' and t['cue']==cue)
                observed=trial['result']['first']
                rows.append({'origin':origin,'history':h,'cue':cue,'predicted':predicted['endpoint'],
                             'observed':observed,'error':abs(predicted['endpoint']-observed),
                             'direction_matches':predicted['direction']==trial['result']['choice']})
    return {'phase':'retrospective formula development, not a preregistered prediction test',
            'Core_engines_created':0,'origins':8,'responses':len(rows),'maximum_error':max(r['error'] for r in rows),
            'directions_correct':sum(r['direction_matches'] for r in rows),'rows':rows}


if __name__=='__main__':
    result=check()
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
