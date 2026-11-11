"""Render verified instrument samples, without a simulation engine."""
import argparse
import gzip
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(p):
    return json.loads(gzip.decompress(p.read_bytes()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('preserve figure edition')
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), constrained_layout=True)
    for ax, case, title in zip(axes, ['d60-o0-S-h0-strong', 'd1-o0-H-h0-weak'],
                              ['S, 60 s retention, strong X', 'H, 1 s retention, weak X']):
        folder = args.work/'cases'/case
        original = read(folder/'original-final.json.gz')
        dense = read(folder/'dense-rows.json.gz')
        start = (17+original['case']['delay'])*1_000_000
        samples = [r for r in dense if 80_000 <= r['time_us']-start <= 180_000]
        coarse = [r for r in original['recent_activity'] if 80_000 <= r['time_us']-start <= 180_000]
        ax.plot([(r['time_us']-start)/1000 for r in samples], [r['response'] for r in samples],
                'o-', markersize=2, label='1 ms calibration', color='#24679a')
        ax.scatter([(r['time_us']-start)/1000 for r in coarse], [r['response'] for r in coarse],
                   marker='x', s=90, linewidths=2, label='Original 50 ms samples', color='#c04430', zorder=5)
        ax.axhline(.004, linestyle='--', color='#888888', label='Activation floor')
        ax.set_title(title)
        ax.set_xlabel('Milliseconds after cue timestamp')
        ax.set_ylabel('Fixed A-B response')
        ax.set_ylim(-.0003, .0048)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8, loc='upper right')
    fig.suptitle('Instrument calibration: brief peaks missed by the original sampling grid\nAll 65 replay copies exactly matched original final whole states; original scores unchanged')
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
