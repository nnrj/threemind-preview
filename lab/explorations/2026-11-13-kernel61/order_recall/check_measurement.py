"""Synthetic checks of integration and preregistered order decisions; no Core run."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a
assert Path(a.__file__).resolve() == Path(__file__).resolve().parent / 'analyze.py'


def check():
    points = [{'time_us': i*20000, 'nodes': [{'channel': 1, 'activation': .2, 'inhibition': .1,
                                           'direct': .3, 'associative': .4}]} for i in range(251)]
    values, error = a.integrals(points, {'A': 1})
    assert all(abs(values['A'][k]-v) < 1e-12 for k, v in
               {'activation': 1., 'inhibition': .5, 'direct': 1.5, 'associative': 2.}.items())
    rows = []
    for parent in a.spec.parents():
        for stage in a.spec.stages(parent)[1:]:
            values = {c: {k: 0. for k in a.spec.FIELDS} for c in 'ABXYK'}
            if stage['cue']: values[parent['order'][-1]]['activation'] = .01
            rows.append({'parent': parent, 'stage': stage, 'integrals': values,
                         'task_activation': {c: 0. for c in 'ABX'}, 'reference_weights': {c: 1. for c in 'AB'}})
    assert a.evaluate(a.paired_rows(rows))['primary_order_expression']['verdict'] == 'PASS'
    for row in rows:
        row['integrals']['A'], row['integrals']['B'] = row['integrals']['B'], row['integrals']['A']
    assert a.evaluate(a.paired_rows(rows))['primary_order_expression']['verdict'] == 'PASS'
    for row in rows:
        row['integrals']['A']['activation'] = row['integrals']['B']['activation'] = 0.
    assert a.evaluate(a.paired_rows(rows))['scientific_stop']
    return {'passed': True, 'scientific_individuals_created': 0,
            'synthetic_cases': ['constant_four_fields', 'recency', 'primacy', 'zero'], 'decimal_error': error}


if __name__ == '__main__': print(json.dumps(check()))
