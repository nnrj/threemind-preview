"""Pre-birth curriculum audit; these checks do not run a research subject."""
import importlib.util
from collections import Counter
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from lab.tools.centered_recognition import WORDS

SOURCE = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color/curriculum.py'
SPEC = importlib.util.spec_from_file_location('e69_curriculum_audit', SOURCE)
CURRICULUM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CURRICULUM)


def assert_valid_semantic_request(row):
    target = row['target']
    shape, color = row['items'][target]
    mode = row['mode']
    if mode == 0:
        matches = [i for i, (_, c) in enumerate(row['items']) if c == color]
        assert row['label'] == shape
        assert row['word_question'] == '这是什么形状？'
        assert row['text'] == f'先看{WORDS[4+color]}的物体，再指出。'
    elif mode == 1:
        matches = [i for i, (s, _) in enumerate(row['items']) if s == shape]
        assert row['label'] == 4+color
        assert row['word_question'] == '这是什么颜色？'
        assert row['text'] == f'先看{WORDS[shape]}，再指出。'
    else:
        matches = [i for i, (s, c) in enumerate(row['items']) if (s, c) == (shape, color)]
        assert sum(s == shape for s, _ in row['items']) >= 2
        assert sum(c == color for _, c in row['items']) >= 2
        assert row['label'] is None and row['word_question'] is None
        assert row['text'] == f'先看{WORDS[4+color]}的{WORDS[shape]}，再指出。'
    assert matches == [target]
    if row['label'] is not None:
        assert WORDS[row['label']] not in row['text']
        assert WORDS[row['label']] not in row['word_question']
    assert len(row['items']) == row['count'] == len(row['positions'])
    assert all(0 <= s < 4 and 0 <= c < 4 for s, c in row['items'])


def test_semantic_banks_have_unambiguous_questions_and_necessary_conjunctions():
    banks = CURRICULUM.banks()
    assert banks == CURRICULUM.banks()
    for bank in banks['semantic'].values():
        for row in bank:
            assert_valid_semantic_request(row)
    transfer = banks['semantic']['transfer']
    assert Counter(row['target'] for row in transfer) == {0: 4, 1: 4, 2: 4}
    for mode in range(3):
        assert {row['target'] for row in transfer if row['mode'] == mode} == {0, 1, 2}


def test_each_taught_concept_rotates_quadrants_without_fabricated_naming_score():
    rows = CURRICULUM.initial('semantic')
    assert len(rows) == 104
    assert len({row['id'] for row in rows}) == len(rows)
    for concept in range(8):
        selected = [row for row in rows if row['concept'] == concept]
        assert len(selected) == 13
        initial = [row for row in selected if '-initial-' in row['id']]
        review = [row for row in selected if '-review-' in row['id']]
        assert {row['target'] for row in initial} == {0, 1, 2, 3}
        assert len({row['target'] for row in review}) == 3
        for row in selected:
            assert row['teacher_only'] and row['mode'] is None
            assert row['label'] is None and row['word_question'] is None
            expected = (concept, 4) if concept < 4 else (2, concept-4)
            assert row['items'][row['target']] == expected
            assert row['statement'] == f'看这个物体，这是{WORDS[concept]}。'


@pytest.mark.parametrize('stage', ['gaze', 'coordination'])
def test_direction_teaching_keeps_all_directions_and_review(stage):
    rows = CURRICULUM.initial(stage)
    assert len(rows) == 52
    for index in range(4):
        assert {row['target'] for row in rows[index*10:(index+1)*10]} == {index}
    assert Counter(row['target'] for row in rows[-12:]) == {0: 3, 1: 3, 2: 3, 3: 3}


def test_correction_covers_attribute_neighbors_and_all_prior_correct_conditions():
    dev = CURRICULUM.banks()['semantic']['dev']
    before = deepcopy(dev)
    results = [{'id': row['id'], 'success': i >= 3} for i, row in enumerate(dev)]
    rows = CURRICULUM.correction('semantic', 1, results, dev)
    assert dev == before
    failed = dev[:3]  # All three instruction modes.
    correction = [row for row in rows if row['split'] == 'correction']
    review = [row for row in rows if row['split'] == 'review']
    assert len(correction) == 4*len(failed)
    assert len(review) == 3*len(dev)
    for original in failed:
        variants = {row['similarity']: row for row in correction if row['original_question'] == original['id']}
        assert set(variants) == {'original-failure', 'position-neighbor', 'changed-color', 'changed-shape'}
        for variant in variants.values():
            assert_valid_semantic_request(variant)
            assert variant['target'] == original['target']
        np.testing.assert_allclose(variants['position-neighbor']['positions'],
                                   np.asarray(original['positions']) + [.025, -.025])
        for factor in ('color', 'shape'):
            changed = variants[f'changed-{factor}']
            assert changed['positions'] == original['positions']
            assert changed['attribute_scope'] == 'all-objects'
            for old, new in zip(original['items'], changed['items']):
                if factor == 'color':
                    assert old[0] == new[0] and old[1] != new[1]
                else:
                    assert old[1] == new[1] and old[0] != new[0]
    counts = Counter(CURRICULUM._condition_key(row) for row in review)
    assert counts == Counter({CURRICULUM._condition_key(row): 3 for row in dev})
    # Frozen source banks do not share nested mutable lists with adaptive lessons.
    rows[0]['positions'][0][0] = 999
    assert dev == before


def test_correction_calibration_covers_every_new_condition_without_review_repeats():
    bank = CURRICULUM.banks()['semantic']
    results = [{'id': row['id'], 'success': i >= 3} for i, row in enumerate(bank['dev'])]
    lessons = CURRICULUM.correction('semantic', 2, results, bank['dev'])
    new = [row for row in lessons if row['split'] == 'correction']
    # Include a deliberately duplicated fixed condition to exercise deduplication.
    calibration = bank['cal'] + [deepcopy(new[0])]
    samples = CURRICULUM.correction_calibration('semantic', 2, results, bank['dev'], calibration)
    expected = {CURRICULUM._condition_key(row) for row in bank['cal'] + new}
    actual = [CURRICULUM._condition_key(row) for row in samples]
    assert set(actual) == expected and len(actual) == len(expected)
    assert len({row['id'] for row in samples}) == len(samples)
    assert all(row['split'] == 'correction-calibration' and row['gap_s'] == 0 for row in samples)
    assert all('reanswer' not in row for row in samples)
    assert not any('-review-' in row['source_condition_id'] for row in samples)
    for row in samples:
        assert_valid_semantic_request(row)


@pytest.mark.parametrize('stage', ['gaze', 'coordination', 'semantic'])
def test_no_failures_adds_no_adaptive_calibration(stage):
    bank = CURRICULUM.banks()[stage]
    results = [{'id': row['id'], 'success': True} for row in bank['dev']]
    samples = CURRICULUM.correction_calibration(stage, 1, results, bank['dev'], bank['cal'])
    assert len(samples) == len(bank['cal'])
    assert {CURRICULUM._condition_key(row) for row in samples} == {
        CURRICULUM._condition_key(row) for row in bank['cal']}
