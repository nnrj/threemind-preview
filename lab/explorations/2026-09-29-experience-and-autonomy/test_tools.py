import importlib.util
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import experiment as e

def test_dose_and_final_age():
    for name in e.PROTOCOLS:
        schedule=e.schedule(name)
        if schedule:
            assert schedule[-1][0]==128
            assert all(a[0]<b[0] for a,b in zip(schedule,schedule[1:]))
    assert sum(x[1] for x in e.schedule('massed_weak'))==pytest.approx(1)
    assert e.schedule('single_high')==[(128,1)]
    assert e.schedule('spaced_ordinary')==e.schedule('spaced_no_consolidation')

def test_pattern_overlap():
    for seed in e.SEEDS:
        base=set(e.pattern(seed,0))
        assert [len(base-set(e.pattern(seed,i))) for i in range(4)]==[0,1,2,4]
        assert len(set(e.features(seed)))==8

def test_environment_feedback_and_equal_dose():
    for seed in e.SEEDS:
        for env in ('P','Q'):
            lo=e.sensation(e.Body(.25),seed,100,env)
            hi=e.sensation(e.Body(.75),seed,100,env)
            assert set(lo.channels)!=set(hi.channels)
            assert lo.intensity==hi.intensity==.8
            assert set(ch for ch,_ in lo.channels+hi.channels)==set(e.symbols(seed).values())

import pytest

def test_time_integral_uses_duration_not_sample_count():
    from analyze import area
    rows=[{'relative_us':0,'x':1},{'relative_us':10000,'x':2},{'relative_us':1000000,'x':0}]
    assert area(rows,lambda r:r['x'])==pytest.approx(1.99)
    assert area(rows,lambda r:r['x'],500000,1000000)==pytest.approx(1)

def test_matched_damage_preserves_count_and_excludes_task_nodes():
    from analyze import EPS
    assert EPS==.0001
    class Image:
        def to_dict(self):
            return {'edges':[dict(source=a,target=b,weight=w,stability=.3)
                for a,b,w in ((1,2,.5),(1,3,.7),(4,5,.51),(5,6,.8),(6,4,.69))]}
    selected,errors=e.matched_edges(Image(),[(1,2),(1,3)],[1,2,3])
    assert selected==[(4,5),(6,4)]
    assert errors==pytest.approx([.01,.01])
