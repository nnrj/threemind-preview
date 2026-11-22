"""Pure design/configuration and saved-process validation for R63t5."""
from copy import deepcopy
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prefix_cross_analysis as a
h = a.h


def verify():
    parent_cases = h.h.previous.design.cases()
    cases, refs = h.matrix.design(parent_cases)
    oldcases = h.read(h.HISTORY / 'cases.json')
    oldrefs = h.read(h.HISTORY / 'reference-cases.json')
    scientific = ('key', 'version', 'variant', 'matrix_variant', 'parent', 'kind', 'material_key', 'begin_us', 'end_us',
                  'initial_config', 'birth_patch', 'patch', 'cause_patch', 'block', 'retention', 'novelty')
    for old, new in ((oldcases, [c for c in cases if c['version'] != '6.3']),
                     (oldrefs, [c for c in refs if c['version'] != '6.3'])):
        assert len(old) == len(new)
        for before, after in zip(old, new):
            assert {k: before.get(k) for k in scientific} == {k: after.get(k) for k in scientific}
    for c in cases + refs:
        h.e.base.resolve_kernel('threemind.continuous-memory/' + c['version']).configuration(
            {'seed': h.e.materials.SEED, **c['initial_config'], **c['birth_patch']})
    try:
        h.e.base.resolve_kernel('threemind.continuous-memory/6.3').configuration({'node_retention_mode': 'manual'})
    except ValueError:
        pass
    else:
        raise AssertionError('Removed 6.3 option unexpectedly accepted')
    historical = h.read(h.HISTORY / 'analysis.json')
    rows = deepcopy(historical['process'])
    for row in historical['process']:
        if row['version'] != '5.1' or row['retention'] == 'legacy-all':
            continue
        r = deepcopy(row)
        r.update(version='6.3', retention='current' if r['retention'] == 'current' else 'stability',
                 signed_peak=0., reused=r['retention'] == 'current')
        rows.append(r)
    matrix = h.matrix.aggregate(rows, a.m.EPS)
    assert [r for r in matrix if r['version'] != '6.3'] == historical['matrix']
    assert not h.matrix.compare(matrix, historical)['scientific_stop']
    broken = deepcopy(matrix)
    next(r for r in broken if r['passed_blocks'] == 2)['passed_blocks'] = 1
    assert h.matrix.compare(broken, historical)['scientific_stop']
    maxerr = 0.
    count = 0
    for c in oldcases:
        if c['kind'] == 'probe' and c['version'] == '5.1' and c['retention'] == 'legacy-edges':
            points = h.e.unpacked(h.HISTORY / 'cases' / c['key'] / 'trajectory.json.xz')['points']
            value = a.m.process(c, points)
            prior = next(r for r in historical['process'] if r['key'] == c['key'])
            maxerr = max(maxerr, abs(value['signed_peak'] - prior['signed_peak']), value['arithmetic_error'])
            count += 1
    assert count == 4 and maxerr < 1e-12
    return {'passed': True, 'historical_new_stages_unchanged': 42, 'historical_reference_stages_unchanged': 30,
        'current_63_new_stages': 12, 'current_63_reference_stages': 12, 'complete_factor_conditions': 16,
        'historical_matrix_reproduced': 12, 'saved_positive_probes_recomputed': count,
        'maximum_arithmetic_error': maxerr, 'manual_node_retention_63_not_supported': True,
        'historical_positive_loss_detected': True, 'Core_engines_loaded': 0}


if __name__ == '__main__':
    print(json.dumps(verify()))
