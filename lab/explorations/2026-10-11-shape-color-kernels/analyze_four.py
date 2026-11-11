"""New E67 r4 analysis edition; preserves the original two-arm analysis."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

from analyze import (TESTS, WORDS, encoded, read, transition, confusion,
                     representation_audit)

ARMS = ('2', '3.1', '4-adaptive', '4-legacy')


def fixed(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError('preserve the existing derived edition: '+str(path))
    else:
        with path.open('xb') as stream:
            stream.write(content)


def paired(stage, questions):
    grouped = {arm: {q['question_id']: q for q in questions[arm]} for arm in ARMS}
    reference = grouped[ARMS[0]]
    for arm, rows in grouped.items():
        if rows.keys() != reference.keys():
            raise ValueError('question identity differs: '+arm)
    result = []
    for key, q in reference.items():
        row = dict(stage=stage, question_id=key, shape=WORDS[q['shape']],
            color=WORDS[4+q['color']] if q['color'] < 4 else '灰色',
            attribute=q['attribute'], x=q['offset'][0], y=q['offset'][1], expected=WORDS[q['label']])
        for arm in ARMS:
            answer = grouped[arm][key]
            if any(answer[k] != q[k] for k in ('shape', 'color', 'label', 'offset', 'attribute', 'text')):
                raise ValueError('question content differs: '+arm+'/'+key)
            row['answer_'+arm] = WORDS[answer['selected']]
            row['correct_'+arm] = answer['correct']
        result.append(row)
    return result


def input_audit(base):
    hashes, times, conditions = {}, {}, {}
    order = ['initial-teaching', *[f'correction-{r}' for r in range(1, 4)]]
    for folder in sorted(base.iterdir(), key=lambda f: (order.index(f.name) if f.name in order else len(order), f.name)):
        paths = sorted((folder/'clips').glob('*.json.gz'))
        if not paths:
            continue
        h = hashlib.sha256()
        count = 0
        for path in paths:
            clip = json.loads(gzip.decompress(path.read_bytes()))
            if clip['kind'] == 'teaching':
                trial = clip['trial']
                when = trial['start_us']/1e6
                times.setdefault(str(trial['label']), []).append(when)
                conditions.setdefault(f"{trial['shape']}:{trial['color']}:{trial['label']}", []).append(when)
            for frame in clip['process']:
                h.update(encoded(frame['stimulus']))
                h.update(b'\n')
                count += 1
        hashes[folder.name] = dict(sha256=h.hexdigest(), frames=count)
    def gaps(values):
        return {k: dict(count=len(v), sim_s=v, intervals_s=[b-a for a, b in zip(v, v[1:])]) for k, v in values.items()}
    return hashes, gaps(times), gaps(conditions)


def analyze(work):
    complete = read(work/'computation-complete-r4.json')
    if complete['arms'] != list(ARMS) or complete['protocol_revision'] != 4:
        raise ValueError('four-arm protocol has not completed')
    result = dict(schema='threemind.e67-analysis/2', protocol_revision=4, arms={}, input_audit={},
        scope='Four independent whole individuals, one paired training seed, same frozen courses/questions. Question counts are not independent training replications.')
    all_questions = {}
    for arm in ARMS:
        base = work/'arms'/arm
        stages = {f.parent.name: read(f) for f in base.glob('*/result.json')}
        primary = [stages['initial-teaching'], *[stages[f'correction-{r}'] for r in range(1, 4)]]
        questions = {name: read(base/name/'predictions.json') for name in TESTS}
        all_questions[arm] = questions
        timing = {}
        for stage in stages.values():
            for key, value in stage['timing'].items():
                timing[key] = timing.get(key, 0)+value
        final = questions['final']
        row = dict(scores={name: {k: stages[name][k] for k in ('n', 'correct', 'shape', 'color', 'pairs')} for name in TESTS},
            transitions={str(r): transition(questions[f'development-{r-1}'], questions[f'development-{r}']) for r in range(1, 4)},
            final_errors=[r for r in final if not r['correct']], final_confusion=confusion(final),
            teaching_lessons=sum(s['lessons'] for s in primary), teaching_sim_s=sum(s['sim_s'] for s in primary),
            measured_stage_wall_s=sum(s['wall_seconds'] for s in stages.values()),
            core_advance_s=timing.get('core_ns', 0)/1e9, core_inject_s=timing.get('core_inject_ns', 0)/1e9,
            timing=timing, stages=stages,
            wall_scope='Completed stage timings, excluding stage-end platform synchronization. /4-adaptive initial teaching wall time covers the resumed segment only; do not treat that total as its full historical elapsed time.',
            bytes=sum(f.stat().st_size for f in base.rglob('*') if f.is_file()))
        row['all_advanced_sim_s'] = sum(s.get('sim_s', 0) for s in stages.values())
        row['core_seconds_per_sim_second'] = row['core_advance_s']/row['all_advanced_sim_s']
        row['teaching_core_s'] = sum(s['timing'].get('core_ns', 0)/1e9 for s in primary)
        row['final_core_ms_per_question'] = stages['final']['timing'].get('core_ns', 0)/1e6/len(final)
        row['restore_s'] = timing.get('restore_ns', 0)/1e9
        row['restore_calls'] = timing.get('restore_calls', 0)
        row['source_graph'] = stages['correction-3']['metrics']
        row['graph_stages'] = {name: {k: stage['metrics'].get(k) for k in ('nodes', 'edges', 'edge_density')}
                               for name, stage in stages.items() if 'metrics' in stage}
        reanswers = [read(base/f'correction-{r}/student-reanswers.json') for r in range(1, 4)]
        row['reanswer_rounds'] = [dict(n=len(r), currently_wrong=sum(not t['correct'] for t in r)) for r in reanswers]
        row['teacher_reanswers'] = sum(len(r) for r in reanswers)
        row['current_wrong_reanswers'] = sum(not t['correct'] for r in reanswers for t in r)
        row['representation_audit'] = {name: representation_audit(base/name, questions[name]) for name in TESTS}
        inputs, words, conditions = input_audit(base)
        result['input_audit'][arm] = inputs
        row['teaching_intervals_by_word'] = words
        row['teaching_intervals_by_object_attribute'] = conditions
        result['arms'][arm] = row
        print(json.dumps(dict(analyzed=arm, final=row['scores']['final'], core_s=row['core_advance_s'])), flush=True)
    if {r['teaching_lessons'] for r in result['arms'].values()} != {497}:
        raise ValueError('teaching quantity differs')
    if {r['teaching_sim_s'] for r in result['arms'].values()} != {865.5}:
        raise ValueError('teaching duration differs')
    result['matched_input_sequences'] = all(v == result['input_audit']['2'] for v in result['input_audit'].values())
    if not result['matched_input_sequences']:
        raise ValueError('recorded external input sequences differ; inspect rather than hide the difference')
    result['paired_final'] = {left+'__'+right: transition(all_questions[left]['final'], all_questions[right]['final'])
                              for i, left in enumerate(ARMS) for right in ARMS[i+1:]}
    table = []
    for name in TESTS:
        table.extend(paired(name, {arm: all_questions[arm][name] for arm in ARMS}))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(table[0]))
    writer.writeheader()
    writer.writerows(table)
    out = work/'analysis-r4'
    fixed(out/'paired-question-scores.csv', stream.getvalue().encode('utf-8-sig'))
    result['question_table'] = 'analysis-r4/paired-question-scores.csv'
    fixed(out/'verified-results.json', json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8'))
    summary = {arm: {k: row[k] for k in ('scores', 'teaching_lessons', 'teaching_sim_s',
        'measured_stage_wall_s', 'core_advance_s', 'core_seconds_per_sim_second', 'final_core_ms_per_question',
        'restore_s', 'bytes', 'graph_stages')} for arm, row in result['arms'].items()}
    fixed(out/'summary.json', json.dumps(summary, ensure_ascii=False, indent=2).encode('utf-8'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    analyze(parser.parse_args().work.resolve())
