"""Independent decimal recomputation from recorded R51f trajectories; no Core load."""
import argparse
from decimal import Decimal, localcontext
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import support as s


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def audit(work):
    assert not (work / 'in-flight.json').exists()
    analysis = read(work / 'analysis.json')
    cases = {c['key']: c for c in read(work / 'cases.json')}
    largest_error = 0.
    correct = {'trained': 0, 'untrained': 0}
    minimum_times = None
    verified = 0
    for result in analysis['probes']:
        c = cases[result['key']]
        base = cases[c['parent'] + '-none-intact']
        a = read(work / 'cases' / c['key'] / 'trajectory.json.gz')['points']
        b = read(work / 'cases' / base['key'] / 'trajectory.json.gz')['points']
        b = {p['time_us']: p for p in b}
        rows = [p for p in a if p['time_us'] in b]
        assert len(rows) == result['common_samples'] and len(rows) >= 2
        minimum_times = len(rows) if minimum_times is None else min(minimum_times, len(rows))
        quantities = {}
        with localcontext() as ctx:
            ctx.prec = 45
            for field in ('activation', 'inhibition', 'direct', 'associative'):
                series = [[], []]
                for p in rows:
                    left = {n['channel']: n for n in p['nodes']}
                    right = {n['channel']: n for n in b[p['time_us']]['nodes']}
                    for j, target in enumerate(c['targets']):
                        value = Decimal(str(left.get(target, {}).get(field, 0.))) - Decimal(str(right.get(target, {}).get(field, 0.)))
                        series[j].append((p['time_us'], value))
                maxima, integrals = [], []
                for xs in series:
                    maxima.append(max(v for _, v in xs))
                    total = Decimal(0)
                    for j in range(len(xs) - 1):
                        total += Decimal(xs[j + 1][0] - xs[j][0]) * xs[j][1] / Decimal(1000000)
                    integrals.append(total)
                quantities[field] = (maxima, integrals)
                for name, values in (('peaks', maxima), ('signed_integrals', integrals)):
                    for j in range(2):
                        error = abs(float(values[j]) - result['process'][field][name][j])
                        largest_error = max(largest_error, error)
                        assert error < 1e-11
            peaks, ints = quantities['activation']
            expected = c['expected']
            measurable = peaks[expected] > Decimal('0.00001')
            passes = measurable and ints[expected] - ints[1 - expected] > Decimal('0.000001')
            assert bool(measurable) == result['measurable_cue_effect']
            assert bool(passes) == result['process_correct']
        if c['arm'] == 'intact':
            correct['untrained' if c['mode'] == 'untrained' else 'trained'] += int(passes)
        if c['arm'] in ('target', 'matched', 'restored'):
            intervention = result['intervention']
            if intervention['valid']:
                assert len(intervention['target']) == len(intervention['matched']) > 0
                target_edges = {tuple(e) for e in intervention['target']}
                matched_edges = {tuple(e) for e in intervention['matched']}
                assert not target_edges & matched_edges
                assert all(e[0] == c['mappings'][c['cue']] for e in target_edges)
                excluded = {c['mappings'][c['cue']], *c['targets']}
                assert all(not set(e) & excluded for e in matched_edges)
        verified += 1
    assert verified == 336
    assert correct['trained'] == analysis['summary']['trained_process']
    assert correct['untrained'] == analysis['summary']['untrained_process']
    result = {'passed': True, 'trajectories_recomputed': verified, 'independent_decimal_precision': 45,
              'largest_absolute_arithmetic_error': largest_error, 'minimum_common_samples': minimum_times,
              'trained_correct': correct['trained'], 'untrained_correct': correct['untrained'],
              'Core_engines_loaded': 0, 'simulation_advanced': False,
              'analysis_sha256': s.sha(work / 'analysis.json')}
    s.base.original(work / 'arithmetic-verification.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    audit(p.parse_args().work.resolve())
