"""Isolated engineering witnesses; never load formal research subjects."""
import copy
from dataclasses import replace
import math

import pytest
import importlib.util
from pathlib import Path
from threemind_core import Stimulus,StateImage
from threemind_kernels.local51 import Local51Engine,Local51Config
from threemind_kernels.local52 import Local52Engine,Local52Config,Local52Edge,Local52Node
from threemind_kernels.decay52 import CURVES,Contribution,Trace


def normalize(doc):
    d=copy.deepcopy(doc)
    for key in ('schema','dynamics','definition','definition_hash'):d.pop(key,None)
    d['config'].pop('decay_curve',None);d['config'].pop('retention_relaxation_enabled',None)
    for group in ('nodes','edges'):
        for row in d[group]:row.pop('decay_curve',None);row.pop('decay_contributions',None)
    return d

def inputs(e):
    for i,t in enumerate((0,73000,180000,611337,1200000)):
        e.inject(Stimulus(t,((10,.8),(11,.6),(20+i%2,.4))))

def test_exponential_preserves_old_full_trajectory():
    old=Local51Engine(Local51Config(quiescence_death_us=10**12))
    new=Local52Engine(Local52Config(quiescence_death_us=10**12))
    for e in [old,new]:inputs(e)
    for t in [0,1,180000,300000,611337,700000,1200000,2300000,31000000,100000000]:
        old.advance_to(t);new.advance_to(t)
        assert normalize(old.capture_state().to_dict())==normalize(new.capture_state().to_dict())
        new=Local52Engine(state=new.capture_state())

@pytest.mark.parametrize('curve',CURVES)
@pytest.mark.parametrize('enabled',[True,False])
def test_six_conditions_observation_partition_restore(curve,enabled,monkeypatch):
    cfg=Local52Config(decay_curve=curve,retention_relaxation_enabled=enabled,quiescence_death_us=10**12)
    one,split=Local52Engine(cfg),Local52Engine(cfg)
    for e in [one,split]:inputs(e)
    one.advance_to(2300000)
    for t in [0,1,180000,300000,611337,700000,1200000,2300000]:
        split.advance_to(t);before=split.capture_state().payload
        monkeypatch.setattr('time.time',lambda:1e99)
        split.graph();split.metrics();split.activations()
        assert split.capture_state().payload==before
        split=Local52Engine(state=split.capture_state())
    assert split.capture_state().to_dict()==one.capture_state().to_dict()
    for e in [one,split]:
        e.inject(Stimulus(3000000,((10,.5),(22,.9))));e.advance_to(4000000)
    assert split.capture_state().to_dict()==one.capture_state().to_dict()

@pytest.mark.parametrize('curve',CURVES[1:])
def test_damage_then_learning_preserves_separate_ages(curve):
    e=Local52Edge(1,2,.5,decay_curve=curve)
    e.decay_contributions=((.5,1.),)
    object.__setattr__(e,'weight',.25)
    e.weight*=.4
    e.weight+=.1
    assert e.decay_contributions==((.2,1.),(.1,0.))
    assert math.isclose(sum(a/(1+b) if curve=='power-law' else a/(1+math.log1p(math.expm1(1)*b)) for a,b in e.decay_contributions),.2)
    n=Local52Node(1,10,decay_curve=curve)
    n.support=.5;n.support*=.5;n.support+=.1
    assert math.isclose(Trace(curve,tuple(Contribution(*x) for x in n.decay_contributions)).value(),n.support)
    assert copy.copy(e).decay_contributions==e.decay_contributions

@pytest.mark.parametrize('curve',CURVES)
def test_relaxation_off_preserves_scale_but_weight_decays(curve):
    e=Local52Engine(Local52Config(decay_curve=curve,retention_relaxation_enabled=False))
    row=Local52Edge(0,1,.5,half_life=300,decay_curve=curve)
    p=e._project_edge(row,300000000)
    assert p.half_life==300 and math.isclose(p.weight,.25)
    assert row.weight==.5 and row.half_life==300

def test_old_identity_is_not_upgraded():
    with pytest.raises(ValueError,match='identity|history'):Local52Engine(state=Local51Engine().capture_state())
    with pytest.raises(ValueError,match='identity'):Local51Engine(state=Local52Engine().capture_state())

@pytest.mark.parametrize('curve',CURVES[1:])
def test_corrupt_or_missing_contribution_is_rejected(curve):
    e=Local52Engine(Local52Config(decay_curve=curve,quiescence_death_us=10**12));inputs(e);e.advance_to(100000)
    original=e.capture_state().to_dict()
    mutations=[lambda d:d['edges'][0].pop('decay_contributions'),
        lambda d:d['edges'][0].update(decay_contributions=[]),
        lambda d:d['edges'][0].update(decay_contributions=[[.3,-1]]),
        lambda d:d['edges'][0].update(decay_curve='exponential'),
        lambda d:d['edges'][0].update(decay_contributions=[[1,1e99]])]
    for mutate in mutations:
        d=copy.deepcopy(original);mutate(d)
        with pytest.raises(ValueError):Local52Engine(state=StateImage.from_dict(d))

def test_curve_immutable_and_relaxation_change_is_continuous():
    e=Local52Engine(Local52Config(decay_curve='power-law',quiescence_death_us=10**12));inputs(e);e.advance_to(2000000)
    before=e.graph();clock=e.time_us
    e.reconfigure(replace(e.config,retention_relaxation_enabled=False))
    after=e.graph()
    assert clock==e.time_us
    for kind,field in [('nodes','support'),('edges','weight')]:
        assert [x[field] for x in before[kind]]==[x[field] for x in after[kind]]
    with pytest.raises(ValueError,match='fixed at birth'):e.reconfigure(replace(e.config,decay_curve='exponential'))

_spec=importlib.util.spec_from_file_location('decay52_existing_witnesses',Path(__file__).resolve().parents[3]/'tools/memory51_witnesses.py')
_witnesses=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_witnesses)

def normalized_witness(v):
    if isinstance(v,list):return [normalized_witness(x) for x in v]
    if not isinstance(v,dict):return v
    if 'decay_contributions' in v:assert not v['decay_contributions']
    return {k:normalized_witness(x) for k,x in v.items() if k not in (
        'schema','dynamics','kernel_id','state_schema','definition','definition_hash','decay_curve','retention_relaxation_enabled','decay_contributions')}

@pytest.mark.parametrize('name,options',list(_witnesses.cases().items()))
def test_full_old_operator_witnesses(name,options,monkeypatch):
    old=_witnesses.trace('5.1','python',options)
    monkeypatch.setattr(_witnesses,'factories',lambda *args:(Local52Config,Local52Engine))
    new=_witnesses.trace('candidate','python',options)
    assert normalized_witness(old)==normalized_witness(new),name

@pytest.mark.parametrize('curve',CURVES[1:])
@pytest.mark.parametrize('enabled',[True,False])
@pytest.mark.parametrize('options',[
    {},{'energy_simulation_enabled':True,'energy_initial_reserve':.001,'energy_starvation_damage_enabled':True},
    {'novelty_mode':'immediate'},
    {'dormant_traces_enabled':True,'revival_enabled':True,'node_wake_threshold':.05,'edge_wake_threshold':.1},
])
def test_new_curves_across_existing_operations(curve,enabled,options,monkeypatch):
    monkeypatch.setattr(_witnesses,'factories',lambda *args:(Local52Config,Local52Engine))
    result=_witnesses.trace('candidate','python',dict(options,decay_curve=curve,retention_relaxation_enabled=enabled))
    restored=Local52Engine(state=StateImage.from_dict(result[-1]['state']))
    assert restored.capture_state().to_dict()==result[-1]['state']

@pytest.mark.parametrize('curve',CURVES[1:])
def test_wrong_expiry_time_is_rejected(curve):
    e=Local52Engine(Local52Config(decay_curve=curve,quiescence_death_us=10**12));inputs(e);e.advance_to(100000)
    d=e.capture_state().to_dict()
    row=next(r for r in d['timers'] if r[0]==2);row[3]=str(int(row[3])+1000000)
    with pytest.raises(ValueError,match='expiry time'):Local52Engine(state=StateImage.from_dict(d))

def test_inverse_log_tail_beyond_time_range_has_no_false_expiry():
    e=Local52Engine(Local52Config(decay_curve='inverse-logarithmic'))
    row=Local52Edge(0,1,1.,decay_curve='inverse-logarithmic')
    assert e._crossing(row,'weight',.008) is None
    e._edge_timer(row)
    assert (2,0,1) not in e.timers.positions
