"""Frozen M5 scoring. Reads originals; creates no subjects or new experiences."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pilot_m2 as m

HEADS = {'full': 'response', 'ports': 'port_response', 'sensory': 'sensory_response'}


def accuracy(rows, head, group, history=None, form='single'):
    selected = [r for r in rows if r['group'] == group and ((len(r['cue']) == 1) == (form == 'single'))]
    correct = 0
    for r in selected:
        target = r['label']
        if history is not None and group == 'new' and history == 1:
            target = -target
        correct += r[HEADS[head]]['answer'] == target
    return {'correct': correct, 'n': len(selected), 'rate': correct/len(selected)}


def summarize_unit(result):
    rows, tests, crosses = [], {}, []
    for head in ('full', 'ports'):
        first, cause, continued = [], [], []
        for h in result['histories']:
            cases, history = h['cases'], h['history']
            before_new = accuracy(result['early'], head, 'new', history)
            before_old = accuracy(result['early'], head, 'old')
            scores = {arm: {group: accuracy(cell['rows'], head, group) for group in ('new', 'old')}
                      for arm, cell in cases.items()}
            sham = scores['sham']
            first.append(before_old['rate'] >= .75 and sham['new']['rate'] >= .75
                         and sham['new']['rate']-before_new['rate'] >= .5 and sham['old']['rate'] >= .75
                         and before_old['rate']-sham['old']['rate'] <= .1)
            restoration = max(abs(a[HEADS[head]]['score']-b[HEADS[head]]['score'])
                              for a, b in zip(cases['sham']['rows'], cases['restored']['rows']))
            cause.append(sham['new']['rate']-scores['plasticity-off']['new']['rate'] >= .5
                         and sham['new']['rate']-scores['target']['new']['rate'] >= .5
                         and sham['new']['rate']-scores['matched']['new']['rate'] <= .1
                         and sham['old']['rate']-scores['target']['old']['rate'] <= .1 and restoration <= 1e-9)
            heldout = {name: {group: accuracy(rr, head, group) for group in ('new', 'old')}
                       for name, rr in cases['sham']['heldout'].items()}
            continued.append(heldout['continued']['new']['rate']-heldout['fixed']['new']['rate'] >= .25
                             and heldout['fixed']['old']['rate']-heldout['continued']['old']['rate'] <= .1)
            rows.append({'history': history, 'head': head, 'early_new': before_new, 'early_old': before_old,
                         'arms': scores, 'heldout': heldout, 'restoration_error': restoration,
                         'joint_cues': {arm: {group: accuracy(cell['rows'], head, group, form='joint') for group in ('new', 'old')}
                                        for arm, cell in cases.items()}})
            for reader_time, readers in (('early', cases['sham']['readers_before']), ('late', cases['sham']['readers_after'])):
                reader = readers[head]
                weights, scales = np.asarray(reader['weights']), np.asarray(reader['scale'])
                for activity_time, observations in (('early', result['early']), ('late', cases['sham']['rows'])):
                    for group in ('new', 'old'):
                        selected = [r for r in observations if r['group'] == group and len(r['cue']) == 1]
                        correct = 0
                        for r in selected:
                            features = r['features' if head == 'full' else 'port_features']
                            score = float(weights@(np.asarray(features)/scales))
                            answer = int(score > .25)-int(score < -.25)
                            target = r['label']*(-1 if activity_time == 'early' and group == 'new' and history == 1 else 1)
                            correct += answer == target
                        crosses.append({'history': history, 'head': head, 'reader_time': reader_time,
                                        'activity_time': activity_time, 'group': group, 'correct': correct, 'n': len(selected)})
        tests[head] = {'first_expression': all(first), 'causal_attribution': all(cause), 'continued_reader_gain': all(continued)}
    representation = all(accuracy(h['cases']['sham']['rows'], 'ports', 'new')['rate']
                         - accuracy(h['cases']['sham']['rows'], 'full', 'new')['rate'] >= .25
                         and accuracy(h['cases']['sham']['rows'], 'ports', 'old')['rate'] >= .75
                         for h in result['histories'])
    sensory = {str(h['history']): {group: accuracy(h['cases']['sham']['rows'], 'sensory', group) for group in ('new', 'old')}
               for h in result['histories']}
    return {'origin': result['origin'], 'valid': result['valid'], 'rows': rows, 'tests': tests,
            'integrity_valid': result['integrity_valid'], 'matching_valid': result['matching_valid'],
            'representation_gain': representation, 'crosses': crosses, 'sensory': sensory}


def analyze(work):
    originals = [m.read(p) for p in sorted((work/'units').glob('o*/result.json'))]
    if len(originals) != 8 or {r['origin'] for r in originals} != set(range(8)):
        raise RuntimeError('incomplete origin denominator')
    units = [summarize_unit(r) for r in originals]
    valid = all(u['valid'] for u in units)
    goals = {}
    for head in ('full', 'ports'):
        for target in ('first_expression', 'causal_attribution', 'continued_reader_gain'):
            count = sum(u['tests'][head][target] for u in units)
            measurable = all(u['integrity_valid'] and (target != 'causal_attribution' or u['matching_valid']) for u in units)
            goals[head+'-'+target] = {'passed_origins': count, 'n': 8,
                                    'verdict': 'INVALID' if not measurable else 'PASS' if count >= 6 else 'FAIL'}
    count = sum(u['representation_gain'] for u in units)
    goals['output-port-representation-gain'] = {'passed_origins': count, 'n': 8,
                                              'verdict': 'INVALID' if not all(u['integrity_valid'] for u in units) else 'PASS' if count >= 6 else 'FAIL'}
    return {'schema': 'threemind.m5-analysis/1', 'independent_origins': 8, 'valid': valid,
            'goals': goals, 'units': units,
            'cross_diagnostic': 'Late reader uses late new-answer calibration data; crossing is explanatory/in-sample, heldout dose tests are separate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args(); result = analyze(args.work)
    m.original(args.work/'analysis-v1.json', result)
    print(json.dumps({'valid': result['valid'], 'goals': result['goals']}, ensure_ascii=False))
