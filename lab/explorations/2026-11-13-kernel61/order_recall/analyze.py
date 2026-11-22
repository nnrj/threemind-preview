"""Read-only audit and fixed-window E20 scoring. Never creates a scientific subject."""
import argparse
from collections import Counter
from decimal import Decimal, localcontext
import gzip
import itertools
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT / 'src')]
import spec
import support as s
from audit import disk_allocation
from threemind_runtime import ArtifactCodec


def read(p): return json.loads(Path(p).read_bytes())
def gz(p): return json.loads(gzip.decompress(Path(p).read_bytes()))


def integrals(points, channels):
    by_time = {int(p['time_us']): p for p in points}
    times = sorted(by_time)
    assert len(times) == 251 and all(b-a == 20000 for a, b in itertools.pairwise(times))
    values, error = {}, 0.
    for letter, channel in channels.items():
        values[letter] = {}
        for field in spec.FIELDS:
            series = [next((n[field] for n in by_time[t]['nodes'] if n['channel'] == channel), 0.) for t in times]
            float_value = math.fsum((a+b)*.01 for a, b in itertools.pairwise(series))
            with localcontext() as context:
                context.prec = 45
                precise = sum((Decimal(str(a))+Decimal(str(b))) / 100 for a, b in itertools.pairwise(series))
            error = max(error, abs(float(precise)-float_value))
            assert abs(float(precise)-float_value) <= 1e-12
            values[letter][field] = float_value
    return values, error


def paired_rows(rows):
    index = {(r['parent']['key'], r['stage']['delay_s'], r['stage']['cue']): r for r in rows}
    pairs = []
    for r in rows:
        p, stage = r['parent'], r['stage']
        if p['order'] != 'AB' or stage['cue'] == 0: continue
        opposite = index[(p['key'].removesuffix('/AB')+'/BA', stage['delay_s'], .5)]
        margins, fast, edges = [], [], []
        for current in (r, opposite):
            blank = index[(current['parent']['key'], stage['delay_s'], 0.)]
            net = {letter: current['integrals'][letter]['activation']-blank['integrals'][letter]['activation'] for letter in 'AB'}
            first, last = current['parent']['order']
            margins.append(net[last]-net[first])
            fast.append(current['task_activation'])
            edges.append(current['reference_weights'])
        pairs.append({k: p[k] for k in ('seed', 'tau', 'shared', 'gap_s')} | {
            'delay_s': stage['delay_s'], 'recency_margins': margins,
            'bidirectional_1e6': margins[0]*margins[1] > 0 and min(map(abs, margins)) > 1e-6,
            'bidirectional_1e9': margins[0]*margins[1] > 0 and min(map(abs, margins)) > 1e-9,
            'recency_1e6': min(margins) > 1e-6,
            'task_activation': fast, 'reference_weights': edges})
    assert len(pairs) == 144
    return pairs


def evaluate(pairs):
    primary = [p for p in pairs if p['shared'] and p['tau'] == 0 and p['gap_s'] == .05 and p['delay_s'] in (1, 30)]
    after_fast = [p for p in primary if p['delay_s'] == 30]
    long = [p for p in pairs if p['shared'] and p['tau'] == 0 and p['gap_s'] == .05 and p['delay_s'] == 300]
    assert len(primary) == 8 and len(after_fast) == len(long) == 4
    primary_pass = all(p['bidirectional_1e6'] for p in primary) and all(
        len({p['recency_margins'][0] > 0 for p in primary if p['delay_s'] == delay}) == 1 for delay in (1, 30))
    fast_pass = all(p['bidirectional_1e6'] and max(v for row in p['task_activation'] for v in row.values()) <= 1e-12 for p in after_fast)
    long_pass = all(p['bidirectional_1e6'] for p in long) and len({p['recency_margins'][0] > 0 for p in long}) == 1
    control = [p for p in pairs if not p['shared']]
    return {'primary_order_expression': {'verdict': 'PASS' if primary_pass else 'FAIL',
                'passing_block_conditions': sum(p['bidirectional_1e6'] for p in primary), 'total': 8, 'independent_blocks': 4},
            'expression_after_task_activation': {'verdict': 'PASS' if fast_pass else 'FAIL', 'conditions': after_fast},
            'extension_to_300_seconds': {'verdict': 'PASS' if long_pass else 'FAIL', 'conditions': long},
            'without_shared_reference': {'bidirectional': sum(p['bidirectional_1e6'] for p in control), 'total': len(control)},
            'scientific_stop': not primary_pass}


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert read(work / 'summary.json')['stages'] == 672
    assert read(work / 'cases.json') == spec.parents()
    frozen = read(work / 'frozen.json')
    for rel, digest in frozen['sources'].items() | frozen['production_sources'].items():
        assert s.sha(ROOT / rel) == digest
    rows, counts, max_error = [], Counter(), 0.
    for p in spec.parents():
        training_digest = None
        for stage in spec.stages(p):
            folder = work / 'cases' / p['key'] / stage['name']
            result, inp = read(folder / 'result.json'), read(folder / 'input.json')
            assert result['status'] == 'complete' and result['life'] == 'active'
            assert inp == {'parent': p, 'stage': stage, 'commands': spec.commands(p, stage), 'mappings': spec.ids(p['seed'])}
            assert result['parent'] == p and result['stage'] == stage
            states = {}
            for path in folder.glob('*.tmind'):
                artifact = ArtifactCodec.decode(path.read_bytes())
                doc = artifact.to_dict()
                assert doc['dynamics'] == spec.KERNEL and doc['config']['seed'] == p['seed']
                assert doc['config']['signal_threshold'] == .0004 and doc['config']['prune_weight'] == .008
                assert all(n['id'] == n['channel'] for n in doc['nodes'])
                states[path.stem] = (artifact.digest, doc)
                counts['states'] += 1
            assert states['initial'][0] == result['initial_sha256']
            assert states['final'][0] == result['final_sha256']
            assert int(states['initial'][1]['time_us']) == stage['begin_us']
            assert int(states['final'][1]['time_us']) == stage['end_us']
            if stage['kind'] == 'train':
                training_digest = states['final'][0]
                assert len(states) == 50
            else:
                assert result['parent_sha256'] == training_digest == states['initial'][0]
                assert len(states) == 3 and int(states['pre-probe'][1]['time_us']) == stage['probe_us']
            for name, digest in result['snapshots'].items(): assert states[name][0] == digest
            delivered = gz(folder / 'delivered.json.gz')
            scheduled = gz(folder / 'scheduled.json.gz')
            expected = [c for c in inp['commands'] if c['op'] == 'input']
            assert len(delivered) == len(scheduled) == len(expected) == result['inputs']
            enqueue_by_id = {}
            for row, command in zip(scheduled, expected):
                assert inp['commands'][row['command_index']] == command
                assert row['enqueue_us'] == command['enqueue_us']
                receipt = row['receipt']
                assert receipt['source'] == command['source'] and int(receipt['scheduled_time_us']) == int(command['stimulus']['time_us'])
                enqueue_by_id[receipt['core_event_id']] = row['enqueue_us']
            # Compare multisets independently of delivery-time ordering; source enqueue order is frozen in commands.
            norm = lambda d: json.dumps(d, sort_keys=True, separators=(',', ':'))
            expected_frames = Counter(norm({'source': c['source'], 'stimulus': c['stimulus'], 'enqueue': c['enqueue_us']}) for c in expected)
            actual_frames = Counter(norm({'source': d['source'], 'stimulus': d['stimulus'], 'enqueue': enqueue_by_id[d['core_event_id']]}) for d in delivered)
            assert expected_frames == actual_frames
            assert all(int(d['delivered_time_us']) == int(d['scheduled_time_us']) == int(d['stimulus']['time_us']) and not d.get('labels') for d in delivered)
            counts['inputs'] += len(delivered)
            counts['stages'] += 1
            trajectory = gz(folder / 'trajectory.json.gz')
            if stage['kind'] == 'probe':
                points = trajectory['points']
                assert points[0]['time_us'] == stage['probe_us'] and points[-1]['time_us'] == stage['end_us']
                values, error = integrals(points, {k: spec.ids(p['seed'])[k] for k in 'ABXYK'})
                max_error = max(max_error, error)
                pre = trajectory['snapshots']['pre-probe']['observation']
                mapping = spec.ids(p['seed'])
                activation = {letter: next((n['activation'] for n in pre['nodes'] if n['channel'] == mapping[letter]), 0.) for letter in 'ABX'}
                weights = {letter: next((edge['weight'] for edge in pre['graph']['edges'] if edge['source'] == mapping['X'] and edge['target'] == mapping[letter]), 0.) for letter in 'AB'}
                rows.append({'parent': p, 'stage': stage, 'integrals': values,
                             'task_activation': activation, 'reference_weights': weights})
        print(p['key'], flush=True)
    assert counts['stages'] == 672 and counts['states'] == 6528 and len(rows) == 576
    pairs = paired_rows(rows)
    goals = evaluate(pairs)
    files = [p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts) & {'.research-records', 'publication', 'readback'}]
    result = {'schema': 'threemind.r51n-order-recall/1', 'kernel': spec.KERNEL, 'independent_blocks': 4,
              'goals': goals, 'scientific_stop': goals['scientific_stop'], 'rows': rows, 'pairs': pairs,
              'bidirectional_1e6': sum(p['bidirectional_1e6'] for p in pairs),
              'resources': read(work / 'resource-summary.json'), 'timing': read(work / 'summary.json'),
              'storage': {'logical_bytes': sum(p.stat().st_size for p in files),
                          'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}}
    audit = {'passed': True, 'created_engines': 0, 'counts': dict(counts),
             'integral_decimal_precision': 45, 'max_integral_error': max_error,
             'scientific_stop': goals['scientific_stop']}
    s.base.original(work / 'analysis.json', result)
    s.base.original(work / 'audit.json', audit)
    print(json.dumps({'goals': goals, 'audit': audit, 'storage': result['storage']}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    analyze(p.parse_args().work.resolve())
