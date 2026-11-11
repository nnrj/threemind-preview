import numpy as np
from lab.tools.ocean_encounter import ActivityHistory,candidate,measurement,observe_encounter
from lab.tools.ocean_behavior import BehaviorOcean
from lab.tools.ocean_contact import ContactProtocol


def test_prospective_observer_preserves_state_and_subtracts_prior_intake(tmp_path):
    w=BehaviorOcean(ContactProtocol(founders=1,nutrient_initial=0,founder_variation=0).model_dump(by_alias=True))
    b=w.bodies[0];b.position=[.4,.4];b.angle=0.;b.velocity=[.01,0.];b.grains=12
    w.food=np.asarray([[.43,.4]]);w.food_ids=[0];w.next_food_id=1
    w.totals['environment_food']=w.p.nutrient_energy
    image=w.engines[0].capture_state().payload
    event=candidate(w,'food')
    assert event and event['focal']==0 and event['target']==0
    history=ActivityHistory();history.sample(w,0)
    assert measurement(w,0,'food',0)['closing_velocity']>0
    assert w.engines[0].capture_state().payload==image
    r=observe_encounter(w,tmp_path/'encounter',event,'intact',.2)
    assert r['status']=='horizon_paused' and r['food']==w.bodies[0].grains-12
    assert not candidate(w,'hunt')
