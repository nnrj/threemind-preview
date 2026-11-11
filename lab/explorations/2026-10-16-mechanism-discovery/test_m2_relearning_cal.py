import copy
import sys
from pathlib import Path

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import closure_rig as g
import m2_relearning_cal_analyze as a
import m2_relearning_cal_spec as s
from m2_relearning_cal_driver import lesson
from m2_relearning_cal_audit import check_probe


def synthetic(firsts):
    results=[]
    for case in s.cases():
        branches=[]
        for dose, first in zip(s.DOSES, firsts):
            for history in (0,1):
                branches.append({'dose':dose,'history':history,'baseline':{'first':0.},'lessons':[
                    {'probe':{'first':(1 if history==0 else -1)*(.01 if j>=first else 0.)}}
                    for j in range(1,s.LESSONS+1)]})
        results.append({'origin':case['origin'],'case':case,'branches':branches})
    return results


def test_floor_ceiling_and_already_correct_do_not_pass():
    r=synthetic([1,17,13,1]); assert a.summarize(r)['verdict']=='FAIL'
    r=synthetic([3,17,17,17])
    for item in r:
        for branch in item['branches']:
            branch['baseline']['first']=.01 if branch['history']==0 else -.01
    assert a.summarize(r)['verdict']=='FAIL'


def test_lowest_eligible_dose_and_all_curves_are_kept():
    result=a.summarize(synthetic([17,6,3,1]))
    assert result['selected_lesson_dose']==.20 and len(result['dose_results'])==4
    assert result['scientific_savings_effect_tested'] is False
    assert result['old_closure_scores_changed'] is False


def test_both_histories_and_six_independent_sources_required():
    r=synthetic([4,17,17,17])
    for item in r[:2]:
        item['branches'][1]['lessons'][-4:]=[{'probe':{'first':0.}} for _ in range(4)]
    assert a.summarize(r)['verdict']=='PASS'
    r[2]['branches'][1]['lessons'][-4:]=[{'probe':{'first':0.}} for _ in range(4)]
    assert a.summarize(r)['verdict']=='FAIL'


def test_fresh_sources_and_instrument_sources_separate():
    seeds={c['seed'] for c in s.cases()}
    assert len(seeds)==8 and not seeds & {s.APPARATUS_SEED,s.TEST_SEED}
    assert not seeds & set(range(1016100,1016108))


def test_instrument_equivalence_continuity_and_answer_isolation():
    parent=g.Rig('threemind',s.TEST_SEED,'S')
    g.teaching(parent,0,delay=s.DELAY_SECONDS,trained=False)
    saved=parent.save(); hashes=[]
    for mode in ('plain','observed','restored','paused'):
        child=parent.fork('instrument')
        start=child.save(); baseline=g.probe(child,'X',s.PROBE_DOSE)
        before=child.save(); check_probe(start,before,baseline)
        row=lesson(child,0,.20,frequent=mode=='observed',restore_mid=mode=='restored',pause_mid=mode=='paused')
        whole=child.save(); check_probe(before,whole,row['probe'],history=0,dose=.20)
        hashes.append(row['probe']['final_sha256'])
        corrupt=copy.deepcopy(whole); corrupt['inputs'][-2]['values']['A']=.1
        with pytest.raises(AssertionError):check_probe(before,corrupt,row['probe'],history=0,dose=.20)
    assert len(set(hashes))==1 and parent.save()==saved
