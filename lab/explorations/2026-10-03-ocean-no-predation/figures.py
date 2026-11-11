import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiment import HERE,WORK,E32
from lab.tools.ocean_cli import read_json


def build():
    data=read_json(WORK/'findings.json')['cases']
    fig,axes=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
    for g in (0,1):
        for mode,color in (('core','#237964'),('random','#a177a1')):
            item=data.get(f'g{g}-{mode}')
            if item is None:continue
            t=item['trajectory']
            axes[g,0].step([r['time_s'] for r in t],[r['alive'] for r in t],where='post',label=mode,color=color)
            axes[g,1].plot([r['time_s'] for r in t],[r['food'] for r in t],label=mode,color=color)
        axes[g,0].axhline(97,color='#999999',linestyle=':',label='population cap')
        for j,title in enumerate(('Living bodies','Nutrients consumed')):
            axes[g,j].set_title(f'World {g+1}: {title}');axes[g,j].set_xlabel('Simulated seconds')
            axes[g,j].legend();axes[g,j].grid(alpha=.2)
    fig.suptitle('E33 · No mutual predation; complete habitat retained')
    (HERE/'figures').mkdir(exist_ok=True);fig.savefig(HERE/'figures/no-predation.png',dpi=145);plt.close(fig)


if __name__=='__main__':build()
