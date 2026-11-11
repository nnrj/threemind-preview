"""Recompute M1 committed originals without importing or advancing a Core."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
from pathlib import Path

from analyze_m2 import describe, read


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def current(folder):
    info = read(folder/'current.json')
    raw = (folder/info['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != info['sha256']:
        raise ValueError('current checkpoint hash mismatch')
    return read(folder/info['path'])


def without_identity(subject):
    state = copy.deepcopy(subject)
    state['case']['id'] = 'same-declared-origin'
    return state


def analyze(work):
    arms = ('intact', 'sham', 'target', 'matched', 'restored')
    parents = read(work/'parents.json')
    if len(parents) != 16 or len({x['seed'] for x in parents}) != 8:
        raise ValueError('source denominator changed')
    records, selections, final_hashes = [], [], {}
    for case in parents:
        parent_folder = work/'parents'/case['id']
        parent = current(parent_folder)['subject']
        if parent['case'] != case:
            raise ValueError('parent identity differs')
        previous = -1
        for path in sorted(parent_folder.glob('whole-*.json.gz')):
            checkpoint = read(path)['subject']
            t = int(checkpoint['core']['time_us'])
            if t <= previous or (previous >= 0 and t-previous > 10_000_000):
                raise ValueError('parent continuity gap')
            previous = t
        if previous != 18_000_000:
            raise ValueError('parent not at registered boundary; report death separately')
        selection = read(parent_folder/'selection.json')
        selections.append({'parent': case, **selection})
        for arm in arms:
            folder = work/'copies'/(case['id']+'-'+arm)
            result, lineage = read(folder/'result.json'), read(folder/'lineage.json')
            state = current(folder)['subject']
            before = read(folder/'whole-0000.json.gz')['subject']
            if digest(without_identity(before)) != digest(without_identity(parent)):
                raise ValueError('causal copy did not preserve whole parent')
            if lineage['parent_subject_sha256'] != digest(parent) or result['whole_state_sha256'] != digest(state):
                raise ValueError('lineage or final hash differs')
            if state['core']['dynamics'] != 'threemind.continuous-memory/5.1':
                raise ValueError('kernel identity changed')
            frames = state['recent_activity']
            early = [r['response'] for r in frames if 100_000 <= r['time_us']-18_000_000 <= 300_000]
            if len(early) != 5 or abs(statistics.mean(early)-result['early_primary']) > 1e-15:
                raise ValueError('primary window mismatch')
            intervention = read(folder/'intervention.json')
            after = read(folder/'after-intervention.json.gz')
            clean_before, clean_after = copy.deepcopy(before), copy.deepcopy(after)
            clean_before['core'].pop('silenced_edges')
            clean_after['core'].pop('silenced_edges')
            if digest(clean_before) != digest(clean_after):
                raise ValueError('intervention changed a non-mask field')
            if intervention['before_sha256'] != digest(before) or intervention['after_sha256'] != digest(after):
                raise ValueError('intervention evidence hash differs')
            if arm in ('intact', 'sham', 'restored') and digest(before) != digest(after):
                raise ValueError('control state changed')
            final_hashes[(case['id'], arm)] = digest(without_identity(state))
            records.append(result)
    by_origin = []
    for origin in sorted({c['origin'] for c in parents}):
        rows = [r for r in records if r['case']['origin'] == origin]
        contrasts = {}
        for arm in arms:
            pair = {r['case']['history']: r for r in rows if r['arm'] == arm}
            if set(pair) != {0, 1}:
                raise ValueError('missing matched history')
            contrasts[arm] = (pair[0]['early_primary']-pair[1]['early_primary'])/2
        by_origin.append({'origin': origin, 'matching_passed': all(r['matching_passed'] for r in rows),
                          'contrasts': contrasts, 'selectivity': contrasts['matched']-contrasts['target']})
    valid = [r for r in by_origin if r['matching_passed']]
    all_controls_exact = all(final_hashes[(c['id'], 'intact')] == final_hashes[(c['id'], a)]
                             for c in parents for a in ('sham', 'restored'))
    return {'schema': 'threemind.m1-silence-analysis/1', 'parents': 16, 'causal_copies': 80,
            'independent_origins': 8, 'matching_passed_origins': len(valid),
            'control_final_whole_states_exact_except_declared_id': all_controls_exact,
            'arm_history_contrasts': {a: describe([r['contrasts'][a] for r in valid], 991+i) for i, a in enumerate(arms)},
            'selectivity': describe([r['selectivity'] for r in valid], 1922),
            'all_source_selectivity': describe([r['selectivity'] for r in by_origin], 1923),
            'late_nonzero_copies': sum(abs(r['mean_response']) > 1e-9 for r in records),
            'maximum_unrelated_activity_sum': max(r['unrelated_activity_sum'] for r in records),
            'by_origin': by_origin, 'selections': selections, 'records': records,
            'interval_scope': 'exploratory paired source bootstrap; eight sources, no multiplicity-adjusted inference',
            'limitations': ['immediate reversal has zero intervening simulated time',
                            'unrelated Z/W activity during X probe is not an independent unrelated-task accuracy test',
                            'edge masking tests expression-path necessity, not isolated durable-storage sufficiency',
                            'no transplant, closed-loop ability transfer, long-retention confirmation or subjective-experience inference']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.work)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in result.items() if k not in ('selections', 'records', 'by_origin')}, ensure_ascii=False))
