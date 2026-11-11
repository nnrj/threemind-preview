"""Actual prospective encounter traces; no simplified demonstration habitat."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from experiment import HERE,WORK
from analyze import compressed
from lab.tools.ocean_cli import read_json


def build():
    sources=read_json(WORK/'findings.json')['sources'];n=len(sources)
    fig,axes=plt.subplots(n,2,figsize=(12,max(3,2.5*n)),squeeze=False,constrained_layout=True)
    for row,(key,source) in enumerate(sources.items()):
        for op,color in (('intact','#237964'),('target','#b25249'),('matched','#80719a')):
            if op not in source['arms']:continue
            trace=compressed(WORK/'cases'/f'{key}-{op}'/'trajectory.json.gz')
            valid=[r for r in trace if r['physical'] and r['gap'] is not None]
            axes[row,0].plot([r['t'] for r in valid],[r['gap']*1000 for r in valid],label=op,color=color)
            axes[row,1].plot([r['t'] for r in valid],[r['toward_action'] for r in valid],label=op,color=color,alpha=.8)
        axes[row,0].axhline(.8,color='#999',linestyle=':')
        axes[row,0].set_ylabel('Surface gap (mm)');axes[row,1].set_ylabel('Command toward counterpart')
        for ax in axes[row]:
            ax.set_title(f'{key}: {source["focal"]} toward {source["target"]}')
            ax.set_xlabel('Seconds after whole-world fork');ax.grid(alpha=.2);ax.legend()
    fig.suptitle('E34: pathway effects during natural encounters')
    (HERE/'figures').mkdir(exist_ok=True);fig.savefig(HERE/'figures/encounters.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),constrained_layout=True)
    x=np.arange(len(sources));width=.22
    for offset,op,color in ((-1,'blank','#a67c50'),(0,'graft','#237964'),(1,'graft-matched','#80719a')):
        distances=[]
        for source in sources.values():
            c=source['comparisons'];base=c['experienced vs blank']['20']['mae']
            distances.append(c['experienced vs '+op]['20']['mae']/base if base else np.nan)
        axes[0].bar(x+offset*width,distances,width,label=op,color=color)
    axes[0].axhline(1,color='#555',linestyle=':');axes[0].set_ylabel('Action difference from experienced / blank baseline')
    axes[0].set_title('Smaller = closer to the experienced action pattern')
    for offset,op,color in ((-1.5,'experienced','#365f80'),(-.5,'blank','#a67c50'),(.5,'graft','#237964'),(1.5,'graft-matched','#80719a')):
        axes[1].bar(x+offset*.18,[s['arms'][op]['captured'] for s in sources.values()],.18,label=op,color=color)
    axes[1].set_ylabel('New captures in 20 simulated seconds');axes[1].set_title('All captures, not only the selected counterpart')
    for ax in axes:
        ax.set_xticks(x,[f'{k}\nbody {s["focal"]}' for k,s in sources.items()]);ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
    fig.suptitle('E34: transferring action patterns and actual capture outcomes')
    fig.savefig(HERE/'figures/graft-effects.png',dpi=140);plt.close(fig)


if __name__=='__main__':build()
