"""Paired temporal-response measurements for the registered E22 replication."""
import itertools
import math

import materials_reference as spec

THRESHOLD = 1e-6
TIMING_TOLERANCE = 1e-12


def score(rows):
    index = {(r['parent']['key'], r['stage']['delay_s'], r['stage']['cue']): r for r in rows}
    assert len(index) == len(rows) == 576
    contrasts = []
    for parent in spec.parents():
        if parent['order'] != 'AB':
            continue
        other = parent['key'].removesuffix('/AB') + '/BA'
        for delay in ((1, 30) if parent['family'] == 'reference' else (30,)):
            for cue in (('X', 'Z', 'XZ') if parent['family'] == 'reference' else ('X',)):
                responses = []
                for key, order in ((parent['key'], 'AB'), (other, 'BA')):
                    answer, blank = (index[(key, delay, c)] for c in (cue, 'none'))
                    net = {letter: math.fsum((answer['integrals'][letter]['activation'],
                                              -blank['integrals'][letter]['activation'])) for letter in 'AB'}
                    responses.append({'order': order, 'net': net,
                                      'recency': net[order[-1]] - net[order[0]],
                                      'raw': {letter: answer['integrals'][letter]['activation'] for letter in 'AB'}})
                margins = [r['recency'] for r in responses]
                contrasts.append({'parent': parent, 'delay_s': delay, 'cue': cue, 'responses': responses,
                                  'bidirectional': margins[0]*margins[1] > 0 and min(map(abs, margins)) > THRESHOLD,
                                  'bidirectional_1e9': margins[0]*margins[1] > 0 and min(map(abs, margins)) > 1e-9,
                                  'recency': min(margins) > THRESHOLD,
                                  'primacy': max(margins) < -THRESHOLD,
                                  'both_raw_zero': all(r['raw']['A'] == r['raw']['B'] == 0 for r in responses)})
    assert len(contrasts) == 176
    families = {}
    for family, total in (('timing', 72), ('jitter', 8), ('reference', 96)):
        selected = [c for c in contrasts if c['parent']['family'] == family]
        assert len(selected) == total
        families[family] = {'total': total, **{field: sum(r[field] for r in selected)
                            for field in ('bidirectional', 'bidirectional_1e9', 'recency', 'primacy', 'both_raw_zero')}}
    maintenance = []
    for seed, tau, phase, order in itertools.product(spec.SEEDS, (0., 1.), (0, 40000, 60000), ('AB', 'BA')):
        values = []
        for k in (0, 40000, 60000):
            key = f'timing/{seed}/f{tau:g}/p{phase}/k{k}/{order}'
            cue, blank = (index[key, 30, c]['integrals'] for c in ('X', 'none'))
            values.append([cue[t]['activation'] for t in 'AB'] +
                          [cue[t]['activation']-blank[t]['activation'] for t in 'AB'])
        spread = max(max(v[i] for v in values)-min(v[i] for v in values) for i in range(4))
        maintenance.append({'seed': seed, 'tau': tau, 'phase_us': phase, 'order': order,
                            'max_response_range': spread, 'unchanged': spread <= TIMING_TOLERANCE})
    assert len(maintenance) == 48
    shared_dense = [c for c in contrasts if c['parent']['family'] == 'reference'
                    and c['parent']['cadence'] == 'dense' and c['parent']['layout'] == 'shared' and c['cue'] == 'X']
    assert len(shared_dense) == 8
    return {'independent_material_blocks': 4, 'contrasts': contrasts, 'families': families,
            'maintenance': maintenance, 'maintenance_unchanged': all(r['unchanged'] for r in maintenance),
            'jitter_order_preserved': families['jitter']['bidirectional'] == 8,
            'shared_dense_order_preserved': all(c['bidirectional'] for c in shared_dense)}


def synthetic_check():
    rows = []
    for p in spec.parents():
        for stage in spec.stages(p)[1:]:
            values = {letter: {'activation': .1} for letter in 'AB'}
            if stage['cue'] != 'none': values[p['order'][-1]]['activation'] += .01
            rows.append({'parent': p, 'stage': stage, 'integrals': values})
    positive = score(rows)
    assert all(positive[k] for k in ('maintenance_unchanged', 'jitter_order_preserved', 'shared_dense_order_preserved'))
    assert all(r['bidirectional'] == r['total'] for r in positive['families'].values())
    for r in rows:
        if r['parent']['family'] == 'timing' and r['parent']['maintenance_phase_us'] == 60000:
            r['integrals']['A']['activation'] += .0001
    assert not score(rows)['maintenance_unchanged']
    for r in rows: r['integrals'] = {letter: {'activation': .1} for letter in 'AB'}
    zero = score(rows)
    assert not zero['jitter_order_preserved'] and not zero['shared_dense_order_preserved']
    assert all(r['bidirectional'] == 0 for r in zero['families'].values())
    return {'passed': True, 'created_engines': 0,
            'tests': ['opposite-order responses', 'maintenance dependence', 'equal responses']}


if __name__ == '__main__':
    import json
    print(json.dumps(synthetic_check()))
