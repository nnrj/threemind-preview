"""Read-only integrity and arithmetic checks for R51p."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study_timing as x
sys.path.insert(0, str(HERE.parent / 'order_recall'))
import analyze as previous_analysis
from audit import disk_allocation
assert Path(previous_analysis.__file__).resolve() == HERE.parent / 'order_recall/analyze.py'


def gz(path): return json.loads(gzip.decompress(Path(path).read_bytes()))


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert x.read(work / 'summary.json')['references'] == 352
    x.frozen_check(work)
    rows, counts, max_error = [], Counter(), 0.

    def state(path):
        image = x.base.image(path)
        d = image.to_dict()
        assert d['dynamics'] == x.spec.KERNEL and d['life'] == 'active'
        assert d['config']['signal_threshold'] == .0004 and d['config']['prune_weight'] == .008
        assert all(n['id'] == n['channel'] for n in d['nodes'])
        counts['states'] += 1
        return image

    for number, parent in enumerate(x.spec.parents(), 1):
        teaching_hash, observer = None, None
        for stage in x.spec.stages(parent):
            folder = work / 'cases' / parent['key'] / stage['name']
            result, actual_input = x.read(folder / 'result.json'), x.read(folder / 'input.json')
            commands = x.spec.commands(parent, stage)
            assert actual_input == {'parent': parent, 'stage': stage, 'commands': commands, 'mappings': x.spec.ids(parent['seed'])}
            assert result['parent'] == parent and result['stage'] == stage and result['status'] == 'complete'
            initial, final = (state(folder / (name+'.tmind')) for name in ('initial', 'final'))
            assert initial.digest == result['initial_sha256'] and final.digest == result['final_sha256']
            assert int(initial.to_dict()['time_us']) == stage['begin_us'] and int(final.to_dict()['time_us']) == stage['end_us']
            assert initial.to_dict()['config'] == final.to_dict()['config']
            if stage['kind'] == 'train':
                assert result['parent_sha256'] is None
                assert not initial.to_dict()['nodes'] and not initial.to_dict()['edges']
                teaching_hash, observer = final.digest, x.read(folder / 'observer.json')
            else:
                assert initial.digest == result['parent_sha256'] == teaching_hash
                assert x.read(folder / 'initial-observer.json') == observer
                before = state(folder / 'pre-probe.tmind')
                assert before.digest == result['snapshots']['pre-probe']
                assert int(before.to_dict()['time_us']) == stage['probe_us']
            scheduled, delivered = gz(folder / 'scheduled.json.gz'), gz(folder / 'delivered.json.gz')
            expected = [c for c in commands if c['op'] == 'input']
            assert len(scheduled) == len(delivered) == len(expected) == result['inputs']
            enqueue = {}
            for row, command in zip(scheduled, expected):
                assert commands[row['command_index']] == command and row['enqueue_us'] == command['enqueue_us']
                receipt = row['receipt']
                assert receipt['source'] == command['source']
                assert int(receipt['scheduled_time_us']) == int(command['stimulus']['time_us'])
                enqueue[receipt['core_event_id']] = row['enqueue_us']
            norm = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'))
            assert Counter(norm({'source': r['source'], 'stimulus': r['stimulus'], 'enqueue_us': enqueue[r['core_event_id']]}) for r in delivered) == Counter(
                norm({k: c[k] for k in ('source', 'stimulus', 'enqueue_us')}) for c in expected)
            assert all(not r.get('labels') and int(r['scheduled_time_us']) == int(r['delivered_time_us']) == int(r['stimulus']['time_us']) for r in delivered)
            cursor = x.read(folder / 'cursor.json')
            assert cursor['next_command'] == len(commands) and cursor['end_us'] == stage['end_us']
            counts['inputs'] += len(delivered)
            counts['stages'] += 1
            if stage['kind'] != 'train':
                trajectory = gz(folder / 'trajectory.json.gz')
                values, error = previous_analysis.integrals(trajectory['points'], {k: x.spec.ids(parent['seed'])[k] for k in 'ABXYZK'})
                max_error = max(max_error, error)
                rows.append({'parent': parent, 'stage': stage, 'integrals': values})
        if number % 16 == 0: print(number, parent['key'], flush=True)
    assert counts == {'states': 5120, 'stages': 1824, 'inputs': 88720}, counts
    scores = x.measurement.score(rows)
    stop = not scores['dense_all_phases_pass']
    files = [p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&{'.research-records', 'publication', 'readback'}]
    result = {'schema': 'threemind.r51p-order-timing/1', 'scores': scores, 'rows': rows,
              'goals': {'dense_order_across_all_five_phases': 'PASS' if not stop else 'FAIL',
                        'sparse_timing_and_separate_reference_comparisons': 'COMPLETE'},
              'scientific_stop': stop, 'resources': x.read(work / 'resource-summary.json'),
              'timing': x.read(work / 'summary.json'),
              'storage': {'logical_bytes': sum(p.stat().st_size for p in files),
                          'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}}
    audit = {'passed': True, 'created_engines': 0, 'counts': dict(counts),
             'max_integral_error': max_error, 'integral_decimal_precision': 45, 'scientific_stop': stop}
    x.s.base.original(work / 'analysis.json', result)
    x.s.base.original(work / 'audit.json', audit)
    print(json.dumps({'audit': audit, 'families': scores['families'], 'goals': result['goals']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True)
    analyze(parser.parse_args().work.resolve())
