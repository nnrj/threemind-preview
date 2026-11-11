"""Unchanged scientific panels; operational costs split by implementation."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')

def read(path):return json.loads(path.read_text('utf-8'))

def main():
    data=read(WORK/'analysis-v1.json');cost=read(WORK/'operational-cost-v1.json')
    assert read(WORK/'independent-audit-v1.json')['passed']
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=1920)
    output=WORK/'figures';output.mkdir(exist_ok=True)
    assert not list(output.glob('assay-*.png')),'preserve an existing rendered version'
    conditions=data['conditions']
    labels=['Exp / on','Exp / off','Log / on','Log / off','Power / on','Power / off']
    colors=['#3366AA','#99BADD']*3
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','pdf.fonttype':42})
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    measures=[('strong','survives','A. Higher dose (1.0): connections retained at 300 s'),
        ('spaced','survives','B. Spaced teaching: connections retained at 300 s'),
        ('weak','forgotten','C. Weak exposure: connections absent at 300 s')]
    for ax,(course,field,title) in zip(axes.flat,measures):
        bars=ax.bar(labels,[c['counts'][course][field] for c in conditions],color=colors)
        ax.bar_label(bars);ax.set_title(title,loc='left');ax.set_ylim(0,9);ax.set_yticks(range(9))
        ax.set_ylabel('Birth-seed repetitions (8)');ax.axhline(6,color='#333333',ls='--',lw=1)
        ax.tick_params(axis='x',rotation=20)
    ax=axes[1,1];x=np.arange(6)
    for offset,course,color in [(-.18,'strong','#BB6633'),(.18,'spaced','#448855')]:
        bars=ax.bar(x+offset,[c['counts'][course]['process'] for c in conditions],.36,label=('higher dose (1.0)' if course=='strong' else course),color=color)
        ax.bar_label(bars)
    ax.set_xticks(x,labels,rotation=20);ax.set_ylim(0,9);ax.set_yticks(range(9));ax.axhline(6,color='#333333',ls='--',lw=1)
    ax.set_title('D. History-dependent temporal response retained at 300 s',loc='left')
    ax.set_ylabel('Birth-seed repetitions (8)');ax.legend()
    fig.suptitle('Three decay curves with original linear timescale relaxation on or off')
    for ext in ('png','svg','pdf'):fig.savefig(output/f'assay-outcomes.{ext}',dpi=190)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5.2),constrained_layout=True)
    for offset,method,color,label in [(-.18,'original-frozen','#999999','Original implementation'),
            (.18,'exact-acceleration-v2','#3366AA','Exact scoped acceleration')]:
        selected={(r['curve'],r['relaxation']):r for r in cost['conditions'] if r['implementation']==method}
        values=[selected.get((c['curve'],c['relaxation']),{}).get('mean_wall_seconds',np.nan) for c in conditions]
        bars=axes[0].bar(x+offset,values,.36,color=color,label=label)
        axes[0].bar_label(bars,labels=[str(selected[c['curve'],c['relaxation']]['sequences'])
            if (c['curve'],c['relaxation']) in selected else '' for c in conditions],fontsize=8)
    axes[0].set_xticks(x,labels,rotation=20);axes[0].legend(fontsize=8)
    axes[0].set_ylabel('Observed mean operation seconds / sequence')
    axes[0].set_title('A. Implementation strata; labels are sequence counts',loc='left',fontsize=10)
    for condition,label,color in zip(conditions,labels,colors):
        rows=[r for r in data['rows'] if r['case']['curve']==condition['curve'] and r['case']['relaxation']==condition['relaxation']]
        axes[1].bar(label,max(r['contributions'] for r in rows),color=color)
    axes[1].tick_params(axis='x',rotation=20)
    axes[1].set_ylabel('Maximum saved contributions per complete subject')
    axes[1].set_title('B. Stored contribution count',loc='left',fontsize=10)
    fig.suptitle('Operational observations; timing strata differ in origin and course composition\nNo randomized implementation-speed comparison',fontsize=12)
    for ext in ('png','svg','pdf'):fig.savefig(output/f'assay-cost-by-implementation.{ext}',dpi=190)
    plt.close(fig)
    with (output/'render-revision.json').open('x',encoding='utf-8') as f:
        json.dump(dict(revision=2,reason='Separate original and exact-acceleration timings; scientific panels unchanged.'),f)

if __name__=='__main__':main()
