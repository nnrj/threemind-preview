import copy
import math

from lab.tools.ocean_behavior import BehaviorOcean,scene,observe,select_region
from lab.tools.ocean_contact import ContactProtocol
from dataclasses import asdict


def source():
    w=BehaviorOcean(ContactProtocol(founders=1,founder_variation=0,nutrient_initial=2).model_dump(by_alias=True))
    for _ in range(10):w.step()
    return w,w.engines[0].capture_state(),asdict(w.bodies[0])


def test_exterior_controls_and_ledger_leave_normal_output_unchanged(tmp_path):
    original,image,body=source();before=image.payload
    a=scene(original.p.model_dump(by_alias=True),image,body,task='hunt',bearing=math.pi/2,seed=311,
            operation='intact')
    b=scene(original.p.model_dump(by_alias=True),image,body,task='hunt',bearing=math.pi/2,seed=311,
            operation='restore',plan={'target_edges':[]})
    for _ in range(20):
        assert a.action(0)==b.action(0)
        a.step();b.step()
    assert abs(a.metrics()['energy_balance_error'])<1e-5
    assert image.payload==before
    x,y=a.engines[0].capture_state().to_dict(),b.engines[0].capture_state().to_dict()
    # Explicit intervention appends audit sequence entries even when immediately undone.
    assert all(x[k]==y[k] for k in x if k!='sequence')
    r,trace,activity=observe(a,tmp_path/'record',.2)
    assert r['status']=='horizon_paused' and len(trace)==10 and activity


def test_births_equal_supply_and_replay_is_exact_exterior_command():
    original,image,body=source();p=original.p.model_dump(by_alias=True)
    a=scene(p,image,body,task='food',bearing=0.,seed=311,operation='experienced')
    b=scene(p,image,body,task='food',bearing=0.,seed=311,operation='blank')
    assert a.engines[0].metrics()['energy']['reserve']==b.engines[0].metrics()['energy']['reserve']
    tape=[[.2,-.3,.1],[.7,0.,-.2]]
    r=scene(p,image,body,task='food',bearing=0.,seed=311,operation='replay',actions=tape)
    assert r.action(0)==tape[0]
    r.step()
    assert r.action(0)==tape[1]


def test_selection_uses_only_old_edges_and_observed_history():
    _,image,_=source();s=image.to_dict();nodes=s['nodes']
    observations=[{'t':2.,'recent_channels':[], 'nodes':[n|{'activation':1.} for n in nodes]}]
    result=select_region(image,observations,2)
    old={(e['source'],e['target']) for e in s['edges']}
    assert all(tuple(p) in old for p in result['target_edges'])
    assert not select_region(image,[observations[0]|{'t':0.1}],2)['applicable']
