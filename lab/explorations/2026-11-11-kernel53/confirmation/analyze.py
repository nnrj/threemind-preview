"""Frozen R47b confirmatory arithmetic, with exploratory samples excluded."""
import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import t

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
spec=importlib.util.spec_from_file_location('r47a_readonly',HERE.parent/'analyze.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
CURVES=('exponential','power-law','inverse-logarithmic','power-exponential')
COURSES=('massed','spaced','strong')


def comparison(delta):
    n=len(delta);mean=float(np.mean(delta));sd=float(np.std(delta,ddof=1));se=sd/math.sqrt(n)
    critical=float(t.ppf(1-.05/3,n-1))
    if se:
        statistic=mean/se;p=float(t.sf(statistic,n-1));lower=mean-critical*se
    else:
        statistic=None;p=2.**(-n) if mean>0 else 1.;lower=None
    return dict(n=n,mean_difference=mean,sd_difference=sd,standard_error=se,t=statistic,p_one_sided=p,
                bonferroni_lower=lower,positive_origins=sum(x>0 for x in delta),ties=sum(x==0 for x in delta),
                significant=p<.05/3,paired_standardized_effect=mean/sd if sd else None,
                zero_variance=sd==0,method='paired t' if se else 'exact sign, zero-variance fallback')


def analyze(work):
    cases=old.load(work/'cases.json');status=old.load(work/'status.json')
    assert status==dict(state='awaiting-analysis',sequences_completed=5376) and len(cases)==5376
    rows={}
    for c in cases:
        p=work/'subjects'/c['key']/'probe/result.json.gz'
        rows[c['origin'],c['curve'],c['course'],c['delay'],c['history'],c['cue']]=old.load(p)
    def vector(o,c,course,delay):
        both=[]
        for h in (0,1):
            a=rows[o,c,course,delay,h,True];b=rows[o,c,course,delay,h,False]
            assert a['before']==b['before']
            both.append([x-y for x,y in zip(old.vector(a),old.vector(b))])
        return [x-y for x,y in zip(both[1],both[0])]
    details=[]
    for o in range(48):
        for c in CURVES:
            goals={};measurements={}
            for course in COURSES:
                expr=old.expression(vector(o,c,course,1),vector(o,c,course,300))
                edges=[old.target_edges(rows[o,c,course,300,h,True]['before'],h) for h in (0,1)]
                goals['S:'+course]=all(len(es)==2 for es in edges)
                goals['E:'+course]=expr['passed']
                goals['F:'+course]=all(old.tail_weight(e,c)<.008 for es in edges for e in es)
                measurements[course]=expr
            goals['W']=all(not old.target_edges(rows[o,c,'weak',30,h,True]['before'],h) for h in (0,1))
            details.append(dict(origin=o,curve=c,goals=goals,measurements=measurements,
                                mean_late_rms=sum(measurements[k]['late_rms'] for k in COURSES)/3))
    summary=[]
    for c in CURVES:
        entries=[d for d in details if d['curve']==c]
        scores={k:dict(passed=sum(d['goals'][k] for d in entries),n=48) for k in entries[0]['goals']}
        for score in scores.values():
            score.update(wilson95=old.interval(score['passed'],48),target_met=score['passed']>=36)
        summary.append(dict(curve=c,scores=scores,combined_candidate=all(v['target_met'] for v in scores.values())))
    by={(d['origin'],d['curve']):d['mean_late_rms'] for d in details}
    comparisons={c:comparison([by[o,'inverse-logarithmic']-by[o,c] for o in range(48)]) for c in CURVES if c!='inverse-logarithmic'}
    return dict(schema='threemind.r47b-analysis/1',independent_origins=48,sequences=5376,
                exploratory=False,primary_comparisons=comparisons,summary=summary,details=details,
                scope='Independent confirmation of local retention; personal learned adapters are a separate layer')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    result=analyze(a.work)
    with (a.work/'analysis-v1.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='details'}))
