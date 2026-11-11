"""Plot saved results only; never loads or advances a subject."""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from analyze_fusion import paired


def main(work):
    a=json.loads((work/'analysis-v1.json').read_bytes())
    s=a['summary']
    contrasts=paired(a['rows'],'response_110ms')
    fig,axes=plt.subplots(1,2,figsize=(14,6),constrained_layout=True)
    cues=['X-low','X','Y','XY-total','XY-per','X-total']
    x=np.arange(len(cues))
    for arm,shift,color,label in [('normalized',-.18,'#2563eb','Normalized reception'),('summed',.18,'#d97706','Summed reception')]:
        means=[s['groups'][c][arm]['mean'] for c in cues]
        axes[0].bar(x+shift,means,.34,label=label,color=color,alpha=.8)
        for i,cue in enumerate(cues):
            vals=[contrasts[(origin,cue,arm)] for origin in s['origins']]
            axes[0].scatter(np.full(8,i+shift)+np.linspace(-.07,.07,8),vals,color=color,s=18,edgecolors='white',linewidths=.4)
    axes[0].set_xticks(x,['X .25','X .5','Y .5','XY .25 each','XY .5 each','X 1.0'],rotation=25,ha='right')
    axes[0].set_ylabel('Opposite-history contrast / 2 at 110 ms')
    axes[0].set_title('Equal total dose can have different effects')
    axes[0].legend(frameon=False,fontsize=9)
    for i,origin in enumerate(s['origins']):
        values=[s['prediction_errors'][model]['per_origin'][origin] for model in ['total-dose','receiver']]
        axes[1].plot([0,1],values,'o-',alpha=.8,label=origin)
    axes[1].set_xticks([0,1],['Total-dose approximation','Per-route threshold + receiver fusion'])
    axes[1].set_ylabel('Mean absolute error at 110 ms per origin')
    axes[1].set_title('Predictions saved before cues; no fitted parameters')
    axes[1].set_xlim(-.2,1.2)
    for ax in axes:
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.15)
        ax.ticklabel_format(axis='y',style='sci',scilimits=(-2,2))
    fig.suptitle('M2 receiver-fusion pilot | /5.1 S mode | 8 new origins, 448 nested causal copies\n15 s retention; teaching dose varied; fixed reader; exploratory results',fontsize=13)
    target=work/'figure-v1.png'
    if target.exists():raise FileExistsError('preserve previous figure')
    fig.savefig(target,dpi=140)
    print(target)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',type=Path,default=Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-fusion-v2'))
    main(parser.parse_args().work)
