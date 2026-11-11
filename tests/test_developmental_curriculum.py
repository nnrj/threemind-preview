import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('developmental_curriculum', Path(__file__).resolve().parents[1]/'lab/explorations/2026-10-07-continuous-development/curriculum.py')
curriculum = importlib.util.module_from_spec(spec); spec.loader.exec_module(curriculum)


def test_schedule_keeps_actual_registered_order_and_spacing():
    steps = curriculum.schedule('direct')
    initial = steps[:120]
    assert [(s['mode'], s['target']) for s in initial] == [(m,t) for m in ('look','point','both') for t in range(4) for _ in range(10)]
    assert all(s['assistance'] == .8-.6*(i%10)/9 for i,s in enumerate(initial))
    assert [s['seconds'] for s in steps if s['kind']=='gap'] == [2.,6.,18.]
    assert len([s for s in steps if s['kind']=='lesson']) == 156
    for review in range(3):
        actual = [s for s in steps if s['phase']==f'review-{review+1}']
        expected = np.random.default_rng(62200+review).permutation(12)
        assert [(s['mode'],s['target']) for s in actual] == [(('look','point','both')[i//4],int(i%4)) for i in expected]
    assert curriculum.schedule('explore')[30:] == steps
    assert curriculum.schedule('quiet')[30:] == steps


def test_resume_keeps_remaining_curriculum_and_rejects_changed_group():
    steps = curriculum.schedule('direct')
    for i, task in enumerate(steps):
        if task['checkpoint']:
            value = curriculum.cursor('direct', i+1)
            restored = curriculum.validate_cursor(value, 'direct')
            assert steps[:restored]+steps[restored:] == steps
            with pytest.raises(ValueError): curriculum.validate_cursor(value, 'explore')
    altered = curriculum.cursor('direct', 10) | {'schedule': 'unregistered'}
    with pytest.raises(ValueError): curriculum.validate_cursor(altered, 'direct')
