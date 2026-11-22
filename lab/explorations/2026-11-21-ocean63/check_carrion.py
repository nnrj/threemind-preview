"""Apparatus qualifications in deliberately arranged worlds, outside the formal series."""
import argparse
import hashlib
from pathlib import Path
import numpy as np

from apparatus import E38_INPUT, read, KERNEL
from carrion import Carrion63
from execution import snapshot, restore, checked_metrics, encoded
from map_view import frame, write_map
from registration import exclusive_json


def fixture(**overrides):
    config = read(E38_INPUT) | dict(schema="threemind.ocean-enclosure/2", founders=2,
        nutrient_initial=0, nutrient_capacity=0, reproduction=False, mixing_m2_s=0,
        flow_m_s=0, flow_variation_m_s=0, founder_variation=0, core_overrides={"quiescence_death_us":200000})
    world = Carrion63(config | overrides)
    world.configure({i:"engineering" for i in world.bodies},{"engineering":"core"})
    for i,b in world.bodies.items():
        b.position=[.2+i*.5,.2]
        b.velocity=[0.,0.]
    return world


def steady(world):
    world.action=lambda i:[0.,0.,0.]


def death_and_meals(out):
    w = fixture()
    steady(w)
    original_senses = w.senses
    w.senses = lambda i: (((((7,1.),) if w.time_us<=20000 else ()),[0.]) if i==0 else original_senses(i))
    events = []
    for _ in range(350):
        events.extend(w.step())
        if w.carcasses:
            break
    assert w.engines[0].life=="dead" and set(w.carcasses)=={0}
    assert w.dead_core_debits[0]==0 and w.carcasses[0]["core_remaining"]>0
    assert [e["kind"] for e in events].count("carcass_formed")==1
    def view():
        return frame(w.time_us,checked_metrics(w)["members"],w.food.tolist())
    frames = [view()]
    assert any(b[-1] and b[0]==0 for b in frames[-1][1])
    original_hash=hashlib.sha256(w.engines[0].capture_state().payload).hexdigest()
    face=w.bodies[1]
    face.position=w.bodies[0].position.copy()
    w.step()
    assert w.carrion_contacts and w.totals["carrion_meals"]==0
    path=out/"contact-before-first-bite.zip"
    snapshot(w,path)
    v=restore(path)
    steady(v)
    assert encoded(v.step())==encoded(w.step()) and encoded(v.capture())==encoded(w.capture())
    frames.append(view())
    # The last part of an otherwise ordinary meal is intentionally too small to cover its shell.
    # Set the fixture's per-bite maximum just below the initial amount, leaving one small remainder.
    amount=w.bodies[0].storage+w.body_material[0]+w.carcasses[0]["core_remaining"]
    w.p=type(w.p).model_validate(w.p.model_dump(by_alias=True)|{"nutrient_energy":amount-0.01})
    meals=[]
    for _ in range(150):
        new=w.step()
        meals.extend(e for e in new if e["kind"]=="carrion_meal")
        if any(e["kind"] in ("carrion_meal","carcass_consumed") for e in new):
            frames.append(view())
        if not w.carcasses:
            break
    assert len(meals)==2 and not w.carcasses and meals[-1]["net_after_shell"]<0
    assert abs(sum(m["gross"] for m in meals)-amount)<1e-8
    assert abs(sum(m["dead_core"] for m in meals)-w.dead_core_debits[0])<1e-8
    assert original_hash==hashlib.sha256(w.engines[0].capture_state().payload).hexdigest()
    assert all(b[0]!=0 for b in frames[-1][1])
    for _ in range(30):
        assert not any(e["kind"] in ("carrion_meal","carcass_formed") for e in w.step())
    write_map(out/"engineering-map.html","装置校验：遗体完整、部分取食和吃尽时的地图",w.p.side_m,frames)
    after=out/"after-last-bite.zip"
    snapshot(w,after)
    state=restore(after)
    return dict(natural_death_us=events[-1]["time_us"],meal_events=meals,unchanged_dead_core=original_hash,
                restored_during_contact=True,restored_after_consumption=True,
                energy_residual=checked_metrics(state)["energy_balance_error"])


def live_predation():
    w=fixture()
    steady(w)
    for b in w.bodies.values():
        b.position=[.3,.3]
        b.angle=0.
    # Explicit fixture geometry to produce a real complete-enclosure event.
    w.bodies[0].radius*=1.5
    w.replace_founder_material([0])
    events=[]
    for _ in range(900):
        events.extend(w.step())
        if w.engines[1].life=="dead":
            break
    assert any(e["kind"]=="body_engulfed" and e["predator"]==0 and e["individual"]==1 for e in events)
    assert w.engines[1].life=="dead" and 1 not in w.carcasses
    assert not any(e["kind"]=="carcass_formed" and e["individual"]==1 for e in events)
    return dict(live_enclosure=True,no_duplicate_carcass=True,balance=checked_metrics(w)["energy_balance_error"])


def drift_check():
    w=fixture(flow_m_s=.002,flow_variation_m_s=.001)
    original=w.senses
    w.senses=lambda i: (((((7,1.),) if w.time_us<=20000 else ()),[0.]) if i==0 else original(i))
    for _ in range(350):
        w.step()
        if w.carcasses:
            break
    assert 0 in w.carcasses
    position=np.array(w.bodies[0].position)
    # The water field is evaluated at the end of the body's next physical step.
    w.step()
    flow,_=w.environment(position)
    expected=(position+flow*w.p.period_us/1e6)%w.p.side_m
    observed=np.array(w.bodies[0].position)
    np.testing.assert_allclose(observed,expected,rtol=0,atol=1e-12)
    moved=float(np.linalg.norm(observed-position))
    assert moved>0 and 0 in w.carcasses
    return dict(displacement_m=moved,body_remains_visible=True)


def birth_check():
    w=fixture(reproduction=True,reproduction_age_us=0,reproduction_interval_us=20000,reproduction_cooldown_us=20000)
    w.bodies[0].storage+=5000
    w.totals["initial_body"]+=5000
    for _ in range(3):
        w.step()
    child=next(b for b in w.bodies.values() if b.parent==0)
    assert w.engines[child.id].dynamics==KERNEL and w.engines[child.id].metrics()["energy"]["initial_total"]==0
    assert w.body_material[child.id]>0 and w.construction_paid[child.id]>0
    return dict(paid_birth=True,material=w.body_material[child.id],balance=checked_metrics(w)["energy_balance_error"])


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("output",type=Path)
    out=p.parse_args().output
    out.mkdir(parents=True,exist_ok=False)
    report=dict(scope="engineering only",death=death_and_meals(out),live=live_predation(),birth=birth_check(),drift=drift_check())
    exclusive_json(out/"checks.json",report)
    print("Carcass checks passed",out,flush=True)
