"""Isolated single-emission witnesses for the two weight-only switches."""
import copy
from dataclasses import replace
import pytest

from threemind_core import Stimulus
from threemind_kernels.local62 import Local62Config, Local62Engine


@pytest.mark.parametrize('exc,inh', [(True,True),(True,False),(False,True),(False,False)])
@pytest.mark.parametrize('master', [True,False])
def test_weight_switch_does_not_disable_other_plasticity(exc,inh,master):
    c=Local62Config(consolidation_mode='stability', local_novelty_gain=0,
                    signal_threshold_enabled=False, inhibitory_learning_enabled=master)
    e=Local62Engine(c)
    e.inject(Stimulus(0,((1,.4),(2,.3))))
    e.advance_to(0)
    # A controlled engineering fixture has both types of offered signal.
    e.nodes[1].inhibition=.2
    state=e.capture_state()
    reference=Local62Engine(state=state)
    test=Local62Engine(state=state)
    test.reconfigure(replace(c,activation_weight_reinforcement_enabled=exc,
                             inhibition_weight_reinforcement_enabled=inh))
    before=copy.deepcopy(test.edges[(1,2)])
    transport=dict(test.transport)
    reference._emit(1);test._emit(1)
    pos=test.transport['transmitted_excitation']-transport['transmitted_excitation']
    neg=test.transport['transmitted_inhibition']-transport['transmitted_inhibition']
    assert pos>0 and neg>0
    expected=min(1.,before.weight+c.associative_gain*((pos if exc else 0)+(neg if master and inh else 0)))
    assert test.edges[(1,2)].weight==pytest.approx(expected)
    for field in ('stability','eligibility','fast','short_term','touches','last_pass_us'):
        assert getattr(test.edges[(1,2)],field)==getattr(reference.edges[(1,2)],field)
    assert test.transport==reference.transport


@pytest.mark.parametrize('field',['activation_weight_reinforcement_enabled','inhibition_weight_reinforcement_enabled'])
@pytest.mark.parametrize('value',[0,1,None,'false'])
def test_weight_switch_requires_boolean(field,value):
    with pytest.raises(ValueError,match='boolean'):
        Local62Config(**{field:value})
