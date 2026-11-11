"""Plot actual fractions, not a positive-only selection of questions."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent


def main():
    data = json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    colors = {'feedback': '#178474', 'no-feedback': '#b88045', 'no-core-learning': '#568cad'}
    names = {'feedback': 'Joint + self-hearing', 'no-feedback': 'Joint, no self-hearing',
             'no-core-learning': 'Core learning off'}
    for arm, color in colors.items():
        for seed in (223, 279):
            totals = []
            for stage in (0, 1, 2):
                rows = [r for r in data['tests'] if (r['arm'], r['seed'], r['stage']) == (arm, seed, stage) and r['item'] >= 0]
                totals.append(sum(r['output'] == r['target'] for r in rows)/len(rows) if rows else float('nan'))
            axes[0].plot(range(3), totals, marker='o', color=color, linestyle='-' if seed == 223 else '--',
                         label=names[arm] if seed == 223 else None)
    axes[0].plot(range(3), [.5, .25, .25], color='#555', linestyle=':', label='Uniform-name reference')
    axes[0].set_xticks(range(3), ['2 objects', '+2 objects', 'Rename first 2'])
    axes[0].set_title('Held-out questions\n223: solid; 279: dashed')
    axes[0].legend(fontsize=8)
    labels, values, counts = [], [], []
    for row in data['linear_transcription']:
        test = row['heard_tests']
        for field, name in (('transformer_output', 'Transformer'), ('output', 'Linear')):
            correct = sum(r[field] == r['target'] for r in test)
            labels.append(f"{row['seed']}: {name}")
            values.append(correct/len(test))
            counts.append(f'{correct}/{len(test)}')
    axes[1].bar(range(len(values)), values, color=['#b88045', '#178474']*2)
    axes[1].set_xticks(range(len(values)), labels, rotation=35, ha='right')
    axes[1].set_title('Actually heard word, withheld intensity')
    for i, (v, count) in enumerate(zip(values, counts)):
        axes[1].text(i, v+.03, count, ha='center', fontsize=9)
    rows = data.get('aligned_tests', [])
    if rows:
        labels, values, counts = [], [], []
        for seed in (223, 279):
            group = [r for r in rows if r['seed'] == seed]
            if not group:
                continue
            for field, name in (('original_output', 'Before'), ('output', 'Recalibrated')):
                correct = sum(r[field] == r['target'] for r in group)
                labels.append(f'{seed}: {name}')
                values.append(correct/len(group))
                counts.append(f'{correct}/{len(group)}')
        axes[2].bar(range(len(values)), values, color=['#b88045', '#568cad']*2)
        axes[2].set_xticks(range(len(values)), labels, rotation=35, ha='right')
        for i, (v, count) in enumerate(zip(values, counts)):
            axes[2].text(i, v+.03, count, ha='center', fontsize=9)
    else:
        axes[2].text(.5, .5, 'Selective pathway interventions\nnot expanded without reliable naming',
                     ha='center', va='center', transform=axes[2].transAxes)
    axes[2].set_title('Same-checkpoint calibration diagnostic')
    for ax in axes:
        ax.set_ylim(0, 1.15)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('Correct fraction (not independent subjects)')
    fig.suptitle('E52: training fit is separate from translating later activity')
    fig.tight_layout()
    fig.savefig(HERE/'outcomes.png', dpi=150)


if __name__ == '__main__':
    main()
