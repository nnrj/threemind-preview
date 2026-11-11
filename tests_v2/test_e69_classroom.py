"""Protocol/runner checks with a deterministic fake Core, not research results."""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.centered_recognition import WORDS

HERE = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color'


@pytest.fixture
def modules(monkeypatch):
    result = {}
    for name in ('system', 'classroom', 'curriculum', 'journal', 'experiment'):
        spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        result[name] = module
    return SimpleNamespace(**result)


class Layout:
    width = 4

    def frame(self, activity):
        return np.array(activity['fake_values'], dtype=np.float32)


class Motor:
    def __init__(self):
        self.layout = Layout()
        self.windows = []
        self.output = {'eye_receptor': 67, 'hand_receptor': 48, 'move': True}

    def intent(self, values):
        self.windows.append(values.copy())
        return copy.deepcopy(self.output)


class Words:
    def __init__(self):
        self.layout = Layout()
        self.features = 4
        self.windows = []

    def predict(self, values):
        self.windows.append(values.copy())
        return np.array([[1., 0., 0., 0., 0., 0., 0., 0.]])


class Session:
    """Actual apparatus mechanics, inexpensive synthetic Core activity."""
    def __init__(self):
        self.world = ActiveEyeClassroom()
        self.base = self.world.observe()
        self.engine = SimpleNamespace(time_us=0)
        self.dt_us = 50000
        self.sensor = SimpleNamespace(frames=lambda text: [{'char': char} for char in text])
        self.text = []

    def observation(self):
        w = self.world
        w._refresh_directions()
        row = copy.deepcopy(self.base)
        row.update(time_s=w.time_s, eye_angle_rad=w.eye_angle.tolist(),
                   eye_velocity_rad_s=w.eye_velocity.tolist(), teacher_marker=copy.deepcopy(w.marker),
                   pointer=copy.deepcopy(w.state()['pointer']), items=w.items, positions=w.positions,
                   camera={'origin_m': w.origin.tolist(), 'forward': w.forward.tolist(),
                           'right': w.right.tolist(), 'up': w.up.tolist(), 'aperture': w.eye_config.aperture})
        return row

    def tick(self, frame=None, *, eye=(0., 0.), hand=(0., 0.)):
        ob = self.observation()
        self.text.append(None if frame is None else frame['char'])
        self.engine.time_us += self.dt_us
        n = self.engine.time_us / self.dt_us
        self.world.advance_physics(hand, self.dt_us / 1e6, eye_action=eye)
        return {'observation': ob, 'activity': {'time_us': str(self.engine.time_us),
                                              'fake_values': [n, n + 1, n + 2, n + 3]},
                'eye_action': list(eye), 'hand_action': list(hand)}


def student(modules):
    return SimpleNamespace(session=Session(), motor=Motor(), words=Words(),
                           executor=modules.system.Executor(), meter={}, identity='stub-e69-not-a-subject')


def test_full_request_and_separate_answer_free_naming_question(modules):
    a = student(modules)
    task = modules.curriculum.task('semantic', 0)
    rows, data, result, _ = modules.classroom.trial(a, task, collect=True)
    assert ''.join(char for char in a.session.text if char is not None) == task['text'] + task['word_question']
    assert len(rows) == modules.classroom.TICKS + 20
    expected = modules.system.window(a.motor.layout, rows[:modules.classroom.QUESTION_TICKS])
    assert np.array_equal(a.motor.windows[0], expected)
    assert a.motor.windows[0][0, 0] == 1
    assert a.motor.windows[0][-1, 0] == modules.classroom.QUESTION_TICKS
    word_expected = modules.system.window(a.words.layout, rows[-20:])[None]
    assert np.array_equal(a.words.windows[-1], word_expected)
    assert np.array_equal(data['word_x'], word_expected)
    assert data['word_y'].tolist() == [task['label']]
    assert result['start_us'] == 0 and result['end_us'] == len(rows) * 50000
    assert result['motor_window_s'] == 6
    main_score = modules.classroom.score(task, rows[:120], result['answer'])
    assert result['hand_final_error_m'] == main_score['hand_final_error_m']
    assert result['new_decisions'] == 8
    assert result['post_naming']['new_decisions'] == 10
    assert all(row['observation']['teacher_marker'] is None for row in rows)


def test_semantic_request_never_supplies_queried_attribute(modules):
    for index in range(72):
        task = modules.curriculum.task('semantic', index, split='final', seed=69300)
        if task['label'] is None:
            continue
        answer = WORDS[task['label']]
        assert answer not in task['text'] and answer not in task['word_question']
        assert task['word_question'] in ('这是什么形状？', '这是什么颜色？')


def test_long_question_rejected_instead_of_silently_truncated(modules):
    a = student(modules)
    task = modules.curriculum.task('gaze', 0)
    task['text'] = '看' * (modules.classroom.QUESTION_TICKS + 1)
    with pytest.raises(ValueError, match='complete registered request'):
        modules.classroom.trial(a, task)
    assert a.session.engine.time_us == 0 and not a.session.text


def test_calibration_labels_match_actual_acquisition_geometry_and_complete_prefix(modules):
    a = student(modules)
    task = modules.curriculum.task('coordination', 1)
    rows, data, _, samples = modules.classroom.trial(a, task, collect=True)
    indices = [i for i in range(modules.classroom.TICKS)
               if i >= modules.classroom.QUESTION_TICKS - 1 and (i + 1) % modules.classroom.DECISION_TICKS == 0]
    assert len(samples) == len(data['x']) == len(indices)
    expected = []
    for j, i in enumerate(indices):
        row = rows[i]
        label = modules.classroom.receptor(row['observation'], modules.classroom.eye_goal(task))
        expected.append(label)
        assert data['eye_y'][j] == label
        assert samples[j]['time_us'] == row['activity']['time_us']
        assert np.array_equal(data['x'][j], modules.system.window(a.motor.layout, rows[:i + 1]))
        if data['move_y'][j]:
            assert data['hand_y'][j] == modules.classroom.receptor(
                row['observation'], [*task['positions'][task['target']], .16])
        else:
            assert data['hand_y'][j] == -1
    assert len(set(expected)) > 1  # A final-pose label would be wrong for some samples.
    assert all(row['observation']['teacher_marker'] is not None for row in rows[:20])
    assert all(row['observation']['teacher_marker'] is None for row in rows[20:])
    assert a.session.world.marker is None


def test_teacher_actions_are_explicit_and_not_autonomous_commands(modules):
    a = student(modules)
    task = modules.curriculum.task('coordination', 2)
    rows, _, result, samples = modules.classroom.trial(a, task, teaching=True)
    assert result['teaching'] is True
    assert result['autonomous_success'] is None
    assert result['eye_before_hand'] is None and result['word_correct'] is None
    assert result['success'] == (result['eye_success'] and result['hand_success'])
    assert modules.experiment.summary([result])['autonomous_n'] == 0
    assert all(row['assistance'] and row['teacher_eye_action'] is not None for row in rows)
    assert all(row['eye_action'] == row['teacher_eye_action'] for row in rows)
    assert all(row['hand_action'] == row['teacher_hand_action'] for row in rows)
    assert any(row['own_eye_action'] != row['eye_action'] for row in rows)
    assert all(sample['source'] == 'demonstration' for sample in samples)


def test_next_question_keeps_body_time_and_counts_inherited_move(modules):
    a = student(modules)
    first = modules.curriculum.task('coordination', 0)
    modules.classroom.trial(a, first)
    w = a.session.world
    before = copy.deepcopy(w.state())
    prior_us = a.session.engine.time_us
    assert a.executor.last_intent['move']
    second = modules.curriculum.task('coordination', 3)
    rows, _, result, _ = modules.classroom.trial(a, second)
    assert rows[0]['observation']['pointer'] == before['pointer']
    assert rows[0]['observation']['eye_angle_rad'] == before['eye_angle']
    assert rows[0]['observation']['eye_velocity_rad_s'] == before['eye_velocity']
    assert result['start_us'] == prior_us
    assert result['first_move_command_s'] == 2
    assert rows[0]['own_decision'] is None
    assert result['new_decisions'] == 8
    assert rows[0]['own_intent']['move'] is True
    xy=np.array([[r['observation']['pointer']['x'],r['observation']['pointer']['y']] for r in rows])
    distance=float(np.linalg.norm(np.diff(xy[:40],axis=0),axis=1).sum())
    assert result['hand_distance_during_first_2s_m'] == pytest.approx(distance)
    assert distance < float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum())


def test_runner_completed_lesson_receipt_does_not_reexecute(modules, monkeypatch, tmp_path):
    a = student(modules)
    a.cursor = 0
    a.phase = 'birth'
    run = modules.experiment.ClassroomRun.__new__(modules.experiment.ClassroomRun)
    run.a, run.work, run.identity = a, tmp_path, a.identity
    run.study = SimpleNamespace(append=lambda *args: None, attach=lambda *args: None, sync=lambda: None)
    keys = set()
    pointer = {'boundary_sha256': 'birth', 'checkpoint': 'test-boundary'}
    calls = []

    def execute(key, operation):
        assert key not in keys
        calls.append(key)
        operation(a)
        keys.add(key)
        pointer['boundary_sha256'] = key

    run.journal = SimpleNamespace(keys=keys, pointer=pointer, execute=execute)
    task = modules.curriculum.task('gaze', 0)
    first = run.lessons('stub-stage', [task])
    assert len(calls) == 1
    after = a.session.engine.time_us

    def forbidden(*args, **kwargs):
        raise AssertionError('completed classroom operation was executed twice')

    monkeypatch.setattr(modules.experiment, 'trial', forbidden)
    second = run.lessons('stub-stage', [task])
    assert first == second and a.session.engine.time_us == after and len(calls) == 1
    # An absent aggregate may be reconstructed from committed per-unit evidence.
    (tmp_path / 'stages/stub-stage/result.json').unlink()
    third = run.lessons('stub-stage', [task])
    assert third['results'] == first['results'] and len(calls) == 1
    assert json.loads((tmp_path / 'stages/stub-stage/units/000000.json').read_text())['id'] == task['id']


def fit_runner(modules, tmp_path):
    class Head:
        computed_updates = 0

        def __init__(self):
            self.batches = []

        def continue_calibration(self, *, x, eye_y, hand_y, move_y, steps):
            self.batches.append(len(x))
            self.computed_updates += steps
            return {'computed_updates': self.computed_updates, 'committed_updates': self.computed_updates,
                    'updates': steps, 'n': len(x)}

    run = modules.experiment.ClassroomRun.__new__(modules.experiment.ClassroomRun)
    a = SimpleNamespace(identity='fit-stub-not-a-subject', session=SimpleNamespace(engine=SimpleNamespace(time_us=123000)),
                        motor=Head(), meter={}, corpora=[], verify_dependencies=lambda: None)
    run.a, run.work, run.identity = a, tmp_path, a.identity
    published = []
    run.study = SimpleNamespace(append=lambda *args: published.append(copy.deepcopy(args)), sync=lambda: None)
    keys = set()

    def execute(key, operation):
        assert key not in keys
        operation(a)
        keys.add(key)

    run.journal = SimpleNamespace(keys=keys, execute=execute)
    path = tmp_path / 'samples.npz'
    np.savez_compressed(path, x=np.zeros((2, 8, 4), dtype=np.float32), eye_y=[0, 1], hand_y=[-1, 2], move_y=[0, 1])
    a.corpora.append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return run, published


def test_completed_fit_receipt_uses_its_own_evidence_not_later_growth(modules, monkeypatch, tmp_path):
    run, published = fit_runner(modules, tmp_path)
    result = run.fit('fit-original', 'motor')
    assert result['computed_updates'] == 1200 and result['examples'] == 2 and result['time_us'] == 123000
    assert run.a.motor.batches == [2] * 24
    # Simulate subsequent complete stages; replaying the orchestration must not
    # reinterpret the old fit using these later states or new sources.
    run.a.motor.computed_updates = 9900
    run.a.session.engine.time_us = 999999
    run.a.corpora.append({'path': 'later-unavailable.npz', 'sha256': 'later'})

    def forbidden(*args, **kwargs):
        raise AssertionError('completed calibration must not load or fit again')

    monkeypatch.setattr(run.a, 'verify_dependencies', forbidden)
    monkeypatch.setattr(run.a.motor, 'continue_calibration', forbidden)
    monkeypatch.setattr(modules.experiment.np, 'load', forbidden)
    assert run.fit('fit-original', 'motor') == result
    # Rebuild only the missing aggregate from the committed old last block.
    (tmp_path / 'stages/fit-original/motor-result.json').unlink()
    assert run.fit('fit-original', 'motor') == result
    assert all(entry[2] == result for entry in published)
    assert run.a.session.engine.time_us == 999999 and run.a.motor.computed_updates == 9900


def test_partially_completed_fit_keeps_frozen_sources_and_never_repeats_blocks(modules, tmp_path):
    run, _ = fit_runner(modules, tmp_path)
    execute = run.journal.execute

    def pause(key, operation):
        if len(run.journal.keys) == 5:
            raise InterruptedError('clean pre-update boundary')
        return execute(key, operation)

    run.journal.execute = pause
    with pytest.raises(InterruptedError):
        run.fit('partial', 'motor')
    assert run.a.motor.computed_updates == 250
    path = tmp_path / 'later.npz'
    np.savez_compressed(path, x=np.zeros((7, 8, 4), dtype=np.float32), eye_y=[0] * 7,
                        hand_y=[-1] * 7, move_y=[0] * 7)
    run.a.corpora.append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    run.journal.execute = execute
    result = run.fit('partial', 'motor')
    assert run.a.motor.batches == [2] * 24
    assert result['computed_updates'] == 1200 and result['examples'] == 2


def test_frozen_curriculum_rejects_changed_questions_even_with_rewritten_manifest(modules, tmp_path):
    experiment = modules.experiment
    expected = {'questions.json': experiment.banks()} | {
        f'curricula/{stage}-initial.json': experiment.initial(stage) for stage in experiment.STAGES}
    for name, value in expected.items():
        experiment.fixed_json(tmp_path / name, value)
    manifest = {name: experiment.sha(tmp_path / name) for name in expected}
    experiment.fixed_json(tmp_path / 'curriculum-manifest.json', manifest)
    experiment.verify_curriculum(tmp_path)
    assert not (tmp_path / 'subject').exists()

    questions = copy.deepcopy(expected['questions.json'])
    questions['semantic']['final'][0]['target'] = (questions['semantic']['final'][0]['target'] + 1) % 4
    (tmp_path / 'questions.json').write_bytes(experiment.encoded(questions))
    with pytest.raises(ValueError, match='frozen curriculum changed: questions.json'):
        experiment.verify_curriculum(tmp_path)
    # Editing both the data and its manifest cannot replace the frozen generator.
    manifest['questions.json'] = experiment.sha(tmp_path / 'questions.json')
    (tmp_path / 'curriculum-manifest.json').write_bytes(experiment.encoded(manifest))
    with pytest.raises(ValueError, match='frozen curriculum changed: questions.json'):
        experiment.verify_curriculum(tmp_path)
    assert not (tmp_path / 'subject').exists()
