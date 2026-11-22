"""Retain all 476 registered historical stages; change only the current-version arm."""
from copy import deepcopy
import json
from pathlib import Path

HISTORY=Path('E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/persistent-activity61-v1')
ARMS=('unchanged','depletion-on','facilitation-off','both','consolidation-off')


def renamed(value):
    return value.replace('v61','v63') if isinstance(value,str) else value


def cases():
    output=[]
    for filename,part in [('cases.json','initial'),('supplement-cases.json','retention-controls'),
                          ('novelty-cases.json','novelty-timing')]:
        for old in json.loads((HISTORY/filename).read_bytes()):
            case=deepcopy(old)
            for field in ('key','parent','variant'):case[field]=renamed(case.get(field))
            if case['version']=='6.1':case['version']='6.3'
            case.update(historical_case=old['key'],historical_case_file=filename,design_part=part)
            output.append(case)
    assert len(output)==476
    seen=set()
    for case in output:
        assert case['parent'] is None or case['parent'] in seen
        assert case['key'] not in seen;seen.add(case['key'])
    return output


def compare_targets(variants):
    historical=[]
    for filename in ('analysis.json','analysis-novelty.json'):
        historical+=json.loads((HISTORY/filename).read_bytes())['variants']
    old={renamed(v['variant']):v for v in historical};lost=[];comparisons=[]
    assert set(old)=={v['variant'] for v in variants}
    for v in variants:
        prior=old[v['variant']]
        for field in ('prefix_blocks','sustained_blocks'):
            if field not in prior:continue
            row={'variant':v['variant'],'measure':field,'historical':prior[field],'new':v[field]}
            comparisons.append(row)
            if prior[field]==2 and v[field]<2:lost.append(row)
    return {'comparisons':comparisons,'newly_lost_positive_conditions':lost,'scientific_stop':bool(lost),
        'known_negative_conditions_are_not_new_contradictions':True}
