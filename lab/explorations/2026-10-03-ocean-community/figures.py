"""Descriptive figures from actual world frames; no re-simulation."""
import gzip
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiment import WORK,HERE
from analyze import rows
from lab.tools.ocean_cli import read_json

COLORS={'core':'#237964','random':'#a177a1','target':'#c25b47','matched':'#4d7da7',
        'experienced':'#237964','blank':'#8a8d8d','graft':'#c49933','graft-matched':'#9972a8'}


def ecology():
    fig,axes=plt.subplots(2,3,figsize=(13,7),constrained_layout=True)
    for g in (0,1):
        for mode in ('core','random'):
            folder=WORK/'cases'/f'g{g}-{mode}'
            if not (folder/'result.json').exists():continue
            series=[]
            for r in rows(folder/'trajectory.jsonl.gz'):
                series.append((r['time_us']/1e6,sum(b['grains'] for b in r['members']),
                    sum(b['physical'] for b in r['members']),r['totals']['predations']))
            final=read_json(folder/'result.json')
            series.append((final['time_us']/1e6,sum(b['grains'] for b in final['members']),
                sum(b['physical'] for b in final['members']),final['totals']['predations']))
            a=np.asarray(series)
            for j in range(3):axes[g,j].plot(a[:,0],a[:,j+1],label=mode,color=COLORS[mode])
        for j,title in enumerate(('Nutrients consumed','Living bodies','Bodies captured')):
            ax=axes[g,j];ax.set_title(f'World {g+1}: {title}');ax.set_xlabel('Simulated seconds');ax.grid(alpha=.18)
            if j==0:ax.legend()
    fig.suptitle('E32 · Complete habitat: 53 founders, 360 nutrients, random replenishment',fontsize=13)
    (HERE/'figures').mkdir(exist_ok=True);fig.savefig(HERE/'figures/ecology.png',dpi=145);plt.close(fig)


def focal():
    for group in (0,1):
        fig,axes=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
        for part,arms in enumerate((('core','target','matched'),('experienced','blank','graft','graft-matched'))):
            for op in arms:
                folder=WORK/'cases'/f'g{group}-{op}'
                if not (folder/'result.json').exists():continue
                trace=[r for r in rows(folder/'focal.jsonl.gz') if r['time_us']>=60000000]
                if not trace:continue
                t=np.array([(r['time_us']-60000000)/1e6 for r in trace]);a=np.array([r['action'] for r in trace])
                food=np.array([r['body']['grains']-trace[0]['body']['grains'] for r in trace])
                axes[0,part].plot(t,a[:,0],color=COLORS[op],label=op,alpha=.85)
                axes[1,part].step(t,food,color=COLORS[op],label=op,where='post')
        for row in axes:
            for ax in row:ax.set_xlabel('Seconds after branch');ax.grid(alpha=.18);ax.legend(fontsize=8)
        axes[0,0].set_title('Focal pathway silencing: forward command')
        axes[0,1].set_title('Paired births and grafts: forward command')
        if group==1:
            for ax in axes[0]:ax.set_xlim(0,4)
            axes[0,0].set_title('First 4 seconds: pathway silencing')
            axes[0,1].set_title('First 4 seconds: paired births and grafts')
        for ax in axes[1]:ax.set_ylabel('Additional nutrients')
        fig.suptitle(f'E32 · World {group+1}: focal changes inside the complete habitat')
        fig.savefig(HERE/f'figures/focal-g{group}.png',dpi=145);plt.close(fig)


if __name__=='__main__':ecology();focal()
