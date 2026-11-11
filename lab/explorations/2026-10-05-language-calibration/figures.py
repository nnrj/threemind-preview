"""Scientific summary plots, generated only from frozen E45 results."""
from collections import defaultdict

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from experiment import HERE, read_json


def main():
    result=read_json(HERE/'results.json')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,3,figsize=(16,9),layout='constrained')
    a=axes.flat[0]
    rank=result['input_selection']['rank']
    labels=[r['route'].replace('stream-','').replace('text-','text\n') for r in rank]
    a.barh(labels,[r['correct']/r['count'] for r in rank],color='#287b72');a.invert_yaxis();a.set_xlim(0,1)
    a.set(title='A  Equal-dose input calibration',xlabel='Joint correct fraction (2 calibration seeds)')
    for i,r in enumerate(rank):a.text(r['correct']/r['count']+0.015,i,f"{r['correct']}/{r['count']}",va='center')
    a=axes.flat[1];rank=result['parameter_selection']['rank']
    a.barh([r['parameter'] for r in rank],[r['correct']/r['count'] for r in rank],color='#498eb5');a.invert_yaxis();a.set_xlim(0,1)
    a.set(title='B  Existing-parameter calibration',xlabel='Joint correct fraction (same calibration seeds)')
    for i,r in enumerate(rank):a.text(r['correct']/r['count']+0.015,i,f"{r['correct']}/{r['count']}",va='center')
    for axis,direction,title in ((axes.flat[2],'vision','C  Word cue: exact object retrieval'),(axes.flat[3],'words','D  Visual cue: exact taught-name retrieval')):
        groups=defaultdict(list)
        for r in result['formal']['pairs']:
            if r['direction']==direction:groups[(r['parameter'],r['seconds'])].append(r)
        for parameter in dict.fromkeys(k[0] for k in groups):
            times=sorted(t for p,t in groups if p==parameter)
            axis.plot([t-266 for t in times],[np.mean([r['correct'] for r in groups[(parameter,t)]]) for t in times],marker='o',label=parameter)
        axis.set(title=title,xlabel='Seconds after teaching',ylabel='Joint normal/reversed accuracy',ylim=(-.03,1.03));axis.legend(fontsize=8)
    a=axes.flat[4];rows=result['composition']['pairs'];groups=defaultdict(list)
    for r in rows:groups[r['seconds']].append(r)
    if groups:
        a.plot([t-532 for t in sorted(groups)],[np.mean([r['correct'] for r in groups[t]]) for t in sorted(groups)],marker='o',color='#ab6e39')
    a.set(title='E  Untaught word-to-sound composition',xlabel='Seconds after second teaching phase',ylabel='Joint normal/reversed accuracy',ylim=(-.03,1.03))
    a=axes.flat[5];groups=defaultdict(list)
    for r in result['expression']['pairs']:groups[(r['parameter'],r['direction'])].append(r)
    labels=[p+'\n'+d for p,d in groups]
    a.bar(labels,[np.mean([r['correct'] for r in v]) for v in groups.values()],color='#9463a0')
    a.set(title='F  Cue-specific cross-sensory words',ylabel='Joint correct fraction; no-cue words excluded',ylim=(0,1));a.tick_params(axis='x',labelsize=8)
    fig.suptitle('E45  Grounded language calibration and reciprocal association\nConditions share source states; counts are not independent subjects. Core dynamics unchanged.',fontsize=15)
    fig.savefig(HERE/'findings.png',dpi=160);fig.savefig(HERE/'findings.svg');plt.close(fig)

    fig,axes=plt.subplots(1,3,figsize=(17,5.5),layout='constrained')
    groups=defaultdict(list)
    for row in result['formal']['rows']:
        groups[(row['direction'],row['condition'])].append(row)
    x=np.arange(2)
    for index,(condition,color) in enumerate((('normal','#287b72'),('reversed','#498eb5'),('frozen','#a6afad'))):
        values=[groups[(direction,condition)] for direction in ('vision','words')]
        counts=[sum(r['reading']['activity_l1']>1e-8 for r in rows) for rows in values]
        fractions=[count/len(rows) for count,rows in zip(counts,values,strict=True)]
        axes[0].bar(x+(index-1)*.24,fractions,width=.24,label=condition,color=color)
        for xi,f,count,rows in zip(x+(index-1)*.24,fractions,counts,values,strict=True):
            axes[0].text(xi,f+.015,f'{count}/{len(rows)}',ha='center',fontsize=8)
    axes[0].set(xticks=x,xticklabels=['Word → visual activity','Vision → name-channel activity'],ylim=(0,1.07),
                title='A  Learned reciprocal influence',ylabel='Nonzero response relative to aligned no-cue')
    axes[0].tick_params(axis='x',labelsize=9);axes[0].legend(fontsize=8)
    items=result['reciprocal-effects']['rows'];sources=list(dict.fromkeys(r['source'] for r in items));x=np.arange(len(sources))
    for index,(mask,color) in enumerate((('target','#c66b50'),('matched','#287b72'))):
        ratios=[next(r['ratio'] for r in items if r['source']==source and r['mask']==mask) for source in sources]
        axes[1].bar(x+(index-.5)*.34,ratios,width=.34,label=mask+' edges silenced',color=color)
    axes[1].axhline(1,color='#6c7775',linestyle='--',linewidth=1)
    axes[1].set(xticks=x,xticklabels=[str(r['seed'])+'\n'+r['condition'][0].upper() for r in items if r['mask']=='target'],
                title='B  Paths carrying visual-to-name influence',ylabel='Remaining response / intact response',ylim=(0,1.85))
    axes[1].legend(fontsize=8)
    items=[r for r in result['pattern-results']['summary'] if r['test']=='name-to-name-is' and not r['centered']]
    labels=['normal','reversed','frozen'];items=[next(r for r in items if r['condition']==c) for c in labels]
    correct=np.array([r['correct'] for r in items]);unknown=np.array([r['unknown'] for r in items]);total=np.array([r['count'] for r in items]);wrong=total-correct-unknown
    axes[2].bar(labels,correct,color='#287b72',label='Same native pattern')
    axes[2].bar(labels,wrong,bottom=correct,color='#c99c68',label='Different pattern')
    axes[2].bar(labels,unknown,bottom=correct+wrong,color='#d6dddb',label='Unresolved')
    for i,r in enumerate(items):axes[2].text(i,37,f"{r['correct']}/{r['count']} same",ha='center',fontsize=9)
    axes[2].set(title='C  Name vs name + is',ylabel='Cross-sensory trajectory cases',ylim=(0,41))
    axes[2].legend(fontsize=8,loc='lower center')
    fig.suptitle('E45  Learned pathways and native patterns\nA: original saved trials. B/C: separately registered follow-up analyses; not replacements for exact retrieval.',fontsize=13)
    fig.savefig(HERE/'learned-influence.png',dpi=160);fig.savefig(HERE/'learned-influence.svg');plt.close(fig)


if __name__=='__main__':main()
