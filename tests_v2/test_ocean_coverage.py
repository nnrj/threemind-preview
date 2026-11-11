import json
import math
import numpy as np
import pytest
from lab.tools.ocean_contact import ContactBody
from lab.tools.ocean_coverage import CoverageOcean,CoverageProtocol,coverage_fractions


def fixture(shell=0,**kwargs):
    p=CoverageProtocol(founders=2,population_limit=97,nutrient_initial=0,
        reproduction=False,founder_variation=0,flow_m_s=0,flow_variation_m_s=0,**kwargs)
    w=CoverageOcean(p.model_dump(by_alias=True));w.configure({0:'all',1:'all'},{'all':'core'})
    a,b=w.bodies.values();a.radius=b.radius=.008
    a.elongation=b.elongation=0;a.position=[.5,.5];b.position=[.504,.5]
    a.angle=b.angle=0;a.thrust*=2;b.shell=shell
    return w


def test_geometric_area_against_circle_formula_and_periodic_rotation():
    w=fixture();a,b=w.bodies.values();r=a.radius;distance=.004
    analytic=(2*r*r*math.acos(distance/(2*r))-.5*distance*math.sqrt(4*r*r-distance*distance))/(math.pi*r*r)
    ab,ba=coverage_fractions(a,b,w.p.side_m)
    assert ab==pytest.approx(analytic,abs=.001) and ab==pytest.approx(ba)
    a.elongation=1.2;b.elongation=.7;b.angle=.4
    before=coverage_fractions(a,b,w.p.side_m)
    angle=.91;rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
    delta=rotation@(np.asarray(b.position)-a.position)
    a.position=[w.p.side_m-.002,.2];b.position=((np.asarray(a.position)+delta)%w.p.side_m).tolist()
    a.angle+=angle;b.angle+=angle
    assert coverage_fractions(a,b,w.p.side_m)==pytest.approx(before,abs=1e-10)


def test_half_coverage_consumes_with_dwell_but_touch_does_not_and_shell_delays():
    w=fixture();w.bodies[1].position=[.516,.5]
    for _ in range(80):w.time_us+=w.p.period_us;w._predation([0,1])
    assert all(b.physical for b in w.bodies.values()) and not w.contacts
    plain,shell=fixture(),fixture(.8)
    for world in (plain,shell):
        for _ in range(16):world.time_us+=world.p.period_us;world._predation([0,1])
    assert not plain.bodies[1].physical and shell.bodies[1].physical
    for _ in range(70):shell.time_us+=shell.p.period_us;shell._predation([0,1])
    event=next(e for e in shell.events if e['kind']=='body_consumed_by_coverage')
    assert .5<=event['coverage_measured']<1 and event['shell_cost']>0
    assert event['method']=='area-coverage' and event['contact_us']>=event['required_us']


def test_ties_are_direction_independent_and_retained_during_contact():
    w=fixture();w.bodies[0].thrust=w.bodies[1].thrust
    before=w.capture();w.geometry(0,1);w.geometry(1,0)
    assert w.capture()==before  # Geometric inspection must not choose a future role.
    w._predation([0,1])
    first=w.geometry(0,1)[1];assert w.geometry(1,0)[1]!=first
    for t in (20000,40000,100000):
        w.time_us=t;assert w.geometry(0,1)[1]==first
    w.bodies[1].position=[.7,.7];w._predation([0,1]);assert not w.contests


def test_protection_larger_option_and_state_restore():
    w=fixture();w.bodies[1].parent=0
    for _ in range(90):w.time_us+=w.p.period_us;w._predation([0,1])
    assert all(b.physical for b in w.bodies.values())
    w=fixture(coverage_contest='larger')
    assert not w.geometry(0,1)[1] and not w.geometry(1,0)[1]
    # Real unmodified endowments for a complete-state ledger check.
    p=CoverageProtocol(founders=2,nutrient_initial=0,reproduction=False)
    w=CoverageOcean(p.model_dump(by_alias=True));w.configure({0:'all',1:'all'},{'all':'core'})
    for _ in range(4):w.step()
    z=CoverageOcean(w.p.model_dump(by_alias=True),state=json.loads(json.dumps(w.capture())),
                    images={i:e.capture_state() for i,e in w.engines.items()})
    for _ in range(4):w.step();z.step()
    assert w.capture()==z.capture()
    assert abs(w.metrics()['energy_balance_error'])<1e-6


def test_disabled_predation_does_not_use_partial_coverage_geometry():
    w=fixture(predation=False)
    assert not w.geometry(0,1)[1] and not w.geometry(1,0)[1]
    before=abs(w.bodies[0].position[0]-w.bodies[1].position[0])
    w._predation([0,1])
    assert abs(w.bodies[0].position[0]-w.bodies[1].position[0])>before
    assert not w.contests and not w.contacts


def test_contact_winner_cannot_flip_when_only_former_loser_remains_eligible():
    w=fixture();w.bodies[0].radius=.007;w.bodies[1].radius=.009
    w.bodies[0].thrust=w.bodies[1].thrust*4
    w.bodies[1].position=[.5,.5];w._predation([0,1])
    assert w.contests[(0,1)]==0
    w.bodies[1].position=[.506,.5]
    ab,ba=coverage_fractions(w.bodies[0],w.bodies[1],w.p.side_m)
    assert ab<.5<=ba
    assert not w.geometry(0,1)[1] and not w.geometry(1,0)[1]


def test_coverage_species_archive_retains_environment_and_brain_identity(tmp_path):
    from lab.tools.ocean_contact_cli import save
    from lab.tools.ocean_species import save_candidate,seed_founders
    from threemind_lab.species_library import inspect_bundle
    p=CoverageProtocol(founders=2,nutrient_initial=0,reproduction=False)
    w=CoverageOcean(p.model_dump(by_alias=True));w.configure({0:'all',1:'all'},{'all':'core'})
    w.step();before=w.engines[0].capture_state().digest
    save(w,tmp_path/'snapshot')
    save_candidate(tmp_path/'snapshot',0,tmp_path/'candidate.tmspecies',name='Coverage candidate',evidence=[])
    raw=(tmp_path/'candidate.tmspecies').read_bytes();manifest,brain=inspect_bundle(raw)
    assert brain.digest==before
    assert manifest['environment_protocol']['schema']=='threemind.ocean-enclosure/3'
    assert manifest['environment_protocol']['enclosure_fraction']==.5
    fresh=CoverageOcean(p.model_dump(by_alias=True));seed_founders(fresh,raw,[1])
    assert fresh.seeds[1]==w.seeds[0]
    assert w.engines[0].capture_state().digest==before
