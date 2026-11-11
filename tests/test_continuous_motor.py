import numpy as np
import pytest
from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.eye_hand_world import EyeHandWorld, teacher_eye_angle, motor_metrics
from lab.tools.continuous_motor import ContinuousMotor, recent_window


def test_new_world_without_nose_preserves_actual_mapping():
    old = ActiveEyeClassroom(); new = EyeHandWorld()
    for i in range(4):
        assert old.channels == new.channels
        assert old.stimulus(old.observe()) == new.stimulus(new.observe())
        old.advance_physics((.3, -.1), eye_action=(.2, .3))
        new.advance_physics((.3, -.1), eye_action=(.2, .3))
    restored = EyeHandWorld.restore(new.state())
    assert new.stimulus(new.observe()) == restored.stimulus(restored.observe())


def test_nose_is_head_fixed_and_not_metadata_or_center_target():
    w = EyeHandWorld(nose=True); plain = EyeHandWorld()
    first = np.asarray(w.observe()['values'][:w.vision_width]).reshape(-1, 4)
    reference = np.asarray(plain.observe()['values'][:w.vision_width]).reshape(-1, 4)
    changed = np.any(first != reference, axis=1)
    assert changed.any() and not changed[:36].any()
    location = w.nose_geometry()[0].copy()
    w.eye_angle[:] = [.15, -.12]
    assert np.array_equal(location, w.nose_geometry()[0])
    observation = w.observe(); stim = w.stimulus(observation)
    assert np.any(first != np.asarray(observation['values'][:w.vision_width]).reshape(-1, 4))
    observation.update(nose=False, items=['answer'], positions=['answer'])
    assert w.stimulus(observation) == stim
    assert w.stimulus(w.observe()) == EyeHandWorld.restore(w.state()).stimulus(EyeHandWorld.restore(w.state()).observe())


def test_physical_eye_can_turn_and_hold_without_dwell_gate():
    w = EyeHandWorld(); target = teacher_eye_angle(w, (.55, .55))
    for _ in range(70): w.advance_physics(eye_action=w.eye_servo(target))
    assert np.linalg.norm(w.eye_angle-target) < .005
    assert np.linalg.norm(w.eye_velocity) < .005


@pytest.mark.parametrize('organization', ['shared', 'separate'])
@pytest.mark.parametrize('readout_version', [1, 2])
def test_motor_raw_input_restore_and_zero_output(tmp_path, organization, readout_version):
    model = ContinuousMotor([91, 38, 72], organization=organization, seed=4, readout_version=readout_version)
    x = np.random.default_rng(7).uniform(0, 1, (3, 16, 12)).astype('float32'); copy = x.copy()
    y = np.zeros((3, 4), dtype='float32'); y[0, :2] = .2
    model.fit(x, y, validation=(x, y), steps=2)
    assert np.array_equal(copy, x)
    assert np.all(model.action(np.zeros((16, 12))) == 0)
    assert model.action(x[0]).shape == (4,)
    model.save(tmp_path/'motor'); restored = ContinuousMotor.restore(tmp_path/'motor')
    assert np.allclose(model.predict(x), restored.predict(x))
    with pytest.raises(ValueError): model.action(np.full((16, 12), np.nan))


def test_recent_windows_are_past_only_and_preserve_order():
    from lab.tools.activity_controller import ActivityLayout
    layout = ActivityLayout([1])
    rows = [{'activity': {'nodes': [{'channel': 1, 'activation': float(i), 'inhibition': 0., 'direct': 0., 'associative': 0.}]}} for i in range(20)]
    assert recent_window(layout, rows)[:, 0].tolist() == list(range(4, 20))
    assert recent_window(layout, rows[:2])[:, 0].tolist() == [0.]*15+[1.]


def test_large_demonstration_bins_actually_learn_instead_of_empty_batches():
    import torch
    torch.set_num_threads(2)
    model = ContinuousMotor([1, 2], seed=11)
    x = np.zeros((128, 16, 8), dtype='float32')
    x[:64, :, 0] = .8; x[64:, :, 0] = .2
    y = np.zeros((128, 4), dtype='float32'); y[:64, :2] = .4
    initial = np.mean((model.predict(x)-y)**2)
    result = model.fit(x, y, validation=(x, y), steps=80)
    assert result['validation_mse'] < initial*.2
    assert np.mean((model.predict(x)-y)**2) < .01
    with pytest.raises(ValueError): model.fit(x[:0], y[:0], validation=(x, y), steps=1)


def test_fixation_requires_target_alignment_as_well_as_low_speed():
    w = EyeHandWorld(); rows = [{'observation': w.observe()} for _ in range(20)]
    wrong = motor_metrics(rows, [[.2, .2]]*20, [[0., 0.]]*20)
    aligned = motor_metrics(rows, [[0., 0.]]*20, [[0., 0.]]*20)
    assert wrong['eye_stable_fraction'] == 0 and wrong['eye_longest_stable_s'] == 0
    assert aligned['eye_stable_fraction'] == 1 and aligned['eye_longest_stable_s'] == 1


def test_replay_accepts_new_world_and_preserves_control_source(tmp_path):
    import gzip, json
    from lab.tools.active_vision_replay import pack
    w = EyeHandWorld(nose=True)
    row = {'observation': w.observe(), 'activity': {'nodes': [], 'time_us': 123456}, 'eye_action': [0, 0], 'hand_action': [0, 0],
           'action_source': 'teacher guidance'}
    path = tmp_path/'process.jsonl.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        f.write(json.dumps({'task': {'text': 'look'}, 'process': [row], 'action_source': 'teacher guidance'})+'\n')
    data = pack([path], 'test', {path.parent.name: 'Teacher-only demonstration'})
    assert data['clips'][0]['action_source'] == 'teacher guidance'
    assert data['clips'][0]['frames'][0]['nose'] is True
    assert data['clips'][0]['frames'][0]['core_t'] == .123456
    assert data['clips'][0]['frames'][0]['t'] == 0
    assert data['clips'][0]['case_label'] == 'Teacher-only demonstration'
