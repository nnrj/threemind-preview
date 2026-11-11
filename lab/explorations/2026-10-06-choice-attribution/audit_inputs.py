"""One bounded check of all request frames, not repeated evidence hashing."""
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.service_study import read_json,new_json
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/choice-attribution-20261006'


def requests(key):
    with gzip.open(WORK/'cases'/key/'process.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line)
            yield row['trial']['text'],[r['stimulus'] for r in row['process']]


def check_state_edits():
    """Check exactly the claimed causal intervention, once; no file hashes."""
    def read_state(key):
        with gzip.open(WORK/'cases'/key/'checkpoint.json.gz','rt',encoding='utf-8') as stream:
            return json.load(stream)
    sources=[read_state(f'B-s223-p1-h{h}-teach') for h in (0,1)]
    checked=[]
    for h in (0,1):
        source=sources[h];before={n['channel']:n for n in source['core']['nodes']}
        donor={n['channel']:n for n in sources[1-h]['core']['nodes']}
        for mode in ('clear-marker','swap-marker','swap-body'):
            key=f'F-s223-h{h}-{mode}'
            after=read_state(key);nodes={n['channel']:n for n in after['core']['nodes']}
            receipt=read_json(WORK/'cases'/key/'receipt.json')
            for change in receipt:
                c=change['channel'];expected=0. if mode=='clear-marker' else donor[c]['activation']
                if change['before']!=before[c]['activation'] or change['after']!=expected or nodes[c]['activation']!=expected:
                    raise ValueError('activation intervention receipt mismatch: '+key)
                nodes[c]['activation']=change['before']  # restore in temporary RAM only
            if after!=source:raise ValueError('unregistered state change: '+key)
            checked.append({'case':key,'selected_nodes':len(receipt),
                            'changed_values':sum(r['before']!=r['after'] for r in receipt),
                            'sum_absolute_activation_change':sum(abs(r['before']-r['after']) for r in receipt),
                            'all_other_saved_fields_identical':True})
    return checked


def main():
    pairs=[]
    for seed in (223,279):
        for p in (0,1):
            for split in ('train','test'):
                names=[f'B-s{seed}-p{p}-h{h}-teach-{split}-normal' for h in (0,1)]
                if all((WORK/'cases'/n/'result.json').exists() for n in names):pairs.append(names)
        names=[f'B-s{seed}-{branch}-test-normal' for branch in ('continue','reverse')]
        if all((WORK/'cases'/n/'result.json').exists() for n in names):pairs.append(names)
    results=[]
    # This check is consequential: a claimed state intervention must not also
    # change the actual stimulus. Read each relevant tape once and cache it.
    for h in (0,1):
        baseline=f'B-s223-p1-h{h}-teach-test-normal'
        for mode in ('silence-target','silence-matched','rescue','transfer-target','transfer-matched'):
            name=f'B-s223-p1-h{h}-teach-test-{mode}'
            if (WORK/'cases'/name/'result.json').exists():pairs.append([baseline,name])
        for mode in ('clear-marker','swap-marker','swap-body'):
            name=f'F-s223-h{h}-{mode}-test-normal'
            if (WORK/'cases'/name/'result.json').exists():pairs.append([baseline,name])
    tapes={name:list(requests(name)) for name in {n for pair in pairs for n in pair}}
    for a,b in pairs:
        left=tapes[a];right=tapes[b]
        if len(left)!=len(right) or any(x!=y for x,y in zip(left,right)):
            raise ValueError('current input mismatch: '+a+' vs '+b)
        results.append({'left':a,'right':b,'pairs':len(left),
                        'frames_compared':sum(len(row[1]) for row in left),'all_identical':True})
    result={'method':'single comparison of complete delivered stimulus dictionaries and query text; no metadata-derived answer',
            'pairs':results,'state_edit_checks':check_state_edits()}
    new_json(HERE/'input-audit.json',result);print(json.dumps(result))


if __name__=='__main__':main()
