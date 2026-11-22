"""Read-only comparison of source-level transfer outcomes with historical 6.1."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study


def compare(work):
    study.frozen_check(work)
    assert study.read(work / 'audit.json')['passed']
    old = work.parent / 'transfer61-v1'
    a = study.read(old / 'analysis.json')
    b = study.read(work / 'analysis.json')
    fields = ('verdict', 'passed_origins', 'origins', 'persistent_verdict', 'fast_verdict', 'target_gain')
    count = 0
    maximum = 0.
    differences = []

    def walk(left, right, path):
        nonlocal count, maximum
        if isinstance(left, dict) and isinstance(right, dict):
            assert left.keys() == right.keys(), path
            for k in left:
                walk(left[k], right[k], path + '/' + k)
        elif isinstance(left, list) and isinstance(right, list):
            assert len(left) == len(right), path
            for i, (x, y) in enumerate(zip(left, right)):
                walk(x, y, path + '/' + str(i))
        elif type(left) in (int, float) and type(right) in (int, float):
            count += 1
            maximum = max(maximum, abs(left - right))
        elif left != right:
            differences.append({'path': path, 'historical': left, 'current': right})

    walk({k: a[k] for k in fields}, {k: b[k] for k in fields}, '')
    result = {
        'historical_work': str(old), 'current_work': str(work), 'fields': list(fields),
        'historical_analysis_sha256': study.s.sha(old / 'analysis.json'),
        'current_analysis_sha256': study.s.sha(work / 'analysis.json'),
        'numeric_fields_checked': count, 'maximum_numeric_difference': maximum,
        'categorical_differences': differences, 'Core_engines_loaded': 0,
        'historical_wall_seconds': study.read(old / 'summary.json')['wall_seconds'],
        'current_wall_seconds': study.read(work / 'summary.json')['wall_seconds'],
        'historical_peak_private_bytes': study.read(old / 'resource-summary.json')['peak_private_bytes'],
        'current_peak_private_bytes': study.read(work / 'resource-summary.json')['peak_private_bytes'],
    }
    study.s.base.original(work / 'historical-comparison.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    compare(parser.parse_args().work.resolve())
