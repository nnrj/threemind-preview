"""E21C process measures and prespecified paired factorial contrasts; no Core."""
from collections import Counter
from decimal import Decimal, localcontext
import itertools
import math
from statistics import mean

FIELDS = ('activation', 'inhibition', 'direct', 'associative')
THRESHOLD = 1e-6


def integrate(cued, blank, start, end):
    times = [t for t in sorted(cued) if start <= t <= end]
    assert cued.keys() == blank.keys() and times[0] == start and times[-1] == end
    out, error = {}, 0.
    for field in FIELDS:
        values, peaks = [], []
        for i in (0, 1):
            delta = {t: cued[t][field][i]-blank[t][field][i] for t in times}
            value = math.fsum((delta[a]+delta[b])*(b-a)/2e6 for a, b in itertools.pairwise(times))
            with localcontext() as ctx:
                ctx.prec = 45
                decimal = sum(((Decimal(str(cued[a][field][i]))-Decimal(str(blank[a][field][i])))+
                               (Decimal(str(cued[b][field][i]))-Decimal(str(blank[b][field][i])))) *
                              Decimal(b-a)/Decimal(2000000) for a, b in itertools.pairwise(times))
            error = max(error, abs(value-float(decimal)))
            values.append(value); peaks.append(max(delta.values()))
        out[field] = {'integrals': values, 'peaks': peaks}
    assert error <= 1e-10
    return out, error


def direction(margin):
    return 'taught' if margin > THRESHOLD else 'opposite' if margin < -THRESHOLD else 'unresolved'


def contrasts(rows):
    assert len(rows) == 256
    index = {(r['seed'], r['mode'], r['learn_d'], r['learn_c'], r['test_d'], r['test_c'], r['sign']): r for r in rows}
    assert len(index) == 256
    seeds = (930101, 930102, 930103, 930104)
    def value(seed, mode, switches):
        return mean(index[(seed, mode, *switches, sign)]['margin'] for sign in (1, -1))
    cells = []
    for mode, switches in itertools.product(('full', 'no_imu'), itertools.product((0, 1), repeat=4)):
        selected = [index[(seed, mode, *switches, sign)] for seed, sign in itertools.product(seeds, (1, -1))]
        cells.append({'mode': mode, 'switches': list(switches), 'responses': 8,
                      'directions': dict(Counter(direction(r['margin']) for r in selected)),
                      'mean_margin': mean(r['margin'] for r in selected),
                      'minimum': min(r['margin'] for r in selected), 'maximum': max(r['margin'] for r in selected)})
    simple = []
    names = ('teaching_depletion', 'teaching_competition', 'test_depletion', 'test_competition')
    for mode, changed in itertools.product(('full', 'no_imu'), range(4)):
        for rest in itertools.product((0, 1), repeat=3):
            off = list(rest); off.insert(changed, 0)
            on = off.copy(); on[changed] = 1
            diffs = [value(seed, mode, on)-value(seed, mode, off) for seed in seeds]
            positive, negative = sum(d > THRESHOLD for d in diffs), sum(d < -THRESHOLD for d in diffs)
            simple.append({'mode': mode, 'changed': names[changed], 'off': off, 'on': on,
                           'block_differences': diffs, 'mean_difference': mean(diffs),
                           'same_direction_blocks': max(positive, negative), 'consistent_effect': max(positive, negative) >= 3,
                           'primary': all(rest)})
    interactions = []
    for mode, stage in itertools.product(('full', 'no_imu'), ('teaching', 'test')):
        for other in itertools.product((0, 1), repeat=2):
            differences = []
            for seed in seeds:
                cell = lambda d,c: value(seed, mode, (d,c,*other) if stage == 'teaching' else (*other,d,c))
                differences.append(cell(1,1)-cell(1,0)-cell(0,1)+cell(0,0))
            interactions.append({'mode': mode, 'stage': stage, 'other_switches': list(other),
                                 'block_differences': differences, 'mean_difference': mean(differences),
                                 'consistent_effect': max(sum(d > THRESHOLD for d in differences),
                                                          sum(d < -THRESHOLD for d in differences)) >= 3})
    assert len(cells) == 32 and len(simple) == 64 and len(interactions) == 16
    primary = [r for r in simple if r['primary']]
    assert len(primary) == 8
    return {'material_blocks': 4, 'cells': cells, 'simple_effects': simple,
            'interactions': interactions, 'primary_effects': primary,
            'primary_effects_detected': sum(r['consistent_effect'] for r in primary)}


def check():
    rows = []
    for seed, mode, d,c,td,tc,sign in itertools.product((930101,930102,930103,930104), ('full','no_imu'),
                                                        (0,1),(0,1),(0,1),(0,1),(1,-1)):
        rows.append({'seed':seed,'mode':mode,'learn_d':d,'learn_c':c,'test_d':td,'test_c':tc,
                     'sign':sign,'margin':d+2*c+4*td+8*tc+16*td*tc})
    result = contrasts(rows)
    assert result['primary_effects_detected'] == 8
    assert sum(r['consistent_effect'] for r in result['interactions']) == 8
    for row in rows: row['margin']=0.
    assert contrasts(rows)['primary_effects_detected'] == 0
    curves = {t:{f:[t/1e6, 0.] for f in FIELDS} for t in (0,20000,40000)}
    blank = {t:{f:[0.,0.] for f in FIELDS} for t in curves}
    integrals,error=integrate(curves,blank,0,40000)
    assert abs(integrals['activation']['integrals'][0]-.0008) < 1e-15
    return {'passed':True,'created_engines':0,'factorial_cells':32,'simple_effects':64,
            'interactions':16,'known_integral_error':error}


if __name__ == '__main__':
    import json
    print(json.dumps(check()))
