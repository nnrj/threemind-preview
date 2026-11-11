import copy
import numpy as np
import pytest
from lab.tools.body_playground import BodyPlayground, ExploratoryMotor
from lab.tools.eye_hand_world import EyeHandWorld


def test_world_restores_action_consequences_and_fixed_channels():
    w = BodyPlayground(); ports = w.channels
    w.pointer.x, w.pointer.y = -.19, -.18
    for _ in range(12): w.advance_physics((-.3, -.1), eye_action=(.2, -.3), mouth=(.6, .1))
    assert w.contact_count > 0 and np.any(w.resonance > 0)
    assert np.any(w.acoustic_bands() > 0) and not np.array_equal(w.anchors, w.positions)
    r = BodyPlayground.restore(w.state())
    assert w.stimulus(w.observe()) == r.stimulus(r.observe())
    for _ in range(4):
        w.advance_physics((.3, -.1), eye_action=(-.2, .1), mouth=(.1, .4))
        r.advance_physics((.3, -.1), eye_action=(-.2, .1), mouth=(.1, .4))
    assert w.state() == r.state() and w.channels == ports and len(set(ports)) == len(ports)


def test_metadata_cannot_supply_answers_and_self_voice_has_feedback():
    w = BodyPlayground(); initial = w.observe(); stim = w.stimulus(initial)
    changed = copy.deepcopy(initial); changed.update(items=['answer'], positions=[[999, 999]], toy_contacts=999)
    assert w.stimulus(changed) == stim
    silent = w.acoustic_bands()
    w.advance_physics(mouth=(.8, -.5))
    assert np.linalg.norm(w.acoustic_bands()-silent) > .1
    assert w.observe()['values'][-4] == .8
    with pytest.raises(ValueError): w.advance_physics(mouth=(float('nan'), 0))


def test_old_eye_ports_and_input_are_unchanged_when_new_senses_are_zero():
    old = EyeHandWorld(); new = BodyPlayground(toys=False)
    new.set_scene(old.items, positions=old.positions)
    a, b = dict(old.stimulus(old.observe()).channels), dict(new.stimulus(new.observe()).channels)
    assert all(a.get(ch, 0) == b.get(ch, 0) for ch in old.channels)
    assert tuple(new.channels[:len(old.channels)]) == old.channels


def test_exploration_wiring_is_reproducible_and_does_not_read_metadata():
    p = ExploratoryMotor(20, seed=1); x = np.linspace(0, .2, 20); before = x.copy()
    a, parts = p.action(x); q = ExploratoryMotor.restore(p.state())
    assert np.array_equal(p.action(x)[0], q.action(x)[0]) and np.array_equal(x, before)
    assert np.allclose(a, np.clip(np.array(parts['core_component'])+parts['motor_variation'], -1, 1))
    pure = ExploratoryMotor(20, seed=1, noise_std=0)
    assert np.array_equal(pure.action(np.zeros(20))[0], np.zeros(6))


def test_replay_preserves_new_physical_feedback_without_semantic_reinterpretation(tmp_path):
    import gzip,json
    from lab.tools.active_vision_replay import pack
    w=BodyPlayground(); w.advance_physics(mouth=(.3,.2))
    row={'observation':w.observe(),'activity':{'nodes':[]},'eye_action':[0,0],'hand_action':[0,0],
        'action_source':'fixed wiring + separately recorded motor variation'}
    path=tmp_path/'process.jsonl.gz'
    with gzip.open(path,'wt',encoding='utf-8') as f:f.write(json.dumps({'kind':'exploration','process':[row]})+'\n')
    data=pack([path],'test'); frame=data['clips'][0]['frames'][0]
    assert frame['body_feedback']['mouth']==[.3,.2]
    assert frame['body_feedback']['ears']==row['observation']['ears_band_pressure']
    assert len(frame['values'])==w.vision_width
    row['action_source']='caregiver withdrawn'
    with gzip.open(path,'at',encoding='utf-8') as f:f.write(json.dumps({'kind':'exploration','process':[row]})+'\n')
    assert len(pack([path],'test')['clips'])==2


def test_external_actor_changes_physics_and_ears_but_does_not_command_infant():
    w=BodyPlayground();w.external_forces[0]=[.2,.4];w.external_sound[:]=[.01,.02,0,.01]
    baseline=w.state(); w.advance_physics()
    assert w.positions!=baseline['positions'] and np.any(w.acoustic_bands()>0)
    r=BodyPlayground.restore(w.state())
    w.advance_physics();r.advance_physics()
    assert w.state()==r.state()
    # Adapter actuator gain does not mutate the raw Core observation.
    motor=ExploratoryMotor(20,noise_std=0,activity_gain=.1);x=np.ones(20);before=x.copy()
    action,_=motor.action(x)
    assert np.array_equal(x,before) and np.allclose(action,np.tanh(.1*(motor.weights@x)))
