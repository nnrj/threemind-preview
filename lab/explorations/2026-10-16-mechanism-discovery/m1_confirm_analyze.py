"""Frozen content-transfer and closed-loop-choice confirmation endpoints."""
import argparse
import json
from pathlib import Path
import statistics

import m1_confirm_spec as spec
from m5_confirm_analyze import inference
import pilot_m2 as m


def source_metrics(result):
    rates = {}
    for arm in spec.ARMS:
        rates[arm] = {}
        for domain, cues in [('target', spec.CUES[:5]), ('unrelated', spec.CUES[5:])]:
            selected = [t for t in result['trials'] if t['arm'] == arm and t['cue'] in cues]
            rates[arm][domain] = {endpoint: statistics.mean(t[endpoint] for t in selected)
                                 for endpoint in ('success', 'final_success')}
    r = rates
    def rate(history, arm, domain, endpoint):
        cues = spec.CUES[:5] if domain == 'target' else spec.CUES[5:]
        return statistics.mean(t[endpoint] for t in result['trials']
                               if t['history'] == history and t['arm'] == arm and t['cue'] in cues)
    gains = [rate(h, 'target-bundle', 'target', e)-rate(h, a, 'target', e)
             for h in (0, 1) for e in ('success', 'final_success') for a in ('sham', 'matched-bundle')]
    damage = max(rate(h, 'sham', 'unrelated', e)-rate(h, 'target-bundle', 'unrelated', e)
                 for h in (0, 1) for e in ('success', 'final_success'))
    minimum_accuracy = min(rate(h, 'target-bundle', 'target', e)
                           for h in (0, 1) for e in ('success', 'final_success'))
    restored = max(abs(rate(h, 'restored', d, e)-rate(h, 'intact', d, e))
                   for h in (0, 1) for d in ('target', 'unrelated') for e in ('success', 'final_success'))
    joint_gain = min(gains)
    qualified = joint_gain >= .5 and minimum_accuracy >= .75 and damage <= .1 and restored == 0
    return {'origin': result['origin'], 'case': result['case'], 'valid': result['valid'], 'rates': rates,
            'joint_gain': joint_gain, 'unrelated_loss': damage, 'minimum_transferred_accuracy': minimum_accuracy,
            'restoration_rate_error': restored, 'qualified': qualified,
            'novel_combinations': {arm: {endpoint: statistics.mean(t[endpoint] for t in result['trials']
                if t['arm'] == arm and t['cue'] in ('XN', 'YN'))
                for endpoint in ('success', 'final_success')} for arm in spec.ARMS}}


def analyze(work):
    assert m.read(work/'cases.json') == spec.cases()
    results = [m.read(work/'units'/f'o{i}'/'result.json') for i in range(spec.N)]
    assert all(r['case'] == spec.cases()[i] and r['origin'] == i for i, r in enumerate(results))
    units = [source_metrics(r) for r in results]
    effect = inference([u['joint_gain'] for u in units], 2026101671)
    valid = all(u['valid'] for u in units)
    passed = sum(u['qualified'] for u in units)
    verdict = ('INVALID' if not valid else 'PASS' if effect['mean_difference'] >= .5
               and effect['p_two_sided'] < .05 and passed >= 36 else 'FAIL')
    return {'schema': 'threemind.m1-confirmation-analysis/1', 'independent_origins': spec.N,
            'valid': valid, 'exploratory_sources_included': 0,
            'goal': {'verdict': verdict, 'qualifying_origins': passed, 'required_origins': 36,
                     'minimum_effect': .5, 'effect': effect}, 'units': units,
            'scope': 'Declared same-origin counterfactual teaching copies with fixed interface; content transfer and two-step environment-contingent choice.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    args = p.parse_args(); report = analyze(args.work)
    m.original(args.work/'analysis-v1.json', report)
    print(json.dumps({'valid': report['valid'], 'goal': report['goal']}))
