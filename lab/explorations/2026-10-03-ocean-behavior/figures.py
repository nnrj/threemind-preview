"""Scientific figures from completed result files, no simulation."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiment import WORK,HERE
from analyze import cases
from lab.tools.ocean_cli import read_json

LABELS={'intact':'Intact','replay':'Opposite-side replay','random':'Random','passive':'Passive',
        'target':'Target silenced','matched':'Matched silenced','all':'Existing edges silenced',
        'experienced':'Experienced birth','blank':'Blank birth','graft':'Target graft','graft-matched':'Matched graft'}


def generate():
    data=cases(recompute_contacts=False);out=HERE/'figures';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
    ops=['intact','replay','random','passive','target','matched','all']
    fig,axes=plt.subplots(1,3,figsize=(13,4.8))
    for ax,task,key,title in zip(axes,['food','hunt','escape'],['food','captured','physical'],
                                ['Food encounters (grains)','Weaker-neighbor captures','Stronger-neighbor survival']):
        values=[sum(r[key] for r in data if r['assay']['task']==task and r['assay']['operation']==op) for op in ops]
        ax.barh(range(len(ops)),values,color=['#287965','#76949a','#c59242','#bbb9ad','#a65352','#8b70a1','#516c7b'])
        ax.set_yticks(range(len(ops)),[LABELS[o] for o in ops]);ax.invert_yaxis();ax.set_title(title)
        for n,v in enumerate(values):ax.text(v+.1,n,str(v),va='center')
        ax.set_xlim(0,max(values+[1])*1.23);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('E31 | 8 donor bodies × 2 target sides per arm; nested in 2 source worlds')
    fig.tight_layout();fig.savefig(out/'behavior-outcomes.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4.8));donors=sorted({r['donor'] for r in data})
    table={}
    for op in ['experienced','blank','graft','graft-matched']:
        table[op]=[sum(r['food'] for r in data if r['donor']==d and r['assay']['task']=='transfer' and r['assay']['operation']==op) for d in donors]
    x=np.arange(len(donors))
    for n,op in enumerate(table):ax.bar(x+(n-1.5)*.19,table[op],.19,label=LABELS[op])
    ax.set_xticks(x,donors);ax.set_ylabel('Original individual grains, summed over two new worlds')
    ax.set_title('E31 | Persistent experience and grafts in unseen food distributions (90 s)')
    ax.legend(ncol=2,fontsize=9);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.tight_layout();fig.savefig(out/'transfer.png');plt.close(fig)
    process=read_json(WORK/'process-findings.json')
    fig,axes=plt.subplots(1,3,figsize=(12,4.4))
    for ax,task in zip(axes,['food','hunt','escape']):
        for j,op in enumerate(['target','matched','all','replay']):
            values=[r['windows']['0-20']['action_mae'] for r in process['interventions'] if r['task']==task and r['operation']==op]
            values=[v for v in values if v is not None]
            ax.scatter(np.full(len(values),j)+np.linspace(-.15,.15,len(values)),values,s=22,alpha=.7)
        ax.set_xticks(range(4),['Target','Matched','All old edges','Replay'],rotation=25);ax.set_title(task)
        ax.set_ylabel('Mean absolute action change vs intact');ax.grid(axis='y',alpha=.2)
    fig.suptitle('Same-clock living pairs; three actuator commands in [-1, 1]')
    fig.tight_layout();fig.savefig(out/'action-effects.png');plt.close(fig)
    print(json.dumps({'figures':[p.name for p in out.glob('*.png')]}))


if __name__=='__main__':generate()
