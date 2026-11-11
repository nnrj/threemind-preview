import json
import numpy as np
import pytest
from lab.tools.ocean_association import AssociationOcean, AssociationProtocol
from lab.tools.ocean_material import MaterialOcean
from lab.tools.ocean_species import save_live_candidate, seed_founders
from threemind_lab.species_library import inspect_bundle


def world(**overrides):
    p=AssociationProtocol(founders=3,population_limit=5,nutrient_initial=1,nutrient_capacity=20,
        founder_variation=0,elongation=0,flow_m_s=0,flow_variation_m_s=0,
        reproduction=False,**overrides)
    w=AssociationOcean(p.model_dump(by_alias=True))
    w.configure({i:'all' for i in w.bodies},{'all':'core'})
    return w


def test_zero_sharing_preserves_material_dynamics_and_restore():
    a=world();p={k:v for k,v in a.p.model_dump(by_alias=True).items()
                 if k not in ('intake_share_fraction','association_gap_m','association_dwell_us')}
    p['schema']='threemind.ocean-enclosure/2';b=MaterialOcean(p)
    b.configure({i:'all' for i in b.bodies},{'all':'core'})
    for _ in range(12):a.step();b.step()
    observed=a.capture()['material'];expected=b.capture()
    # Protocol identity/optional observation parameters intentionally differ.
    observed['enclosure']['group']['community']['world']['protocol']=p
    assert observed==expected
    restored=AssociationOcean(a.p.model_dump(by_alias=True),state=json.loads(json.dumps(a.capture())),
        images={i:e.capture_state() for i,e in a.engines.items()})
    a.step();restored.step()
    assert a.capture()==restored.capture()


def test_shares_only_new_intake_after_proximity_dwell_without_extra_energy():
    w=world(intake_share_fraction=.25)
    w.bodies[0].position=[.3,.3];w.bodies[1].position=[.3165,.3];w.bodies[2].position=[.7,.7]
    w._update_associations([0,1,2])
    w.time_us=500000;w.food=np.array([[.3,.3]])
    w._ingest([0,1,2]);w._predation([0,1,2])
    assert not [e for e in w.events if e['kind']=='intake_resource_exchange']
    w.time_us=1000000;w._add_food(1);w.food=np.array([[.3,.3]])
    w._ingest([0,1,2]);before=[b.storage for b in w.bodies.values()]
    w._predation([0,1,2])
    e=next(e for e in w.events if e['kind']=='intake_resource_exchange')
    assert e['donor']==0 and e['receiver']==1
    assert e['sent']==pytest.approx(w.p.nutrient_energy*.25)
    assert e['received']==pytest.approx(e['sent']*.9)
    assert w.bodies[2].storage==before[2]
    assert abs(w.metrics()['energy_balance_error'])<1e-6
    balances=[b.storage for b in w.bodies.values()]
    w._predation([0,1,2])
    assert [b.storage for b in w.bodies.values()]==balances


def test_proximity_is_geometric_and_capacity_limits_transfer():
    w=world(intake_share_fraction=.25)
    w.bodies[0].position=[.7998,.3];w.bodies[1].position=[.0163,.3];w.bodies[2].position=[.6,.6]
    assert (0,1) in w._near_pairs([0,1,2])  # Periodic boundary.
    w.bodies[1].position=list(w.bodies[0].position)
    assert (0,1) not in w._near_pairs([0,1,2])  # Deep enclosure is not edge contact.
    w.bodies[1].position=[.0163,.3];w.associations={(0,1):0};w.time_us=1000000
    w.totals['initial_body']+=w.p.storage_capacity-w.bodies[1].storage
    w.bodies[1].storage=w.p.storage_capacity;w.intake={0:100.}
    old=w.bodies[0].storage;w._share_intake()
    assert w.bodies[0].storage==old and w.bodies[1].storage==w.p.storage_capacity
    assert abs(w.metrics()['energy_balance_error'])<1e-6


def test_multiple_candidate_sources_preserve_provenance(tmp_path):
    source=world();source.step()
    raws=[]
    for i in (0,1):
        path=tmp_path/f'{i}.tmspecies'
        save_live_candidate(source,i,path,name=f'source{i}',evidence=[],source={'case':'fixture'},
                            description='test archive')
        raws.append(path.read_bytes())
    target=world();seed_founders(target,raws[0],[0]);seed_founders(target,raws[1],[1,2])
    assert len(target.research['species_founder_batches'])==2
    assert target.research['species_founders']['ids']==[0]
    before=target.engines[0].capture_state().digest
    with pytest.raises(ValueError,match='unassigned'):seed_founders(target,raws[1],[0])
    assert target.engines[0].capture_state().digest==before
    out=tmp_path/'descendant.tmspecies'
    save_live_candidate(target,2,out,name='copied',evidence=[],source={})
    m,_=inspect_bundle(out.read_bytes())
    assert m['source']['inherited_candidate']['ids']==[1,2]
    assert abs(target.metrics()['energy_balance_error'])<1e-6


def test_many_neighbors_split_one_budget_and_predation_intake_can_be_shared():
    w=world(intake_share_fraction=.25);w.time_us=1000000
    w.associations={(0,1):0,(0,2):0};w.intake={0:100.}
    before=[b.storage for b in w.bodies.values()];w._share_intake()
    assert before[0]-w.bodies[0].storage==pytest.approx(25)
    assert w.bodies[1].storage-before[1]==pytest.approx(11.25)
    assert w.bodies[2].storage-before[2]==pytest.approx(11.25)
    assert abs(w.metrics()['energy_balance_error'])<1e-6
    gain=w._consume_body_energy(w.bodies[0],w.bodies[2])
    w.bodies[2].physical=False
    old=w.bodies[1].storage;w._share_intake()
    assert w.bodies[1].storage-old==pytest.approx(gain['transferred']*.25*.9)
    assert w.bodies[2].storage==0
    assert abs(w.metrics()['energy_balance_error'])<1e-6
