"""Read-only 48-source transfer scoring with the unchanged historical primary target."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent), str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery')]
import support as s
import spec
from audit import disk_allocation
from audit_transfer import audit
from m1_confirm_analyze import source_metrics
from m5_confirm_analyze import inference


def evaluate_units(units):
    assert len(units) == 48 and {u['origin'] for u in units} == set(range(48))
    effect = inference([u['joint_gain'] for u in units], 2026111351)
    valid = all(u['valid'] for u in units)
    passed = sum(u['qualified'] for u in units)
    verdict = ('INVALID' if not valid else 'PASS' if effect['mean_difference'] >= .5
               and effect['p_two_sided'] < .05 and passed >= 36 else 'FAIL')
    return {'schema': 'threemind.r51l-transfer-confirmation-analysis/1', 'independent_origins': 48,
            'valid': valid, 'exploratory_sources_included': 0,
            'goal': {'verdict': verdict, 'qualifying_origins': passed, 'required_origins': 36,
                     'minimum_effect': .5, 'effect': effect}, 'units': units}


def analyze(work):
    read = lambda p: json.loads(p.read_bytes())
    assert not (work / 'in-flight.json').exists()
    assert read(work / 'summary.json')['origins'] == 48
    assert read(work / 'cases.json') == spec.cases()
    units = []
    for case in spec.cases():
        r = read(work / 'units' / f'o{case["origin"]}' / 'result.json')
        assert r['case'] == case and r['seed'] == case['seed'] and r['origin'] == case['origin']
        units.append(source_metrics(r))
    result = evaluate_units(units)
    checked = audit(work)
    from check_statistics import verify_statistics
    checked['statistics'] = verify_statistics(result)
    checked['scientific_stop'] = result['goal']['verdict'] != 'PASS'
    files = [p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts) & {'.research-records', 'publication', 'readback'}]
    result.update(kernel='6.1', scientific_stop=checked['scientific_stop'],
                  resources=read(work / 'resource-summary.json'), timing=read(work / 'summary.json'),
                  storage={'logical_bytes': sum(p.stat().st_size for p in files),
                           'allocated_bytes': sum(disk_allocation(p)['allocated_bytes'] for p in files)})
    s.base.original(work / 'analysis.json', result)
    s.base.original(work / 'audit.json', checked)
    print(json.dumps({'goal': result['goal'], 'audit': checked, 'storage': result['storage']}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    analyze(p.parse_args().work.resolve())
