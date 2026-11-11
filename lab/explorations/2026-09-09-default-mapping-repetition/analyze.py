"""Read-only observer analysis; fixed windows and all planned cases retained."""
from __future__ import annotations

import json
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from run import HERE, WORK, META, SEEDS, SENSOR, encoded
from dataclasses import asdict
from threemind_lab import calibration
from threemind_lab.config import Settings
from threemind_lab.database import Database

TOLERANCE = 1e-12  # Floating-point equality only; not a biological significance threshold.


def mean(values):
    return statistics.mean(values) if values and all(v is not None for v in values) else None


def diff(a, b):
    return a - b if a is not None and b is not None else None


def integrate(curve, word, start, end):
    values = [p['terms'][word] for p in curve if start <= p['offset_us'] <= end]
    if len(values) < 2 or any(v is None for v in values):
        return None
    return (sum(values) - (values[0] + values[-1]) / 2) / (len(values) - 1)


def project(result):
    sham = next(row for row in result['rows'] if row['cue'] is None)
    rows = {}
    for row in result['rows']:
        if not row['cue']:
            continue
        early = {w: diff(integrate(row['curve'], w, 0, 200000),
                         integrate(sham['curve'], w, 0, 200000)) for w in result['protocol']['terms']}
        assert all(abs(v - diff(row['endpoint'][w], sham['endpoint'][w])) < 1e-12
                   for w, v in row['net_endpoint'].items() if v is not None)
        rows[row['cue']] = dict(late=row['net_endpoint'], early=early, raw_late=row['endpoint'],
                                sham_late=sham['endpoint'], available=row['available'],
                                peak_saturated_fraction=max(p['saturated_fraction'] for p in row['curve']),
                                life=row['life'], transport=row['transport'])
    return rows


def scores(group, rows, arm, window):
    def response(cue):
        return rows[cue][window]
    if group in ['pair', 'who']:
        expected = ([('甲', '松子', '铃铛'), ('乙', '铃铛', '松子')] if group == 'pair' else
                    [('谁是松子？', '甲', '乙'), ('谁是铃铛？', '乙', '甲'),
                     ('松子是谁？', '甲', '乙'), ('铃铛是谁？', '乙', '甲')])
        if arm == 'pair_swap':
            expected = [(cue, other, target) for cue, target, other in expected]
        cases = [dict(cue=cue, expected=target, other=other,
                      margin=diff(response(cue)[target], response(cue)[other]),
                      values=response(cue)) for cue, target, other in expected]
        return dict(mean_margin=mean([r['margin'] for r in cases]), cases=cases)
    families = [('C', 'A', 'B', 'D'), ('F', 'D', 'E', 'A')] if group == 'seen_family' else [
                 ('Z', 'X', 'Y', 'U'), ('W', 'U', 'V', 'X')]
    cases = []
    for child, grand, father, other in families:
        canonical = grand
        if arm == 'crossed':
            grand, other = other, grand
        g, p, bare = [response(child + suffix) for suffix in ['的爷爷是谁？', '的父亲是谁？', '']]
        margin = g[grand] - max(v for k, v in g.items() if k != grand) if all(v is not None for v in g.values()) else None
        pmargin = p[father] - max(v for k, v in p.items() if k != father) if all(v is not None for v in p.values()) else None
        cases.append(dict(child=child, expected_grandfather=grand, father=father, values=g,
                          father_values=p, bare_values=bare, target_margin=margin, father_margin=pmargin,
                          role=diff(diff(g[grand], g[father]), diff(p[grand], p[father])),
                          grandfather_vs_other=diff(g[grand], g[other]),
                          query_vs_bare=diff(diff(g[grand], g[other]), diff(bare[grand], bare[other])),
                          canonical_bias=diff(g[canonical], g['U' if canonical == 'X' else 'X'])
                          if group == 'family' else None))
    return dict(mean_role=mean([r['role'] for r in cases]), cases=cases)


def analyze():
    meta = json.loads(META.read_bytes())
    phase_names = [f'seed-{s}' for s in SEEDS]
    phase_names += [f'pair-swap-{s}' for s in meta.get('pair_control', {}).get('seeds', [])]
    phases = [json.loads((WORK / meta['completed_phases'][name]).read_bytes()) for name in phase_names]
    assert all(p['error'] is None for p in phases)
    db = Database(Settings.from_env().database_url)
    measures, traces, curves = [], [], []
    try:
        for phase in phases:
            for anchor in phase['rows']:
                for key, compact in anchor['measurements'].items():
                    group, route = key.split('/')
                    result = calibration.result(db, meta['project_id'], compact['id'])
                    assert result['source_hash'] == anchor['source_hash']
                    assert result['sensor_config'] == asdict(SENSOR)
                    assert result['protocol']['learning_during_probe'] is True
                    assert result['protocol']['blank_us'] == 0
                    rows = project(result)
                    item = dict(seed=anchor['seed'], arm=anchor['arm'], stage=anchor['stage'],
                                count=anchor['count'], group=group, route=route, id=compact['id'],
                                source_hash=anchor['source_hash'], rows=rows, coverage=result['mapping']['coverage'],
                                late=scores(group, rows, anchor['arm'], 'late'),
                                early=scores(group, rows, anchor['arm'], 'early'))
                    measures.append(item)
                    if anchor['seed'] == SEEDS[0] and anchor['stage'] == 'final' and group == 'family':
                        curves.append(dict(seed=anchor['seed'], arm=anchor['arm'], route=route,
                                           source_hash=anchor['source_hash'], rows=result['rows']))
            seed = phase['rows'][0]['seed']
            trace_name = f'pair-swap-{seed}-trace.jsonl' if phase['phase'].startswith('pair-swap') else f'seed-{seed}-trace.jsonl'
            traces.extend(json.loads(line) for line in (WORK / trace_name).read_bytes().splitlines())
    finally:
        db.close()
    (HERE / 'measurements.json').write_bytes(encoded(measures))
    (HERE / 'training-traces.json').write_bytes(encoded(traces))
    (HERE / 'time-courses.json').write_bytes(encoded(curves))
    groups = defaultdict(list)
    for m in measures:
        groups[(m['arm'], m['stage'], m['group'], m['route'])].append(m)
    aggregates = []
    for key, items in groups.items():
        arm, stage, group, route = key
        field = 'mean_margin' if group in ['pair', 'who'] else 'mean_role'
        late = {m['seed']: m['late'][field] for m in items}
        early = {m['seed']: m['early'][field] for m in items}
        available = [v for v in late.values() if v is not None]
        cases = [r for m in items for r in m['late']['cases']]
        target_key = 'margin' if group in ['pair', 'who'] else 'target_margin'
        margins = [r[target_key] for r in cases if r[target_key] is not None]
        peaks = [r['peak_saturated_fraction'] for m in items for r in m['rows'].values()]
        aggregates.append(dict(arm=arm, stage=stage, group=group, route=route, metric=field,
                               by_seed=late, early_by_seed=early, complete_seeds=len(available),
                               mean=mean(available), positive_seeds=sum(v > TOLERANCE for v in available),
                               strict_target_top=sum(v > TOLERANCE for v in margins), scorable_queries=len(margins),
                               total_queries=len(cases), ties=sum(abs(v) <= TOLERANCE for v in margins),
                               min_margin=min(margins) if margins else None,
                               max_margin=max(margins) if margins else None,
                               peak_saturation_range=[min(peaks), max(peaks)]))
    following = []
    for route in ['continuation', 'birth']:
        for seed in SEEDS:
            pair = {m['arm']: m for m in measures if m['seed'] == seed and m['stage'] == 'final'
                    and m['group'] == 'family' and m['route'] == route}
            values = [diff(a['canonical_bias'], b['canonical_bias']) for a, b in
                      zip(pair['normal']['late']['cases'], pair['crossed']['late']['cases'])]
            following.append(dict(seed=seed, route=route, by_family=values, mean=mean(values)))
    trace_summary = []
    for seed in SEEDS:
        items = [t for t in traces if t['seed'] == seed and t['arm'] == 'normal']
        for count in [20, 40, 200, 600, 1020, 1070, 1310]:
            t = next(t for t in items if t['count'] == count)
            trace_summary.append({k: t[k] for k in ['seed', 'count', 'metrics', 'mean_edge_stability',
                                                   'first_sentence_edges', 'retained_first_sentence_edges',
                                                   'anchor_mean_weight', 'anchor_mean_stability']})
    pair_following = []
    for added_seed in meta.get('pair_control', {}).get('seeds', []):
        for route in ['continuation', 'birth']:
            for group in ['pair', 'who']:
                for stage in ['pair_20_each', 'dialogue_1', 'dialogue_3', 'review', 'final']:
                    selected = {m['arm']:m for m in measures if m['seed']==added_seed and m['route']==route
                                and m['group']==group and m['stage']==stage}
                    if 'normal' in selected and 'pair_swap' in selected:
                        a,b=selected['normal']['late']['mean_margin'],selected['pair_swap']['late']['mean_margin']
                        pair_following.append(dict(seed=added_seed,route=route,group=group,stage=stage,
                            normal_correct_margin=a,swapped_correct_margin=b,
                            following_difference=a+b if a is not None and b is not None else None))
    summary = dict(project_id=meta['project_id'], experiment='default-mapping-repetition/1',
                   inference='Four encoding seeds; descriptive observation; no confirmation claim or calibrated language accuracy.',
                   tolerance=TOLERANCE, seeds=SEEDS, aggregates=aggregates, follows_crossed_facts=following,
                   training_anchors=trace_summary, follows_swapped_pairs=pair_following,
                   resources=dict(elapsed_s=sum(p['elapsed_s'] for p in phases),
                                  max_process_rss=max(p['peak_rss'] for p in phases),
                                  measurement_jobs=len(measures),
                                  probe_copies=sum(1 + len(m['rows']) for m in measures),
                                  source_runs=len({r['run_id'] for p in phases for r in p['rows']}),
                                  checkpoints=sum(len(p['rows']) for p in phases),
                                  delivered_training_carriers=4 * (1070 + 240 + 240)+1310*len(meta.get('pair_control',{}).get('seeds',[]))))
    (HERE / 'summary.json').write_bytes(encoded(summary))
    plot(measures, traces, curves)
    print(encoded(dict(resources=summary['resources'], final=[a for a in aggregates if a['stage']=='final'],
                       follows_crossed_facts=following)).decode())
    return summary


def plot(measures, traces, curves):
    colors = ['#19756b', '#a46928', '#5278a5', '#ad5362']
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True, constrained_layout=True)
    for seed, color in zip(SEEDS, colors):
        series = [t for t in traces if t['seed'] == seed and t['arm'] == 'normal']
        x = [t['count'] for t in series]
        axes[0].plot(x, [t['metrics']['edges'] for t in series], color=color, label=str(seed))
        axes[1].plot(x, [t['anchor_mean_weight'] for t in series], color=color)
        axes[2].plot(x, [t['anchor_mean_stability'] for t in series], color=color)
    for ax in axes:
        for boundary in [600, 1020, 1070]:
            ax.axvline(boundary, ls=':', color='grey', alpha=.5)
        ax.grid(alpha=.2)
    axes[0].legend(ncol=4)
    axes[0].set_ylabel('Edges')
    axes[1].set_ylabel('Mean weight of present\nfirst-sentence endpoint pairs')
    axes[2].set_ylabel('Mean stability of present\nfirst-sentence endpoint pairs')
    axes[2].set_xlabel('Complete sentences delivered (20 consecutive repetitions per initial block)')
    fig.suptitle('Training trajectory: original endpoint pairs, including possible reconnection; observation only')
    fig.savefig(HERE / 'training.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True, constrained_layout=True)
    stages = ['pair_20_each', 'dialogue_1', 'dialogue_3', 'review', 'final']
    counts = [40, 200, 600, 1070, 1310]
    for row, group in enumerate(['pair', 'who']):
        for col, route in enumerate(['continuation', 'birth']):
            ax = axes[row, col]
            for seed, color in zip(SEEDS, colors):
                found = {m['stage']: m for m in measures if m['seed'] == seed and m['group'] == group
                         and m['route'] == route and m['arm'] == 'normal'}
                ax.plot(counts, [found[s]['late']['mean_margin'] if s in found else float('nan')
                                            for s in stages], marker='o', color=color, label=str(seed))
            ax.axhline(0, color='grey', lw=.8)
            ax.set_title(group + ' / ' + route)
            ax.set_xticks(counts, ['40', '200', '600', '1070', '1310'])
            ax.set_ylabel('Expected minus other activity')
            ax.grid(alpha=.2)
    axes[0, 0].legend(ncol=2)
    for ax in axes[1]:
        ax.set_xlabel('Cumulative training sentences')
    fig.suptitle('Pair and question probes: sham-corrected 0.2-1.0 s; markers are encoding seeds')
    fig.savefig(HERE / 'learning.png', dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True, constrained_layout=True)
    for col, route in enumerate(['continuation', 'birth']):
        item = next(c for c in curves if c['arm'] == 'normal' and c['route'] == route)
        sham = next(r for r in item['rows'] if r['cue'] is None)
        for row, child in enumerate(['Z', 'W']):
            ax = axes[row, col]
            probe = next(r for r in item['rows'] if r['cue'] == child + '的爷爷是谁？')
            for name, color in zip(['X', 'Y', 'U', 'V'], colors):
                ax.plot([p['offset_us']/1e6 for p in probe['curve']],
                        [diff(p['terms'][name], b['terms'][name]) for p, b in zip(probe['curve'], sham['curve'])],
                        label=name, color=color)
            ax.axvspan(.2, 1, color='grey', alpha=.07)
            ax.set_title(f'{child}: grandfather query / {route}')
            ax.set_ylabel('Net term activation')
            ax.grid(alpha=.2)
            ax.legend(ncol=4)
    for ax in axes[1]:
        ax.set_xlabel('Simulated seconds after query')
    fig.suptitle('Fixed first seed 41701: all four candidate projections, no selected best-case example')
    fig.savefig(HERE / 'family-curves.png', dpi=160)
    plt.close(fig)


def self_check():
    result = {'甲': {'late': {'松子': .8, '铃铛': .2}}, '乙': {'late': {'松子': .1, '铃铛': .7}}}
    assert abs(scores('pair', result, 'normal', 'late')['mean_margin'] - .6) < 1e-12
    assert abs(scores('pair', result, 'pair_swap', 'late')['mean_margin'] + .6) < 1e-12
    result['乙']['late']['松子'] = None
    assert scores('pair', result, 'normal', 'late')['mean_margin'] is None
    rows = {}
    for child, grand, father in [('Z', 'X', 'Y'), ('W', 'U', 'V')]:
        for suffix in ['的爷爷是谁？', '的父亲是谁？', '']:
            values = {name: 0.0 for name in ['X', 'Y', 'U', 'V']}
            if suffix:
                values[grand if '爷爷' in suffix else father] = 1.0
            rows[child + suffix] = {'late': values}
    assert scores('family', rows, 'normal', 'late')['mean_role'] == 2
    assert all(c['target_margin'] == -1 for c in scores('family', rows, 'crossed', 'late')['cases'])


if __name__ == '__main__':
    import sys
    self_check()
    if '--check' in sys.argv:
        print('Observer checks passed: expected contrasts, crossed truth and missing values.')
    else:
        analyze()
