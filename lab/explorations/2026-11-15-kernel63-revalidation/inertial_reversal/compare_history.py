"""Read-only comparison with R51m; preserve both versions' raw identities."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, str):
        # Only the declared target-version labels are aligned for comparison.
        return value.replace('v61', 'v63').replace('continuous-memory/6.1', 'continuous-memory/6.3')
    return value


def differences(left, right):
    count, maximum, categories = 0, 0., []

    def walk(a, b, path):
        nonlocal count, maximum
        if isinstance(a, dict) and isinstance(b, dict):
            assert a.keys() == b.keys(), path
            for key in a:
                walk(a[key], b[key], path+'/'+key)
        elif isinstance(a, list) and isinstance(b, list):
            assert len(a) == len(b), path
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path+'/'+str(i))
        elif type(a) in (int, float) and type(b) in (int, float):
            count += 1
            maximum = max(maximum, abs(a-b))
        elif a != b:
            categories.append({'path': path, 'historical': a, 'current': b})

    walk(normalize(left), normalize(right), '')
    return {'numeric_fields_checked': count, 'maximum_numeric_difference': maximum,
            'categorical_differences': categories}


def compare(work):
    study.freeze_check(work, True)
    assert study.read(work/'audit.json')['passed']
    old = work.parent/'inertial-reversal61-v1'
    a, b = study.read(old/'analysis.json'), study.read(work/'analysis.json')
    fields = ('responses', 'groups', 'block_results', 'causal_comparisons',
              'historical_deletion_necessity_rejected', 'historical_observed_disappearances',
              'historical_weight_lower_bound', 'scientific_stop')
    result = {'historical_work': str(old), 'current_work': str(work),
              'historical_sha256': study.s.sha(old/'analysis.json'),
              'current_sha256': study.s.sha(work/'analysis.json'),
              'scientific_comparison': differences({k: a[k] for k in fields}, {k: b[k] for k in fields}),
              'structure_comparison': differences(a['structure'], b['structure']),
              'calibration_comparison': differences(
                  {k:v for k,v in a['calibration'].items() if k != 'subjects_sha256'},
                  {k:v for k,v in b['calibration'].items() if k != 'subjects_sha256'}),
              'historical_wall_seconds': a['summary']['wall_seconds'],
              'current_wall_seconds': b['summary']['wall_seconds'],
              'historical_peak_private_bytes': a['resources']['peak_private_bytes'],
              'current_peak_private_bytes': b['resources']['peak_private_bytes'],
              'Core_engines_loaded': 0}
    study.s.base.original(work/'historical-comparison.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    compare(p.parse_args().work.resolve())
