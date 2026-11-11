"""Confirmation inference on independent origins, not questions or branches."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import beta, t

import m5_analyze as old
import m5_confirm_spec as spec
import pilot_m2 as m


def source_metrics(result):
    summary = old.summarize_unit(result)
    contrasts = {'fixed-expression': [], 'selective-pathway': [], 'readout-scope': []}
    preservation, restoration = [], []
    for history in (0, 1):
        ports = next(r for r in summary['rows'] if r['history'] == history and r['head'] == 'ports')
        full = next(r for r in summary['rows'] if r['history'] == history and r['head'] == 'full')
        s = ports['arms']
        n = lambda arm: s[arm]['new']['rate']
        o = lambda arm: s[arm]['old']['rate']
        contrasts['fixed-expression'].append(min(n('sham')-ports['early_new']['rate'],
                                                   n('sham')-n('plasticity-off')))
        contrasts['selective-pathway'].append(min(n('sham')-n('target'), n('matched')-n('target'),
                                                   o('sham')-o('matched'), o('target')-o('matched')))
        contrasts['readout-scope'].append(n('sham')-full['arms']['sham']['new']['rate'])
        preservation.append(ports['early_old']['rate'] >= .75 and o('sham') >= .75
                            and ports['early_old']['rate']-o('sham') <= .1
                            and n('sham')-n('matched') <= .1 and o('sham')-o('target') <= .1)
        restoration.append(ports['restoration_error'] <= 1e-9)
    return {'origin': result['origin'], 'case': result['case'], 'summary': summary,
            'contrasts': {key: min(value) for key, value in contrasts.items()},
            'preservation': all(preservation), 'restoration': all(restoration), 'valid': result['valid']}


def inference(values, seed):
    """Two-sided source-level t test; sign-flip sensitivity and source bootstrap."""
    x = np.asarray(values, dtype=float)
    n = len(x); mean = float(x.mean()); sd = float(x.std(ddof=1))
    if sd == 0:
        statistic, p = (None, 1.) if mean == 0 else (None, 2.**(1-n))
    else:
        statistic = mean/(sd/np.sqrt(n)); p = float(2*t.sf(abs(statistic), n-1))
    rng = np.random.default_rng(seed)
    boot = x[rng.integers(0, n, size=(20000, n))].mean(axis=1)
    # Bounded-memory sensitivity analysis. This does not change registered scores.
    extreme = 0
    for _ in range(20):
        signs = rng.choice(np.array([-1., 1.]), size=(10000, n))
        extreme += int(np.count_nonzero(np.abs((signs*x).mean(axis=1)) >= abs(mean)-1e-12))
    positive = int(np.count_nonzero(x > 0))
    interval = [float(beta.ppf(.025, positive, n-positive+1)) if positive else 0.,
                float(beta.ppf(.975, positive+1, n-positive)) if positive < n else 1.]
    return {'n_independent': n, 'mean_difference': mean, 'sample_sd': sd,
            'paired_standardized_effect': mean/sd if sd else None, 't_statistic': statistic,
            'p_two_sided': p, 'p_signflip_sensitivity': (extreme+1)/200001,
            'bootstrap_observed_source_95': [float(v) for v in np.quantile(boot, [.025, .975])],
            'positive_origins': positive, 'positive_fraction_exact_95': interval,
            'zero_variance': sd == 0, 'test': 'exact-two-sided-source-sign' if sd == 0 else 'paired-t',
            'interval_note': 'A degenerate empirical bootstrap is not population certainty; the exact source-sign interval remains finite.'}


def holm(pvalues):
    ordered = sorted(pvalues, key=pvalues.get)
    answer, previous = {}, 0.
    for i, key in enumerate(ordered):
        previous = max(previous, min(1., pvalues[key]*(len(ordered)-i)))
        answer[key] = previous
    return answer


def analyze(work):
    registered = m.read(work/'cases.json')
    assert registered == spec.cases(), 'registered cases differ'
    results = [m.read(work/'units'/f'o{i}'/'result.json') for i in range(spec.N)]
    assert all(r['origin'] == i and r['case'] == registered[i] for i, r in enumerate(results))
    units = [source_metrics(r) for r in results]
    thresholds = {'fixed-expression': .5, 'selective-pathway': .5, 'readout-scope': .25}
    goals = {key: inference([u['contrasts'][key] for u in units], 2026101660+j)
             for j, key in enumerate(thresholds)}
    adjusted = holm({key: row['p_two_sided'] for key, row in goals.items()})
    for key, row in goals.items():
        qualifiers = [u['preservation'] and (key != 'selective-pathway' or u['restoration'])
                      and (key != 'fixed-expression' or u['summary']['tests']['ports']['first_expression'])
                      and u['contrasts'][key] >= thresholds[key] for u in units]
        row.update(holm_p=adjusted[key], minimum_mean=thresholds[key],
                   qualifying_origins=sum(qualifiers), required_origins=36)
        row['verdict'] = ('INVALID' if not all(u['valid'] for u in units) else
                          'PASS' if row['mean_difference'] >= thresholds[key] and adjusted[key] < .05
                          and sum(qualifiers) >= 36 else 'FAIL')
        row['decision_scope'] = 'Preregistered effect and source-consistency target; FAIL does not assert a zero effect.'
    strata = []
    for dose in spec.DOSES:
        for delay in spec.DELAYS:
            selected = [u for u in units if u['case']['dose'] == dose and u['case']['delay_s'] == delay]
            strata.append({'dose': dose, 'delay_s': delay, 'n': len(selected),
                           'mean_contrasts': {key: float(np.mean([u['contrasts'][key] for u in selected]))
                                              for key in thresholds}})
    return {'schema': 'threemind.m5-confirmation-analysis/1', 'independent_origins': spec.N,
            'exploratory_sources_included': 0, 'valid': all(u['valid'] for u in units),
            'goals': goals, 'secondary_strata': strata, 'units': units,
            'secondary_rule': 'Joint cues, continued-reader gains and crossing retain exploratory identities, not additional confirmatory wins.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args(); report = analyze(args.work)
    m.original(args.work/'analysis-v1.json', report)
    print(json.dumps({'valid': report['valid'], 'goals': report['goals']}))
