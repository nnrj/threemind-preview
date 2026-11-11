import json

import pytest

from lab.tools.ocean_enclosure import EnclosureOcean, EnclosureProtocol


def fixture(shell=0):
    p=EnclosureProtocol(founders=2,population_limit=97,nutrient_initial=0,
        reproduction=False,founder_variation=0,flow_m_s=0,flow_variation_m_s=0)
    w=EnclosureOcean(p.model_dump(by_alias=True))
    w.configure({0:'all',1:'all'},{'all':'core'})
    a,b=w.bodies.values()
    a.radius,b.radius=.014,.007
    a.elongation=b.elongation=0;a.position,b.position=[.5,.5],[.525,.5]
    a.angle=b.angle=0;b.shell=shell
    return w


def advance_inward(w,steps):
    for _ in range(steps):
        for _ in range(4):
            w._move(w.bodies[0],[1,0,0]);w._move(w.bodies[1],[-1,0,0])
        w.time_us+=w.p.period_us;w._predation([0,1])
        if not w.bodies[1].physical:break


def test_full_enclosure_reachable_by_motion_not_contact_capture():
    w=fixture();advance_inward(w,250)
    events=[e for e in w.events if e['kind']=='body_engulfed']
    assert len(events)==1 and events[0]['method']=='enclosure'
    assert events[0]['contact_us']>=events[0]['required_us']
    assert w.geometry(0,1)[1]
    assert w.bodies[0].captured==1


def test_touch_does_not_consume_and_shell_delays_complete_enclosure():
    w=fixture();w.bodies[1].position=[.521,.5]
    for _ in range(150):
        w.time_us+=w.p.period_us;w._predation([0,1])
    assert w.bodies[1].physical and not w.contacts
    worlds=[fixture(shell) for shell in (0,.8)]
    for w in worlds:
        w.bodies[1].position=[.5,.5]
        for _ in range(16):
            w.time_us+=w.p.period_us;w._predation([0,1])
    assert not worlds[0].bodies[1].physical and worlds[1].bodies[1].physical
    for _ in range(40):
        worlds[1].time_us+=worlds[1].p.period_us;worlds[1]._predation([0,1])
    e=next(e for e in worlds[1].events if e['kind']=='body_engulfed')
    assert e['shell_cost']>0 and e['required_us']>worlds[0].p.engulf_dwell_us


def test_bilateral_protection_and_state_identity():
    w=fixture();w.bodies[0].parent=1;w.bodies[1].position=[.5,.5]
    for _ in range(70):
        w.time_us+=w.p.period_us;w._predation([0,1])
    assert all(b.physical for b in w.bodies.values())
    # A newly initialized world verifies wrapper and parameter preservation.
    w=fixture();state=json.loads(json.dumps(w.capture()))
    z=EnclosureOcean(w.p.model_dump(by_alias=True),state=state,
        images={i:e.capture_state() for i,e in w.engines.items()})
    for _ in range(5):w.step();z.step()
    assert w.capture()==z.capture() and not z.p.capture_enabled
    with pytest.raises(ValueError):EnclosureProtocol(capture_enabled=True)
