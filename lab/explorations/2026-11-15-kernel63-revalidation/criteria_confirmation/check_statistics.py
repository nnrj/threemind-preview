"""Independent counting, exact-binomial and Holm checks; no scientific subjects."""
import copy
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery'))
from m3_confirm_analyze import evaluate
from m3_confirm_spec import KINDS


def verify_statistics(result):
    units = sorted(result['units'], key=lambda u: u['origin'])
    assert len(units) == 64 and [u['origin'] for u in units] == list(range(64))
    matrices = {k: [u['scores'][k]['passes'] for u in units] for k in KINDS}
    conjunctions = {}
    for kind, matrix in matrices.items():
        counts = [sum(row[j] for row in matrix) for j in range(4)]
        joint = [all(row) for row in matrix]
        item = result['systems'][kind]
        assert counts == item['criterion_counts'] and sum(joint) == item['joint_count']
        assert item['joint_rate'] == sum(joint) / 64
        assert item['criterion_verdicts'] == ['PASS' if n >= 48 else 'FAIL' for n in counts]
        assert item['cohort_all_four'] == ('PASS' if min(counts) >= 48 else 'FAIL')
        lo, hi = item['joint_proportion_95']
        assert 0 <= lo <= item['joint_rate'] <= hi <= 1
        if not any(joint): assert abs(hi - (1 - .025 ** (1 / 64))) < 1e-12 and lo == 0
        if all(joint): assert abs(lo - .025 ** (1 / 64)) < 1e-12 and hi == 1
        conjunctions[kind] = joint
    pvalues = {}
    for kind in KINDS[:-1]:
        pairs = list(zip(conjunctions['threemind'], conjunctions[kind]))
        plus = sum(t and not c for t, c in pairs)
        minus = sum(c and not t for t, c in pairs)
        n = plus + minus
        p = 1. if n == 0 else min(1., 2 * sum(math.comb(n, j) for j in range(min(plus, minus) + 1)) / 2**n)
        row = result['paired_comparisons'][kind]
        assert (plus, minus, 64 - n) == (row['positive'], row['negative'], row['ties'])
        assert abs(p - row['exact_two_sided_p']) < 1e-14
        assert row['mean_paired_difference'] == (plus - minus) / 64
        pvalues[kind] = p
    running = 0.
    for rank, (kind, p) in enumerate(sorted(pvalues.items(), key=lambda item: item[1])):
        running = max(running, min(1., (4 - rank) * p))
        row = result['paired_comparisons'][kind]
        assert abs(row['holm_p'] - running) < 1e-14
        assert row['verdict'] == ('PASS' if running < .05 and row['mean_paired_difference'] >= .1 else 'FAIL')
    expected = (result['systems']['threemind']['cohort_all_four'] == 'PASS'
                and sum(conjunctions['threemind']) >= 48
                and all(result['systems'][k]['cohort_all_four'] == 'FAIL' for k in KINDS[:-1])
                and all(r['verdict'] == 'PASS' for r in result['paired_comparisons'].values()))
    assert result['valid'] and result['verdict'] == ('PASS' if expected else 'FAIL')
    return {'passed': True, 'sources': 64, 'comparisons': 4, 'exact_counts_and_pvalues': True, 'holm_recomputed': True}


def test():
    def fixture():
        return [{'origin': i, 'case': {}, 'scores': {k: {'origin': i, 'passes': [k == 'threemind'] * 4,
                 'matching_valid': True, 'replay_valid': True} for k in KINDS}} for i in range(64)]
    positive = fixture(); a = evaluate(positive); verify_statistics(a); assert a['verdict'] == 'PASS'
    for k in KINDS[:-1]: assert a['paired_comparisons'][k]['holm_p'] == 2**-61
    # A comparator also meeting the conjunction must defeat the uniqueness target.
    shared = copy.deepcopy(positive)
    for u in shared: u['scores']['hebbian']['passes'] = [True] * 4
    b = evaluate(shared); verify_statistics(b); assert b['verdict'] == 'FAIL'
    negative = copy.deepcopy(positive)
    for u in negative: u['scores']['threemind']['passes'][2] = False
    c = evaluate(negative); verify_statistics(c); assert c['verdict'] == 'FAIL'
    boundary = copy.deepcopy(positive)
    for u in boundary[47:]: u['scores']['threemind']['passes'][3] = False
    d = evaluate(boundary); verify_statistics(d); assert d['verdict'] == 'FAIL'
    invalid = copy.deepcopy(positive); invalid[0]['scores']['threemind']['matching_valid'] = False
    assert evaluate(invalid)['verdict'] == 'INVALID'
    return {'passed': True, 'synthetic_cases': 5, 'scientific_individuals': 0}


if __name__ == '__main__':
    import json
    print(json.dumps(test()))
