"""Engineering checks on new disposable subjects; never a formal E69 student."""
import copy
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import torch

from lab.tools.active_eye import ActiveEyeClassroom

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/system.py'
SPEC = importlib.util.spec_from_file_location('e69_system_engineering_tests', SOURCE)
SYSTEM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYSTEM)


@pytest.fixture(autouse=True)
def limited_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def assert_equal(left, right):
    if isinstance(left, torch.Tensor):
        assert torch.equal(left, right)
    elif isinstance(left, np.ndarray):
        assert np.array_equal(left, right)
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            assert_equal(left[key], right[key])
    elif isinstance(left, (list, tuple)):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            assert_equal(a, b)
    else:
        assert left == right


def subject(tmp_path):
    return SYSTEM.EyeHandSystem(identity='engineering-e69-continuity-only', data_root=tmp_path)


def tick(a, text):
    s = a.session
    if s.history:
        intent = a.motor.intent(SYSTEM.window(a.motor.layout, list(s.history)))
        a.executor.accept(intent, s.history[-1]['observation'], s.world)
    eye, hand = a.executor.commands(s.world)
    return s.tick(text, eye=eye, hand=hand)


def test_complete_current_system_restores_next_input_action_and_both_updates(tmp_path):
    a = subject(tmp_path)
    frames = list(a.session.sensor.frames('看这里。'))
    for frame in frames[:3]:
        tick(a, frame)
    x = SYSTEM.window(a.motor.layout, list(a.session.history))[None]
    a.motor.continue_calibration(x, [17], [35], [1], steps=1, batch_size=1)
    a.words.continue_calibration(x, [2], steps=1)
    a.phase, a.cursor = 'engineering-check', 3
    a.meter = {'observations': 3}
    a.save(tmp_path / 'complete')
    b = SYSTEM.EyeHandSystem.restore(tmp_path / 'complete', device='cpu', backend='native', data_root=tmp_path)
    assert a.session.engine.dynamics == b.session.engine.dynamics == 'threemind.continuous-memory/5.1'
    assert_equal(a.session.snapshot(), b.session.snapshot())
    assert_equal(a.executor.state(), b.executor.state())
    assert_equal(list(a.session.history), list(b.session.history))
    assert a.phase == b.phase and a.cursor == b.cursor and a.meter == b.meter
    next_frame = next(iter(a.session.sensor.frames('手')))
    left, right = tick(a, next_frame), tick(b, next_frame)
    assert_equal(left, right)
    assert_equal(a.session.snapshot(), b.session.snapshot())
    assert_equal(a.executor.state(), b.executor.state())
    current = SYSTEM.window(a.motor.layout, list(a.session.history))[None]
    for value in (a, b):
        value.motor.continue_calibration(current, [16], [-1], [0], steps=1, batch_size=1)
        value.words.continue_calibration(current, [4], steps=1)
    for name in ('motor', 'words'):
        one, two = getattr(a, name), getattr(b, name)
        assert_equal(one.state_dict(), two.state_dict())
        assert_equal(one.optimizer.state_dict(), two.optimizer.state_dict())
        assert_equal(one.learning_rng, two.learning_rng)
        assert one.computed_updates == one.committed_updates == two.committed_updates == 2


def test_observation_and_complete_save_do_not_advance_or_change_core(tmp_path):
    a = subject(tmp_path)
    tick(a, next(iter(a.session.sensor.frames('看'))))
    core = a.session.engine.capture_state().to_dict()
    world = copy.deepcopy(a.session.world.state())
    current = copy.deepcopy(a.session.current)
    history = copy.deepcopy(list(a.session.history))
    before = a.describe()
    a.session.world.observe()
    a.session.world.observe()
    a.save(tmp_path / 'inspection')
    assert_equal(core, a.session.engine.capture_state().to_dict())
    assert_equal(world, a.session.world.state())
    assert_equal(current, a.session.current)
    assert_equal(history, list(a.session.history))
    assert_equal(before, a.describe())


def test_scene_change_preserves_body_eye_velocities_and_physical_time():
    world = ActiveEyeClassroom()
    world.advance_physics((.2, -.1), .05, eye_action=(.4, -.3))
    before = copy.deepcopy(world.state())
    channels = world.channels
    world.set_scene([(0, 1), (2, 3), (1, 0)], positions=[[-.5, -.5], [.5, .5], [-.5, .5]])
    after = world.state()
    for key in ('pointer', 'eye_angle', 'eye_velocity', 'eye_power', 'time_s', 'body_temperature',
                'acceleration', 'motor_power', 'contact_force'):
        assert_equal(before[key], after[key])
    assert channels == world.channels
    assert len(world.items) == 3


def test_wait_latches_own_hand_position_and_ignores_scoring_metadata():
    world = ActiveEyeClassroom()
    world.advance_physics((.8, -.1), .05, eye_action=(.1, 0))
    row = world.observe()
    altered = copy.deepcopy(row)
    altered.update(items=['false answer'], positions=[[99., 99.]], teacher_marker=[-99., 99.],
                   target=[99., -99.], scoring_goal='never pass to execution')
    first, second = SYSTEM.Executor(), SYSTEM.Executor()
    intent = {'eye_receptor': 12, 'hand_receptor': None, 'move': False}
    for executor, observation in ((first, row), (second, altered)):
        executor.accept(intent, observation, world)
    assert_equal(first.state(), second.state())
    initial = [world.pointer.x, world.pointer.y]
    assert first.hand_target == initial
    world.advance_physics((1., 0.), .05, eye_action=(0., 0.))
    first.accept(intent, world.observe(), world)
    assert first.hand_target == initial
    eye, hand = first.commands(world)
    assert np.isfinite(eye).all() and np.isfinite(hand).all()
    assert np.any(hand)  # A servo counters drift; the body was not forcibly frozen.


def test_eye_and_hand_selections_are_independent_and_none_adds_no_intent():
    world = ActiveEyeClassroom()
    observation = world.observe()
    a, b, c = SYSTEM.Executor(), SYSTEM.Executor(), SYSTEM.Executor()
    a.accept({'eye_receptor': 0, 'hand_receptor': 50, 'move': True}, observation, world)
    b.accept({'eye_receptor': 0, 'hand_receptor': 60, 'move': True}, observation, world)
    c.accept({'eye_receptor': 35, 'hand_receptor': 50, 'move': True}, observation, world)
    assert a.eye_target == b.eye_target and a.hand_target != b.hand_target
    assert a.hand_target == c.hand_target and a.eye_target != c.eye_target
    original = a.state()
    a.accept(None, observation, world)
    assert a.state() == original
    d = SYSTEM.Executor()
    d.accept(None, observation, world)
    assert not any(np.any(v) for v in d.commands(world))


def corpus(a, root):
    location = root / 'source' / 'calibration.npz'
    location.parent.mkdir()
    np.savez_compressed(location, x=np.zeros((1, 8, a.motor.layout.width), dtype=np.float32), y=[0])
    a.corpora = [{'path': 'source/calibration.npz', 'sha256': hashlib.sha256(location.read_bytes()).hexdigest()}]
    return location


@pytest.mark.parametrize('failure', ['missing', 'changed', 'unsafe', 'absolute', 'no-root'])
def test_checkpoint_rejects_missing_changed_or_unsafe_dependencies(tmp_path, failure):
    a = subject(tmp_path)
    file = corpus(a, tmp_path)
    a.save(tmp_path / 'dependent')
    if failure == 'missing':
        file.unlink()
    elif failure == 'changed':
        file.write_bytes(file.read_bytes() + b'changed')
    elif failure == 'unsafe':
        a.corpora[0]['path'] = '../outside.npz'
    elif failure == 'absolute':
        a.corpora[0]['path'] = str(file.resolve())
    else:
        a.data_root = None
    with pytest.raises(ValueError, match='calibration'):
        a.save(tmp_path / 'invalid')
    assert not (tmp_path / 'invalid').exists()
    assert not (tmp_path / 'invalid.partial').exists()
    if failure in ('missing', 'changed', 'no-root'):
        with pytest.raises(ValueError, match='calibration'):
            SYSTEM.EyeHandSystem.restore(tmp_path / 'dependent', data_root=None if failure == 'no-root' else tmp_path)
