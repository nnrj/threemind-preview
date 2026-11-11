import json
import numpy as np
import pytest
import torch
from lab.tools.developmental_motor import DevelopmentalMotor
from lab.tools.developmental_world import DevelopmentalWorld
from lab.tools.developmental_session import DevelopmentalSession


def test_learning_optimizer_replay_and_rng_continue(tmp_path):
    torch.set_num_threads(2)
    m = DevelopmentalMotor([1, 2, 3, 4, 5], [1, 2, 3, 4], identity='individual-a', seed=19)
    x = np.random.default_rng(5).uniform(0, 1, (16, 20)).astype('float32')
    y = np.array([.2, -.1, .4, -.2], dtype='float32')
    m.teach(x, y); m.variation(.05, .1); m.save(tmp_path/'head')
    r = DevelopmentalMotor.restore(tmp_path/'head', expected_identity='individual-a')
    assert np.array_equal(m.intent(x), r.intent(x))
    assert np.array_equal(m.variation(.05, .1), r.variation(.05, .1))
    assert m.teach(x*.7, -y) == r.teach(x*.7, -y)
    assert m.steps == r.steps == 4
    for a, b in zip(m.parameters(), r.parameters()): assert torch.equal(a, b)
    assert m.intent(x*0) is None
    with pytest.raises(ValueError, match='wrong individual'): DevelopmentalMotor.restore(tmp_path/'head', expected_identity='b')


def test_calibration_inspection_leaves_next_update_unchanged(tmp_path):
    from lab.tools.developmental_inspect import retained_calibration
    torch.set_num_threads(2)
    m = DevelopmentalMotor([1,2,3,4,5], [1,2,3,4], identity='inspection', seed=52)
    x = np.random.default_rng(5).normal(size=(16,20)).astype('float32')
    y = np.array([.2,-.3,.1,.4], dtype='float32')
    m.teach(x,y); m.save(tmp_path/'model')
    reference = DevelopmentalMotor.restore(tmp_path/'model')
    report = retained_calibration(m)
    assert report['retained_examples'] == 1
    assert report['mean_squared_pose_error'] >= 0
    assert retained_calibration(m, reference)['example_source_motor_steps'] == reference.steps
    reference.identity = 'different-individual'
    with pytest.raises(ValueError, match='same individual'):
        retained_calibration(m, reference)
    reference.identity = m.identity
    assert m.teach(x,-y) == reference.teach(x,-y)
    for a,b in zip(m.parameters(), reference.parameters()): assert torch.equal(a,b)


def test_complete_system_resume_action_feedback_and_next_update(tmp_path):
    torch.set_num_threads(2)
    a = DevelopmentalSession(seed=623, identity='a')
    target = [.2, .1, .3, .2]
    for _ in range(5): a.step(teacher_pose=target, assistance=.6, learn=True, variation=.04)
    assert np.array_equal(a.motor.replay_x[-1], a.window())
    assert a.session.history[-1]['development']['supervision_time_us'] == a.session.current['time_us']
    a.save(tmp_path/'system'); b = DevelopmentalSession.restore(tmp_path/'system')
    assert a.session.current == b.session.current
    assert json.loads(json.dumps(list(a.session.history))) == list(b.session.history)
    assert np.array_equal(a.window(), b.window())
    assert a.session.snapshot() == b.session.snapshot()
    for _ in range(2):
        ra = a.step(teacher_pose=target, assistance=.3, learn=True, variation=.04)
        rb = b.step(teacher_pose=target, assistance=.3, learn=True, variation=.04)
        assert json.loads(json.dumps(ra)) == json.loads(json.dumps(rb))
        assert a.session.snapshot() == b.session.snapshot()
    for x, y in zip(a.motor.parameters(), b.motor.parameters()): assert torch.equal(x, y)
    assert a.session.stream.published == b.session.stream.published


def test_sensory_metadata_cannot_supply_answer_and_servo_can_hold():
    w = DevelopmentalWorld(toys=False)
    observation = w.observe(); actual = w.stimulus(observation)
    observation.update(answer='red sphere', target=[.7, .8], items=[], positions=[])
    assert w.stimulus(observation) == actual
    for _ in range(200): w.advance_physics()
    assert np.linalg.norm([w.pointer.x, w.pointer.y]) < .04
    target = np.array([.2, -.2, .4, -.4])
    for _ in range(100):
        forces = w.execute_pose(target)
        w.advance_physics(forces[2:], eye_action=forces[:2])
    assert np.linalg.norm(np.array([w.pointer.x, w.pointer.y])-target[2:]) < .01
    assert np.linalg.norm(w.eye_angle-target[:2]*w.eye_config.angle_limit_rad) < .002
    r = DevelopmentalWorld.restore(w.state())
    assert r.state() == w.state()
    assert r.stimulus(r.observe()) == w.stimulus(w.observe())


def test_moving_toys_contact_and_self_hearing_survive_restore():
    w = DevelopmentalWorld()
    for _ in range(45):
        force = w.execute_pose([0., 0., .29, .28])
        w.advance_physics(force[2:], eye_action=force[:2], mouth=(.2, .3))
    assert w.contact_count > 0
    assert np.any(w.acoustic_bands() > 0)
    r = DevelopmentalWorld.restore(w.state())
    for _ in range(3):
        assert w.stimulus(w.observe()) == r.stimulus(r.observe())
        w.advance_physics((-.3, .2), eye_action=(.1, -.1), mouth=(.2, .3))
        r.advance_physics((-.3, .2), eye_action=(.1, -.1), mouth=(.2, .3))
        assert w.state() == r.state()


def test_checkpoint_cannot_be_overwritten_or_swapped(tmp_path):
    a = DevelopmentalSession(seed=624, identity='a'); a.save(tmp_path/'a')
    sibling = DevelopmentalSession.restore(tmp_path/'a', branch='quiet')
    assert sibling.identity == sibling.motor.identity == 'a/quiet'
    for x, y in zip(a.motor.parameters(), sibling.motor.parameters()): assert torch.equal(x, y)
    assert a.session.snapshot() == sibling.session.snapshot()
    with pytest.raises(FileExistsError): a.save(tmp_path/'a')
    manifest = tmp_path/'a'/'motor'/'manifest.json'
    state = json.loads(manifest.read_text(encoding='utf-8')); state['identity'] = 'b'
    manifest.write_text(json.dumps(state), encoding='utf-8')
    with pytest.raises(ValueError, match='wrong individual'): DevelopmentalSession.restore(tmp_path/'a')


def test_developmental_replay_distinguishes_teacher_and_own_output(tmp_path):
    import gzip
    from lab.tools.active_vision_replay import pack
    a = DevelopmentalSession(seed=623, identity='replay')
    rows = [a.step(teacher_pose=[0.,0.,.3,.2], assistance=.6)]
    p = tmp_path/'process.jsonl.gz'
    with gzip.open(p, 'wt', encoding='utf-8') as stream:
        stream.write(json.dumps({'phase':'teaching', 'trial':{'text':'用手指这里。'}, 'process':rows})+'\n')
        stream.write(json.dumps({'phase':'evaluation', 'trial':{'text':'用眼睛看这里。'}, 'process':[a.step()]})+'\n')
    replay = pack([p], 'continuous')
    assert len(replay['clips']) == 2
    assert '60%' in replay['clips'][0]['action_source']
    assert '0%' in replay['clips'][1]['action_source']
    assert replay['clips'][0]['frames'][0]['body_feedback']['motor']['identity'] == 'replay'
