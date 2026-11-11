"""Plot completed R46a measurements and declared pass counts, without simulation."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')


def main():
    data=json.loads((WORK/'analysis-v1.json').read_text('utf-8'))
    assert json.loads((WORK/'independent-audit-v1.json').read_text('utf-8'))['passed']
    output=WORK/'figures';output.mkdir(exist_ok=True)
    conditions=data['conditions'];labels=['Exp / on','Exp / off','Log / on','Log / off','Power / on','Power / off']
    colors=['#3366AA','#99BADD']*3
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','pdf.fonttype':42})
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    measures=[('strong','survives','A. Strong exposure: connections retained at 300 s'),
        ('spaced','survives','B. Spaced teaching: connections retained at 300 s'),
        ('weak','forgotten','C. Weak exposure: connections absent at 300 s')]
    for ax,(course,field,title) in zip(axes.flat,measures):
        bars=ax.bar(labels,[c['counts'][course][field] for c in conditions],color=colors)
        ax.bar_label(bars);ax.set_title(title,loc='left');ax.set_ylim(0,9);ax.set_yticks(range(9))
        ax.set_ylabel('Independent origins (N = 8)');ax.axhline(6,color='#333333',ls='--',lw=1)
        ax.tick_params(axis='x',rotation=20)
    ax=axes[1,1];x=np.arange(6)
    for offset,course,color in [(-.18,'strong','#BB6633'),(.18,'spaced','#448855')]:
        bars=ax.bar(x+offset,[c['counts'][course]['process'] for c in conditions],.36,label=course,color=color)
        ax.bar_label(bars)
    ax.set_xticks(x,labels,rotation=20);ax.set_ylim(0,9);ax.set_yticks(range(9));ax.axhline(6,color='#333333',ls='--',lw=1)
    ax.set_title('D. History-dependent temporal response retained at 300 s',loc='left');ax.set_ylabel('Independent origins (N = 8)');ax.legend()
    fig.suptitle('Three decay curves with original linear timescale relaxation on or off')
    for extension in ('png','svg','pdf'):fig.savefig(output/f'assay-outcomes.{extension}',dpi=190)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    for condition,label,color in zip(conditions,labels,colors):
        rows=[r for r in data['rows'] if r['case']['curve']==condition['curve'] and r['case']['relaxation']==condition['relaxation']]
        axes[0].bar(label,sum(r['wall_seconds'] for r in rows)/len(rows),color=color)
        axes[1].bar(label,max(r['contributions'] for r in rows),color=color)
    axes[0].set_ylabel('Mean wall seconds per complete sequence')
    axes[1].set_ylabel('Maximum saved decay contributions per subject')
    for ax in axes:ax.tick_params(axis='x',rotation=20)
    fig.suptitle('Observed computational cost; individual sequences remain nested observations')
    for extension in ('png','svg','pdf'):fig.savefig(output/f'assay-cost.{extension}',dpi=190)
    plt.close(fig)


if __name__=='__main__':main()
