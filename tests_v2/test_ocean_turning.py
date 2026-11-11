import numpy as np

from lab.tools.ocean_turning import measure_window, TurningObserver


def samples():
    t=np.arange(0,5_000_000,20_000);n=len(t)
    raw=np.zeros((n,26));actions=np.zeros((n,3))
    angle=np.linspace(np.pi/2,0,n)
    raw[:,5]=1;raw[:,7]=-.2;raw[:,8]=np.sin(angle);raw[:,9]=np.cos(angle)
    # Fixed world +x concentration gradient, represented in the turning body.
    raw[:,1]=np.cos(angle);raw[:,4]=np.sin(angle)
    actions[:,2]=-.3
    return t,raw,actions


def test_turn_toward_food_is_observable():
    t,r,a=samples();v=measure_window(t,r,a)
    assert v['passes'] and v['turn_degrees']>60


def test_collision_drift_and_fixed_direction_do_not_qualify():
    t,r,a=samples();r[10,23]=1
    assert not measure_window(t,r,a)['passes']


def test_live_observer_uses_same_pre_ingestion_window():
    t,r,a=samples();observer=TurningObserver()
    for k in range(len(t)):
        assert observer.observe({'time_us':int(t[k]),'events':[],
            'inputs':[{'individual':7,'raw':r[k].tolist(),'action':a[k].tolist()}]})==[]
    hits=observer.observe({'time_us':5_000_000,'events':[{'kind':'nutrient_contact',
        'individual':7,'energy':600,'time_us':5_000_000,'particle':9}],
        'inputs':[{'individual':7,'raw':r[-1].tolist(),'action':a[-1].tolist()}]})
    assert len(hits)==1 and hits[0]['individual']==7
    assert hits[0]['turn_degrees']==measure_window(t,r,a)['turn_degrees']
    t,r,a=samples();a[:,2]=0
    assert not measure_window(t,r,a)['passes']
    t,r,a=samples();r[:,8]=0;r[:,9]=1
    assert not measure_window(t,r,a)['passes']
