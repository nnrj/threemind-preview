"""Read-only scientific summary of the frozen closure endpoints."""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main(work):
    a=json.loads((work/'analysis-v1.json').read_bytes())
    fig,axs=plt.subplots(1,3,figsize=(16,5.5),constrained_layout=True)
    arms=['sham','target-bundle','persistent','fast','matched-bundle']
    means=[np.mean([o['rates'][arm]['target'] for o in a['X1']['origins']])*100 for arm in arms]
    bars=axs[0].bar(range(5),means,color=['#94a3b8','#2563eb','#0d9488','#94a3b8','#94a3b8'])
    axs[0].bar_label(bars,fmt='%.1f%%',padding=4)
    axs[0].set_xticks(range(5),['Sham','Target\npackage','Persistent /\ntopology','Fast','Matched'])
    axs[0].set_ylim(0,110);axs[0].set_ylabel('Donor-consistent gate arrival (%)')
    axs[0].set_title('X1: behavioral transfer | '+a['X1']['verdict'])
    axs[0].text(.5,-.2,'8 origins; 48 nested target trials per arm\nUnrelated performance measured separately',
                ha='center',transform=axs[0].transAxes,fontsize=9)
    ds=['1','30','60','300'];xs=np.arange(4)
    cohorts=a['X2']['cohorts']
    axs[1].bar(xs-.17,[cohorts[d]['separation_count'] for d in ds],width=.34,label='Cue-dependent expression',color='#2563eb')
    axs[1].bar(xs+.17,[cohorts[d]['transient_count'] for d in ds],width=.34,label='Transient / sustained',color='#d97706')
    axs[1].axhline(6,ls=':',color='#475569',label='Frozen 6/8 pass rule')
    axs[1].set_xticks(xs,ds);axs[1].set_ylim(0,8.8);axs[1].set_xlabel('Retention delay (internal s)')
    axs[1].set_ylabel('Origins passing paired conditions (of 8)');axs[1].set_title('X2: separation goals')
    axs[1].legend(fontsize=8,frameon=False,loc='lower left')
    kinds=['reactive','finite-state','hebbian','fixed-rnn-reader','threemind']
    vals=np.array([a['X3']['systems'][k]['counts'] for k in kinds])
    axs[2].imshow(vals,vmin=0,vmax=8,cmap='Blues',aspect='auto')
    for i,k in enumerate(kinds):
        for j in range(4):
            verdict=a['X3']['systems'][k]['verdicts'][j]
            axs[2].text(j,i,f'{vals[i,j]}/8\n{verdict}',ha='center',va='center',fontsize=8,
                        color='white' if vals[i,j]>4 else '#111827')
    axs[2].set_xticks(range(4),['C1\nhistory','C2\ncausal','C3\ninteraction','C4\nreshaping'])
    axs[2].set_yticks(range(5),['Reactive','Finite-state','Hebbian','RNN + reader','ThreeMind /5.1'])
    axs[2].set_title('X3: all four criteria, separately judged')
    fig.suptitle('Frozen goals, explicit verdicts | closure-v1 | 16 October2026',fontsize=14)
    target=work/'figure-v1.png'
    if target.exists():raise FileExistsError(target)
    fig.savefig(target,dpi=160)
    print(target)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    main(p.parse_args().work)
