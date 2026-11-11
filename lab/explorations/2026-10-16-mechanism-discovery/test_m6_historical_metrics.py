import copy
import pytest
from m6_historical_metrics import action_matrix,world_result,overall,MODES,OPERATIONS


def rows(value):
    return [{'action_time_us':20_000_000+j*20_000,'actions':{str(i):[value,0.,0.] for i in range(8)}} for j in range(500)]


def factorial(target=.05,matched=.09,baseline=.1):
    return {f'{mode}-{op}':rows(({'sham':baseline,'target':target,'matched':matched,'restored':baseline}[op]) if mode=='live' else 0.)
            for mode in MODES for op in OPERATIONS}


def test_registered_target_and_full_restoration():
    r=world_result(factorial(),range(8),{'live':True,'muted':True})
    assert r['verdict']=='PASS' and r['attenuation']['target']==pytest.approx(.5)
    assert r['selectivity']==pytest.approx(.4)
    assert overall([r,r])['verdict']=='PASS'


def test_failure_is_distinct_from_invalid_measurement():
    valid=world_result(factorial(target=.09),range(8),{'live':True,'muted':True})
    assert valid['verdict']=='FAIL'
    for arms,ids,exact in [(factorial(baseline=0),range(8),{'live':True,'muted':True}),
                           (factorial(),range(7),{'live':True,'muted':True}),
                           (factorial(),range(8),{'live':False,'muted':True})]:
        assert world_result(arms,ids,exact)['verdict']=='MEASUREMENT_NOT_QUALIFIED'
    assert overall([valid,valid])['verdict']=='FAIL'


def test_dead_body_retained_as_zero_no_survivor_conditioning():
    x=rows(.2);del x[0]['actions']['0'];before=copy.deepcopy(x)
    a=action_matrix(x,range(8));assert a.shape==(50,8,3)
    assert a[0,0,0]==0 and a[1,0,0]==.2 and x==before


def test_window_is_fixed_and_missing_or_duplicate_frame_rejected():
    x=rows(.1);x[50]['actions']['0'][0]=.9
    assert action_matrix(x,range(8)).max()==.1
    with pytest.raises(ValueError):action_matrix(x[1:],range(8))
    with pytest.raises(ValueError):action_matrix([x[0]]+x,range(8))


def test_complete_factorial_and_observational_unit_required():
    x=factorial();del x['muted-target']
    with pytest.raises(ValueError):world_result(x,range(8),{'live':True,'muted':True})
    with pytest.raises(ValueError):overall([])
