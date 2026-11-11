"""Read-only scoring/continuity audit of E65; no simulation or fitting."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from lab.tools.service_study import read_json, new_json, encoded

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/centered-learning-20261008'


def counts(rows):
    return dict(n=len(rows), correct=sum(r['correct'] for r in rows))


def score(rows, covered):
    conf = [[0]*8 for _ in range(8)]
    for r in rows:
        if r['correct'] != (r['selected'] == r['label']): raise AssertionError('scoring mismatch')
        conf[r['label']][r['selected']] += 1
    keys = lambda r: (r['shape'], r['color'], r['label'])
    colored = [r for r in rows if r['color'] < 4]
    pairs = {}
    for r in colored: pairs.setdefault(r['pair_id'], []).append(r)
    if len(pairs) != 16 or any(len(v) != 2 or {r['attribute'] for r in v} != {'shape','color'} for v in pairs.values()):
        raise AssertionError('complete two-attribute grid required')
    return counts(rows) | dict(
        shape=counts([r for r in rows if r['attribute'] == 'shape']),
        gray_shape=counts([r for r in rows if r['color'] == 4]),
        colored_shape=counts([r for r in rows if r['color'] < 4 and r['attribute'] == 'shape']),
        color=counts([r for r in rows if r['attribute'] == 'color']),
        covered_attribute_type=counts([r for r in rows if keys(r) in covered]),
        uncovered_attribute_type=counts([r for r in rows if keys(r) not in covered]),
        combinations=dict(n=16, correct=sum(all(r['correct'] for r in v) for v in pairs.values()),
            pairs={k: dict(correct=all(r['correct'] for r in v),
                          shape=next(r['word'] for r in v if r['attribute']=='shape'),
                          color=next(r['word'] for r in v if r['attribute']=='color')) for k,v in sorted(pairs.items())}),
        confusion=conf, wrong=[r for r in rows if not r['correct']])


def whole_state(path):
    with gzip.open(path/'system.json.gz', 'rt', encoding='utf-8') as f: return json.load(f)


def main():
    cases = {p.parent.name: read_json(p) for p in (WORK/'cases').glob('*/result.json')}
    failures = {p.parent.name: read_json(p) for p in (WORK/'cases').glob('*/stopped.json')}
    required = {'preflight','baseline','teaching','new-calibration','final-fit','primary','confirmation'}
    if set(cases) != required: raise RuntimeError('complete registered stages required for final analysis')
    old = sum((read_json(WORK/'reference'/f'{name}.json') for name in ('first-calibration','later-calibration')), [])
    new = read_json(WORK/'cases/new-calibration/predictions.json')
    types = lambda rows: {(r['shape'],r['color'],r['label']) for r in rows}
    old_types, final_types = types(old), types(old+new)
    predictions = {name: read_json(WORK/f'cases/{name}/predictions.json') for name in ('baseline','primary','confirmation')}
    answers = {name: score(rows, old_types if name=='baseline' else final_types) for name,rows in predictions.items()}
    # Also score baseline under FINAL coverage, to compare like with like.
    answers['baseline_final_coverage'] = score(predictions['baseline'], final_types)
    before = {r['question_id']:r for r in predictions['baseline']}
    after = predictions['primary']
    assert before.keys() == {r['question_id'] for r in after}
    paired = dict(n=len(after), changed=sum(r['selected'] != before[r['question_id']]['selected'] for r in after),
        wrong_to_correct=sum(not before[r['question_id']]['correct'] and r['correct'] for r in after),
        correct_to_wrong=sum(before[r['question_id']]['correct'] and not r['correct'] for r in after),
        remained_wrong=sum(not before[r['question_id']]['correct'] and not r['correct'] for r in after))
    targets = {(1,0,1),(2,1,2),(1,3,1),(2,0,2),(3,1,5)}
    target_results = {name: counts([r for r in rows if (r['shape'],r['color'],r['label']) in targets])
                      for name,rows in predictions.items()}
    taught, fitted = (whole_state(WORK/f'cases/{name}/system') for name in ('teaching','final-fit'))
    state_fields = ('identity','cursor','session','current','history','published','sensor','layout')
    physical_unchanged = all(encoded(taught[k]) == encoded(fitted[k]) for k in state_fields)
    if not physical_unchanged: raise AssertionError('offline fit changed complete physical/Core state')
    model_sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    unchanged_head = model_sha(WORK/'reference/system/words/model.safetensors') == model_sha(WORK/'cases/teaching/system/words/model.safetensors')
    if not unchanged_head: raise AssertionError('teaching unexpectedly modified peripheral weights')
    source = ROOT/'.work/centered-restart-20261008/cases/final-fit/system'
    original_unchanged = all(model_sha(source/name) == sha for name,sha in read_json(WORK/'reference/source-hashes.json').items())
    if not original_unchanged: raise AssertionError('original E64 changed')
    # Audit every frame, including failures and intervals, for fixed apparatus and complete records.
    frames, clips = {}, {}
    action_max = 0.
    for path in sorted((WORK/'cases').glob('*/process.jsonl.gz')):
        n = c = 0
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                row = json.loads(line); c += 1
                for frame in row['process']:
                    n += 1
                    if frame['observation']['schema'] != 'threemind.centered-observation/1': raise AssertionError('world version')
                    if frame['observation']['teacher_marker'] is not None: raise AssertionError('unexpected teacher marker')
                    action_max = max(action_max, *(abs(v) for k in ('eye_action','hand_action') for v in frame[k]))
        frames[path.parent.name] = n; clips[path.parent.name] = c
    if action_max != 0: raise AssertionError('actuator command during fixed-eye experiment')
    expected = dict(baseline=720,teaching=3150,**{'new-calibration':960},primary=720,confirmation=720)
    if frames != expected: raise AssertionError(('missing raw frames', frames, expected))
    lessons = read_json(WORK/'cases/teaching/lesson-timing.json')
    if len(lessons) != 89 or any(r['end_us']-r['start_us'] != 1500000 for r in lessons):
        raise AssertionError('registered lesson durations')
    intervals = {}
    for key, key_fn in [('concept', lambda r: str(r['label'])),
                        ('example_attribute', lambda r: f"{r['shape']}-{r['color']}-{r['label']}")]:
        grouped = {}
        for row in lessons: grouped.setdefault(key_fn(row), []).append(row)
        intervals[key] = {k: dict(lessons=[r['lesson'] for r in v],
            starts_us=[r['start_us'] for r in v],
            end_to_next_start_seconds=[(b['start_us']-a['end_us'])/1e6 for a,b in zip(v,v[1:])])
            for k,v in grouped.items()}
    new_json(HERE/'teaching-intervals.json', intervals)
    result = dict(schema='threemind.centered-learning-results/1', cases=cases, failures=failures,
        answers=answers, paired=paired, repeated_E64_targets=target_results,
        compute_minutes=(sum(v['wall_seconds'] for v in cases.values())+sum(v['wall_seconds'] for k,v in failures.items() if k not in cases))/60,
        instances=read_json(WORK/'instances.json'), independent_training_sources=1,
        calibration_type_counts=dict(original=len(old_types), final=len(final_types)),
        continuity=dict(core_body_history_unchanged_during_fit=physical_unchanged,
                        peripheral_weights_unchanged_during_teaching=unchanged_head,
                        original_E64_files_unchanged=original_unchanged),
        process_audit=dict(frames=frames, total_frames=sum(frames.values()), raw_records=clips, max_actuator_command=action_max),
        all_correct_both_sets=all(answers[k]['correct']==36 and answers[k]['combinations']['correct']==16 for k in ('primary','confirmation')))
    new_json(HERE/'results.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','answers')},ensure_ascii=False))
    for name, score_ in answers.items():
        print(json.dumps(dict(case=name,**{k:v for k,v in score_.items() if k not in ('wrong','confusion','combinations')}),ensure_ascii=False))


if __name__ == '__main__': main()
