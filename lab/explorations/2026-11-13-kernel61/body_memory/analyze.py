"""Read-only R51f retention and causal analysis; no subject loading or advancement."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parents[3] / 'src')]
import support as s
from audit import disk_allocation
from threemind_runtime import ArtifactCodec

FIELDS = ('activation', 'inhibition', 'direct', 'associative')


def read(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_bytes())


def analyze(work):
    assert not (work / 'in-flight.json').exists()
    assert read(work / 'summary.json')['formal_conditions'] == 616
    assert s.sha(work / 'cases.json') == read(work / 'calibration.json')['cases_sha256']
    cases = read(work / 'calibration-cases.json') + read(work / 'cases.json')
    records, curves, fullcurves, digests = {}, {}, {}, {}
    peak_nodes = peak_edges = 0
    for c in cases:
        key = c['key']; folder = work / 'cases' / key
        r = read(folder / 'result.json'); assert r['status'] == 'complete'
        assert read(folder / 'input.json') == c
        first = ArtifactCodec.decode((folder / 'initial.tmind').read_bytes())
        last = ArtifactCodec.decode((folder / 'final.tmind').read_bytes())
        assert first.digest == r['initial_sha256'] and last.digest == r['final_sha256']
        doc = last.to_dict(); assert doc['dynamics'] == 'threemind.continuous-memory/6.1'
        assert all(n['id'] == n['channel'] for n in doc['nodes'])
        assert int(doc['time_us']) == r['clock_us']
        if c['parent']: assert first.digest == digests[c['parent']]
        digests[key] = last.digest
        trajectory = read(folder / 'trajectory.json.gz')
        pts = trajectory['points']; times = [p['time_us'] for p in pts]
        peak_nodes = max(peak_nodes, *(p['metrics']['nodes'] for p in pts))
        peak_edges = max(peak_edges, *(p['metrics']['edges'] for p in pts))
        assert times == sorted(set(times)) and times[-1] == r['clock_us']
        assert r['clock_us'] == c['end_us'] or r['life'] == 'dead'
        row = {k: v for k, v in r.items() if k not in ('config', 'mappings', 'final_file')}
        row['task_fast_state_before_probe'] = {field: [next((n.get(field, 0.) for n in pts[0]['nodes'] if n['channel'] == ch), 0.) for ch in c['targets']] for field in FIELDS}
        if c['stage'] == 'probe':
            points = {p['time_us'] - c['begin_us']: {n['channel']: {f: n.get(f, 0.) for f in FIELDS} for n in p['nodes']} for p in pts}
            fullcurves[key] = points
            curves[key] = {t: {f: [nodes.get(ch, {}).get(f, 0.) for ch in c['targets']] for f in FIELDS} for t, nodes in points.items()}
            events = [e['payload'] for e in trajectory['events'] if e.get('payload', {}).get('analysis_schema')]
            event = events[0] if events else {}
            pattern = event.get('analyses', {}).get('pattern', {})
            status = pattern.get('status', 'no-window')
            values = {n['node_id']: n['activation'] for n in pattern.get('nodes', [])} if status == 'converged' else {}
            targets = [values.get(ch, 0.) for ch in c['targets']]
            outcome = 'not-converged'
            if status == 'converged':
                outcome = 'target-not-elicited' if max(targets) <= 1e-8 else 'tie' if abs(targets[0] - targets[1]) <= 1e-6 else (
                    'correct' if int(targets[1] > targets[0]) == c['expected'] else 'opposite')
            row.update(pattern_status=status, primary_outcome=outcome, primary_targets=targets,
                       pattern_end_us=pattern.get('end_us'), classification=event.get('classification'))
        records[key] = row
    formal_probes = []
    for key, row in records.items():
        if row['stage'] != 'probe' or row['cue'] == 'none': continue
        blank = row['parent'] + '-none-intact'
        a, b = curves[key], curves[blank]
        common = sorted(a.keys() & b.keys())
        assert common
        quantities = {}
        for field in FIELDS:
            deltas = [[(t, a[t][field][i] - b[t][field][i]) for t in common] for i in (0, 1)]
            peaks = [max(v for _, v in xs) for xs in deltas]
            integrals = [sum((nt - t) / 1e6 * value for (t, value), (nt, _) in zip(xs, xs[1:])) for xs in deltas]
            quantities[field] = {'peaks': peaks, 'signed_integrals': integrals}
        exp = row['expected']; q = quantities['activation']
        measurable = q['peaks'][exp] > 1e-5
        correct = measurable and q['signed_integrals'][exp] - q['signed_integrals'][1 - exp] > 1e-6
        row.update(common_samples=len(common), common_seconds=(common[-1] - common[0]) / 1e6,
                   same_sample_times=set(a) == set(b), process=quantities,
                   measurable_cue_effect=measurable, process_correct=correct)
        formal_probes.append(row)
    causal = []
    for row in formal_probes:
        if row['arm'] == 'intact': continue
        key = row['key']; refkey = key.rsplit('-', 1)[0] + '-intact'
        reference = records[refkey]
        a, b = fullcurves[key], fullcurves[refkey]
        assert a.keys() == b.keys()
        max_error = {field: max(abs(a[t].get(ch, {}).get(field, 0.) - b[t].get(ch, {}).get(field, 0.))
                                for t in a for ch in a[t].keys() | b[t].keys()) for field in FIELDS}
        same = row['final_sha256'] == reference['final_sha256']
        if row['arm'] == 'restored' and row['intervention']['valid']:
            assert same and max(max_error.values()) == 0
        causal.append({'key': key, 'arm': row['arm'], 'valid_selection': row['intervention']['valid'],
                       'reference_process_correct': reference['process_correct'], 'process_correct': row['process_correct'],
                       'measurable_cue_effect': row['measurable_cue_effect'], 'whole_state_equal': same,
                       'trajectory_max_abs_error': max_error, 'selection': row['intervention']})
    intact = [r for r in formal_probes if r['arm'] == 'intact']
    trained = [r for r in intact if r['mode'] != 'untrained']; untrained = [r for r in intact if r['mode'] == 'untrained']
    assert len(trained) == 192 and len(untrained) == 48 and len(causal) == 96
    groups = []
    for preset in ('ordinary', 'facilitation'):
        for mode in ('full', 'no_imu', 'dose_matched', 'shuffled_imu', 'untrained'):
            for delay in (1, 60, 300):
                rows = [r for r in intact if (r['preset'], r['mode'], r['delay']) == (preset, mode, delay)]
                assert len(rows) == 8
                groups.append({'preset': preset, 'mode': mode, 'delay': delay, 'denominator': 8,
                               'process_correct': sum(r['process_correct'] for r in rows),
                               'measurable': sum(r['measurable_cue_effect'] for r in rows),
                               'primary_correct': sum(r['primary_outcome'] == 'correct' for r in rows)})
    early = [r for r in intact if (r['preset'], r['mode'], r['delay']) == ('ordinary', 'full', 1)]
    late = [r for r in intact if (r['preset'], r['mode'], r['delay']) == ('ordinary', 'full', 300)]
    early_all = all(r['process_correct'] for r in early)
    late_none = not any(r['process_correct'] for r in late)
    no_early = not any(r['measurable_cue_effect'] for r in early)
    stop = (early_all and late_none) or no_early
    files = [p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    result = {'kernel': '6.1', 'formal_encoding_blocks': 4, 'formal_conditions': 616, 'calibration_conditions': 16,
              'summary': {'trained_process': sum(r['process_correct'] for r in trained), 'trained_denominator': 192,
                          'untrained_process': sum(r['process_correct'] for r in untrained), 'untrained_denominator': 48,
                          'primary_correct': sum(r['primary_outcome'] == 'correct' for r in intact), 'primary_denominator': 240,
                          'primary_outcomes': dict(Counter(r['primary_outcome'] for r in intact)),
                          'life': dict(Counter(r['life'] for r in records.values())),
                          'maximum_observed_nodes': peak_nodes, 'maximum_observed_edges': peak_edges,
                          'condition_wall_seconds': sum(r['wall_seconds'] for r in records.values())},
              'groups': groups, 'probes': formal_probes, 'causal': causal,
              'scientific_stop': stop, 'stop_reasons': {'one_second_expression_then_total_300s_loss': early_all and late_none, 'no_early_full_sensory_cue_effect': no_early},
              'storage': {'logical_bytes': sum(p.stat().st_size for p in files), 'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)}}
    s.base.original(work / 'analysis.json', result)
    s.base.original(work / 'audit.json', {'passed': True, 'complete_states': 1264, 'conditions': 632, 'scientific_stop': stop})
    print(json.dumps({k: v for k, v in result.items() if k not in ('probes', 'causal')}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    analyze(p.parse_args().work.resolve())
