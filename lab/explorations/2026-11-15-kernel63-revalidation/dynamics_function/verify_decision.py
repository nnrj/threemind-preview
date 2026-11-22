"""R63t4 measurement validation using saved histories; never create an engine."""
import ast
from copy import deepcopy
from decimal import Decimal, localcontext
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decision_analysis as a
h = a.h
d = h.d


def verify():
    cases = d.table()
    assert cases == h.read(h.HISTORY / 'cases.json') and len(cases) == 64
    olddir = h.ROOT / 'lab/explorations/2026-11-13-kernel61/dynamics_function'
    functions = lambda p: {f.name: ast.dump(f, include_attributes=False)
        for f in ast.parse(p.read_text('utf-8')).body if isinstance(f, ast.FunctionDef)}
    assert functions(olddir / 'decision_design.py') == functions(HERE / 'decision_design.py')
    old, new = functions(olddir / 'decision_execute.py'), functions(HERE / 'decision_execute.py')
    for name in ('selected', 'score'):
        assert old[name] == new[name]
    historical = h.read(h.HISTORY / 'analysis.json')
    blocks, benefits = a.aggregate(historical['answers'])
    assert blocks == historical['blocks'] and benefits == historical['benefits']
    decision = a.campaign_decision({'blocks': blocks, 'benefits': benefits}, historical)
    assert not decision['scientific_stop']
    synthetic = deepcopy(historical)
    synthetic['benefits'][0]['functional_benefit'] = True
    assert a.campaign_decision(historical, synthetic)['scientific_stop']
    # One correct direction cannot satisfy the original two-direction, two-textbook rule.
    sample = deepcopy(historical['answers'])
    for r in sample:
        if r['task'] == 'prefix' and r['profile'] == 'prefix-candidate':
            r['correct'] = r['cue'] == 'A'
    bs, _ = a.aggregate(sample)
    assert not any(r['prefix_recovery'] for r in bs if r['profile'] == 'prefix-candidate')
    for r in sample:
        if r['task'] == 'prefix' and r['profile'] == 'prefix-candidate':
            r['correct'] = True
    bs, _ = a.aggregate(sample)
    assert sum(r['prefix_recovery'] for r in bs if r['profile'] == 'prefix-candidate') == 4
    maxerr = 0.
    count = 0
    for key in ('b0/pair/s0/reference', 'b0/prefix/s0/reference', 'b0/prefix/s1/prefix-candidate'):
        c = next(c for c in cases if c['key'] == key)
        ids, _ = d.mapping(c['seed'])
        for i, q in enumerate(c['tests']):
            folder = h.HISTORY / 'cases' / key / f'04-final{i:02d}'
            r = h.read(folder / 'result.json')
            points = h.e.unpacked(folder / 'trajectory.json.xz')
            window = [p for p in points if p['time_us'] >= r['end_us'] - 500000]
            with localcontext() as ctx:
                ctx.prec = 45
                areas = {}
                for label in ('C', 'E'):
                    value = lambda p: Decimal(str(next((n['activation'] for n in p['nodes'] if n['channel'] == ids[label]), 0.)))
                    areas[label] = sum((value(a) + value(b)) * Decimal(b['time_us'] - a['time_us']) / Decimal(2000000)
                                      for a, b in zip(window, window[1:]))
                delta = float(areas['C'] - areas['E'])
            choice = ('C' if delta > 0 else 'E') if abs(delta) > 1e-6 else 'WAIT'
            expected = d.expected(c, q['cue'])
            maxerr = max(maxerr, abs(delta - r['answer']['margin_C_minus_E']))
            assert choice == r['answer']['choice'] and (choice == expected) == r['answer']['correct']
            count += 1
    assert count == 42 and maxerr < 1e-11
    phases = 0
    inputs = 0
    order = ['00-teaching', '01-review'] + [name for i in range(4)
        for name in (f'02-dev{i}', f'03-correction{i}')] + [f'04-final{i:02d}' for i in range(14)]
    for c in cases:
        wrong = {}
        for name in order:
            folder = h.HISTORY / 'cases' / c['key'] / name
            result = h.read(folder / 'result.json')
            rows = h.e.unpacked(folder / 'inputs.json.xz')
            assert rows == a.expected_rows(c, name, result['begin_us'], h.HISTORY, wrong)
            if name.startswith('02-dev'):
                wrong[int(name[-1])] = not result['answer']['correct']
            phases += 1
            inputs += len(rows)
    assert phases == 1536 and inputs == 88384
    return {'passed': True, 'unchanged_system_table': 64, 'independent_material_blocks': 4,
        'unchanged_final_questions': 896, 'unchanged_phases': 1536, 'historical_block_scores': len(blocks),
        'historical_functional_comparisons': len(benefits), 'recomputed_saved_questions': count,
        'historical_curriculum_phases_verified': phases, 'historical_input_frames_verified': inputs,
        'maximum_arithmetic_error': maxerr, 'single_direction_false_recovery_rejected': True,
        'lost_positive_detected': True, 'known_negatives_not_new_stops': True, 'Core_engines_loaded': 0}


if __name__ == '__main__':
    print(json.dumps(verify()))
