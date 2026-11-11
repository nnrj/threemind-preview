import copy

import numpy as np
import pytest
import torch

from lab.tools.continuous_foveal_motor import ContinuousFovealMotor


@pytest.fixture(autouse=True)
def limited_threads():
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(old)


def model():
    centers = [(x / 10, y / 10) for y in (-1, 0, 1) for x in (-1, 0, 1)]
    return ContinuousFovealMotor(range(1, 39), range(1, 37), centers, [[.1, .1]] * 9,
                                 identity='continuous-student', seed=17)


def examples(m):
    x = np.random.default_rng(31).uniform(0, .8, (6, 8, m.layout.width)).astype('float32')
    return x, np.array([0, 1, 2, 3, 4, 5]), np.array([8, -1, 6, -1, 4, -1]), np.array([1, 0, 1, 0, 1, 0])


def assert_tree_equal(left, right):
    if isinstance(left, torch.Tensor):
        assert torch.equal(left, right)
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            assert_tree_equal(left[key], right[key])
    elif isinstance(left, (list, tuple)):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            assert_tree_equal(a, b)
    else:
        assert left == right


def test_complete_restore_preserves_next_prediction_and_learning_update(tmp_path):
    a = model()
    data = examples(a)
    a.continue_calibration(*data, steps=3)
    a.save(tmp_path / 'head')
    b = ContinuousFovealMotor.restore(tmp_path / 'head', expected_identity=a.identity)
    assert a.intent(data[0][0]) == b.intent(data[0][0])
    assert_tree_equal(a.state_dict(), b.state_dict())
    assert_tree_equal(a.optimizer.state_dict(), b.optimizer.state_dict())
    assert torch.equal(a.learning_rng, b.learning_rng)
    for head in (a, b):
        head.continue_calibration(*data, steps=1)
    assert_tree_equal(a.state_dict(), b.state_dict())
    assert_tree_equal(a.optimizer.state_dict(), b.optimizer.state_dict())
    assert torch.equal(a.learning_rng, b.learning_rng)
    assert a.computed_updates == a.committed_updates == b.committed_updates == 4
    with pytest.raises(ValueError, match='wrong individual'):
        ContinuousFovealMotor.restore(tmp_path / 'head', expected_identity='different')


def test_training_batches_and_pauses_preserve_last_state_not_best():
    a, b = model(), model()
    data = examples(a)
    a.continue_calibration(*data, steps=5)
    for _ in range(5):
        b.continue_calibration(*data, steps=1)
    assert_tree_equal(a.state_dict(), b.state_dict())
    assert_tree_equal(a.optimizer.state_dict(), b.optimizer.state_dict())
    assert torch.equal(a.learning_rng, b.learning_rng)
    assert a.committed_updates == b.committed_updates == 5


def test_pause_before_update_keeps_complete_current_update():
    a, b = model(), model()
    data = examples(a)
    calls = 0

    def pause():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise InterruptedError('boundary')

    with pytest.raises(InterruptedError):
        a.continue_calibration(*data, steps=5, check=pause)
    b.continue_calibration(*data, steps=2)
    assert a.computed_updates == a.committed_updates == 2
    assert_tree_equal(a.state_dict(), b.state_dict())
    assert_tree_equal(a.optimizer.state_dict(), b.optimizer.state_dict())
    assert torch.equal(a.learning_rng, b.learning_rng)


def test_no_input_no_command_and_no_answer_argument():
    a = model()
    x = examples(a)[0]
    before = copy.deepcopy(a.state_dict())
    assert a.intent(np.zeros_like(x[0])) is None
    for key in ('target', 'stage', 'teacher', 'correct_position', 'task'):
        with pytest.raises(TypeError):
            a.intent(x[0], **{key: 0})
    assert_tree_equal(before, a.state_dict())
    assert a.learning_rng is None and not a.optimizer.state
    with pytest.raises(TypeError, match='continue_calibration'):
        a.fit(x, [0] * len(x))
    with pytest.raises(TypeError, match='independent'):
        a.select(x[0])


def test_wait_masks_hand_output_and_hand_supervision():
    a = model()
    x, eye, _, _ = examples(a)
    with torch.no_grad():
        a.move_head.weight.zero_()
        a.move_head.bias.copy_(torch.tensor([20., -20.]))
    output = a.intent(x[0])
    assert output['move'] is False and output['hand_receptor'] is None
    assert 0 <= output['eye_receptor'] < 9
    result = a.continue_calibration(x, eye, [-1] * len(x), [0] * len(x), steps=1)
    assert result['hand_supervised'] == 0 and np.isfinite(result['loss'])
    with torch.no_grad():
        a.move_head.weight.zero_()
        a.move_head.bias.copy_(torch.tensor([-20., 20.]))
    output = a.intent(x[0])
    assert output['move'] is True and 0 <= output['hand_receptor'] < 9


@pytest.mark.parametrize('bad', ['empty', 'nonfinite', 'fractional', 'move-range', 'hand-range', 'move-missing-hand'])
def test_invalid_training_evidence_fails_before_mutation(bad):
    a = model()
    x, eye, hand, move = examples(a)
    if bad == 'empty':
        x, eye, hand, move = x[:0], eye[:0], hand[:0], move[:0]
    elif bad == 'nonfinite':
        x[0, 0, 0] = float('nan')
    elif bad == 'fractional':
        eye = eye.astype(float) + .5
    elif bad == 'move-range':
        move[0] = 2
    elif bad == 'hand-range':
        hand[1] = 9
    elif bad == 'move-missing-hand':
        hand[0] = -1
    before = copy.deepcopy(a.state_dict())
    with pytest.raises(ValueError):
        a.continue_calibration(x, eye, hand, move, steps=1)
    assert_tree_equal(before, a.state_dict())
    assert a.committed_updates == 0 and not a.optimizer.state


def test_birth_and_restore_do_not_reseed_global_rng(tmp_path):
    torch.manual_seed(452)
    before = torch.random.get_rng_state().clone()
    a = model()
    assert torch.equal(before, torch.random.get_rng_state())
    a.save(tmp_path / 'blank')
    b = ContinuousFovealMotor.restore(tmp_path / 'blank')
    assert torch.equal(before, torch.random.get_rng_state())
    assert b.learning_rng is None and b.computed_updates == 0


def test_move_gate_does_not_read_receptor_geometry():
    a = model()
    x = examples(a)[0]
    before = a.predict(x)
    with torch.no_grad():
        a.geometry.add_(100)
    after = a.predict(x)
    assert np.array_equal(before['move_logits'], after['move_logits'])
    assert not np.array_equal(before['eye_logits'], after['eye_logits'])


@pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA unavailable')
def test_cuda_restore_next_update_and_global_rng(tmp_path):
    torch.cuda.manual_seed_all(457)
    before = torch.cuda.get_rng_state_all()
    a = model().to('cuda')
    assert all(torch.equal(x, y) for x, y in zip(before, torch.cuda.get_rng_state_all()))
    data = examples(a)
    a.continue_calibration(*data, steps=2)
    a.save(tmp_path / 'cuda')
    b = ContinuousFovealMotor.restore(tmp_path / 'cuda', device='cuda', expected_identity=a.identity)
    for item in (a, b):
        item.continue_calibration(*data, steps=1)
    assert_tree_equal(a.state_dict(), b.state_dict())
    assert_tree_equal(a.optimizer.state_dict(), b.optimizer.state_dict())
    assert torch.equal(a.learning_rng, b.learning_rng)
    assert all(torch.equal(x, y) for x, y in zip(before, torch.cuda.get_rng_state_all()))
