"""Plot saved measurements only; no experimental subject is loaded."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def draw(work):
    assert json.loads((work/'audit.json').read_bytes())['passed']
    analysis=json.loads((work/'analysis.json').read_bytes())
    profiles={r['key']:r for r in json.loads((work/'profiles.json').read_bytes())['rows']}
    variants=[('v1','Kernel 1'),('v31','Kernel 3.1'),('v61','Kernel 6.1'),
              ('v31-legacy-edges','3.1, legacy connection retention'),
              ('no-inhibition','6.1, inhibition off from birth'),
              ('post-no-inhibition','6.1, inhibition off after teaching')]
    palette=['#2166ac','#b2182b','#4d4d4d','#1b9e77','#e08214','#762a83']
    fig,axes=plt.subplots(2,2,figsize=(13,8.5),layout='constrained')
    for (variant,label),color in zip(variants,palette):
        points=profiles[f'{variant}/readout/s0/011/paired/d300/wait']['activity']
        axes[0,0].plot([p['seconds'] for p in points],[p['activation'] for p in points],label=label,color=color,lw=1.5)
        axes[0,1].plot([p['seconds'] for p in points if p['seconds']<=15],
                       [p['activation'] for p in points if p['seconds']<=15],color=color,lw=1.5)
        points=profiles[f'{variant}/sustain/s0/unchanged']['activity']
        axes[1,0].plot([p['seconds'] for p in points],[p['activation'] for p in points],color=color,lw=1.5)
    axes[0,0].set(xlabel='Seconds after teaching',ylabel='Maximum task-node activation',title='A  Waiting without new task cues')
    axes[0,1].set(xlabel='Seconds after teaching',ylabel='Maximum task-node activation',title='B  First 15 seconds of waiting')
    axes[1,0].set(xlabel='Seconds after the 300-second wait',ylabel='Maximum task-node activation',title='C  Registered 15-second observation')
    for ax in axes.flat[:3]:
        ax.set_yscale('symlog',linthresh=1e-6);ax.grid(alpha=.18)
    labels=[];x=[];y=[]
    prefix_variants=[('v1','Kernel 1'),('v2','Kernel 2'),('v2-immediate','2, immediate novelty'),
                     ('v61','Kernel 6.1'),('v61-immediate','6.1, immediate novelty')]
    prefix_analysis=analysis['variants']+json.loads((work/'analysis-novelty.json').read_bytes())['variants']
    for i,(variant,label) in enumerate(prefix_variants):
        r=next(r for r in prefix_analysis if r['variant']==variant)
        labels.append(label.replace(', ','\n'))
        for block in r['blocks']:
            for j,margin in enumerate(block.get('prefix_margins',block.get('margins'))):
                x.append(i+(block['block']-.5)*.12+(j-.5)*.025);y.append(margin)
    axes[1,1].scatter(x,y,s=24,color='#2166ac',alpha=.75)
    axes[1,1].axhline(1e-6,color='grey',ls='--',lw=.8)
    axes[1,1].set_xticks(range(len(labels)),labels,rotation=25,ha='right',fontsize=8)
    axes[1,1].set(ylabel='Taught ending minus alternative (peak)',title='D  Prefix discrimination: two blocks, two cues')
    axes[1,1].set_yscale('symlog',linthresh=1e-6);axes[1,1].grid(axis='y',alpha=.18)
    axes[1,1].set_ylim(min(y)*1.8,max(y)*1.8)
    axes[0,0].legend(fontsize=8,loc='upper right')
    fig.suptitle('R51t1: connection retention and inhibition affect persistent activity',fontsize=14)
    dest=work/'figures';dest.mkdir(exist_ok=True)
    for suffix in ('svg','png','pdf'):fig.savefig(dest/f'activity-causes.{suffix}',dpi=200)
    plt.close(fig)
    print(str(dest/'activity-causes.png'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);a=p.parse_args();draw(a.work)
