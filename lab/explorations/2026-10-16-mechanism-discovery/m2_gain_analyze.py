"""Frozen new-material prediction scores, not a revision of M2 threshold P1."""
import argparse,json
from pathlib import Path
from scipy.stats import beta
import m2_gain_rig as spec
import pilot_m2 as m


def score(raw):
    rows=[r for h in raw['histories'] for r in h['tests']]
    assert len(rows)==20
    correct=sum(r['prediction']['direction']==r['probe']['direction'] for r in rows)
    error=max(abs(r['prediction']['endpoint']-r['probe']['first']) for r in rows)
    classes={r['probe']['direction']==0 for r in rows if r['dose']>0}
    return {'origin':raw['origin'],'qualified':correct==20 and error<=1e-6 and len(classes)==2,
            'correct':correct,'n':len(rows),'maximum_absolute_error':error,
            'both_nonblank_expression_classes':len(classes)==2,
            'old_predictor_correct':sum(r['comparison']['direction']==r['probe']['direction'] for r in rows)}


def evaluate(units):
    assert len(units)==8 and {r['origin'] for r in units}==set(range(8))
    k=sum(r['qualified'] for r in units)
    return {'schema':'threemind.m2-gain-prediction-analysis/1','valid':True,'verdict':'PASS' if k>=6 else 'FAIL',
            'independent_origins':8,'qualified':k,'exact95':[0 if k==0 else float(beta.ppf(.025,k,9-k)),1 if k==8 else float(beta.ppf(.975,k+1,8-k))],
            'correct':sum(r['correct'] for r in units),'predictions':160,'maximum_absolute_error':max(r['maximum_absolute_error'] for r in units),
            'old_predictor_correct':sum(r['old_predictor_correct'] for r in units),'units':units}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);w=p.parse_args().work
    assert m.read(w/'status.json')['state']=='awaiting-analysis'
    units=[]
    for c in spec.cases():
        raw=m.read(w/'units'/f'o{c["origin"]}'/'result.json');assert raw['case']==c;units.append(score(raw))
    result=evaluate(units);m.original(w/'analysis-v1.json',result);print(json.dumps(result))
