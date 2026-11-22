"""Fixed-window order scoring for E21 timing and reference conditions."""
import math

import materials_timing as spec

THRESHOLD = 1e-6


def score(rows):
    index = {(r['parent']['key'], r['stage']['delay_s'], r['stage']['cue']): r for r in rows}
    assert len(index) == len(rows) == 1472
    contrasts = []
    for parent in spec.parents():
        if parent['order'] != 'AB':
            continue
        other = parent['key'].removesuffix('/AB') + '/BA'
        for delay in (1, 30):
            for cue in ('X', 'Z') if parent['separate'] else ('X',):
                responses = []
                for key, order in ((parent['key'], 'AB'), (other, 'BA')):
                    answer, blank = (index[(key, delay, c)] for c in (cue, 'none'))
                    net = {letter: math.fsum((answer['integrals'][letter]['activation'],
                                              -blank['integrals'][letter]['activation'])) for letter in 'AB'}
                    responses.append({'order': order, 'net': net,
                                      'recency': net[order[-1]] - net[order[0]],
                                      'raw': {letter: answer['integrals'][letter]['activation'] for letter in 'AB'}})
                margins = [r['recency'] for r in responses]
                contrasts.append({k: parent[k] for k in ('family', 'seed', 'tau', 'gap_us', 'phase_us')} | {
                    'delay_s': delay, 'cue': cue, 'responses': responses,
                    'bidirectional': margins[0] * margins[1] > 0 and min(map(abs, margins)) > THRESHOLD,
                    'bidirectional_1e9': margins[0] * margins[1] > 0 and min(map(abs, margins)) > 1e-9,
                    'recency': min(margins) > THRESHOLD,
                    'primacy': max(margins) < -THRESHOLD,
                    'both_raw_zero': all(r['raw']['A'] == r['raw']['B'] == 0 for r in responses)})
    assert len(contrasts) == 384
    families = {}
    for family, total in (('cadence', 80), ('phase', 240), ('reference', 64)):
        selected = [c for c in contrasts if c['family'] == family]
        assert len(selected) == total
        families[family] = {'total': total, **{field: sum(r[field] for r in selected)
                            for field in ('bidirectional', 'bidirectional_1e9', 'recency', 'primacy', 'both_raw_zero')}}
    return {'independent_material_blocks': 4, 'contrasts': contrasts, 'families': families,
            'dense_all_phases_pass': families['cadence']['bidirectional'] == 80}


def synthetic_check():
    rows = []
    for parent in spec.parents():
        for stage in spec.stages(parent)[1:]:
            values = {letter: {'activation': .1} for letter in 'AB'}
            if stage['cue'] != 'none':
                values[parent['order'][-1]]['activation'] += .01
            rows.append({'parent': parent, 'stage': stage, 'integrals': values})
    positive = score(rows)
    assert positive['dense_all_phases_pass']
    assert all(r['bidirectional'] == r['total'] for r in positive['families'].values())
    for row in rows:
        row['integrals'] = {letter: {'activation': .1} for letter in 'AB'}
    negative = score(rows)
    assert not negative['dense_all_phases_pass']
    assert all(r['bidirectional'] == 0 for r in negative['families'].values())
    return {'passed': True, 'test_cases': ['opposite_order_responses', 'equal_responses'], 'created_engines': 0}


if __name__ == '__main__':
    import json
    print(json.dumps(synthetic_check()))
