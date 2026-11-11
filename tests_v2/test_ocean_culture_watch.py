from types import SimpleNamespace
from lab.tools.ocean_culture_watch import CultureWatch
from lab.tools.ocean_association import AssociationOcean


def test_observer_leaves_core_unchanged_and_branch_stats_independent(tmp_path):
    p={'schema':'threemind.ocean-association/1','founders':2,'population_limit':3,
       'nutrient_initial':2,'nutrient_capacity':8,'reproduction':False}
    a=AssociationOcean(p);b=AssociationOcean(p)
    for w in (a,b):w.configure({0:'all',1:'all'},{'all':'core'})
    watch=CultureWatch(tmp_path,'a','test')
    for _ in range(10):
        a.step(lambda row:watch.observe(a,row,[0,1]));b.step()
    assert a.capture()==b.capture()
    state=watch.capture();left=CultureWatch(tmp_path,'left','test',state=state)
    right=CultureWatch(tmp_path,'right','test',state=state)
    left.item(0)['turns']=9
    assert right.item(0)['turns']==0 and state['stats'][0]['turns']==0


def test_improvement_uses_exposure_and_minimum_evidence(tmp_path):
    watch=CultureWatch(tmp_path,'a','test')
    w=SimpleNamespace(bodies={0:SimpleNamespace(parent=None),1:SimpleNamespace(parent=0)})
    watch.stats={0:{'observed_us':100_000_000,'turns':2,'captures':0},
                 1:{'observed_us':60_000_000,'turns':3,'captures':2}}
    assert watch.improved(w,1,'turns') and watch.improved(w,1,'captures')
    watch.stats[1]['observed_us']=59_000_000
    assert not watch.improved(w,1,'turns')
