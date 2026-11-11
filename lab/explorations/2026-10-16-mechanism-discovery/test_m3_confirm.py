import copy
import sys
from pathlib import Path

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import closure_rig as g
import m3_confirm_spec as s
from m3_confirm_analyze import evaluate
from m3_confirm_audit import exact_p,check_probe,check_world


def fixture_scores():
    patterns={'reactive':[False]*4,'finite-state':[True,True,False,False],
              'hebbian':[True,True,False,True],'fixed-rnn-reader':[True,False,True,True],
              'threemind':[True]*4}
    return [{'origin':i,'case':s.cases()[i],'scores':{k:{'passes':p.copy(),'matching_valid':True,'replay_valid':True}
             for k,p in patterns.items()}} for i in range(s.N)]


def test_new_origins_exclude_previous_sources_and_instruments():
    cases=s.cases();assert len(cases)==len({c['seed'] for c in cases})==64
    assert all(g.case_seed('X3',c['rig_origin'])==c['seed'] for c in cases)
    assert not {c['seed'] for c in cases}&(set(range(1036100,1036108))|{s.APPARATUS_SEED,s.TEST_SEED})


def test_complete_goal_closes_and_counterexample_cannot_be_hidden():
    rows=fixture_scores();result=evaluate(rows)
    assert result['verdict']=='PASS'
    assert all(v['exact_two_sided_p']==pytest.approx(2**-63) for v in result['paired_comparisons'].values())
    for row in rows:row['scores']['finite-state']['passes']=[True]*4
    result=evaluate(rows)
    assert result['verdict']=='FAIL' and result['cohort_counterexamples']==['finite-state']
    assert result['paired_comparisons']['finite-state']['exact_two_sided_p']==1


def test_invalid_matching_is_not_a_comparator_failure():
    rows=fixture_scores();rows[0]['scores']['fixed-rnn-reader']['matching_valid']=False
    report=evaluate(rows)
    assert report['verdict']=='INVALID'
    assert report['systems']['fixed-rnn-reader']['criterion_verdicts'][1]=='INVALID'
    assert exact_p(8,2)==pytest.approx(.109375)


@pytest.mark.parametrize('kind',s.KINDS)
def test_whole_state_observer_pause_restore_and_actual_loop_equations(kind):
    parent=g.Rig(kind,s.TEST_SEED);g.teaching(parent,0);saved=parent.save();hashes=[]
    for mode in ('plain','observed','restored','paused'):
        child=g.Rig.restore(saved)
        result=g.probe(child,'X',second='Y',frequent=mode=='observed',restore_mid=mode=='restored',pause_mid=mode=='paused')
        check_probe(saved,child.save(),result,'X','Y');hashes.append(result['final_sha256'])
    assert len(set(hashes))==1 and parent.save()==saved
    ring=g.Rig(kind,s.TEST_SEED);ring.tick(0,{'K':.2});start=ring.save()
    world=g.ring_stage(ring,'P');check_world(start,ring.save(),world)
    wrong=copy.deepcopy(world);wrong['input_frames'][0]['values']['X']+=.1
    with pytest.raises(AssertionError):check_world(start,ring.save(),wrong)


def test_saved_five_system_instrument_fixture_passes_full_independent_audit(monkeypatch):
    import uuid
    import m3_confirm_driver as driver
    import m3_confirm_analyze as analysis
    import m3_confirm_audit as audit
    import pilot_m2 as m
    work=Path(__file__).resolve().parents[3]/'.work'/('m3-instrument-audit-'+uuid.uuid4().hex)
    work.mkdir(parents=True)
    (work/'INSTRUMENT_ONLY.txt').write_text('Isolated instrument seed; excluded from all scientific N. No historical originals touched.',encoding='utf-8')
    monkeypatch.setattr(s,'N',1)
    monkeypatch.setattr(s,'SEED_START',s.TEST_SEED)
    monkeypatch.setattr(s,'RIG_ORIGIN_OFFSET',s.TEST_SEED-1036100)
    # This fixture has no registered frozen package. Formal batches retain the real check.
    monkeypatch.setattr(m,'frozen_check',lambda _:None)
    m.original(work/'cases.json',s.cases())
    m.original(work/'status.json',{'state':'awaiting-analysis'})
    result=driver.unit(work/'units/o0',0)
    m.original(work/'units/o0/result.json',result)
    analysis.analyze(work)
    audit.audit(work)
    report=m.read(work/'audit-v1.json')
    assert report['passed'] and report['counts']['whole_snapshots']==530
