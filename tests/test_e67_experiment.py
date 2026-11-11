"""Integrity checks for the E67 apparatus and matched teaching design."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from lab.tools.centered_recognition import CenteredWorld
from lab.tools.whole_scene_classroom import WholeSceneClassroom
from lab.tools.recognition_session import RecognitionSystem
from lab.tools.sensorimotor_session import SensorimotorSession

PATH = Path(__file__).resolve().parents[1]/'lab/explorations/2026-10-11-shape-color-kernels/curriculum.py'
spec = importlib.util.spec_from_file_location('e67_curriculum', PATH)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def test_empty_centered_scene_preserves_background_and_next_observation():
    w = CenteredWorld()
    w.set_scene([], positions=[])
    for _ in range(3):
        w.advance_physics()
    restored = CenteredWorld.restore(w.state())
    assert restored.state() == w.state()
    w.advance_physics(); restored.advance_physics()
    left, right = w.observe(), restored.observe()
    assert left == right
    assert left['items'] == [] and left['positions'] == []
    assert np.isfinite(left['values']).all()
    assert w.stimulus(left) == restored.stimulus(right)
    with pytest.raises(ValueError):
        WholeSceneClassroom().set_scene([], positions=[])


@pytest.mark.parametrize('kernel', ['2', '3.1', '4'])
def test_full_subject_keeps_selected_kernel_on_restore(tmp_path, kernel):
    identity = 'threemind.continuous-memory/' + kernel
    a = RecognitionSystem(kernel_id=identity)
    a.session.tick()
    a.save(tmp_path/'whole')
    b = RecognitionSystem.restore(tmp_path/'whole')
    assert b.session.engine.dynamics == identity
    assert a.session.tick() == b.session.tick()
    with pytest.raises(ValueError):
        SensorimotorSession(state=a.session.snapshot(), kernel_id='threemind.causal/9')


def test_matched_correction_covers_exact_errors_and_excludes_final_positions():
    questions = c.bank('development', c.DEV, 6711)
    predictions = {arm: [t | {'correct': i not in errors} for i, t in enumerate(questions)]
                   for arm, errors in zip(c.ARMS, ({0, 1}, {1, 2}))}
    plan = c.matched_correction(1, predictions)
    assert len(plan['union_errors']) == 3
    calibration = {c.condition(t) for t in plan['calibration']}
    assert all(c.condition(t) in calibration for t in plan['union_errors'])
    assert len([t for t in plan['lessons'] if t['operation'] == 'correct-failed-question']) == 3
    assert set(c.FINAL).isdisjoint(tuple(t['offset']) for t in plan['calibration'] + plan['lessons'])
    assert len(c.initial_curriculum()) == 104
    assert sum(t['gap_s'] + 1.5 for t in c.initial_curriculum()) == 180
    assert len(c.initial_calibration()) == 48
    assert c.score([t | {'correct': True} for t in questions])['pairs'] == {'n': 32, 'correct': 32}
    assert c.ARMS == ('2', '3.1')
    with pytest.raises(ValueError, match='exactly the active'):
        c.matched_correction(1, predictions | {'4-adaptive': []})
