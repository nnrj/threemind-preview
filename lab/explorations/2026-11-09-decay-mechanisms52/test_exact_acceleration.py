"""Bitwise scalar and complete-state witnesses; excluded from scientific N."""
import math
import random
import pytest
from threemind_core import Stimulus,StateImage
from threemind_kernels.decay52 import Trace,Contribution
from threemind_kernels.local52 import Local52Config,Local52Engine
from exact_acceleration import accelerated,ORIGINAL_VALUE,ORIGINAL_CROSSING


@pytest.mark.parametrize('curve',['exponential','inverse-logarithmic','power-law'])
def test_exact_values_and_crossings(curve):
    rng=random.Random(5231)
    traces=[Trace(curve,()),Trace(curve,(Contribution(.8,0.),)),
        Trace(curve,(Contribution(.2,1e301),Contribution(.4,0.)))]
    for count in (2,9,90):
        ages=sorted(rng.sample(range(100000),count),reverse=True)
        traces.append(Trace(curve,tuple(Contribution(rng.uniform(.0001,.01),a/100) for a in ages)))
    for trace in traces:
        queries=(0.,1e-12,.01,1.,45.,5000.,1e200,1e302)
        expected=[trace.value(a) for a in queries]
        crossings=[trace.crossing_age(f,1e305) for f in (.0001,.008,.1,1.)]
        with accelerated():
            assert [trace.value(a) for a in queries]==expected
            assert [trace.crossing_age(f,1e305) for f in (.0001,.008,.1,1.)]==crossings
        assert Trace.value is ORIGINAL_VALUE and Trace.crossing_age is ORIGINAL_CROSSING


@pytest.mark.parametrize('curve',['exponential','inverse-logarithmic','power-law'])
@pytest.mark.parametrize('relaxation',[True,False])
def test_complete_next_events_are_exact(curve,relaxation):
    def sequence():
        core=Local52Engine(Local52Config(decay_curve=curve,retention_relaxation_enabled=relaxation,quiescence_death_us=10**10))
        states=[]
        for i in range(8):
            t=i*100000
            core.advance_to(t)
            core.inject(Stimulus(t,((11,.4),(12,.4))))
        for t in (1000000,3000000,12000000):
            core.advance_to(t);states.append(core.capture_state().to_dict())
            before=core.capture_state().to_dict();core.graph();assert core.capture_state().to_dict()==before
        restored=Local52Engine(state=StateImage.from_dict(states[-1]))
        restored.inject(Stimulus(12000000,((11,.8),)))
        restored.advance_to(13000000);states.append(restored.capture_state().to_dict())
        return states
    expected=sequence()
    with accelerated():assert sequence()==expected


@pytest.mark.parametrize('bad',[-1,float('inf'),float('nan'),True])
def test_invalid_ages_still_rejected(bad):
    trace=Trace('power-law',(Contribution(.3,0.),))
    with accelerated(),pytest.raises(ValueError):trace.value(bad)
