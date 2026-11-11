"""Non-simulation checks; unseen diagnostic doses are not exercised here."""
import copy
import math
import pytest
from m2_threshold_predictor import recovered_fraction
from m2_threshold_analyze import score
import m2_threshold_rig as s


def test_short_term_recovery_conserves_resource():
    c={'stp_utilization':.5,'stp_facilitation_tau_s':0.,'stp_active_tau_s':.003,'stp_recovery_tau_s':.8}
    empty={'available':0.,'active':0.,'utilization':.5,'time_us':'0'}
    assert recovered_fraction(empty,0,c)==0
    assert recovered_fraction(empty,100000,c)==pytest.approx(.5*(1-math.exp(-.1/.8)))
    full={**empty,'available':1.}
    assert recovered_fraction(full,100000,c)==.5
    active={**empty,'active':1.}
    assert 0<recovered_fraction(active,100000,c)<recovered_fraction(empty,100000,c)


def synthetic():
    histories=[]
    for h in (0,1):
        rows=[];sign=1-2*h
        for d in s.DELAYS:
            for arm in s.ARMS:
                doses=s.CAUSAL_DOSES+s.NOVEL_DOSES if arm=='intact' else s.CAUSAL_DOSES
                for q in doses:
                    direction=sign if q>.6 or (q==.55 and arm=='target-full') else 0
                    if arm=='target-empty':direction=0
                    rows.append({'delay':d,'arm':arm,'dose':q,'novel':q in s.NOVEL_DOSES,
                                 'probe':{'direction':direction,'first':direction*.01},'prediction':{'direction':direction}})
        histories.append({'history':h,'tests':rows})
    return {'origin':0,'histories':histories}


def test_scores_require_both_complete_targets():
    data=synthetic();row=score(data);assert row['P1'] and row['P2']
    wrong=copy.deepcopy(data)
    r=next(x for x in wrong['histories'][0]['tests'] if x['novel']);r['prediction']['direction']=7
    assert not score(wrong)['P1'] and score(wrong)['P2']
    failed=copy.deepcopy(data)
    r=next(x for x in failed['histories'][1]['tests'] if x['delay']==0 and x['arm']=='target-full' and x['dose']==.55)
    r['probe']['first']=0.;r['probe']['direction']=0
    assert not score(failed)['P2']


def test_source_and_probe_counts():
    assert len(set(s.SEEDS))==8 and not set(s.SEEDS)&{s.APPARATUS_SEED,s.TEST_SEED}
    assert len(s.NOVEL_DOSES)==4 and not set(s.NOVEL_DOSES)&set(s.CAUSAL_DOSES)
    row=score(synthetic());assert len(row['all_predictions'])==88 and len(row['novel_predictions'])==16
