"""Prepared E21 response tests, using the historical bidirectional criterion."""
import itertools
import math

from intervention import GROUPS

THRESHOLD = 1e-6


def score(rows):
    """Rows contain five-second A and B activation integrals for each probe."""
    index = {(r['seed'], r['tau'], r['order'], r['groups'], r['cue']): r for r in rows}
    assert len(index) == len(rows) == 512
    sources = sorted({(r['seed'], r['tau'], r['order']) for r in rows})
    assert len(sources) == 16 and len({r['seed'] for r in rows}) == 4

    def net(source, label):
        cue, blank = (index[(*source, label, value)] for value in (.5, 0.))
        return math.fsum((cue['A'], -blank['A'], -cue['B'], blank['B']))

    contrasts = []
    for source in sources:
        own, donor = net(source, 'none'), net((*source[:2], source[2][::-1]), 'none')
        valid = abs(own) > THRESHOLD and abs(donor) > THRESHOLD and own * donor < 0
        for bits in itertools.product((0, 1), repeat=4):
            selected = ''.join(g for g, on in zip(GROUPS, bits) if on) or 'none'
            current = net(source, selected)
            contrasts.append({'seed': source[0], 'tau': source[1], 'order': source[2], 'groups': selected,
                              'baseline_net': own, 'donor_net': donor, 'net': current,
                              'valid_opposite_reference': valid,
                              'follows_recipient': valid and abs(current) > THRESHOLD and current * own > 0,
                              'follows_donor': valid and abs(current) > THRESHOLD and current * donor > 0})
    only_w = [r for r in contrasts if r['groups'] == 'W']
    with_w = [r for r in contrasts if 'W' in r['groups']]
    without_w = [r for r in contrasts if 'W' not in r['groups']]
    return {'independent_material_blocks': 4, 'teaching_references': 16, 'probes': 512,
            'weight_only': {'passed': sum(r['follows_donor'] for r in only_w), 'total': 16},
            'with_weight': {'passed': sum(r['follows_donor'] for r in with_w), 'total': 128},
            'without_weight': {'passed': sum(r['follows_recipient'] for r in without_w), 'total': 128},
            'valid_opposite_references': all(r['valid_opposite_reference'] for r in contrasts),
            'contrasts': contrasts}


def synthetic_check():
    rows = []
    for seed, tau, order, bits, cue in itertools.product(range(4), (0., 1.), ('AB', 'BA'),
                                                        itertools.product((0, 1), repeat=4), (0., .5)):
        label = ''.join(g for g, on in zip(GROUPS, bits) if on) or 'none'
        sign = (1 if order == 'AB' else -1) * (-1 if 'W' in label else 1)
        rows.append({'seed': seed, 'tau': tau, 'order': order, 'groups': label, 'cue': cue,
                     'A': .1 + (.01 if cue and sign > 0 else 0),
                     'B': .1 + (.01 if cue and sign < 0 else 0)})
    good = score(rows)
    assert good['weight_only']['passed'] == 16
    assert good['with_weight']['passed'] == good['without_weight']['passed'] == 128
    for row in rows: row['A'] = row['B'] = .1
    zero = score(rows)
    assert not zero['valid_opposite_references'] and zero['weight_only']['passed'] == 0
    return {'passed': True, 'conditions': ['selective_weight_transfer', 'equal_responses'], 'created_engines': 0}


if __name__ == '__main__':
    import json
    print(json.dumps(synthetic_check()))
