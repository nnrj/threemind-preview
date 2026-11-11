"""Inspect pre-probe delayed states and paired immediate scores after completion."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def run(work):
    assert load(work/'independent-audit-v1.json')['passed']
    analysis = load(work/'analysis-v1.json')
    subjects = {s['key']:s for s in analysis['subjects']}
    pairs = {}
    for stage in ('initial','new','reversal','return'):
        differences = []
        for origin in range(8):
            x = subjects[f'o{origin}/weight-slow']['stages'][stage]['scores']['immediate']['total']['accuracy']
            y = subjects[f'o{origin}/matched-slow']['stages'][stage]['scores']['immediate']['total']['accuracy']
            differences.append(x-y)
        pairs[stage] = dict(differences=differences,mean=sum(differences)/8,
                            improved=sum(x>0 for x in differences),tied=sum(x==0 for x in differences),
                            worsened=sum(x<0 for x in differences))
    delayed = []
    for s in analysis['subjects']:
        for stage in ('initial','new','reversal','return'):
            path=work/'subjects'/s['key']/stage/'delay/whole.json.gz'
            value=load(path)
            delayed.append(dict(key=s['key'],curve=s['curve'],stage=stage,time_us=value['core']['time_us'],
                                edges=len(value['core']['edges']),
                                weights=[e['weight'] for e in value['core']['edges']],
                                source=path.relative_to(work).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    result=dict(schema='threemind.r48b-delay-followup/1',retrospective=True,independent_origins=8,
                immediate_slow_minus_matched=pairs,pre_probe_delay_states=delayed,
                interpretation='Eight-origin descriptive paired comparison, no new pass criterion. Delay states precede delayed questioning and therefore do not include its effects.')
    with (work/'delay-readout-followup-v1.json').open('x',encoding='utf8') as f:
        json.dump(result,f,indent=2)
    print(json.dumps(pairs))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    run(p.parse_args().work)
