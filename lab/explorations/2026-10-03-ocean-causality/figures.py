"""Small figures from measured summaries and targeted trajectories; no simulation."""
import gzip
import json
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiment import WORK,HERE
from lab.tools.ocean_cli import read_json

OUT=WORK/'figures';OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
COLORS={'core':'#18786b','random':'#ba7944','random-fast':'#7761a8'}


def save(fig,name):
    fig.tight_layout();fig.savefig(OUT/f'{name}.png',bbox_inches='tight');plt.close(fig)
    (HERE/'figures').mkdir(exist_ok=True);shutil.copy2(OUT/f'{name}.png',HERE/'figures'/f'{name}.png')


def ecology():
    fig,axes=plt.subplots(2,3,figsize=(12,6.4))
    for g in (0,1):
        for mode in COLORS:
            r=read_json(WORK/'cases'/f'g{g}-{mode}'/'process-summary.json');t=[x['time_s'] for x in r['series']]
            label={'core':'Core','random':'Random / 1 s','random-fast':'Random / 20 ms'}[mode]
            for j,k in enumerate(('food','alive','predations')):
                axes[g,j].plot(t,[x[k] for x in r['series']],label=label,color=COLORS[mode])
                axes[g,j].set_xlabel('Simulated seconds');axes[g,j].set_title(f'World {g+1}: '+{'food':'nutrients consumed','alive':'living bodies','predations':'captures completed'}[k])
        axes[g,0].legend()
    fig.suptitle('Fixed paired worlds: mutation and predation retained',y=1.025);save(fig,'ecology')


def process():
    folder=WORK/'probes/g0-core-200';traces={}
    with gzip.open(folder/'trajectories.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            x=json.loads(line)
            if x['individual']==10:traces[x['operation']]=x['trace']
    p=next(x['plan'] for x in read_json(folder/'summary.json')['individuals'] if x['individual']==10)
    base=traces['sham'];t=(np.array([x['time_us'] for x in base])-200000000)/1e6
    fig,axes=plt.subplots(3,1,figsize=(9,7.4),sharex=True)
    for name,color in (('target','#18786b'),('matched','#ba7944'),('release','#7761a8')):
        trace=traces[name]
        activity=[sum(dict(a['nodes']).get(n,0)-dict(b['nodes']).get(n,0) for n in p['targets']) for a,b in zip(base,trace)]
        motor=[np.abs(np.array(a['action'])-b['action']).max() for a,b in zip(base,trace)]
        axes[0].plot(t,activity,label=name,color=color);axes[1].plot(t,motor,color=color)
    a=next(x for x in read_json(folder/'process-analysis.json')['individuals'] if x['individual']==10)
    end=(a['first_direct_target_after_probe_us']-200000000)/1e6
    for ax in axes[:2]:ax.axvspan(0,end,color='#18786b',alpha=.08);ax.axvline(2,color='gray',lw=.7,ls='--')
    axes[0].set_ylabel('Target activation lost\n(sham minus intervention)');axes[0].legend()
    axes[1].set_ylabel('Largest motor difference')
    for name,color in (('experienced_birth','#18786b'),('blank_birth','#ba7944')):
        axes[2].plot(t,[x['action'][0] for x in traces[name]],label=name.replace('_',' '),color=color)
    axes[2].legend();axes[2].set_ylabel('Motor component 1');axes[2].set_xlabel('Seconds after intervention')
    axes[0].set_title('World 1, individual 10, 200 s: same actual sensory input\nShaded prefix: no selected target receives direct input; release at 2 s')
    save(fig,'causal-process')


def closed():
    fig,axes=plt.subplots(2,2,figsize=(11,6.5))
    palette={'sham':'#18786b','target':'#aa625e','matched':'#ba7944','history-strength-zero':'#7761a8','region':'#26609b','region-matched':'#555555'}
    for g in (0,1):
        for op,color in palette.items():
            r=read_json(WORK/'closed-loop'/f'g{g}-{op}'/'process-summary.json')
            axes[g,0].plot([x['time_s'] for x in r['series']],[x['food'] for x in r['series']],color=color,label=op)
        rows=read_json(WORK/'closed-loop'/f'g{g}-paired-process-v5.json')
        for r in rows:
            axes[g,1].plot([x['elapsed_s'] for x in r['series']],[None if x['position_mean_m'] is None else 1000*x['position_mean_m'] for x in r['series']],label=r['operation'],color=palette[r['operation']])
        axes[g,0].set_title(f'World {g+1}: new food after intervention');axes[g,1].set_title(f'World {g+1}: position difference from sham')
        axes[g,0].legend(fontsize=8);axes[g,1].set_ylabel('Mean distance, mm');axes[g,1].legend(fontsize=8)
        for ax in axes[g]:ax.set_xlabel('Seconds after 200 s checkpoint')
    save(fig,'closed-loop')

if __name__=='__main__':ecology();process();closed()
