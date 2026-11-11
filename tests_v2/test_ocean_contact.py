import json
import math

import numpy as np
import pytest

from lab.tools.ocean_contact import ContactOcean, ContactProtocol, capsule, uniform_counter


def world(**kw):
    return ContactOcean(ContactProtocol(founders=2, reproduction=False, founder_variation=0, **kw).model_dump(by_alias=True))


def contact_fixture(shell):
    w = world(nutrient_initial=0)
    a, b = w.bodies.values()
    a.radius, b.radius = .011, .008
    a.elongation = b.elongation = 0
    a.position, b.position = [.1, .1], [.119, .1]
    a.angle = b.angle = 0
    b.shell = shell
    return w


def test_capture_shell_delay_release_and_parent_protection():
    light, hard = contact_fixture(0), contact_fixture(.8)
    for w in (light, hard):
        for _ in range(22):
            w.time_us += w.p.period_us
            w._predation([0, 1])
    assert light.totals['predations'] == 1
    assert hard.totals['predations'] == 0
    hard.bodies[1].position = [.5, .5]
    hard._predation([0, 1])
    assert not hard.contacts and hard.totals['capture_breaks'] > 0
    protected = contact_fixture(0)
    protected.bodies[1].parent = 0
    for _ in range(30):
        protected.time_us += protected.p.period_us
        protected._predation([0, 1])
    assert protected.totals['predations'] == 0 and protected.totals['protected_contacts'] > 0


def test_capsule_shape_changes_contact_and_preserves_area():
    w = world(nutrient_initial=0)
    a, b = w.bodies.values()
    a.position, b.position = [.1, .1], [.12, .1]
    a.angle = b.angle = 0
    a.elongation = b.elongation = 1.5
    p, q, r = capsule(a)
    assert math.isclose(math.pi*r*r + 2*r*np.linalg.norm(q-p), math.pi*a.radius*a.radius)
    gap1 = w.geometry(0, 1)[0]
    a.angle = b.angle = math.pi/2
    assert w.geometry(0, 1)[0] > gap1


def test_food_noise_not_shifted_by_deleted_neighbor():
    assert uniform_counter([2, 7, 99], 123, 3031).tolist()[1:] == uniform_counter([7, 99], 123, 3031).tolist()


def test_save_resume_and_energy_without_altering_core():
    w = world(mode='random', nutrient_initial=20)
    for _ in range(25):
        w.step()
    assert abs(w.metrics()['energy_balance_error']) < 1e-6
    state = json.loads(json.dumps(w.capture()))
    images = {i:e.capture_state() for i,e in w.engines.items()}
    z = ContactOcean(state['protocol'], state=state, images=images)
    for _ in range(10):
        w.step(); z.step()
    assert w.capture() == z.capture()
    assert all(e.config.propagation_interval_us == 100000 for e in w.engines.values())
    assert all(e.capture_state().to_dict()['dynamics'] == 'threemind.continuous-memory/2' for e in w.engines.values())


def test_core_actions_ignore_random_control_parameters():
    a, b = world(), world(random_interval_us=20000, random_amplitude=.1)
    for _ in range(12):
        a.step(); b.step()
    assert a.last_actions == b.last_actions
    assert a.engines[0].capture_state().digest == b.engines[0].capture_state().digest


def test_fusion_disabled_and_bad_clock_rejected():
    with pytest.raises(ValueError):
        ContactProtocol(recombination_probability=.1)
    with pytest.raises(ValueError):
        ContactProtocol(random_interval_us=31000)


def test_optional_age_control_does_not_become_a_default_limit():
    assert ContactProtocol().maximum_age_us is None
    w=world(maximum_age_us=20000,nutrient_initial=0)
    w.step();events=w.step()
    assert all(not b.physical and b.body_failure=='configured_age_limit' for b in w.bodies.values())
    assert sum(e['kind']=='body_age_limit' for e in events)==2


def test_predation_disabled_keeps_collision_without_capture_or_transfer():
    w=world(nutrient_initial=0,predation=False)
    a,b=w.bodies.values()
    a.radius,b.radius=.011,.008
    a.elongation=b.elongation=0
    a.position,b.position=[.1,.1],[.118,.1]
    before=a.storage,b.storage;peak_collision=0
    for _ in range(60):
        w.time_us+=w.p.period_us;w._predation([0,1])
        peak_collision=max(peak_collision,a.collision,b.collision)
    assert a.physical and b.physical
    assert w.totals['contact_frames']>0 and peak_collision>0
    assert w.totals['predations']==w.totals['capture_starts']==0
    assert (a.storage,b.storage)==before
    assert not w.contacts
