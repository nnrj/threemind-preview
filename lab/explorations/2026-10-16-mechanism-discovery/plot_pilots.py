"""Static scientific plots from saved analyses only; no simulator imports."""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('figure exists; preserve prior edition')
    data = json.loads(args.analysis.read_bytes())
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    if data['schema'] == 'threemind.m2-pilot-analysis/1':
        fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), constrained_layout=True)
        colors = {'H': '#1764ab', 'S': '#cc6d13'}
        for mode in ('H', 'S'):
            rows = sorted((g for g in data['groups'] if g['mode'] == mode and g['cue'] == 'strong'), key=lambda g:g['delay'])
            x = [r['delay'] for r in rows]
            axes[0].plot(x, [r['mean_preprobe_weight'] for r in rows], 'o-', label=mode, color=colors[mode])
            axes[1].plot(x, [r['main_history_contrast']['mean'] for r in rows], 'o-', label=mode, color=colors[mode])
            axes[2].plot(x, [r['posthoc_early_history_contrast']['mean'] for r in rows], 'o-', label=mode, color=colors[mode])
        titles = ['Stored trace: same-time total weight', 'PRIMARY: late history contrast', 'POST-HOC: early history contrast']
        for ax, title in zip(axes, titles):
            ax.set_title(title)
            ax.set_xscale('log')
            ax.set_xticks([1, 30, 60, 300], ['1', '30', '60', '300'])
            ax.set_xlabel('Independent-cohort delay (simulated s)')
            ax.grid(alpha=.2)
            ax.legend(title='Birth mode')
        axes[0].set_ylabel('Effective weight sum; 12 taught edges')
        axes[1].set_ylabel('Mean A-B response, 0.5-1.5 s')
        axes[2].set_ylabel('Mean A-B response, 0<t<0.5 s')
        upper = max(g['posthoc_early_history_contrast']['bootstrap_95'][1] for g in data['groups'])
        for ax in axes[1:]:
            ax.set_ylim(-.05*max(upper, 1e-6), 1.15*max(upper, 1e-6))
        fig.suptitle('M2 pilot: strong X cue; eight independent origins per delay\nMatched history difference / 2; other cue conditions retained in full report', fontsize=12)
    else:
        fig, ax = plt.subplots(figsize=(8, 4.7), constrained_layout=True)
        arms = ['intact', 'sham', 'target', 'matched', 'restored']
        for row in data['by_origin']:
            ax.plot(arms, [row['contrasts'][a] for a in arms], 'o-', alpha=.65, label=row['origin'])
        ax.set_ylabel('Paired history contrast / 2, 0.1-0.3 s')
        ax.set_title('M1 pilot: eight independent origins\nEdge-mask controls; restored = immediate zero-time reversal')
        ax.grid(alpha=.2)
        ax.legend(ncol=2, fontsize=8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
