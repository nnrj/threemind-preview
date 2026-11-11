"""Frozen task generation. Correct targets never enter inference."""
import json
from copy import deepcopy

import numpy as np

from lab.tools.centered_recognition import WORDS

STAGES = ('gaze', 'coordination', 'semantic')
BASE = np.array([[-.55, -.55], [.55, -.55], [-.55, .55], [.55, .55]])


def _semantic_fields(row):
    """Rebuild truthful teaching and answer-free questions after scene changes."""
    shape, color = row['items'][row['target']]
    mode = row['mode']
    row['label'] = None
    row['word_question'] = None
    if mode == 0:
        row['text'] = f'先看{WORDS[4+color]}的物体，再指出。'
        row['label'] = shape
        row['word_question'] = '这是什么形状？'
    elif mode == 1:
        row['text'] = f'先看{WORDS[shape]}，再指出。'
        row['label'] = 4+color
        row['word_question'] = '这是什么颜色？'
    else:
        row['text'] = f'先看{WORDS[4+color]}的{WORDS[shape]}，再指出。'
    row['statement'] = f'这是{WORDS[4+color]}的{WORDS[shape]}，先看清，再指出。'
    return row


def _conjunction_items(items, target, rng):
    """Make neither the target shape nor color sufficient on its own."""
    shape, color = items[target]
    other_shapes = list(map(int, rng.permutation([v for v in range(4) if v != shape])))
    other_colors = list(map(int, rng.permutation([v for v in range(4) if v != color])))
    distractors = [(shape, other_colors[0]), (other_shapes[0], color),
                   (other_shapes[1], other_colors[1])]
    slots = list(map(int, rng.permutation([i for i in range(len(items)) if i != target])))
    for slot, item in zip(slots, distractors):
        items[slot] = item
    return items


def task(stage, index, *, split='teach', seed=6900, count=4):
    if stage not in STAGES or count not in (3, 4):
        raise ValueError('E69 tasks require a declared stage and three or four objects')
    rng = np.random.default_rng(seed+index)
    # A three-object transfer must not bind the three question modes to position.
    target = (index+index//3) % count if count == 3 else index % count
    positions = BASE[:count]+rng.uniform(-.045, .045, (count, 2))
    # Final coordinates are in a distinct outer-jitter band, not training copies.
    if split in ('final', 'transfer'):
        positions = BASE[:count]+rng.choice([-1, 1], (count, 2))*rng.uniform(.065, .09, (count, 2))
    shapes = list(map(int, rng.permutation(4)[:count]))
    colors = list(map(int, rng.permutation(4)[:count]))
    items = list(zip(shapes, colors))
    mode = index % 3 if stage == 'semantic' else None
    if stage == 'semantic' and mode == 2:
        items = _conjunction_items(items, target, rng)
    goal = 'marker' if stage == 'gaze' else 'object'
    label = None
    word_question = None
    if stage == 'gaze':
        text, statement = '看亮点，手先等待。', '看这个亮点，眼睛转过去，手先等待。'
    elif stage == 'coordination':
        text = '先看标记下的物体，再指给我。'
        statement = '先用眼睛看这个物体，看清以后再用手指出。'
    else:
        text = statement = ''
    row = {'id': f'{stage}-{split}-{index:04d}', 'stage': stage, 'split': split, 'items': items,
                'positions': positions.tolist(), 'target': target, 'goal': goal, 'text': text,
                'statement': statement, 'label': label, 'word_question': word_question, 'count': count,
                'index': index, 'mode': mode, 'teacher_only': False, 'gap_s': 0}
    return _semantic_fields(row) if stage == 'semantic' else row


def banks():
    return {stage: {split: [task(stage, i, split=split, seed=seed, count=3 if split=='transfer' else 4)
                           for i in range(n)]
                   for split, n, seed in (('cal', 48, 69100), ('dev', 24, 69200),
                                           ('final', 24 if stage != 'semantic' else 72, 69300),
                                           ('transfer', 12, 69400))}
            for stage in STAGES}


def initial(stage):
    rows = []
    # Eight semantic teaching concepts, four directional tasks in the first stages.
    concepts = 8 if stage == 'semantic' else 4
    for c in range(concepts):
        for rep in range(10):
            t = task(stage, c+rep*concepts, seed=69500+STAGES.index(stage)*1000)
            if stage == 'semantic':
                _concept_lesson(t, c, (c+rep) % t['count'])
            t['id'] = f'{stage}-initial-{len(rows):04d}'
            rows.append(t)
    for review, gap in enumerate((0, 6, 18)):
        for c in range(concepts):
            t = task(stage, c+review*concepts, seed=69700+STAGES.index(stage)*1000)
            if stage == 'semantic':
                _concept_lesson(t, c, (c+review) % t['count'])
            t['id'] = f'{stage}-review-{len(rows):04d}'
            t['gap_s'] = gap if c == 0 else 0
            rows.append(t)
    return rows


def _concept_lesson(row, concept, target):
    """A cued teaching example is not an autonomous naming trial."""
    row['target'] = target
    row['items'][target] = (concept, 4) if concept < 4 else (2, concept-4)
    row.update(statement=f'看这个物体，这是{WORDS[concept]}。',
               text='看标记下的物体，再指出。', concept=concept, teacher_only=True,
               mode=None, label=None, word_question=None)


def correction(stage, round_index, results, development):
    lookup = {t['id']: t for t in development}
    failed = [lookup[r['id']] for r in results if not r['success']]
    rows = []
    for t in failed:
        original = deepcopy(t)
        original.update(split='correction', original_question=t['id'], gap_s=0,
                        similarity='original-failure')
        rows.append(original | {'id': f'{stage}-r{round_index}-failed-{len(rows):04d}', 'reanswer': True})
        # Related condition: same target, shape/color and utterance; only layout shifts.
        nearby = dict(deepcopy(original), positions=(np.asarray(t['positions'])+[.025, -.025]).tolist(),
                      similarity='position-neighbor')
        rows.append(nearby | {'id': f'{stage}-r{round_index}-nearby-{len(rows):04d}', 'reanswer': False})
        if stage == 'semantic':
            # A reversible change of one attribute across the scene preserves
            # uniqueness and conjunction distractors without revealing answers.
            for factor in ('color', 'shape'):
                related = deepcopy(original)
                related['items'] = [((shape+1) % 4, color) if factor == 'shape'
                                    else (shape, (color+1) % 4)
                                    for shape, color in t['items']]
                related.update(similarity=f'changed-{factor}', attribute_scope='all-objects',
                               id=f'{stage}-r{round_index}-{factor}-{len(rows):04d}', reanswer=False)
                rows.append(_semantic_fields(related))
    # All old conditions, including formerly correct ones, are revisited.
    for review, gap in enumerate((0, 6, 18)):
        for i, t in enumerate(development):
            rows.append(dict(deepcopy(t), split='review', id=f'{stage}-r{round_index}-review-{review}-{i:04d}',
                             gap_s=gap if i == 0 else 0, reanswer=False))
    return rows


def _condition_key(row):
    # IDs, review gaps and teacher metadata do not create new request conditions.
    keys = ('stage', 'items', 'positions', 'target', 'goal', 'text', 'label',
            'word_question', 'count', 'mode', 'teacher_only')
    return json.dumps({key: row.get(key) for key in keys}, sort_keys=True, ensure_ascii=False)


def correction_calibration(stage, round_index, results, development, calibration):
    """Fixed calibration plus failed/related answer-free conditions, once each.

    This generates sampling requests, never fits a head or changes the subject.
    Expected labels remain teacher-side metadata; trial inference only uses text.
    """
    candidates = list(calibration) + [row for row in correction(stage, round_index, results, development)
                                      if row['split'] != 'review']
    seen, rows = set(), []
    for row in candidates:
        key = _condition_key(row)
        if key in seen:
            continue
        seen.add(key)
        sampled = deepcopy(row)
        sampled.update(source_condition_id=row['id'], split='correction-calibration', gap_s=0,
                       id=f'{stage}-r{round_index}-cal-{len(rows):04d}')
        sampled.pop('reanswer', None)
        rows.append(sampled)
    return rows
