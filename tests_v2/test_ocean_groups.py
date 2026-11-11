"""Research controls must not change normal Core-driven physics or dynamics."""
import importlib.util
from pathlib import Path
from lab.tools.ocean_community import CommunityOcean
from lab.tools.ocean_groups import copy_community,load
from lab.tools.ocean_contact_cli import save


def base():
    return CommunityOcean({'schema':'threemind.ocean/3','founders':2,'population_limit':8,
        'nutrient_initial':8,'nutrient_capacity':20,'reproduction':False},backend='reference')


def test_whole_copy_default_is_exact():
    original=base();group=copy_community(original)
    group.configure({0:'all',1:'all'},{'all':'core'})
    # No parent/child pair is present, so the approved bilateral rule is neutral.
    for _ in range(10):original.step();group.step()
    assert original.metrics()['members']==[{k:v for k,v in r.items() if k not in
        ('cohort','controller','core_running')} for r in group.metrics()['members']]
    assert all(original.engines[i].capture_state().digest==group.engines[i].capture_state().digest for i in (0,1))


def test_stopped_core_no_advance_charge_or_delivery_and_restore(tmp_path):
    w=copy_community(base());w.configure({0:'A',1:'B'},{'A':'random-stopped','B':'random-shadow'},cross_only=True)
    frozen=w.engines[0].capture_state().digest;record=[]
    for _ in range(10):w.step(record.append)
    assert w.engines[0].capture_state().digest==frozen
    assert w.engines[1].time_us==w.time_us
    assert all(next(r for r in row['inputs'] if r['individual']==0)['stimulus'] is None for row in record)
    assert abs(w.metrics()['energy_balance_error'])<1e-6
    save(w,tmp_path/'saved');restored=load(tmp_path/'saved')
    # Original uses reference backend; restored native implementation must preserve state.
    assert restored.engines[0].capture_state().digest==frozen
    assert restored.group_controls==w.group_controls and restored.cross_only
    assert restored.metrics()['groups']==w.metrics()['groups']
    import pytest
    with pytest.raises(ValueError,match='clock'):
        restored.configure(restored.cohorts,{'A':'core','B':'random-shadow'})


def test_cohort_protection_and_descendant_control():
    w=copy_community(base());w.configure({0:'A',1:'A'},{'A':'random-stopped'},cross_only=True)
    assert w._protected_pair(0,1,0) and w._protected_pair(1,0,0)
    w.cohorts[1]='B';w.group_controls['B']='core'
    assert not w._protected_pair(0,1,0)
    w.bodies[1].parent=0
    assert w._protected_pair(0,1,0) and w._protected_pair(1,0,0)
    assert w._reproduction_ready(0)


def test_stopped_descendants_keep_control_and_energy_ledger():
    from lab.tools.ocean_groups import GroupOcean
    w=GroupOcean({'schema':'threemind.ocean-groups/1','founders':1,'population_limit':4,
        'nutrient_initial':0,'nutrient_capacity':8,'initial_body_energy':10000.,
        'reproduction_age_us':0,'reproduction_cooldown_us':1000000},backend='reference')
    w.configure({0:'all'},{'all':'random-stopped'})
    for _ in range(51):w.step()
    assert len(w.bodies)>1
    assert all(w.controller(i)=='random-stopped' for i in w.bodies)
    assert all(e.time_us==0 for e in w.engines.values())
    assert abs(w.metrics()['energy_balance_error'])<1e-6


def test_refactored_contact_matches_frozen_e32_default():
    path=Path('.work/ocean-community-20261003/sources/ocean_contact.py')
    if not path.exists():
        import pytest
        pytest.skip('local frozen experiment source is optional outside this workspace')
    spec=importlib.util.spec_from_file_location('frozen_ocean_contact',path)
    module=importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name]=module;spec.loader.exec_module(module)
    from lab.tools.ocean_contact import ContactOcean
    p={'schema':'threemind.ocean/3','founders':2,'population_limit':8,
        'nutrient_initial':8,'nutrient_capacity':20,'reproduction':False}
    old=module.ContactOcean(p,backend='reference');new=ContactOcean(p,backend='reference')
    for _ in range(10):old.step();new.step()
    assert old.capture()==new.capture()
