"""Post-design error description from saved answers; no subject is loaded."""
from collections import Counter
import gzip
import json
from pathlib import Path

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1')

def main():
    assert json.loads((WORK/'status.json').read_text('utf-8'))==dict(state='awaiting-analysis',branches_completed=112)
    summary={}
    for phase,arms in [('late',['baseline','target','matched','all']),('early',['baseline','target','all'])]:
        for arm in arms:
            confusion=Counter();new=0;mixed=0;view=0
            for p in (WORK/phase).glob(f'o*/h*/{arm}/trial-*/result.json.gz'):
                r=json.loads(gzip.decompress(p.read_bytes()))
                if r['case']['kind']=='clear':
                    confusion[f"{r['case']['expected']}->{r['first']['predictions']['action']}"]+=1;new+=1
                elif r['case']['kind']=='ambiguous':
                    mixed+=1;view+=r['first']['predictions']['action']==2
            assert new==128 and mixed==192
            summary[phase+':'+arm]=dict(new_cue_expected_to_observed_action=dict(confusion),new_cue_n=new,
                new_cue_view=sum(v for k,v in confusion.items() if k.endswith('->2')),mixed_cue_view=view,mixed_cue_n=mixed)
    out=dict(classification='post-design description of action errors; not a new primary outcome or a changed success criterion',
        action_codes={'0':'exit 0','1':'exit 1','2':'view'},summary=summary)
    with (WORK/'action-diagnostic-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,sort_keys=True)
    print(json.dumps(out))

if __name__=='__main__':main()
