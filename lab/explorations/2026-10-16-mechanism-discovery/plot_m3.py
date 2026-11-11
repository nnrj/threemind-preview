"""Plot saved C1 development results; no model loading or inference."""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('preserve previous figure')
    data = json.loads(args.analysis.read_bytes())
    x = np.arange(5)
    fig, ax = plt.subplots(figsize=(10.5, 5.2), constrained_layout=True)
    for offset, key, label, color in [(-.19, 'early', '0.1-0.3 s (prospective replay endpoint)', '#2877aa'),
                                     (.19, 'late', '0.5-1.5 s (secondary)', '#c17b2e')]:
        values = [r[key]['above_registered_threshold'] for r in data['systems']]
        bars = ax.bar(x+offset, values, .36, label=label, color=color)
        ax.bar_label(bars, labels=[f'{v}/8' for v in values], padding=3)
    ax.set_xticks(x, ['Reactive\n+ actuator filter', 'Finite-state\n8 ternary slots', 'Local\nHebbian', 'Fixed RNN\n+ personal reader', 'ThreeMind /5.1\narchived replay'])
    ax.set_ylim(0, 9.6)
    ax.set_yticks(range(0, 9, 2))
    ax.set_ylabel('Origins with positive cue-corrected history contrast > 0.0001')
    ax.set_title('M3-C1 development replay: one history-dependence component\nEight reused origin panels; other autonomy criteria were NOT tested')
    ax.legend(loc='upper right', fontsize=8)
    ax.spines[['top', 'right']].set_visible(False)
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
