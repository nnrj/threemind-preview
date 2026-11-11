"""Synthetic arithmetic witnesses; no scientific subject is instantiated."""
import math
from analyze_stimulus import response_vector,benefit,retained,rms
from audit_stimulus import decay


def test_entire_process_and_all_four_fields_are_measured():
    frame=lambda:dict(out0=dict(activation=0.,inhibition=0.,direct=0.,associative=0.))
    before=[frame() for _ in range(20)];after=[frame() for _ in range(20)]
    after[19]['out0']['inhibition']=2.
    values=response_vector(dict(baseline=dict(raw=before),response=dict(raw=after)))
    assert len(values)==80 and values[77]==2. and sum(values)==2.
    assert rms(values)==math.sqrt(4/80)


def test_retention_requires_early_signal_late_signal_and_shape():
    early=[1.,0.]*40
    assert retained(early,[.11,0.]*40)['passed']
    assert not retained(early,[0.,1.]*40)['passed']
    assert not retained(early,[.09,0.]*40)['passed']
    assert not retained([0.]*80,[1.]*80)['passed']


def test_absolute_and_relative_benefit_are_both_required():
    assert benefit(.12,.1,1e-6,.1)['passed']
    assert not benefit(.1001,.1,1e-6,.1)['passed']
    assert not benefit(1e-7,0.,1e-6,.1)['passed']
    assert benefit(.001,0.,1e-6,.1)['relative_difference'] is None


def test_independent_fading_arithmetic_without_relaxation():
    row=dict(state_us=0,half_life=30.,weight=.2,decay_contributions=[[.2,0.]])
    cfg=dict(memory_half_life_min_s=30.,memory_half_life_decay_rate=.125,retention_relaxation_enabled=False)
    for curve,expected in (('exponential',0.),('power-law',.2/(1+86400)),
                           ('inverse-logarithmic',.2/(1+math.log1p((math.e-1)*86400)))):
        cfg['decay_curve']=curve
        assert math.isclose(decay(row,dict(config=cfg,time_us=0)),expected,rel_tol=1e-14,abs_tol=1e-300)
