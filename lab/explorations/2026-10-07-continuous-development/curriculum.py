"""Explicit resumable schedule; checkpointing never changes a lesson."""
import hashlib
import json
import numpy as np


def schedule(group):
    if group not in ('explore', 'quiet', 'direct'):
        raise ValueError('registered developmental condition')
    steps = []
    if group != 'direct':
        for second in range(30):
            steps.append({'kind': 'preschool', 'phase': 'preschool', 'index': second,
                          'seconds': 1., 'variation': .12, 'passive': group == 'quiet',
                          'checkpoint': f'preschool-{second+1}' if (second+1) % 10 == 0 else None})
        steps[-1]['checkpoint'] = 'preschool'
    for mode in ('look', 'point', 'both'):
        for target in range(4):
            for rep in range(10):
                steps.append({'kind': 'lesson', 'phase': 'teaching', 'mode': mode, 'target': target,
                              'assistance': .8-.6*rep/9, 'checkpoint': f'teaching-{mode}-{target}' if rep == 9 else None})
    steps[-1]['checkpoint'] = 'initial-teaching'
    for review, gap in enumerate((2., 6., 18.)):
        steps.append({'kind': 'gap', 'phase': 'review-gap', 'index': review, 'seconds': gap, 'checkpoint': None})
        for index in np.random.default_rng(62200+review).permutation(12):
            steps.append({'kind': 'lesson', 'phase': f'review-{review+1}', 'mode': ('look', 'point', 'both')[index//4],
                          'target': int(index % 4), 'assistance': .2, 'checkpoint': None})
        steps[-1]['checkpoint'] = f'review-{review+1}'
    return steps


def signature(group):
    return hashlib.sha256(json.dumps(schedule(group), sort_keys=True, allow_nan=False).encode()).hexdigest()


def cursor(group, next_step):
    if not 0 <= next_step <= len(schedule(group)):
        raise ValueError('curriculum position outside schedule')
    return {'schema': 'threemind.developmental-curriculum/1', 'group': group,
            'schedule': signature(group), 'next_step': next_step}


def validate_cursor(value, group):
    expected = cursor(group, value['next_step'])
    if value != expected:
        raise ValueError('resume must preserve registered curriculum and condition')
    return value['next_step']
