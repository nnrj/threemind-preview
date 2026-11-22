"""Read audited R51t4 records and produce descriptive tables and figures only."""
import argparse
from collections import Counter
import json
import lzma
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(path):
    return json.loads(path.read_text('utf8'))


def produce(work):
    assert read(work / 'audit.json')['passed']
    a = read(work / 'analysis.json')
    assert a['counts']['systems'] == 64
    rows = a['answers']
    profiles = ('reference', 'short-inhibition', 'prefix-candidate', 'no-inhibition')
    tasks = ('pair', 'prefix')
    categories = ('short', 'long', 'distractor', 'blank')
    aggregate = []
    for task in tasks:
        for profile in profiles:
            rr = [r for r in rows if r['task'] == task and r['profile'] == profile]
            row = {'task': task, 'profile': profile}
            for category in categories:
                cc = [r for r in rr if r['category'] == category]
                row[category] = {
                    'correct': sum(r['correct'] for r in cc), 'total': len(cc),
                    'choices': dict(Counter(r['choice'] for r in cc)),
                    'expected_and_choice': dict(Counter(str(r['expected']) + '->' + r['choice'] for r in cc)),
                }
            row['saturation_fraction'] = sum(r['saturated'] for r in rr) / sum(r['observations'] for r in rr)
            row['prefix_recovered_blocks'] = sum(
                b['prefix_recovery'] for b in a['blocks'] if b['task'] == task and b['profile'] == profile)
            aggregate.append(row)
    result = {
        'description': 'Descriptive aggregation of the audited, unchanged preregistered scores.',
        'independent_material_blocks': 4, 'systems': 64, 'final_questions': len(rows),
        'aggregate': aggregate, 'benefits': a['benefits'],
        'selected_trace_rule': 'block 0, swap 0, clean 30-second A and D tests; selection does not depend on score',
    }
    dest = work / 'report-numbers.json'
    if dest.exists():
        assert read(dest) == result, 'Never replace an existing numerical analysis'
    else:
        dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

    labels = ('Reference', 'Faster inhibition\ndecay', 'Immediate novelty;\nno inhibitory strengthening', 'Inhibition off')
    colors = ('#56708c', '#127d78', '#b87918', '#a34e5b')
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.5), layout='constrained')
    for ax, task in zip(axes, tasks):
        for pi, profile in enumerate(profiles):
            rr = next(r for r in aggregate if r['task'] == task and r['profile'] == profile)
            values = [rr[cat]['correct'] / rr[cat]['total'] * 100 for cat in categories]
            x = [ci + (pi - 1.5) * .2 for ci in range(4)]
            ax.bar(x, values, width=.19, color=colors[pi], label=labels[pi])
            for xx, value, cat in zip(x, values, categories):
                ax.text(xx, value + 1, str(rr[cat]['correct']) + '/' + str(rr[cat]['total']),
                        ha='center', va='bottom', fontsize=6.5, rotation=90)
        ax.set_xticks(range(4), ('Short delay', 'Long delay', 'Distractor', 'Blank: WAIT'))
        ax.set_ylim(0, 121)
        ax.set_yticks((0, 25, 50, 75, 100))
        ax.set_ylabel('Correct answers (%)')
        ax.set_title('Paired associations' if task == 'pair' else 'Shared-middle sequences')
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
    handles, legend_labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, legend_labels, fontsize=8, loc='upper center',
               bbox_to_anchor=(.5, -.01), ncol=4, frameon=False)
    figures = work / 'figures'
    figures.mkdir(exist_ok=True)
    for ext in ('png', 'svg', 'pdf'):
        fig.savefig(figures / ('delayed-choice.' + ext), dpi=180, bbox_inches='tight')
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11.8, 7.2), layout='constrained')
    tokens = {'C': 6969, 'E': 1925}
    for ti, task in enumerate(tasks):
        for ci, cue in enumerate(('A', 'D')):
            ax = axes[ti, ci]
            for pi, profile in enumerate(profiles):
                r = next(r for r in rows if r['block'] == 0 and r['swap'] == 0 and r['task'] == task
                         and r['profile'] == profile and r['cue'] == cue and r['delay'] == 30 and not r['distractor'])
                folder = work / 'cases' / r['key'] / f"04-final{r['question_index']:02d}"
                pr = read(folder / 'result.json')
                points = json.loads(lzma.decompress((folder / 'trajectory.json.xz').read_bytes()))
                mask = (r['seed'] * 2654435761) & 0xffffffff
                ids = {k: v ^ mask for k, v in tokens.items()}
                origin = pr['begin_us'] + (3000000 if task == 'prefix' else 2000000)
                points = [p for p in points if p['time_us'] >= origin]
                t = [(p['time_us'] - origin) / 1e6 for p in points]
                delta = [next((n['activation'] for n in p['nodes'] if n['channel'] == ids['C']), 0.)
                         - next((n['activation'] for n in p['nodes'] if n['channel'] == ids['E']), 0.) for p in points]
                ax.plot(t, delta, color=colors[pi], linewidth=1.1, label=labels[pi])
            ax.axhline(0, color='black', lw=.7)
            ax.set_title(('Paired' if task == 'pair' else 'Prefix') + ': ' + cue + ('-B' if task == 'prefix' else ''))
            ax.set_xlabel('Time since the final cue (s)')
            ax.set_ylabel('C activation minus E activation')
            ax.grid(alpha=.18)
    axes[0, 0].legend(fontsize=7)
    for ext in ('png', 'svg', 'pdf'):
        fig.savefig(figures / ('choice-processes.' + ext), dpi=180)
    plt.close(fig)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, required=True)
    produce(p.parse_args().work)
