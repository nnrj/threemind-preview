"""Pure-fixture checks only; no real Core/world is created or advanced."""
import copy
from types import SimpleNamespace
import pytest
import m6_historical_state as s


def reference():
    return {'definition':{'kernel_id':s.KERNEL},'sequence':4,'silenced_nodes':[],
            'silenced_edges':[],'time_us':'20000000','energy':{'reserve':1.},'weight':.2}


def test_only_declared_native_sequence_and_edge_mask_are_allowed():
    old=reference();new=copy.deepcopy(old);new['sequence']+=2;new['silenced_edges']=[[1,2],[4,5]]
    s.check_native_intervention(old,new,[[4,5],[1,2]])
    restored=copy.deepcopy(old);restored['sequence']+=2
    s.check_native_intervention(old,restored,[])
    assert old==reference()


@pytest.mark.parametrize('field,value',[
    ('sequence',7),('time_us','20000001'),('energy',{'reserve':2.}),('weight',.3),
    ('definition',{'kernel_id':'threemind.continuous-memory/5.1'}),('silenced_nodes',[1])])
def test_undeclared_intervention_change_fails(field,value):
    old=reference();new=copy.deepcopy(old);new['sequence']+=2;new[field]=value
    with pytest.raises(ValueError):s.check_native_intervention(old,new,[])


def test_actual_pre_physics_actions_are_retained_after_death():
    w=SimpleNamespace(time_us=20_000_000,p=SimpleNamespace(period_us=20000),last_actions={})
    def step(callback):
        w.last_actions={1:[.2,-.3,.4]};w.time_us+=20000
        callback({'time_us':w.time_us,'inputs':[], 'events':[{'kind':'death','body':1}]})
    w.step=step
    row=s.physical_step(w)
    assert row['action_time_us']==20_000_000 and row['actions']=={'1':[.2,-.3,.4]}
    assert row['native']['events'][0]['kind']=='death'


def test_extra_observation_cannot_silently_advance_time(monkeypatch):
    w=SimpleNamespace(time_us=20_000_000,engines={})
    w.metrics=lambda:setattr(w,'time_us',w.time_us+1)
    monkeypatch.setattr(s,'canonical',lambda world:{'time_us':world.time_us})
    with pytest.raises(ValueError,match='observation altered'):s.physical_step(w,extra_observation=True)


def test_numeric_body_keys_have_stable_file_roundtrip_order(monkeypatch):
    context={'nested':{2:'body-2',10:'body-10',1:'body-1'}}
    w=SimpleNamespace(p=SimpleNamespace(schema_id=s.WORLD),capture=lambda:context)
    monkeypatch.setattr(s,'extras',lambda world:{'cache':{2:[0.1,0.2],10:[]}})
    value=s.canonical(w)
    assert value['context']['nested']=={'1':'body-1','2':'body-2','10':'body-10'}
    assert s.m.digest(value)==s.m.digest(s.json.loads(s.m.encoded(value)))
    assert set(context['nested'])=={1,2,10}
