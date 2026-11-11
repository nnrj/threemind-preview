"""Plot recorded E58 results; no model calls or hidden score transformations."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parent


def main():
    result=json.loads((HERE/'results.json').read_bytes());c=result['cases']
    fig,axes=plt.subplots(2,2,figsize=(13,8))
    fig.suptitle('E58 | Memory, movement feedback, and a whole-scene eye',fontsize=16)
    b=c.get('B-feedback',{}).get('conditions',{})
    labels=['Reference','Self vision','Body feedback','Both']
    axes[0,0].bar(labels,[b[k]['activation_integral'] for k in ('v0b0','v1b0','v0b1','v1b1')],color='#178075')
    axes[0,0].set_title('Movement feedback: 6 simulated seconds')
    axes[0,0].set_ylabel('Activation integral (raw recorded units)')
    selected=[('Old reader','C-s223-p1-d6-frozen'),('Recalibrated','C-s223-p1-d6-refit-saved-layout'),
              ('Edges silent','C-s223-d6-silence-score'),('Restored','C-s223-d6-rescue-score'),
              ('Teacher swap','C-s223-d6-teacher-swap-score')]
    selected=[(label,c[key]['correct']) for label,key in selected if key in c]
    axes[0,1].bar([r[0] for r in selected],[r[1] for r in selected],color='#178075')
    axes[0,1].axhline(16,color='#a96a23',ls='--',label='Identical-input, no-history ceiling')
    axes[0,1].set_ylim(0,36);axes[0,1].set_title('Memory causation: seed 223, common tail + 6 s')
    axes[0,1].set_ylabel('Correct / 32 (paired, not independent trials)');axes[0,1].tick_params(axis='x',rotation=15)
    axes[0,1].legend(fontsize=8,loc='upper right')
    axes[0,1].text(.02,.83,'Second environment: recalibrated test 14/32',fontsize=9,transform=axes[0,1].transAxes)
    for kind,color in [('activity','#178075'),('incoming','#a96a23')]:
        d=c.get('D-'+kind)
        if d:
            axes[1,0].plot([0,4,16],[d['frozen_new_correct']]+[r['new_correct'] for r in d['conditions']],'-o',color=color,label=kind)
    axes[1,0].set(xlabel='New supervised examples to external reader (+ 8 old)',ylabel='New mapping correct / 16',ylim=(0,17),title='Adaptation to a previously unseen mapping')
    if axes[1,0].lines:axes[1,0].legend()
    for index,kind in enumerate(('activity','incoming')):
        a=c.get('A-fit-'+kind)
        if a:
            x=[i-.18+.36*index for i in range(3)];color=('#178075','#a96a23')[index]
            arrived=[result['physical_pointing'][kind][cat]['arrived_within_0_20m'] for cat in ('color','shape','pair')]
            residual=[a['categories'][cat]-n for cat,n in zip(('color','shape','pair'),arrived)]
            axes[1,1].bar(x,arrived,width=.36,color=color,label=kind)
            axes[1,1].bar(x,residual,width=.36,bottom=arrived,color=color,alpha=.3)
    axes[1,1].set_xticks(range(3),['Color','Shape','Combination']);axes[1,1].set(ylim=(0,8.7),ylabel='Trials / 8',title='Single eye: solid = arrived; pale = nearest only')
    if axes[1,1].patches:axes[1,1].legend()
    else:axes[1,1].text(.5,.5,'No completed pointing evaluation',ha='center',transform=axes[1,1].transAxes)
    for ax in axes.ravel():
        ax.spines[['top','right']].set_visible(False);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.15)
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(HERE/'summary.png',dpi=150);plt.close(fig)


if __name__=='__main__':main()
