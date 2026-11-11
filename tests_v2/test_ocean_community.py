"""Counterfactual apparatus checks; these are not ecological evidence."""
import gzip
import json

import pytest
from lab.tools.ocean_community import CommunityOcean,place_birth_clock,focal_intervention,load,run
from lab.tools.ocean_contact import ContactProtocol
from lab.tools.ocean_contact_cli import save
from threemind_core import Stimulus
from threemind_runtime import create_engine
from threemind_runtime.inheritance import birth


def world():
    w=CommunityOcean(ContactProtocol(founders=3,nutrient_initial=20,reproduction=False).model_dump(by_alias=True))
    for _ in range(12):w.step()
    return w


def test_birth_origin_translation_preserves_relative_dynamics():
    w=world();image=birth(w.engines[0].capture_state());offset=60000000
    a=create_engine(state=image,backend='native')
    b=create_engine(state=place_birth_clock(image,offset),backend='native')
    for e in (a,b):
        e.supply_energy(100,time_us=e.time_us,source='test');e.advance_to(e.time_us)
    for t in (20000,120000,200000):
        for e,origin in ((a,0),(b,offset)):
            e.inject(Stimulus(t+origin,((100,1.),(101,.5)),.3));e.advance_to(t+origin)
        assert a.activations()==b.activations()
        x,y=a.capture_state().to_dict(),b.capture_state().to_dict()
        for k in ('since_us','last_settlement_us'):y['energy'][k]=str(int(y['energy'][k])-offset)
        assert x['energy']==y['energy'] and x['transport']==y['transport']
        for key in ('nodes','edges'):
            for left,right in zip(x[key],y[key],strict=True):
                for k in ('birth_us','last_touch_us'):right[k]=str(int(right[k])-offset)
            assert x[key]==y[key]
    with pytest.raises(ValueError):place_birth_clock(a.capture_state(),offset)


def test_focal_births_retain_whole_habitat_age_reserves_and_other_engines(tmp_path):
    w=world();save(w,tmp_path/'source')
    original=w.capture();images={i:e.capture_state().payload for i,e in w.engines.items()}
    edges=w.engines[0].capture_state().to_dict()['edges']
    plan={'target_edges':[[e['source'],e['target']] for e in edges[:2]],
          'matched_edges':[[e['source'],e['target']] for e in edges[2:4]]}
    for op in ('experienced','blank','graft','graft-matched','target','matched','random'):
        z=load(tmp_path/'source');reserve=z.engines[0].metrics()['energy']['reserve']
        focal_intervention(z,0,op,plan);after=z.capture()['world']
        assert after['bodies']==original['world']['bodies']
        for k in ('food','food_ids','next_food_id','time_us','contacts'):
            assert after[k]==original['world'][k]
        assert z.engines[0].time_us==w.engines[0].time_us
        assert z.engines[0].metrics()['energy']['reserve']==pytest.approx(reserve)
        assert all(z.engines[i].capture_state().payload==images[i] for i in (1,2))
        z.step();assert abs(z.metrics()['energy_balance_error'])<1e-5
    assert w.capture()==original


def test_random_control_resume_and_full_recording(tmp_path):
    w=world();focal_intervention(w,0,'random',{})
    save(w,tmp_path/'state');z=load(tmp_path/'state')
    for _ in range(5):
        assert w.action(0)==z.action(0)
        w.step();z.step()
    assert w.capture()==z.capture()
    result=run(z,tmp_path/'observed',.3,focal=0)
    assert result['status']=='horizon_paused'
    with gzip.open(tmp_path/'observed/trajectory.jsonl.gz','rt') as f:rows=[json.loads(s) for s in f]
    assert len(rows)==3 and all(len(r['members'])==3 and len(r['food_positions'])>1 for r in rows)


def test_bilateral_parent_protection_is_explicit_restorable_and_expires(tmp_path):
    w=world();w.bodies[1].parent=0;w.bodies[1].birth_us=w.time_us
    assert w._protected_pair(0,1,w.time_us)
    assert not w._protected_pair(1,0,w.time_us)  # Old state keeps the original rule.
    w.research['parent_protection']='bilateral-until-maturity/1'
    assert w._protected_pair(0,1,w.time_us) and w._protected_pair(1,0,w.time_us)
    assert not w._protected_pair(2,1,w.time_us)
    mature=w.time_us+w.p.maturity_us
    assert not w._protected_pair(0,1,mature) and not w._protected_pair(1,0,mature)
    save(w,tmp_path/'protected');z=load(tmp_path/'protected')
    assert z._protected_pair(1,0,z.time_us)
