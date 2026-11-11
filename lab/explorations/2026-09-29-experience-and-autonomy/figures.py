"""Scientific figures from saved results only."""
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from common import ROOT,WORK,read_json

def save(fig,name):
    fig.tight_layout()
    path=WORK/(name+'.png');fig.savefig(path,dpi=160,bbox_inches='tight');plt.close(fig)
    shutil.copy2(path,ROOT/'docs/images'/f'experience-autonomy-{name}-2026-09-29.png')

def main():
    local=read_json(WORK/'local-analysis.json')['rows'];parents=list(dict.fromkeys(r['parent'] for r in local))
    fig,ax=plt.subplots(figsize=(11,4.5))
    for i,(cond,color,label) in enumerate(zip(('normal','task_edges','matched_edges','returns','restore'),
            ('#238776','#c65c51','#ddaa44','#648bc0','#9468a7'),
            ('Intact','Task edges silenced','Matched edges silenced','Returns to cue silenced','Task edges restored'))):
        ax.bar(np.arange(4)+(i-2)*.15,[next(r for r in local if r['parent']==p and r['condition']==cond)['history_motor'] for p in parents],
               .14,color=color,label=label)
    ax.axhline(0,color='gray',lw=.5);ax.set_xticks(range(4),['W1/G0','W1/G1','W2/G0','W2/G1'])
    ax.set_ylabel('Experience-dependent action (control x s)');ax.set_title('Specific learned routes carry the behavioral difference')
    ax.legend(fontsize=8,ncol=3);save(fig,'pathways')

    memory=read_json(WORK/'memory-analysis.json')
    protocols=('single_high','single_ordinary','massed_ordinary','spaced_ordinary','massed_weak','spaced_weak')
    labels=('Single strong','Single ordinary','Massed ordinary','Spaced ordinary','Massed weak','Spaced weak')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),sharex=True)
    for ax,seed in zip(axes,(9293201,9293202)):
        for p,label in zip(protocols,labels):
            data=[r for r in memory if r['seed']==seed and r['protocol']==p and r['mode']=='live']
            ax.plot([r['age_s'] for r in data],[r['training_effect']['motor'] for r in data],marker='o',label=label)
        ax.set_xscale('log');ax.set_xticks([1,30,300],['1','30','300']);ax.axhline(0,color='gray',lw=.5)
        ax.set_title(f'Wiring {seed}');ax.set_xlabel('Seconds since final training');ax.set_ylabel('Training-dependent action (control x s)')
    axes[0].legend(fontsize=8);fig.suptitle('Equal final-stimulus age; ongoing identical background; normal forgetting')
    save(fig,'retention')

    seq=read_json(WORK/'sequence-analysis.json');env=read_json(WORK/'environment-analysis.json')['rows']
    fig,axes=plt.subplots(1,2,figsize=(12,4.4))
    for i,(hist,col) in enumerate((('P','#238776'),('Q','#648bc0'))):
        axes[0].bar(np.arange(4)+(i-.5)*.32,[next(r for r in seq if r['parent']==p and r['history']==hist)['communication_effect'] for p in parents],.3,label=hist,color=col)
    for i,(route,col) in enumerate((('PQP','#238776'),('QPQ','#648bc0'))):
        axes[1].bar(np.arange(4)+(i-.5)*.32,[next(r for r in env if r['parent']==p and r['changed']==route and r['phase']==2 and r['mode']=='live')['history_effect']['motor'] for p in parents],.3,label=route+' vs constant',color=col)
    for ax in axes:
        ax.axhline(0,color='gray',lw=.5);ax.set_xticks(range(4),['W1/G0','W1/G1','W2/G0','W2/G1']);ax.legend(fontsize=8)
        ax.set_ylabel('Integrated action difference (control x s)')
    axes[0].set_title('Earlier input changes the next response\nInternal-communication contribution')
    axes[1].set_title('A changed environment reshapes one individual\nIdentical test input and starting body')
    save(fig,'adaptation')

    novel=read_json(WORK/'novelty-analysis.json')['variability']
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,seed in zip(axes,(9293201,9293202)):
        for cond,color in zip(('intact','erase','matched_erase','novelty_off'),('#238776','#c65c51','#ddaa44','#648bc0')):
            r=next(r for r in novel if r['seed']==seed and r['condition']==cond)
            ax.plot([0,1,2,4],r['fixed_motor_series'],marker='o',label=cond.replace('_',' '),color=color)
        ax.set_xticks([0,1,2,4]);ax.set_xlabel('Features replaced in the training texture');ax.set_title(f'Wiring {seed}')
        ax.set_ylabel('Response to the SAME original test texture');ax.axhline(0,color='gray',lw=.5);ax.legend(fontsize=8)
    save(fig,'erasure')

if __name__=='__main__':main()
