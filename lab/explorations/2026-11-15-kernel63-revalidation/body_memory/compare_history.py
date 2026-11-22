"""Compare completed 6.3 and 6.1 recordings without loading either Core."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import support as s

FIELDS = ('activation', 'inhibition', 'direct', 'associative')


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def compare(work, historical):
    assert not (work / 'in-flight.json').exists()
    assert read(work / 'audit.json')['passed']
    assert read(historical / 'publication/completion.json')['coverage'] == 'verified'
    new, old = read(work / 'analysis.json'), read(historical / 'analysis.json')
    new_rows = {r['key']: r for r in new['probes']}
    old_rows = {r['key']: r for r in old['probes']}
    assert new_rows.keys() == old_rows.keys()
    categorical = []
    metric_error = {f: 0. for f in FIELDS}
    for key, a in new_rows.items():
        b = old_rows[key]
        for field in ('primary_outcome', 'process_correct', 'measurable_cue_effect', 'same_sample_times'):
            if a[field] != b[field]:
                categorical.append({'key': key, 'field': field, '6.1': b[field], '6.3': a[field]})
        for field in FIELDS:
            for metric in ('peaks', 'signed_integrals'):
                metric_error[field] = max(metric_error[field], *(abs(x-y) for x, y in zip(a['process'][field][metric], b['process'][field][metric])))
    cases = read(work / 'calibration-cases.json') + read(work / 'cases.json')
    old_cases = {c['key']: c for c in read(historical / 'calibration-cases.json') + read(historical / 'cases.json')}
    field_error = {f: 0. for f in FIELDS}
    same_present_error = {f: 0. for f in FIELDS}
    lifecycle = Counter()
    missing_samples = []
    state_size_changes = []
    for i, case in enumerate(cases, 1):
        key = case['key']
        a_case, b_case = dict(case), dict(old_cases[key])
        a_case.pop('config'); b_case.pop('config')
        assert a_case == b_case, key
        a = read(work / 'cases' / key / 'result.json')
        b = read(historical / 'cases' / key / 'result.json')
        lifecycle[(b['life'], a['life'])] += 1
        if (a['nodes'], a['edges']) != (b['nodes'], b['edges']):
            state_size_changes.append({'key': key, '6.1': [b['nodes'], b['edges']], '6.3': [a['nodes'], a['edges']]})
        ap = {r['time_us']: r for r in read(work / 'cases' / key / 'trajectory.json.gz')['points']}
        bp = {r['time_us']: r for r in read(historical / 'cases' / key / 'trajectory.json.gz')['points']}
        if ap.keys() != bp.keys():
            missing_samples.append({'key': key, '6.1': len(bp), '6.3': len(ap), 'common': len(ap.keys() & bp.keys())})
        for t in ap.keys() & bp.keys():
            an = {n['channel']: n for n in ap[t]['nodes']}
            bn = {n['channel']: n for n in bp[t]['nodes']}
            for channel in an.keys() | bn.keys():
                for field in FIELDS:
                    error = abs(an.get(channel, {}).get(field, 0.) - bn.get(channel, {}).get(field, 0.))
                    field_error[field] = max(field_error[field], error)
                    if channel in an and channel in bn:
                        same_present_error[field] = max(same_present_error[field], error)
        if i % 100 == 0:
            print(json.dumps({'compared_conditions': i, 'total': len(cases)}), flush=True)
    result = {
        'historical_directory': str(historical), 'new_directory': str(work),
        'conditions': len(cases), 'same_declared_materials': True,
        'new_analysis_sha256': s.sha(work / 'analysis.json'),
        'historical_analysis_sha256': s.sha(historical / 'analysis.json'),
        'categorical_differences': categorical, 'process_metric_max_abs_difference': metric_error,
        'whole_process_max_abs_difference': field_error,
        'both_nodes_present_max_abs_difference': same_present_error,
        'different_sampling_sets': missing_samples,
        'life_transitions': [{'6.1': a, '6.3': b, 'conditions': n} for (a,b),n in lifecycle.items()],
        'endpoint_node_or_edge_changes': state_size_changes,
        'condition_runtime_ratio': new['summary']['condition_wall_seconds'] / old['summary']['condition_wall_seconds'],
        'runtime_interpretation': 'Sequential historical comparison; not a controlled benchmark.',
        'Core_engines_loaded': 0, 'simulation_advanced': False,
    }
    s.base.original(work / 'historical-comparison.json', result)
    print(json.dumps({k:v for k,v in result.items() if k != 'endpoint_node_or_edge_changes'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--historical', type=Path, required=True)
    args = parser.parse_args()
    compare(args.work.resolve(), args.historical.resolve())
