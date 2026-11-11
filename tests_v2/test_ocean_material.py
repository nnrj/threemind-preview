import json

import pytest

from lab.tools.ocean_material import MaterialOcean, MaterialProtocol
from lab.tools.ocean_enclosure import EnclosureOcean
from lab.tools.ocean_contact_cli import save
from lab.tools.ocean_species import save_candidate, seed_founders
from threemind_lab.species_library import inspect_bundle


def world(fraction=.5, **kwargs):
    p=MaterialProtocol(founders=2, population_limit=4, nutrient_initial=0,
        founder_variation=0, flow_m_s=0, flow_variation_m_s=0,
        reproduction=False, body_material_fraction=fraction, **kwargs)
    w=MaterialOcean(p.model_dump(by_alias=True))
    w.configure({0:'all',1:'all'},{'all':'core'})
    return w


def test_paid_material_empty_reserve_and_no_double_consumption():
    w=world();a,b=w.bodies.values()
    assert w.body_material[1]==pytest.approx(120)
    assert a.storage==pytest.approx(960)
    assert abs(w.metrics()['energy_balance_error'])<1e-6
    # Account for reserve expenditure, leaving an empty yet material body.
    w.totals['body_heat']+=b.storage;b.storage=0
    gain=w._consume_body_energy(a,b)
    assert gain['transferred']==pytest.approx(120*w.p.predation_efficiency)
    assert gain['reserve_received']==0 and gain['material_received']>0
    assert w._consume_body_energy(a,b)['transferred']==0
    assert abs(w.metrics()['energy_balance_error'])<1e-6


def test_storage_capacity_loss_and_zero_fraction_control():
    for fraction in (0,.5):
        w=world(fraction);a,b=w.bodies.values()
        w.totals['initial_body']+=w.p.storage_capacity-a.storage
        a.storage=w.p.storage_capacity
        gain=w._consume_body_energy(a,b)
        assert gain['transferred']==0 and gain['digestion_loss']>0
        assert abs(w.metrics()['energy_balance_error'])<1e-6
    zero=world(0)
    assert all(v==0 for v in zero.body_material.values())
    assert zero.totals['body_heat']==pytest.approx(480)


def test_birth_retains_part_of_existing_cost_and_restore(tmp_path):
    w=world();w.p=w.protocol_model.model_validate(w.p.model_dump(by_alias=True)|{
        'reproduction':True,'reproduction_age_us':0,'reproduction_cooldown_us':20000,
        'reproduction_interval_us':20000,'mutation_probability':0})
    w._reproduction_ready=lambda i:True
    a=w.bodies[0];w.totals['initial_body']+=6000-a.storage;a.storage=6000
    w.time_us=20000;w._reproduce()
    e=next(e for e in w.events if e['kind']=='birth')
    assert e['body_material_energy']==pytest.approx(e['construction_cost']*.5)
    assert abs(w.metrics()['energy_balance_error'])<1e-6
    # Independent fresh state verifies the version and the material ledger.
    w=world();w.step();state=json.loads(json.dumps(w.capture()))
    z=MaterialOcean(w.p.model_dump(by_alias=True),state=state,
        images={i:e.capture_state() for i,e in w.engines.items()})
    for _ in range(3):w.step();z.step()
    assert w.capture()==z.capture()
    with pytest.raises(ValueError):EnclosureOcean(w.p.model_dump(by_alias=True),state=state)
    save(w,tmp_path/'snapshot')
    save_candidate(tmp_path/'snapshot',0,tmp_path/'candidate.tmspecies',name='material candidate',evidence=[])
    raw=(tmp_path/'candidate.tmspecies').read_bytes()
    m,_=inspect_bundle(raw)
    assert m['body']['body_material_energy']==w.body_material[0]
    new=world();seed_founders(new,raw,[1])
    assert abs(new.metrics()['energy_balance_error'])<1e-6


def test_material_does_not_bypass_containment_or_shell():
    w=world(initial_body_energy=2000);a,b=w.bodies.values()
    a.radius=.014;b.radius=.007;a.elongation=b.elongation=0
    b.shell=.8
    # Explicitly reassign the funded time-zero bodies after fixture geometry.
    w.replace_founder_material([0,1])
    a.position=[.5,.5];b.position=[.521,.5]
    for _ in range(50):w.time_us+=w.p.period_us;w._predation([0,1])
    assert b.physical
    b.position=[.5,.5]
    for _ in range(16):w.time_us+=w.p.period_us;w._predation([0,1])
    assert b.physical
    for _ in range(40):w.time_us+=w.p.period_us;w._predation([0,1])
    event=next(e for e in w.events if e['kind']=='body_engulfed')
    assert event['method']=='enclosure' and event['shell_cost']>0
    assert event['prey_material']>0 and abs(w.metrics()['energy_balance_error'])<1e-6


def test_unfunded_body_is_rejected():
    with pytest.raises(ValueError,match='cannot fund construction'):
        world(initial_body_energy=100)


def test_zero_construction_replays_original_core_dynamics():
    new=world(construction_energy=0)
    p=new.p.model_dump(by_alias=True);p.pop('body_material_fraction')
    p['schema']='threemind.ocean-enclosure/1'
    old=EnclosureOcean(p);old.configure({0:'all',1:'all'},{'all':'core'})
    for _ in range(10):old.step();new.step()
    for i in old.engines:
        assert old.engines[i].capture_state()==new.engines[i].capture_state()
    assert [b.storage for b in old.bodies.values()]==[b.storage for b in new.bodies.values()]
