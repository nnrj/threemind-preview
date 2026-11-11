"""Static scientific summary of every completed, valid E60 comparison."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/eye-hand-learning-20261007'


def main():
    data = json.loads((HERE/'results.json').read_text(encoding='utf-8'))['cases']
    selected = json.loads((WORK/'selection.json').read_text(encoding='utf-8'))['model']
    new = 'C-fit-B-teach-shared-activity-fit2-E-correct-B-teach'+('-v2' if selected.endswith('-v2') else '')+'-val2'
    labels = []
    rows = []
    configurations = [
        ('Before correction', 'B-teach', selected, 'normal'),
        ('Core taught; old reader', 'E-correct-B-teach', selected, 'normal'),
        ('New reader; old Core', 'B-teach', new, 'normal'),
        ('Both taught', 'E-correct-B-teach', new, 'normal'),
        ('Output disconnected', 'E-correct-B-teach', new, 'empty'),
        ('Existing edges silenced', 'E-correct-B-teach', new, 'silence'),
        ('Edges restored', 'E-correct-B-teach', new, 'rescue'),
        ('Explicit sensory bypass', 'E-correct-B-teach', new.replace('-activity-', '-incoming-'), 'normal'),
    ]
    for label, source, model, mode in configurations:
        key = f'D-{source}-{model}-{mode}-brief-confirmation-world-B-teach'
        if key in data:
            labels.append(label); rows.append(data[key])
    if not rows: raise RuntimeError('confirmation results required')
    fig, axes = plt.subplots(1, 3, figsize=(15, max(4.8, len(rows)*.65)), layout='constrained')
    metrics = [('eye_requested', 'eye_center_fraction', 100, 'Target inside clear center (%)'),
               ('eye_requested', 'eye_stable_fraction', 100, 'Aligned AND low speed (%)'),
               ('hand_requested', 'hand_mean_distance_m', 1, 'Hand distance from target (m)')]
    colors = ['#276d69' if r['input_source']=='activity' else '#ae7a2c' for r in rows]
    for ax, (group, metric, scale, title) in zip(axes, metrics):
        values = [r[group][metric]*scale for r in rows]
        ax.barh(labels, values, color=colors); ax.invert_yaxis(); ax.set_title(title, fontsize=11)
        ax.grid(axis='x', alpha=.2); ax.set_axisbelow(True)
        for i, value in enumerate(values): ax.text(value, i, f' {value:.2f}', va='center', fontsize=9)
        ax.spines[['top', 'right']].set_visible(False); ax.margins(x=.2)
    fig.suptitle('E60 | same held-out layouts, six requested-movement trials per metric\n'
                 'Core dynamics unchanged; correction and fixed-reader interventions separated', fontsize=13)
    fig.supxlabel('Zero-command alignment came from already-aligned starts, with no entry from outside.\n'
                  'These are time fractions, not answer accuracy. Hand distance: lower is closer.', fontsize=10)
    path = WORK/'eye-hand-results.png'; fig.savefig(path, dpi=150); plt.close(fig)
    print(str(path.resolve()))


if __name__ == '__main__': main()
