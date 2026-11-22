"""Compare saved bodily-transfer measurements; do not create or advance a Core."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study


def compare(work):
    study.frozen_check(work)
    assert study.f.read(work / 'audit.json')['passed']
    old = work.parent / 'body-transfer61-v1'
    before = study.f.read(old / 'analysis.json')
    after = study.f.read(work / 'analysis.json')
    assert before['formal_encoding_blocks'] == after['formal_encoding_blocks'] == 4
    left = {row['key']: row for row in before['probes']}
    right = {row['key']: row for row in after['probes']}
    assert left.keys() == right.keys() and len(left) == 240
    numeric = 0
    max_difference = 0.
    changed = []

    def walk(a, b, path):
        nonlocal numeric, max_difference
        if isinstance(a, dict) and isinstance(b, dict):
            assert a.keys() == b.keys(), path
            for k in a:
                walk(a[k], b[k], path + '/' + k)
        elif isinstance(a, list) and isinstance(b, list):
            assert len(a) == len(b), path
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path + '/' + str(i))
        elif type(a) in (int, float) and type(b) in (int, float):
            numeric += 1
            max_difference = max(max_difference, abs(a-b))
        elif a != b:
            changed.append({'path': path, 'historical': a, 'current': b})

    fields = ('life', 'status', 'pattern_status', 'primary_outcome', 'primary_targets', 'process')
    for key in left:
        walk({k: left[key][k] for k in fields}, {k: right[key][k] for k in fields}, key)
    result = {
        'historical_work': str(old), 'current_work': str(work),
        'historical_analysis_sha256': study.s.sha(old / 'analysis.json'),
        'current_analysis_sha256': study.s.sha(work / 'analysis.json'),
        'matched_probes': len(left), 'numeric_fields_checked': numeric,
        'maximum_numeric_difference': max_difference, 'categorical_differences': changed,
        'groups_equal': before['groups'] == after['groups'],
        'Core_engines_loaded': 0,
        'historical_wall_seconds': study.f.read(old / 'summary.json')['wall_seconds'],
        'current_wall_seconds': study.f.read(work / 'summary.json')['wall_seconds'],
        'historical_peak_private_bytes': study.f.read(old / 'resource-summary.json')['peak_private_bytes'],
        'current_peak_private_bytes': study.f.read(work / 'resource-summary.json')['peak_private_bytes'],
    }
    study.s.base.original(work / 'historical-comparison.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    compare(parser.parse_args().work.resolve())
