"""Frozen M4 source-level decisions; incomplete behavioral baselines are explicit."""
import argparse,json
from pathlib import Path
from scipy.stats import beta
import pilot_m2 as m


def evaluate(units):
    assert len(units)==8 and {u['origin'] for u in units}==set(range(8)) and all(u['valid'] for u in units)
    goals={};eligible=sum(u['causal_eligible'] for u in units)
    for key in ('G1','G2','G3'):
        k=sum(u[key]['qualified'] for u in units)
        goals[key]={'qualified':k,'independent_origins':8,'verdict':'PASS' if k>=6 else 'FAIL',
                    'exact95':[0 if k==0 else float(beta.ppf(.025,k,9-k)),1 if k==8 else float(beta.ppf(.975,k+1,8-k))]}
    if eligible<6:goals['G3']['verdict']='INSUFFICIENT_VALID_BASELINES'
    return {'schema':'threemind.m4-balanced-analysis/1','valid':True,'independent_origins':8,
            'verdict':'PASS' if all(g['verdict']=='PASS' for g in goals.values()) else 'TARGET_NOT_MET',
            'goals':goals,'causal_eligible_origins':eligible,'units':units,
            'scope':'balanced 255s course, declared selected groups and fixed-reader causal copies; no population or other architecture ranking'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);w=p.parse_args().work.resolve()
    m.frozen_check(w);assert m.read(w/'status.json')['state']=='awaiting-analysis'
    assert not any((w/n).exists() for n in ('STOP','in-flight.json'))
    result=evaluate([m.read(w/'units'/f'o{i}'/'result.json') for i in range(8)])
    m.original(w/'analysis-v1.json',result);print(json.dumps({k:v for k,v in result.items() if k!='units'}))
