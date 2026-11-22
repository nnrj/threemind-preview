"""Read-only bodily-transfer scores and independent Decimal integral verification."""
import argparse
from collections import Counter
from decimal import Decimal, localcontext
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parents[3] / 'src')]
import support as s
from allocation import disk_allocation
from threemind_runtime import ArtifactCodec
FIELDS = ('activation', 'inhibition', 'direct', 'associative')


def read(p):
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix == '.gz' else raw)


def process(cued, blank, start, end):
    assert cued.keys() == blank.keys()
    times = [t for t in sorted(cued) if start <= t <= end]
    assert times[0] == start and times[-1] == end
    out = {}; maximum_error = 0.
    for field in FIELDS:
        peaks, integrals = [], []
        for i in (0, 1):
            delta = [cued[t][field][i] - blank[t][field][i] for t in times]
            peaks.append(max(delta))
            value = sum((b - a) / 1e6 * v for a, b, v in zip(times, times[1:], delta))
            with localcontext() as ctx:
                ctx.prec = 45
                independent = sum((Decimal(str(cued[a][field][i])) - Decimal(str(blank[a][field][i])))
                                  * Decimal(b - a) / Decimal(1000000) for a, b in zip(times, times[1:]))
            error = abs(value - float(independent)); assert error < 1e-10
            maximum_error = max(maximum_error, error); integrals.append(value)
        out[field] = {'peaks': peaks, 'signed_integrals': integrals}
    return out, maximum_error


def direction(q, expected):
    if q['peaks'][expected] > 1e-5 and q['signed_integrals'][expected] - q['signed_integrals'][1-expected] > 1e-6:
        return 'correct'
    if q['peaks'][1-expected] > 1e-5 and q['signed_integrals'][1-expected] - q['signed_integrals'][expected] > 1e-6:
        return 'opposite'
    return 'no-measurable-direction'


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert read(work / 'summary.json')['conditions'] == 280
    frozen = read(work / 'frozen.json')
    assert s.sha(work / 'cases.json') == frozen['cases_sha256']
    for rel, value in frozen['copied_evidence'].items(): assert s.sha(work / rel) == value['sha256']
    table = read(work / 'cases.json'); parents = {p['key']: p for p in read(work / 'parents.json')}
    assert len(parents) == 40
    records = {}; curves = {}; states = 0; peaks = {'nodes': 0, 'edges': 0}
    for c in table:
        folder = work / 'cases' / c['key']; r = read(folder / 'result.json')
        assert read(folder / 'input.json') == c and r['status'] == 'complete'
        first = ArtifactCodec.decode((folder / 'initial.tmind').read_bytes())
        final = ArtifactCodec.decode((folder / 'final.tmind').read_bytes())
        assert first.digest == r['initial_sha256'] == c['parent_sha256'] == parents[c['parent']]['final_sha256']
        assert final.digest == r['final_sha256']
        doc = final.to_dict(); assert doc['dynamics'] == 'threemind.continuous-memory/6.3'
        assert all(n['id'] == n['channel'] for n in doc['nodes'])
        assert int(doc['time_us']) == r['clock_us'] == c['end_us'] and r['life'] == 'active'
        states += 2
        trajectory = read(folder / 'trajectory.json.gz')
        points = trajectory['points']
        times = [p['time_us'] - c['begin_us'] for p in points]
        assert times == list(range(0, 5600001, 100000))
        curves[c['key']] = {t: {field: [next((n.get(field, 0.) for n in p['nodes'] if n['channel'] == target), 0.)
                                        for target in c['targets']] for field in FIELDS} for t, p in zip(times, points)}
        peaks['nodes'] = max(peaks['nodes'], *(p['metrics']['nodes'] for p in points))
        peaks['edges'] = max(peaks['edges'], *(p['metrics']['edges'] for p in points))
        events = [e['payload'] for e in trajectory['events'] if e.get('payload', {}).get('analysis_schema')]
        pattern = events[0].get('analyses', {}).get('pattern', {}) if events else {}
        status = pattern.get('status', 'no-window')
        values = {n['node_id']: n['activation'] for n in pattern.get('nodes', [])} if status == 'converged' else {}
        targets = [values.get(ch, 0.) for ch in c['targets']]
        outcome = 'not-converged'
        if c['domain'] != 'none' and status == 'converged':
            outcome = ('target-not-elicited' if max(targets) <= 1e-8 else 'tie' if abs(targets[0]-targets[1]) <= 1e-6 else
                       'correct' if int(targets[1] > targets[0]) == c['expected'] else 'opposite')
        records[c['key']] = {k: v for k, v in r.items() if k not in ('config', 'mappings', 'final_file')}
        records[c['key']].update(pattern_status=status, primary_outcome=outcome, primary_targets=targets)
    probes = []; maximum_error = 0.
    for c in table:
        if c['domain'] == 'none': continue
        row = records[c['key']]
        blank_key = f"transfer-{c['seed']}-{c['preset']}-{c['mode']}-none-0"
        assert records[blank_key]['parent'] == row['parent']
        measures = {}
        for window, start, end in [('input', 0, 600000), ('post_input', 600000, 5600000)]:
            q, error = process(curves[c['key']], curves[blank_key], start, end)
            maximum_error = max(maximum_error, error)
            measures[window] = {'fields': q, 'direction': direction(q['activation'], c['expected']),
                                'start_us': start, 'end_us': end, 'complete_blank_window': True}
        row['process'] = measures; probes.append(row)
    assert len(probes) == 240 and states == 560
    groups = []
    for preset in ('ordinary', 'facilitation'):
        for mode in ('full', 'no_imu', 'dose_matched', 'shuffled_imu', 'untrained'):
            for domain in ('original', 'angle', 'gravity'):
                rows = [r for r in probes if (r['preset'], r['mode'], r['domain']) == (preset, mode, domain)]
                assert len(rows) == 8
                groups.append({'preset': preset, 'mode': mode, 'domain': domain, 'denominator': 8,
                               'primary': dict(Counter(r['primary_outcome'] for r in rows)),
                               'post_input': dict(Counter(r['process']['post_input']['direction'] for r in rows)),
                               'input': dict(Counter(r['process']['input']['direction'] for r in rows))})
    joint_original = [r for r in probes if r['mode'] == 'no_imu' and r['domain'] == 'original']
    joint_new = [r for r in probes if r['mode'] == 'no_imu' and r['domain'] != 'original']
    old_all = all(r['process']['post_input']['direction'] == 'correct' for r in joint_original)
    original_none = not any(r['process']['post_input']['direction'] == 'correct' for r in joint_original)
    new_none = not any(r['process']['post_input']['direction'] == 'correct' for r in joint_new)
    reasons = {'joint_original_complete_loss': original_none, 'joint_original_correct_but_new_domains_complete_loss': old_all and new_none}
    stop = any(reasons.values())
    files = [p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    result = {'kernel': '6.3', 'formal_encoding_blocks': 4, 'inherited_parents': 40, 'conditions': 280,
              'summary': {'primary': dict(Counter(r['primary_outcome'] for r in probes)),
                          'post_input': dict(Counter(r['process']['post_input']['direction'] for r in probes)),
                          'input': dict(Counter(r['process']['input']['direction'] for r in probes)),
                          'maximum_observed': peaks, 'condition_wall_seconds': sum(r['wall_seconds'] for r in records.values())},
              'groups': groups, 'probes': probes, 'scientific_stop': stop, 'stop_reasons': reasons,
              'storage': {'logical_bytes': sum(p.stat().st_size for p in files),
                          'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}}
    s.base.original(work / 'analysis.json', result)
    s.base.original(work / 'audit.json', {'passed': True, 'complete_new_states': states, 'unchanged_parents': 40,
                                        'conditions': 280, 'paired_curves': 240, 'windows_per_pair': 2,
                                        'Decimal_precision': 45, 'maximum_integral_error': maximum_error,
                                        'Core_engines_loaded': 0, 'scientific_stop': stop})
    print(json.dumps({k: v for k, v in result.items() if k not in ('groups', 'probes')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    analyze(p.parse_args().work.resolve())
