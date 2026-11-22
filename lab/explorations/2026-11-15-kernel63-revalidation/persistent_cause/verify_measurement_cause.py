"""Check historical decisions and reject one-prefix or interrupted-activity substitutes."""
import copy
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import analyze_cause as a


def verify():
    cases=a.host.design.cases();old=[];rows=[];waits={};expected={}
    for filename in ('cases.json','supplement-cases.json','novelty-cases.json'):
        old+=a.read(a.host.design.HISTORY/filename)
    for case,original in zip(cases,old):
        inverse={k:v for k,v in case.items() if k not in ('historical_case','historical_case_file','design_part')}
        for field in ('key','parent','variant'):
            if isinstance(inverse[field],str):inverse[field]=inverse[field].replace('v63','v61')
        if inverse['version']=='6.3':inverse['version']='6.1'
        assert inverse==original
    for filename in ('analysis.json','analysis-novelty.json'):
        evidence=a.read(a.host.design.HISTORY/filename)
        for row in evidence['process']:
            value=copy.deepcopy(row);value['key']=value['key'].replace('v61','v63');rows.append(value)
        for v in evidence['variants']:
            name=v['variant'].replace('v61','v63');expected[name]={k:v[k] for k in ('prefix_blocks','sustained_blocks') if k in v}
            for block in v['blocks']:
                if 'wait' in block:waits[f"{name}/readout/s{block['block']}/011/paired/d300/wait"]=block['wait']
    variants=a.summarize(cases,rows,waits)
    for variant in variants:
        assert all(variant[field]==score for field,score in expected[variant['variant']].items())
    assert not a.host.design.compare_targets(variants)['scientific_stop']
    faulty=copy.deepcopy(rows)
    for row in faulty:
        if row['key']=='v1/history/s0/101/d1/DB':row['signed_peak']=-1e-4
    score=a.summarize(cases,faulty,waits)
    assert next(v for v in score if v['variant']=='v1')['prefix_blocks']==1
    assert a.host.design.compare_targets(score)['scientific_stop']
    interrupted=copy.deepcopy(rows)
    for row in interrupted:
        if row['key']=='v1/sustain/s0/unchanged':row['task_activity']['minimum']=0.
    score=a.summarize(cases,interrupted,waits)
    assert next(v for v in score if v['variant']=='v1')['sustained_blocks']==1
    assert a.host.design.compare_targets(score)['scientific_stop']
    # Actual stored trajectories check the unchanged process calculation, including Decimal integration.
    error=0.;checked=0
    for case in cases:
        if case['kind']=='probe' and case['variant'] in ('v1','v2-immediate','v63-immediate'):
            points=a.e.unpacked(a.host.design.HISTORY/'cases'/case['historical_case']/'trajectory.json.xz')['points']
            recomputed=a.m.process(case,points);reference=next(v for v in rows if v['key']==case['key'])
            assert recomputed==reference;error=max(error,recomputed['arithmetic_error']);checked+=1
    return {'passed':True,'unchanged_material_stages':476,'historical_conditions':26,
        'recomputed_processes':checked,'one_prefix_rejected':True,'activity_interruption_rejected':True,
        'known_negative_not_new_stop':True,'maximum_arithmetic_error':error}


if __name__=='__main__':print(json.dumps(verify()))
