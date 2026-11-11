"""Predeclared observer contrasts. Reads evidence; never executes Core."""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from run import HERE, META, WORK, encoded
from threemind_lab.statistics import compare_pairs


def mean(values):
    return statistics.mean(values) if values and all(v is not None for v in values) else None


def delta(a, b):
    return a - b if a is not None and b is not None else None


def family_scores(case, group='family'):
    a, b, c, d, e, f = case['names']
    m = case['measurements'][group]
    rows = {r['cue']: r for r in m['rows']}
    scores = []
    for grand, father, child, other in [(a, b, c, d), (d, e, f, a)]:
        canonical = grand
        if case['arm'] == 'crossed_chain':
            grand, other = other, grand
        g = rows[child+'的爷爷是谁？']['net_endpoint']
        p = rows[child+'的父亲是谁？']['net_endpoint']
        bare = rows[child]['net_endpoint']
        margin = (g[grand] - max(v for k, v in g.items() if k != grand)
                  if all(v is not None for v in g.values()) else None)
        scores.append({
            'child': child, 'expected_grandfather': grand, 'father': father,
            'role': delta(delta(g[grand], g[father]), delta(p[grand], p[father])),
            'grandfather_vs_other': delta(g[grand], g[other]),
            'query_vs_bare': delta(delta(g[grand], g[other]), delta(bare[grand], bare[other])),
            'target_margin': margin, 'canonical_grandfather_bias': delta(g[canonical], g[other] if canonical == grand else g[grand]),
            'grandfather_activity': g[grand], 'father_activity': g[father],
            'father_query_margin': p[father] - max(v for k, v in p.items() if k != father)
            if all(v is not None for v in p.values()) else None,
        })
    return scores


def who_score(case):
    rows = {r['cue']: r for r in case['measurements']['who']['rows']}
    pine, bell = rows['松子是谁？']['net_endpoint'], rows['铃铛是谁？']['net_endpoint']
    return mean([delta(pine['甲'], pine['乙']), delta(bell['乙'], bell['甲'])])


def block_values(cases, arm, metric='role', n=8, family=None):
    groups = defaultdict(list)
    for case in cases:
        if case['arm'] == arm and case['n'] == n and (family is None or case['family'] == family):
            value = who_score(case) if metric == 'who' else mean([r[metric] for r in family_scores(case)])
            groups[case['seed']].append(value)
    # The amendment freezes one formal alphabet. All planned cases within a seed are required.
    expected = 1 if family is not None else len({c['family'] for c in cases if c['n'] == n})
    return {s: mean(v) if len(v) == expected else None for s, v in groups.items()}


def compare(cases, control):
    a, b = block_values(cases, control), block_values(cases, 'full')
    pairs = [
        {'seed': seed, 'control': {'query_role_specificity': a.get(seed)},
         'treatment': {'query_role_specificity': b.get(seed)}} for seed in sorted(set(a) | set(b))
    ]
    failed = (HERE/'instrument-decision.json').exists() and not json.loads((HERE/'instrument-decision.json').read_bytes())['calibration_passed']
    if failed:
        available = [(a[s], b[s]) for s in sorted(set(a)&set(b)) if a[s] is not None and b[s] is not None]
        result = {'method':'uncalibrated-descriptive-paired-means/1','pairs':pairs,'metrics':[{
            'metric':'query_role_specificity','n':len(available),'missing_pairs':len(pairs)-len(available),
            'control_mean':mean([v[0] for v in available]),'treatment_mean':mean([v[1] for v in available]),
            'difference':mean([v[1]-v[0] for v in available]),'ci95':None,'p':None,'p_holm':None,'paired_dz':None}]}
    else:
        result = compare_pairs(pairs, seed=20260909, resamples=5000)
    result['unit'] = 'complete encoding seed blocks, conditional on fixed teaching material; not individual queries'
    result['inference'] = 'exploratory small-sample paired contrasts; two comparisons jointly Holm corrected'
    if failed:
        result['method'] = 'uncalibrated-descriptive-paired-means/1'
        result['inference'] = ('Instrument physical gate failed. These are descriptive activation differences only; '
                               'no confirmatory test, no language or consciousness claim.')
        for metric in result['metrics']:
            for key in ['p','p_holm','ci95','paired_dz']:
                metric[key] = None
    return result


def describe(values):
    valid = [v for v in values if v is not None]
    return {'total': len(values), 'available': len(valid), 'unscorable': len(values)-len(valid),
            'mean': statistics.mean(valid) if valid else None,
            'positive': sum(v > 0 for v in valid), 'zero': sum(v == 0 for v in valid)}


def analyze():
    meta = json.loads(META.read_bytes())
    phases = {key: json.loads((WORK/file).read_bytes()) for key, file in meta.get('completed_phases', {}).items()}
    if 'main' not in phases:
        raise RuntimeError('no completed formal phase; report incomplete evidence separately')
    cases = phases['main']['rows']
    analyses = {key: compare(cases, control) for key, control in
                [('rules', 'rule_scrambled'), ('teaching', 'teaching_scrambled')]}
    ordered = sorted([v['metrics'][0] for v in analyses.values() if v['metrics'][0]['p'] is not None], key=lambda r: r['p'])
    adjustment = 0
    for i, row in enumerate(ordered):
        adjustment = max(adjustment, min(1, row['p'] * (len(ordered)-i)))
        row['p_holm'] = adjustment
    arms = {}
    flat = []
    for arm in sorted({c['arm'] for c in cases}):
        selected = [c for c in cases if c['arm'] == arm]
        scores = [r for c in selected for r in family_scores(c)]
        arms[arm] = {
            'role_blocks': block_values(cases, arm),
            'role': describe(list(block_values(cases, arm).values())),
            'who': describe(list(block_values(cases, arm, 'who').values())),
            'grandfather_dominance': describe([r['target_margin'] for r in scores]),
            'grandfather_minus_other': describe([r['grandfather_vs_other'] for r in scores]),
            'query_minus_bare': describe([r['query_vs_bare'] for r in scores]),
            'father_dominance': describe([r['father_query_margin'] for r in scores]),
        }
        for case in selected:
            for score in family_scores(case):
                flat.append({'seed': case['seed'], 'family': case['family'], 'arm': arm, 'rounds': case['n'],
                             'route': 'birth', **score})
            if 'continuous_family' in case['measurements']:
                for score in family_scores(case, 'continuous_family'):
                    flat.append({'seed': case['seed'], 'family': case['family'], 'arm': arm, 'rounds': case['n'],
                                 'route': 'continuation', **score})
    with (HERE/'family-cases.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    measurements = []
    for phase, data in phases.items():
        for case in data['rows']:
            for key, m in case['measurements'].items():
                for p in m['rows']:
                    if p['cue']:
                        measurements.append({'phase': phase, 'group': key, 'seed': case['seed'], 'arm': case['arm'],
                                             'cue': p['cue'], 'dose': p['intensity'], 'available': p['available'],
                                             'sent': p['transport']['sent'], 'delivered': p['delivered_signal_amount'],
                                             'saturation': p['max_saturated_fraction'],
                                             'scorable': all(v is not None for v in p['net_endpoint'].values())})
    with (HERE/'probe-observability.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(measurements[0]))
        writer.writeheader()
        writer.writerows(measurements)
    formal = [r for r in measurements if r['phase'] == 'main']
    counts = {key: {'parents': 0 if key=='weak_probe' else len(data['rows']),
                    'source_cases': len(data['rows']),
                    'copies': sum(len(m['rows']) for c in data['rows'] for m in c['measurements'].values()),
                    'elapsed_s': data['elapsed_s'], 'peak_rss': data['peak_rss']} for key, data in phases.items()}
    summary = {'analyses': analyses, 'arms': arms, 'counts': counts,
               'continuous': {key: describe([r[key] for r in flat if r['route']=='continuation'])
                              for key in ['role', 'target_margin', 'query_vs_bare']},
               'observability': {'formal_probes': len(formal),
                                 'nonzero_delivery': sum(r['delivered']>0 for r in formal),
                                 'unscorable': sum(not r['scorable'] for r in formal),
                                 'peak_saturation': max(r['saturation'] for r in formal)},
               'core_changed': False, 'not_language_accuracy': True}
    if 'long' in phases:
        long = phases['long']['rows'][0]
        summary['long_course'] = {'seed':long['seed'],'rounds':long['n'],
                                 'birth':family_scores(long),'continuation':family_scores(long,'continuous_family'),
                                 'who':who_score(long)}
    (HERE/'summary.json').write_bytes(encoded(summary))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    order = ['full', 'rule_scrambled', 'teaching_scrambled', 'crossed_chain', 'learning_off']
    labels = ['Full', 'Rule shuffled', 'Teaching shuffled', 'Crossed chain', 'Learning off']
    for i, arm in enumerate(order):
        ys = [v for v in arms[arm]['role_blocks'].values() if v is not None]
        axes[0].scatter([i]*len(ys), ys, color='#237e74', s=24)
        if ys:
            axes[0].plot([i-.25,i+.25], [statistics.mean(ys)]*2, color='black')
        dom = arms[arm]['grandfather_dominance']
        margins = [r['target_margin'] for r in flat if r['arm']==arm and r['route']=='birth' and r['target_margin'] is not None]
        axes[1].scatter([i]*len(margins), margins, color='#a77530', s=24)
        if margins:
            axes[1].plot([i-.25,i+.25],[statistics.mean(margins)]*2,color='black')
        axes[1].text(i,.94,f"{dom['positive']}/{dom['available']}",transform=axes[1].get_xaxis_transform(),ha='center',fontsize=9)
    axes[0].set_ylabel('Query-role contrast (activation a.u.)')
    axes[0].axhline(0, color='grey', linewidth=.8)
    axes[1].set_ylabel('Grandfather minus strongest other (a.u.)')
    axes[1].axhline(0,color='grey',linewidth=.8)
    axes[1].set_title('Top labels: strict dominance / scorable queries', fontsize=10)
    for ax in axes:
        ax.set_xticks(range(5), labels, rotation=25, ha='right')
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('Teaching study: observer projections, not language answers')
    fig.savefig(HERE/'results.png', dpi=180)
    plt.close(fig)
    print(encoded({'analyses': {k:v['metrics'] for k,v in analyses.items()},
                   'arms': arms, 'counts': counts, 'continuous': summary['continuous'],
                   'observability': summary['observability']}).decode())
    return summary


if __name__ == '__main__':
    analyze()
