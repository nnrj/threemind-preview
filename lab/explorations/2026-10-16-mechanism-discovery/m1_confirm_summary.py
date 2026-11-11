"""Read-only M1 confirmation counts, figure and file allocation inventory."""
import argparse
import gzip
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import m1_confirm_spec as spec
import pilot_m2 as m
from m5_confirm_summary import inventory


def build(work):
    analysis = m.read(work/'analysis-v1.json')
    results = [m.read(work/'units'/f'o{i}'/'result.json') for i in range(spec.N)]
    tables = {}
    for arm in spec.ARMS:
        tables[arm] = {}
        for domain, cues in [('target', spec.CUES[:5]), ('unrelated', spec.CUES[5:]), ('novel-target', ('XN', 'YN'))]:
            rows = [t for r in results for t in r['trials'] if t['arm'] == arm and t['cue'] in cues]
            tables[arm][domain] = {e: {'correct':sum(t[e] for t in rows), 'n':len(rows)}
                                   for e in ('success', 'final_success')}
    scale = []
    for i in range(spec.N):
        parent = json.loads(gzip.decompress((work/'units'/f'o{i}'/'parent-h0.json.gz').read_bytes()))
        end = json.loads(gzip.decompress((work/'units'/f'o{i}'/'h0-target-bundle-X-final.json.gz').read_bytes()))
        scale.append({'origin':i, 'parent_seconds':parent['time_us']/1e6, 'final_seconds':end['time_us']/1e6,
                      'parent_nodes':len(parent['model']['nodes']), 'parent_edges':len(parent['model']['edges']),
                      'end_nodes':len(end['model']['nodes']), 'end_edges':len(end['model']['edges'])})
    strata = []
    for dose in (.38, .42, .46):
        for delay in (2, 5):
            rows = [u for u in analysis['units'] if u['case']['teaching_dose'] == dose and u['case']['delay_s'] == delay]
            assert len(rows) == 8
            strata.append({'dose':dose, 'delay_s':delay, 'n':8, 'qualifying':sum(u['qualified'] for u in rows),
                           'mean_joint_gain':statistics.mean(u['joint_gain'] for u in rows)})
    matching = [v for r in results for v in r['matching'].values()]
    return {'schema':'threemind.m1-confirmation-summary/1', 'independent_origins':spec.N,
            'tables':tables, 'strata':strata, 'scale':scale,
            'max_matching_residuals':{'weight':max(abs(v['weight_residual']) for v in matching),
                                      'activity':max(abs(v['teaching_activity_residual']) for v in matching)},
            'restore_max_error':max(u['restoration_rate_error'] for u in analysis['units']),
            'maximum_unrelated_loss':max(u['unrelated_loss'] for u in analysis['units']),
            'nested_observations':True, 'scope':'Same-origin declared counterfactual histories, fixed interface and fixed readout.'}


def figure(summary, path):
    if path.exists():raise FileExistsError(path)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    labels = ['Intact', 'Sham', 'Target\nbundle', 'Matched\nbundle', 'Persistent\npackage', 'Fast\npackage', 'Restored']
    xs = np.arange(7)
    for ax, endpoint, title in zip(axes, ('success','final_success'), ('First choice, 110 ms', 'Final gate after action-dependent feedback')):
        for j, domain in enumerate(('target', 'unrelated')):
            rows = [summary['tables'][a][domain][endpoint] for a in spec.ARMS]
            bars = ax.bar(xs+(j-.5)*.38, [100*r['correct']/r['n'] for r in rows], .38,
                          color=('#2563eb','#e87924')[j], label=('Donor target', 'Recipient unrelated')[j])
            for b, r in zip(bars, rows):
                h = b.get_height()
                ax.text(b.get_x()+b.get_width()/2, h-3 if h else 2, f"{r['correct']}/{r['n']}",
                        rotation=90, ha='center', va='top' if h else 'bottom', fontsize=8,
                        color='white' if h else 'black')
        ax.set_xticks(xs, labels, fontsize=8);ax.set_ylim(0, 122);ax.set_ylabel('Correct choices (%)')
        ax.set_title(title, fontsize=11);ax.legend(loc='upper center', ncol=2, fontsize=8)
    fig.suptitle('M1 confirmation | 48 new origins | fixed reader | seven intervention arms')
    fig.savefig(path, dpi=160);plt.close(fig)


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('--work', type=Path, required=True);work = p.parse_args().work
    assert m.read(work/'audit-v1.json')['passed'] and m.read(work/'status.json')['completed'] == spec.N
    summary = build(work);m.original(work/'summary-v1.json', summary)
    figure(summary, work/'figure-v1.png')
    disk = inventory(work);m.original(work/'storage-inventory-v1.json', disk)
    print(json.dumps({'tables':summary['tables'], 'matching':summary['max_matching_residuals'], 'storage':disk}))
