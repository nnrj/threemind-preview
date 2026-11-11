"""Separate file/arithmetic audit; does not create, restore or advance a subject."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

import m1_confirm_spec as spec
import pilot_m2 as m
from pilot_m1 import differences


def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def check_matching(parent, matching, observations):
    edges = parent['model']['edges']
    node_ids = {n['channel']: n['id'] for n in parent['model']['nodes']}
    ids = {s: node_ids[c] for s, c in parent['mappings'].items()}
    groups = {}
    for symbols in ('XY', 'ZW'):
        selected = [e for e in edges if e['source'] in {ids[s] for s in symbols}
                    and e['target'] in {ids[s] for s in 'AB'}]
        assert len(selected) == 2
        degrees = [[[sum(f['source'] == n for f in edges), sum(f['target'] == n for f in edges)]
                    for n in (e['source'], e['target'])] for e in selected]
        assert sorted(map(str, degrees)) == sorted(str(r['degrees']) for r in matching['rows'][symbols])
        assert all(int(e['state_us']) == parent['time_us'] for e in selected)
        groups[symbols] = degrees
    assert sorted(map(str, groups['XY'])) == sorted(map(str, groups['ZW']))
    weight_delta = (sum(r['weight'] for r in matching['rows']['XY'])
                    -sum(r['weight'] for r in matching['rows']['ZW']))/2
    activity_delta = sum(sum(o['activation'][s] for s in 'XY')-sum(o['activation'][s] for s in 'ZW')
                         for o in observations)/(2*len(observations))
    assert abs(weight_delta-matching['weight_residual']) < 1e-14
    assert abs(activity_delta-matching['teaching_activity_residual']) < 1e-14
    assert abs(weight_delta) <= .02 and abs(activity_delta) <= .02


def audit(work):
    m.frozen_check(work)
    assert m.read(work/'cases.json') == spec.cases()
    counts = {'origins': 0, 'causal_copies': 0, 'frames': 0, 'fast_zero_change': 0}
    for case in spec.cases():
        folder = work/'units'/f"o{case['origin']}"
        result = m.read(folder/'result.json')
        assert result['case'] == case and result['valid']
        assert len(result['trials']) == 2*len(spec.ARMS)*len(spec.CUES)
        birth = load(folder/'birth-h0.json.gz')
        assert birth == load(folder/'birth-h1.json.gz') and birth['time_us'] == 0
        parents = {h: load(folder/f'parent-h{h}.json.gz') for h in (0, 1)}
        for history, parent in parents.items():
            assert parent['seed'] == case['seed'] and parent['time_us'] == (17+case['delay_s'])*1_000_000
            assert parent['model']['config']['seed'] == case['seed']
            assert parent['rng'] == birth['rng'] and parent['mappings'] == birth['mappings']
            before_settlement = load(folder/f'parent-h{history}-before-settlement.json.gz')
            assert before_settlement['time_us'] == parent['time_us']
            assert before_settlement['inputs'] == parent['inputs']
            matching = result['matching'][str(history)]
            assert matching['count'] == [2, 2] and matching['degree_equal']
            assert abs(matching['weight_residual']) <= .02 and abs(matching['teaching_activity_residual']) <= .02
            check_matching(parent, matching, m.read(folder/f'teaching-observation-h{history}.json'))
            for arm in spec.ARMS:
                initial = load(folder/f'h{history}-{arm}-initial.json.gz')
                receipt = m.read(folder/f'h{history}-{arm}-intervention.json')
                difference = set(differences(parent, initial))
                assert difference <= {'branch', 'model.edges', 'model.timers'}
                if arm in ('intact', 'sham', 'restored'):
                    comparable = copy.deepcopy(initial); comparable['branch'] = parent['branch']
                    assert comparable == parent
                else:
                    assert receipt['recipient_whole_sha256'] == m.digest(parent)
                    assert receipt['donor_whole_sha256'] == m.digest(parents[1-history])
                    assert set(receipt['changed_paths']) <= {'model.edges', 'model.timers'}
                    old = {(e['source'], e['target']) for e in receipt['removed']}
                    expected_edges = sorted([e for e in parent['model']['edges'] if (e['source'], e['target']) not in old]
                                            +receipt['inserted'], key=lambda e: (e['source'], e['target']))
                    assert initial['model']['edges'] == expected_edges
                    counts['fast_zero_change'] += arm == 'fast' and not receipt['changed_paths']
                trials = [t for t in result['trials'] if t['history'] == history and t['arm'] == arm]
                assert [t['cue'] for t in trials] == list(spec.CUES)
                for trial in trials:
                    path = folder/trial['checkpoint']['path']
                    assert hashlib.sha256(path.read_bytes()).hexdigest() == trial['checkpoint']['sha256']
                    whole = load(path); outcome = trial['result']; start = initial['time_us']
                    assert whole['branch']['parent_sha256'] == m.digest(initial)
                    assert whole['reader'] == initial['reader'] and whole['rng'] == initial['rng']
                    assert whole['mappings'] == initial['mappings']
                    assert whole['time_us'] == start+1_500_000 and outcome['start_us'] == start
                    rows = whole['rows'][len(initial['rows']):]
                    assert len(rows) == 1500 and [r['time_us'] for r in rows] == list(range(start+1000, start+1_500_001, 1000))
                    assert rows[109]['response'] == outcome['first']
                    action = int(outcome['first'] > 1e-4)-int(outcome['first'] < -1e-4)
                    assert outcome['choice'] == action and rows[109]['body']['gate'] == action
                    next_action = int(rows[359]['response'] > 1e-4)-int(rows[359]['response'] < -1e-4)
                    expected_gate = max(-1, min(1, action+next_action))
                    assert outcome['final_gate'] == whole['body']['gate'] == expected_gate
                    events = whole['inputs'][len(initial['inputs']):]
                    assert events == [
                        {'time_us': start, 'values': spec.cue_values(trial['cue'])},
                        {'time_us': start+250_000, 'values': {'X' if action > 0 else 'Z' if action < 0 else 'N': .2}},
                        *[{'time_us': start+t, 'values': {'K': .2}} for t in (500_000, 1_000_000, 1_500_000)]]
                    assert trial['goal'] == (-1 if history == 0 else 1)
                    assert trial['success'] == (action == trial['goal'])
                    assert trial['final_success'] == (expected_gate == trial['goal'])
                    assert outcome['final_sha256'] == m.digest(whole)
                    for lo, hi, key in [(100_000, 300_000, 'early_integral'), (500_000, 1_500_000, 'late_integral')]:
                        assert abs(sum(r['response']*.001 for r in rows if lo <= r['time_us']-start <= hi)-outcome[key]) < 1e-14
                    counts['causal_copies'] += 1; counts['frames'] += len(rows)
        counts['origins'] += 1
    assert counts['origins'] == spec.N
    return {'schema': 'threemind.m1-confirmation-audit/1', 'passed': True, 'counts': counts,
            'Core_engines_loaded': 0, 'method': 'Executing-assistant saved-file/arithmetic review; not external replication.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    args = p.parse_args(); report = audit(args.work)
    m.original(args.work/'audit-v1.json', report)
    print(json.dumps(report))
