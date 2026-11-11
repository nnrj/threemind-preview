"""Descriptive origin-level intervals and scientific figure; no simulation."""
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pilot_m2 as m


def build(analysis):
    units = analysis['units']
    tables = {}
    for head in ('full', 'ports'):
        rs = [r for u in units for r in u['rows'] if r['head'] == head]
        totals = {}
        for arm in ('sham', 'target', 'matched', 'restored', 'plasticity-off'):
            totals[arm] = {}
            for group in ('new', 'old'):
                totals[arm][group] = {'correct': sum(r['arms'][arm][group]['correct'] for r in rs),
                                     'n': sum(r['arms'][arm][group]['n'] for r in rs),
                                     'joint_correct': sum(r['joint_cues'][arm][group]['correct'] for r in rs),
                                     'joint_n': sum(r['joint_cues'][arm][group]['n'] for r in rs)}
        heldout = {kind: {group: {'correct': sum(r['heldout'][kind][group]['correct'] for r in rs),
                               'n': sum(r['heldout'][kind][group]['n'] for r in rs)} for group in ('new', 'old')}
                   for kind in ('fixed', 'continued')}
        early = {group: {'correct': sum(r['early_'+group]['correct'] for r in rs),
                         'n': sum(r['early_'+group]['n'] for r in rs)} for group in ('new', 'old')}
        crosses = {}
        for rt in ('early', 'late'):
            for at in ('early', 'late'):
                for group in ('new', 'old'):
                    data = [r for u in units for r in u['crosses'] if r['head'] == head and r['reader_time'] == rt
                            and r['activity_time'] == at and r['group'] == group]
                    crosses[f'{rt}-reader/{at}-activity/{group}'] = {
                        'correct': sum(r['correct'] for r in data), 'n': sum(r['n'] for r in data)}
        tables[head] = {'early': early, 'first': totals, 'heldout': heldout, 'crosses': crosses}
    sensory = {group: {'correct': sum(v[group]['correct'] for u in units for v in u['sensory'].values()),
                       'n': sum(v[group]['n'] for u in units for v in u['sensory'].values())} for group in ('new', 'old')}
    effects = {}
    for head in ('full', 'ports'):
        for name in ('first_gain', 'plasticity_effect', 'target_loss', 'matched_loss', 'target_old_loss', 'continued_gain'):
            vector = []
            for unit in units:
                values = []
                for r in unit['rows']:
                    if r['head'] != head: continue
                    a, held = r['arms'], r['heldout']
                    values.append({'first_gain': a['sham']['new']['rate']-r['early_new']['rate'],
                                   'plasticity_effect': a['sham']['new']['rate']-a['plasticity-off']['new']['rate'],
                                   'target_loss': a['sham']['new']['rate']-a['target']['new']['rate'],
                                   'matched_loss': a['sham']['new']['rate']-a['matched']['new']['rate'],
                                   'target_old_loss': a['sham']['old']['rate']-a['target']['old']['rate'],
                                   'continued_gain': held['continued']['new']['rate']-held['fixed']['new']['rate']}[name])
                vector.append(float(np.mean(values)))
            rng = np.random.default_rng(1056200)
            samples = np.mean(np.asarray(vector)[rng.integers(0, 8, size=(20000, 8))], axis=1)
            effects[head+'/'+name] = {'origin_effects': vector, 'mean': float(np.mean(vector)),
                                    'descriptive_95_interval': np.quantile(samples, [.025, .975]).tolist()}
    intervals = {}
    z = 1.959963984540054
    for name, goal in analysis['goals'].items():
        n, p = goal['n'], goal['passed_origins']/goal['n']
        center = (p+z*z/(2*n))/(1+z*z/n)
        half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
        intervals[name] = [max(0., center-half), min(1., center+half)]
    return {'schema': 'threemind.m5-summary/1', 'tables': tables, 'sensory': sensory, 'effects': effects,
            'descriptive_wilson_95_source_pass_intervals': intervals,
            'sampling_unit': 'eight independent birth origins; two histories paired within origin; no trial-level pseudoreplication'}


def figure(summary, work):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), constrained_layout=True)
    colors = ['#64748b', '#2563eb']
    xs = np.arange(3)
    for h, head in enumerate(('full', 'ports')):
        table = summary['tables'][head]
        vals = [table['early']['new'], table['first']['sham']['new'], table['first']['sham']['old']]
        bars = axes[0].bar(xs+(h-.5)*.35, [100*r['correct']/r['n'] for r in vals], .35,
                           label='All activity' if h == 0 else 'Output ports', color=colors[h])
        axes[0].bar_label(bars, labels=[f"{r['correct']}/{r['n']}" for r in vals], padding=3, fontsize=9)
    axes[0].set_xticks(xs, ['New: before', 'New: first\nafter teaching', 'Old: after'])
    axes[0].set_ylim(0, 116); axes[0].set_ylabel('Correct singleton answers (%)')
    axes[0].set_title('Fixed personal readers'); axes[0].legend(loc='upper left', fontsize=8)
    names = ['sham', 'plasticity-off', 'target', 'matched', 'restored']
    vals = [summary['tables']['ports']['first'][name]['new'] for name in names]
    bars = axes[1].bar(range(5), [100*r['correct']/r['n'] for r in vals], color='#2563eb')
    axes[1].bar_label(bars, labels=[f"{r['correct']}/{r['n']}" for r in vals], padding=3)
    axes[1].set_xticks(range(5), ['Sham', 'Plasticity\nbundle off', 'Target\nsilenced', 'Matched\nsilenced', 'Restored'])
    axes[1].set_ylim(0, 116); axes[1].set_title('Output-port causal controls')
    vals = [summary['tables'][h]['heldout'][k]['new'] for h in ('full', 'ports') for k in ('fixed', 'continued')]
    bars = axes[2].bar(range(4), [100*r['correct']/r['n'] for r in vals], color=[colors[0]]*2+[colors[1]]*2)
    axes[2].bar_label(bars, labels=[f"{r['correct']}/{r['n']}" for r in vals], padding=3)
    axes[2].set_xticks(range(4), ['All: fixed', 'All:\ncontinued', 'Ports: fixed', 'Ports:\ncontinued'])
    axes[2].set_ylim(0, 116); axes[2].set_title('Held-out doses: new answers')
    fig.suptitle('M5: Core experience and personal expression | 8 independent origins, paired histories', fontsize=13)
    path = work/'figure-v1.png'
    if path.exists(): raise FileExistsError(path)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def decomposition(work):
    """Post-result arithmetic explanation, separate from all frozen endpoints."""
    rows = []
    for folder in sorted((work/'units').glob('o*')):
        result = m.read(folder/'result.json')
        state = json.loads(gzip.decompress((folder/'old-calibrated.json.gz').read_bytes()))
        channels = sorted(state['mappings'].values())
        indices = {s: channels.index(c) for s, c in state['mappings'].items()}
        reader = state['reader']
        w = np.asarray(reader['weights'])/np.asarray(reader['scale'])
        fractions, new_scores = [], []
        for history in result['histories']:
            for row in history['cases']['sham']['rows']:
                if len(row['cue']) != 1: continue
                contributions = w*np.asarray(row['features'])
                assert abs(float(contributions.sum())-row['response']['score']) < 1e-9
                if row['group'] == 'old':
                    fractions.append(float(sum(abs(contributions[indices[s]]) for s in 'UVZW')/abs(contributions).sum()))
                else:
                    new_scores.append(float(contributions.sum()))
        rows.append({'origin': result['origin'], 'new_cue_weights_all_zero': all(w[indices[s]] == 0 for s in 'XYCD'),
                     'old_cue_absolute_contribution_fraction_mean': float(np.mean(fractions)),
                     'old_cue_absolute_contribution_fraction_min': min(fractions),
                     'old_cue_absolute_contribution_fraction_max': max(fractions),
                     'new_score_min': min(new_scores), 'new_score_max': max(new_scores)})
    return {'identity': 'post-result arithmetic explanation; not a primary goal, causal intervention or new simulation',
            'origins': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args(); summary = build(m.read(args.work/'analysis-v1.json'))
    summary['readout_decomposition'] = decomposition(args.work)
    m.original(args.work/'summary-v1.json', summary)
    figure(summary, args.work)
    print(json.dumps({'tables': summary['tables'], 'sensory': summary['sensory']}))
