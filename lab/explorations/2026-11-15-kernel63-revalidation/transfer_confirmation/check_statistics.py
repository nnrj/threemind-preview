"""Independent arithmetic and synthetic decision cases; no Core is constructed."""
import copy
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scipy.stats import t
from analyze import evaluate_units


def verify_statistics(result):
    units = result['units']; n = len(units)
    assert n == 48
    values = [u['joint_gain'] for u in units]
    mean = math.fsum(values) / n
    sd = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (n - 1))
    p = (1. if mean == 0 else 2. ** (1-n)) if sd == 0 else float(2*t.sf(abs(mean/(sd/math.sqrt(n))), n-1))
    effect = result['goal']['effect']
    assert abs(mean - effect['mean_difference']) < 1e-12
    assert abs(sd - effect['sample_sd']) < 1e-12
    assert abs(p - effect['p_two_sided']) < 1e-12
    assert effect['n_independent'] == n
    assert effect['positive_origins'] == sum(v > 0 for v in values)
    qualified = [u['joint_gain'] >= .5 and u['minimum_transferred_accuracy'] >= .75
                 and u['unrelated_loss'] <= .1 and u['restoration_rate_error'] == 0 for u in units]
    assert qualified == [u['qualified'] for u in units]
    assert sum(qualified) == result['goal']['qualifying_origins']
    valid = all(u['valid'] for u in units)
    expected = 'INVALID' if not valid else 'PASS' if sum(qualified) >= 36 and mean >= .5 and p < .05 else 'FAIL'
    assert result['valid'] == valid and result['goal']['verdict'] == expected
    return {'passed': True, 'sources': n, 'source_mean_sd_test_and_qualification_recounted': True}


def check():
    base = [{'origin': i, 'valid': True, 'joint_gain': 1., 'minimum_transferred_accuracy': 1.,
             'unrelated_loss': 0., 'restoration_rate_error': 0., 'qualified': True} for i in range(48)]
    fixtures = [('positive', base, 'PASS')]
    zero = copy.deepcopy(base)
    for u in zero: u.update(joint_gain=0., minimum_transferred_accuracy=0., qualified=False)
    fixtures.append(('zero', zero, 'FAIL'))
    boundary = copy.deepcopy(base)
    for u in boundary[35:]: u.update(joint_gain=0., minimum_transferred_accuracy=0., qualified=False)
    fixtures.append(('35_of_48', boundary, 'FAIL'))
    valid_boundary = copy.deepcopy(base)
    for u in valid_boundary[36:]: u.update(joint_gain=0., minimum_transferred_accuracy=0., qualified=False)
    fixtures.append(('36_of_48', valid_boundary, 'PASS'))
    damage = copy.deepcopy(base)
    for u in damage: u.update(unrelated_loss=.2, qualified=False)
    fixtures.append(('unrelated_damage', damage, 'FAIL'))
    invalid = copy.deepcopy(base); invalid[0]['valid'] = False
    fixtures.append(('invalid', invalid, 'INVALID'))
    for _, units, expected in fixtures:
        result = evaluate_units(units); verify_statistics(result)
        assert result['goal']['verdict'] == expected
    return {'passed': True, 'synthetic_cases': [n for n, _, _ in fixtures], 'scientific_individuals_created': 0}


if __name__ == '__main__':
    import json
    print(json.dumps(check()))
