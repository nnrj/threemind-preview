"""E68 question and matched-course rules; no state management or rollback."""
import numpy as np
from lab.tools.centered_recognition import WORDS

INITIAL = ((0., 0.), (-.008, 0.), (.008, 0.), (0., .008))
TEACH = ((0., 0.), (-.012, 0.), (.012, 0.), (0., -.012), (0., .012))
CAL = ((.006, -.006), (-.006, .006))
DEV = ((.010, .010), (-.010, -.010))
FINAL = ((.018, -.006), (-.018, .006))
ARMS = ('2', '3.1')
DEFERRED_ARMS = ()
KERNELS = {arm: 'threemind.continuous-memory/'+arm.split('-')[0] for arm in ARMS + DEFERRED_ARMS}
CONFIGS = {arm: ({'consolidation_mode': 'legacy-stability'} if arm == '4-legacy' else {}) for arm in ARMS + DEFERRED_ARMS}


def task(label, shape=None, color=None, offset=(0., 0.), category='basic'):
    shape = (label if label < 4 else 2) if shape is None else shape
    color = (4 if label < 4 else label - 4) if color is None else color
    noun = WORDS[label] if label < 4 else WORDS[label] + '的物体'
    return dict(label=label, shape=shape, color=color, offset=list(offset), category=category,
                attribute='shape' if label < 4 else 'color', pair_id=f'{shape}-{color}',
                statement=f'这是{noun}。', text='这是什么形状？' if label < 4 else '这是什么颜色？')


def grid(offset):
    return ([task(i, offset=offset, category='gray-shape') for i in range(4)] +
            [task(label, s, c, offset, 'colored-pair') for s in range(4)
             for c in range(4) for label in (s, 4+c)])


def bank(name, offsets, seed):
    rows = []
    for side, offset in enumerate(offsets):
        values = grid(offset)
        rows += [values[int(j)] | dict(split=name, side=side, question_id=f'{name}-{side}-{i}')
                 for i, j in enumerate(np.random.default_rng(seed+side).permutation(36))]
    return rows


def initial_calibration():
    rows = [task(i, offset=o) for i in range(8) for o in INITIAL]
    rows += [task(label, s, c, category='colored-pair') for s in range(4)
             for c in (s, (s+1) % 4) for label in (s, 4+c)]
    return [t | dict(question_id=f'initial-cal-{i}') for i, t in enumerate(rows)]


def initial_curriculum():
    rows = [task(label, offset=INITIAL[rep % 4]) | dict(operation='initial-teaching', gap_s=0)
            for label in range(8) for rep in range(10)]
    for review, gap in enumerate((0, 6, 18)):
        rows += [task(label, offset=INITIAL[(10+review) % 4]) |
                 dict(operation='initial-review', review=review+1, gap_s=gap if label == 0 else 0)
                 for label in range(8)]
    return [t | dict(lesson=i+1) for i, t in enumerate(rows)]


def key(t):
    return t['shape'], t['color'], t['label']


def condition(t):
    return (*key(t), *t['offset'])


def matched_correction(round_index, predictions):
    if set(predictions) != set(ARMS):
        raise ValueError('correction requires exactly the active protocol arms')
    errors = {}
    for arm in ARMS:
        for t in predictions[arm]:
            if not t['correct']:
                errors.setdefault(condition(t), dict(task(t['label'], t['shape'], t['color'], t['offset']),
                    question_id=t['question_id'], failed_arms=[]))['failed_arms'].append(arm)
    errors = [errors[k] for k in sorted(errors)]
    wrong_types = {key(t) for t in errors}
    all_types = {key(t): t for t in grid((0., 0.))}
    similar = {k for k in all_types if any(k[0] == w[0] or k[1] == w[1] for w in wrong_types)}
    ordered = sorted(wrong_types) + sorted(similar-wrong_types) + sorted(set(all_types)-similar-wrong_types)
    lessons = [t | dict(operation='correct-failed-question', gap_s=0) for t in errors]
    for k in sorted(wrong_types):
        lessons += [all_types[k] | dict(operation='target-strengthening', gap_s=0,
                    offset=list(TEACH[(round_index+rep) % len(TEACH)])) for rep in range(3)]
    for review, gap in enumerate((0, 6, 18)):
        lessons += [all_types[k] | dict(operation='interleaved-review', review=review+1,
                    gap_s=gap if i == 0 else 0, offset=list(TEACH[(round_index+review+i) % len(TEACH)]))
                    for i, k in enumerate(ordered)]
    calibration = bank(f'round-{round_index}-cal', CAL, 6701+round_index)
    seen = {condition(t) for t in calibration}
    for t in errors:
        if condition(t) not in seen:
            calibration.append(t | dict(question_id=f'round-{round_index}-corrected-{len(calibration)}'))
            seen.add(condition(t))
    return dict(round=round_index, union_errors=errors, wrong_types=sorted(wrong_types),
                lessons=[t | dict(lesson=i+1) for i, t in enumerate(lessons)], calibration=calibration,
                expected_sim_s=sum(t['gap_s']+1.5+(t['operation'] == 'correct-failed-question') for t in lessons))


def score(rows):
    pairs = {}
    for row in rows:
        if row['color'] < 4:
            pairs.setdefault((tuple(row['offset']), row['shape'], row['color']), []).append(row['correct'])
    return dict(n=len(rows), correct=sum(r['correct'] for r in rows),
        shape=dict(n=sum(r['attribute'] == 'shape' for r in rows),
                   correct=sum(r['attribute'] == 'shape' and r['correct'] for r in rows)),
        color=dict(n=sum(r['attribute'] == 'color' for r in rows),
                   correct=sum(r['attribute'] == 'color' and r['correct'] for r in rows)),
        pairs=dict(n=len(pairs), correct=sum(len(v) == 2 and all(v) for v in pairs.values())))
