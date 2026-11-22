"""Post-run descriptive comparison with the original E22 scores; no Core."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_reference as x


def compare(work):
    assert x.read(work/'audit.json')['passed']
    source=x.spec.OLD/'final.json';old=x.read(source);current=x.read(work/'analysis.json')
    lookup={r['keys'][0]:r for r in old['pairs'] if r['family'] in ('timing','jitter','reference')}
    rows=[]
    for new in current['scores']['contrasts']:
        key=new['parent']['key']+f"/wait{new['delay_s']}/cue{new['cue']}"
        prior=lookup[key]
        assert prior['seed']==new['parent']['seed'] and prior['family']==new['parent']['family']
        rows.append({'key':key,'family':prior['family'],'old_pass':prior['bidirectional_1e6'],
                     'new_pass':new['bidirectional'],'old_margins':prior['margins'],
                     'new_margins':[r['recency'] for r in new['responses']],
                     'old_primacy':prior['bidirectional_1e6'] and max(prior['margins']) < -1e-6,
                     'new_recency':new['recency']})
    assert len(rows)==len(lookup)==176
    groups={}
    for family in ('timing','jitter','reference'):
        selected=[r for r in rows if r['family']==family]
        groups[family]={'total':len(selected),'old_positive':sum(r['old_pass'] for r in selected),
            'new_positive':sum(r['new_pass'] for r in selected),
            'gained':sum(r['new_pass'] and not r['old_pass'] for r in selected),
            'lost':sum(r['old_pass'] and not r['new_pass'] for r in selected),
            'primacy_to_recency':sum(r['old_primacy'] and r['new_recency'] for r in selected)}
    result={'interpretation':'post-run descriptive comparison; original criteria unchanged',
            'old_source':str(source),'old_sha256':x.s.sha(source),'new_analysis_sha256':x.s.sha(work/'analysis.json'),
            'created_engines':0,'groups':groups,'rows':rows}
    x.s.base.original(work/'postprocessing/historical-comparison.json',result)
    print(json.dumps(groups),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    compare(p.parse_args().work.resolve())
