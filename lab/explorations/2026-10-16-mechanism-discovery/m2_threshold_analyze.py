"""Frozen P1/P2 arithmetic on saved diagnostic results only."""
import argparse,json
from pathlib import Path
from scipy.stats import beta
import m2_threshold_rig as spec
import pilot_m2 as m


def score(raw):
    predictions=[];histories=[];allrows=[]
    for h in raw['histories']:
        sign=1-2*h['history'];cells={(r['delay'],r['arm'],r['dose']):r for r in h['tests']}
        def value(delay,arm,dose):return cells[delay,arm,dose]['probe']['first']
        for r in h['tests']:
            row={'history':h['history'],'delay':r['delay'],'arm':r['arm'],'dose':r['dose'],
                 'predicted':r['prediction']['direction'],'actual':r['probe']['direction'],
                 'correct':r['prediction']['direction']==r['probe']['direction'],'first':r['probe']['first']}
            allrows.append(row)
            if r['novel']:predictions.append(row)
        conditions={'intact_mid_silent':sign*value(0,'intact',.55)<=1e-4,
                    'target_full_rescues_mid':sign*value(0,'target-full',.55)>1e-4,
                    'matched_full_preserves_mid':abs(value(0,'matched-full',.55)-value(0,'intact',.55))<=1e-9,
                    'intact_strong_expresses':sign*value(0,'intact',.8)>1e-4,
                    'target_empty_suppresses_strong':abs(value(0,'target-empty',.8))<=.25*abs(value(0,'intact',.8)),
                    'matched_empty_preserves_strong':abs(value(0,'matched-empty',.8)-value(0,'intact',.8))<=1e-9,
                    'blank_absent':all(abs(value(d,arm,0.))<=1e-4 for d in spec.DELAYS for arm in spec.ARMS),
                    'restoration_exact':all(abs(value(d,'restored',q)-value(d,'intact',q))<=1e-9 for d in spec.DELAYS for q in (.55,.8))}
        histories.append({'history':h['history'],'conditions':conditions,'passed':all(conditions.values()),
                          'mid_resource_gain':sign*(value(0,'target-full',.55)-value(0,'intact',.55)),
                          'strong_depletion_loss':sign*(value(0,'intact',.8)-value(0,'target-empty',.8))})
    assert len(predictions)==16 and len(allrows)==88
    accuracy=sum(x['correct'] for x in predictions)/len(predictions)
    classes={x['actual']==0 for x in predictions}
    return {'origin':raw['origin'],'P1':accuracy>=.95 and len(classes)==2,'P2':all(x['passed'] for x in histories),
            'novel_accuracy':accuracy,'novel_predictions':predictions,'histories':histories,'all_predictions':allrows}


def evaluate(units):
    assert len(units)==spec.N and {x['origin'] for x in units}==set(range(spec.N))
    goals={}
    for name in ('P1','P2'):
        k=sum(x[name] for x in units);n=len(units)
        goals[name]={'qualified':k,'n':n,'verdict':'PASS' if k>=6 else 'FAIL',
                     'exact95':[0 if k==0 else float(beta.ppf(.025,k,n-k+1)),1 if k==n else float(beta.ppf(.975,k+1,n-k))]}
    return {'schema':'threemind.m2-threshold-analysis/1','valid':True,
            'verdict':'PASS' if all(x['verdict']=='PASS' for x in goals.values()) else 'FAIL',
            'goals':goals,'independent_origins':len(units),'units':units,
            'novel_predictions':sum(len(x['novel_predictions']) for x in units),
            'novel_correct':sum(sum(y['correct'] for y in x['novel_predictions']) for x in units),
            'all_predictions':sum(len(x['all_predictions']) for x in units),
            'all_correct':sum(sum(y['correct'] for y in x['all_predictions']) for x in units)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
    assert m.read(w/'status.json')['state']=='awaiting-analysis'
    units=[]
    for case in spec.cases():
        raw=m.read(w/'units'/f'o{case["origin"]}'/'result.json');assert raw['case']==case
        units.append(score(raw))
    result=evaluate(units);m.original(w/'analysis-v1.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='units'}))
