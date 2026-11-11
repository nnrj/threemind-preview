import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import closure_analyze as a
import closure_rig as g


@pytest.fixture(scope='module')
def parents():
    p,q=g.Rig('threemind',1016000),g.Rig('threemind',1016000)
    g.teaching(p,0);g.teaching(q,1);g.settle(p);g.settle(q)
    return p,q


def test_transplant_preserves_non_target_state_and_parent(parents):
    p,q=parents; originals=[p.save(),q.save()]
    child,receipt=g.transfer(p,q)
    assert receipt['changed_paths']
    assert set(receipt['changed_paths'])<= {'model.edges','model.timers'}
    assert g.Rig.restore(child.save()).save()==child.save()
    assert [p.save(),q.save()]==originals
    restored,_=g.transfer(child,p)
    assert restored.save()==p.save()


def test_refuse_different_time_and_queued_packets(parents):
    p,q=parents
    later=q.fork('instrument-only');later.tick(q.time+1000)
    with pytest.raises(ValueError):g.transfer(p,later)
    queued=q.fork('instrument-only')
    queued.model.inject(g.m.Stimulus(q.time+1000,((q.channels['X'],.8),),1.))
    with pytest.raises(ValueError):g.transfer(p,queued)


def test_fast_package_cannot_replace_topology_or_slow_weights(parents):
    p,q=parents;c,_=g.transfer(p,q,mode='fast')
    before,after=p.save()['model'],c.save()['model']
    fields=('source','target','weight','stability','half_life','state_us')
    assert [[e[k] for k in fields] for e in before['edges']]==[[e[k] for k in fields] for e in after['edges']]
    assert before['timers']==after['timers']


def test_x1_requires_behavior_specificity_and_not_just_transplant_effect():
    results=[]
    for o in range(8):
        trials=[]
        for arm in ('intact','sham','target-bundle','matched-bundle','persistent','fast','restored'):
            for cue in ('X','Y','XY','Z','W','ZW'):
                success=(arm in ('target-bundle','persistent')) if cue in ('X','Y','XY') else True
                trials.append({'arm':arm,'cue':cue,'success':success})
        results.append({'origin':o,'valid':True,'trials':trials})
    assert a.x1(results)['verdict']=='PASS'
    damaged=copy.deepcopy(results)
    for r in damaged:
        for t in r['trials']:
            if t['arm']=='target-bundle' and t['cue'] in ('Z','W','ZW'):t['success']=False
    assert a.x1(damaged)['verdict']=='FAIL'
