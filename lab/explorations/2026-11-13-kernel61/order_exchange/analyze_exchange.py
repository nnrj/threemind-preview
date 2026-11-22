"""Read-only state, input and arithmetic audit for the R51o exchange batch."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study_exchange as x
import analyze as recall_analysis
from audit import disk_allocation
assert Path(recall_analysis.__file__).resolve() == HERE.parent / 'order_recall/analyze.py'


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert x.read(work / 'summary.json')['probes'] == 512
    x.frozen_check(work)
    source_work = work.parent / 'order-recall61-v1'
    rows, count = [], Counter()
    state_hashes, max_error, preparation_error = {}, 0., 0.
    changed = Counter()

    def state(path):
        value = x.base.image(path)
        d = value.to_dict()
        assert d['dynamics'] == x.materials.recall.KERNEL
        assert d['config']['signal_threshold'] == .0004 and d['config']['prune_weight'] == .008
        assert all(n['id'] == n['channel'] for n in d['nodes'])
        key = path.relative_to(work).as_posix()
        if key not in state_hashes:
            state_hashes[key] = value.digest
            count['states'] += 1
        return value

    def stage_check(folder, p, stage, expected_initial, expected_observer):
        result, inputs = x.read(folder / 'result.json'), x.read(folder / 'input.json')
        assert result['status'] == 'complete' and result['life'] == 'active'
        commands = x.materials.recall.commands(p, stage)
        assert inputs == {'parent': p, 'stage': stage, 'commands': commands, 'mappings': x.materials.recall.ids(p['seed'])}
        assert result['parent'] == p and result['stage'] == stage
        assert x.read(folder / 'initial-observer.json') == expected_observer
        initial, final, before = (state(folder / (name+'.tmind')) for name in ('initial', 'final', 'pre-probe'))
        assert initial.digest == expected_initial == result['parent_sha256'] == result['initial_sha256']
        assert final.digest == result['final_sha256'] and before.digest == result['snapshots']['pre-probe']
        assert int(initial.to_dict()['time_us']) == stage['begin_us']
        assert int(final.to_dict()['time_us']) == stage['end_us']
        assert int(before.to_dict()['time_us']) == stage['probe_us']
        actual, scheduled = x.gz(folder / 'delivered.json.gz'), x.gz(folder / 'scheduled.json.gz')
        expected = [c for c in commands if c['op'] == 'input']
        assert len(actual) == len(scheduled) == len(expected) == result['inputs']
        enqueue = {}
        for row, cmd in zip(scheduled, expected):
            assert commands[row['command_index']] == cmd and row['enqueue_us'] == cmd['enqueue_us']
            r = row['receipt']
            assert r['source'] == cmd['source'] and int(r['scheduled_time_us']) == int(cmd['stimulus']['time_us'])
            enqueue[r['core_event_id']] = row['enqueue_us']
        normal = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'))
        assert Counter(normal({'source': r['source'], 'stimulus': r['stimulus'], 'enqueue': enqueue[r['core_event_id']]}) for r in actual) == Counter(
            normal({'source': c['source'], 'stimulus': c['stimulus'], 'enqueue': c['enqueue_us']}) for c in expected)
        assert all(int(r['delivered_time_us']) == int(r['scheduled_time_us']) == int(r['stimulus']['time_us']) and not r.get('labels') for r in actual)
        count['inputs'] += len(actual)
        count['stages'] += 1
        cursor = x.read(folder / 'cursor.json')
        assert cursor['next_command'] == len(commands) and cursor['end_us'] == stage['end_us']
        return final

    for seed in x.materials.recall.SEEDS:
        for tau in (0, 1):
            unit = work / 'cases' / f'{seed}/f{tau}'
            entries = {}
            for p in [p for p in x.materials.parents() if p['seed'] == seed and p['tau'] == tau]:
                source = source_work / 'cases' / p['key']
                taught = x.base.image(source / 'train/final.tmind')
                held = stage_check(unit / p['order'] / 'hold', p, x.materials.hold_stage(p), taught.digest, x.read(source / 'train/observer.json'))
                assert all(held.digest == x.base.image(source / f'wait30/cue{cue}/pre-probe.tmind').digest for cue in ('0', '0.5'))
                aligned = state(unit / p['order'] / 'settled.tmind')
                prep = x.read(unit / p['order'] / 'preparation.json')
                assert prep['before_sha256'] == held.digest and prep['after_sha256'] == aligned.digest and prep['advanced_us'] == 0
                assert prep['changes'] == x.differences(held.to_dict(), aligned.to_dict())
                for key in ('time_us', 'config', 'queue', 'sequence', 'next_event'):
                    assert held.to_dict()[key] == aligned.to_dict()[key]
                entries[p['order']] = p, aligned, x.read(unit / p['order'] / 'hold/observer.json')
            for order in ('AB', 'BA'):
                p, aligned, observer = entries[order]
                source = source_work / 'cases' / p['key']
                for groups in x.materials.groups():
                    label = ''.join(groups) or 'none'
                    folder = unit / order / label
                    expected, receipt = x.intervention.exchange(aligned, entries[order[::-1]][1], groups)
                    assert state(folder / 'intervened.tmind').digest == expected.digest
                    assert x.read(folder / 'intervention.json') == receipt
                    for change in receipt['changes']:
                        location = change['location']
                        changed[f'{label}:{location[0]}:{location[-1] if len(location)>1 else location[0]}'] += 1
                    count['interventions'] += 1
                    for cue in (0., .5):
                        stage = dict(x.materials.probe_stage(p, cue), name=f'{label}/cue{cue:g}')
                        case = folder / f'cue{cue:g}'
                        stage_check(case, p, stage, expected.digest, observer)
                        trajectory = x.gz(case / 'trajectory.json.gz')
                        values, error = recall_analysis.integrals(trajectory['points'], {k: x.materials.recall.ids(seed)[k] for k in 'ABXYK'})
                        max_error = max(max_error, error)
                        rows.append({'seed': seed, 'tau': tau, 'order': order, 'groups': label, 'cue': cue,
                                     'A': values['A']['activation'], 'B': values['B']['activation'], 'integrals': values})
                        if label == 'none':
                            preparation_error = max(preparation_error, x.trajectory_error(trajectory, x.gz(source / f'wait30/cue{cue:g}/trajectory.json.gz')))
            print(f'{seed}/f{tau}', flush=True)
    assert count == {'states': 1856, 'inputs': 6336, 'stages': 528, 'interventions': 256}, count
    scores = x.measurement.score(rows)
    primary = scores['valid_opposite_references'] and scores['weight_only']['passed'] == 16
    pattern = scores['with_weight']['passed'] == scores['without_weight']['passed'] == 128
    goals = {'weight_only_carries_order': 'PASS' if primary else 'FAIL',
             'historical_factorial_pattern': 'PASS' if pattern else 'FAIL'}
    files = [p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&{'.research-records', 'publication', 'readback'}]
    result = {'schema': 'threemind.r51o-order-exchange/1', 'scores': scores, 'goals': goals, 'rows': rows,
              'changes_by_group_field': dict(changed), 'scientific_stop': not primary,
              'resources': x.read(work / 'resource-summary.json'), 'timing': x.read(work / 'summary.json'),
              'storage': {'logical_bytes': sum(p.stat().st_size for p in files),
                          'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}}
    audit = {'passed': True, 'created_engines': 0, 'counts': dict(count), 'max_integral_error': max_error,
             'max_preparation_response_error': preparation_error, 'integral_decimal_precision': 45,
             'scientific_stop': not primary}
    x.s.base.original(work / 'analysis.json', result)
    x.s.base.original(work / 'audit.json', audit)
    print(json.dumps({'goals': goals, 'audit': audit, 'weight_only': scores['weight_only'],
                      'with_weight': scores['with_weight'], 'without_weight': scores['without_weight']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True)
    analyze(parser.parse_args().work.resolve())
