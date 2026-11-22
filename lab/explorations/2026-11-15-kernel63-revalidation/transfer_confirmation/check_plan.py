"""Check the original-scale confirmation table and port without creating a Core."""
import ast
from collections import Counter
import json
from pathlib import Path

import spec

HERE = Path(__file__).resolve().parent
OLD = HERE.parents[3] / 'lab/explorations/2026-10-16-mechanism-discovery'


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text('utf-8')).body if isinstance(n, ast.FunctionDef)}


def check():
    rows = spec.cases()
    assert len(rows) == 48 and len({r['seed'] for r in rows}) == 48
    assert {r['seed'] for r in rows} == set(range(1116100, 1116148))
    assert spec.APPARATUS_SEED not in {r['seed'] for r in rows}
    strata = Counter((r['teaching_dose'], r['delay_s']) for r in rows)
    parity = Counter((r['teaching_dose'], r['delay_s'], r['seed'] % 2) for r in rows)
    assert len(strata) == 6 and set(strata.values()) == {8}
    assert len(parity) == 12 and set(parity.values()) == {4}
    for row in rows:
        assert row['histories'] == [0, 1] and len(row['arms']) == 7 and len(row['cues']) == 10
        for cue in row['cues']:
            assert set(cue['values']) == set(cue['cue'])
            assert abs(sum(cue['values'].values()) - .88) < 1e-15
    for filename, historical, names in (
        ('probe.py', 'm1_confirm_probe.py', ('probe',)),
        ('measurement.py', 'm1_confirm_driver.py', ('save', 'unit')),
    ):
        a, b = functions(HERE / filename), functions(OLD / historical)
        for name in names: assert ast.dump(a[name]) == ast.dump(b[name])
    return {'passed': True, 'origins': 48, 'strata': 6, 'origins_per_stratum': 8,
            'probes': 6720, 'unchanged_functions': ['probe', 'save', 'unit'],
            'scientific_individuals_created': 0}


if __name__ == '__main__': print(json.dumps(check()))
