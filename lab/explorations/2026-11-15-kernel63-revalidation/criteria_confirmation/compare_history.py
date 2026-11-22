"""Post-analysis, read-only comparison against the completed 6.1 confirmation."""
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
    old = work.parent / 'criteria-confirmation61-v1'
    before = study.read(old / 'analysis.json')
    after = study.read(work / 'analysis.json')
    assert before['independent_origins'] == after['independent_origins'] == 64
    assert before['criterion_implementation'] == after['criterion_implementation']
    excluded = {'kernel', 'storage'}
    numeric = 0
    changed_numeric = []
    changed_other = []

    def walk(a, b, path):
        nonlocal numeric
        if isinstance(a, dict) and isinstance(b, dict):
            assert set(a) == set(b), path
            for key in a:
                walk(a[key], b[key], path + '/' + str(key))
        elif isinstance(a, list) and isinstance(b, list):
            assert len(a) == len(b), path
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, path + '/' + str(i))
        elif type(a) in (int, float) and type(b) in (int, float):
            numeric += 1
            if a != b:
                changed_numeric.append({'path': path, 'historical': a, 'current': b, 'absolute_difference': abs(a - b)})
        elif a != b:
            changed_other.append({'path': path, 'historical': a, 'current': b})

    walk({k: v for k, v in before.items() if k not in excluded},
         {k: v for k, v in after.items() if k not in excluded}, '')
    result = {'historical_work': str(old), 'historical_analysis_sha256': study.s.sha(old / 'analysis.json'),
        'current_analysis_sha256': study.s.sha(work / 'analysis.json'), 'excluded_fields': sorted(excluded),
        'numeric_fields_checked': numeric, 'changed_numeric_fields': changed_numeric,
        'changed_other_fields': changed_other,
        'maximum_numeric_difference': max((r['absolute_difference'] for r in changed_numeric), default=0.),
        'all_scientific_summary_fields_identical': not changed_numeric and not changed_other,
        'Core_engines_loaded': 0,
        'historical_wall_seconds': study.read(old / 'summary.json')['wall_seconds'],
        'current_wall_seconds': study.read(work / 'summary.json')['wall_seconds'],
        'historical_peak_private_bytes': study.read(old / 'resource-summary.json')['peak_private_bytes'],
        'current_peak_private_bytes': study.read(work / 'resource-summary.json')['peak_private_bytes']}
    study.s.base.original(work / 'historical-comparison.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('changed_numeric_fields', 'changed_other_fields')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    compare(parser.parse_args().work.resolve())
