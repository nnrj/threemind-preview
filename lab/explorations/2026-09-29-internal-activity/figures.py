"""Static scientific figures from saved evidence, without Core execution."""
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from common import ROOT, WORK, read_json
from analyze import behavior

COLORS={'communication_off':'#cc6655','temporary_off':'#258a79','edges_even':'#577fc0','edges_odd':'#a47bb2'}

def save(fig,name):
    fig.tight_layout()
    path=WORK/(name+'.png')
    fig.savefig(path,dpi=170,bbox_inches='tight')
    shutil.copy2(path,ROOT/'docs/images'/f'internal-activity-{name}-2026-09-29.png')
    plt.close(fig)

def run():
    fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
    for ax,parent in zip(axes,('s9293201/region0','s9293202/region0')):
        normal=behavior('expression/'+parent+'/normal')['rows']
        for cond,color in COLORS.items():
            actual=behavior('expression/'+parent+'/'+cond)['rows']
            ax.plot([r['relative_us']/1e6 for r in actual],
                    [a['control']-b['control'] for a,b in zip(actual,normal)],
                    label=cond.replace('_',' '),color=color,linewidth=1.2)
        ax.axvspan(5,10,color='gray',alpha=.12,label='temporary intervention' if ax is axes[0] else None)
        ax.axhline(0,color='gray',linewidth=.5)
        ax.set_ylabel('Motor output difference')
        ax.set_title(parent+' — identical starting state and input')
    axes[0].legend(fontsize=8,ncol=3)
    axes[-1].set_xlabel('Seconds after branching')
    save(fig,'intervention')

    birth=read_json(WORK/'birth-analysis.json')
    parents=list(dict.fromkeys(x['parent'] for x in birth))
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for ax,metric,label in zip(axes,('association_contrast','P_minus_Q_net_control'),
                             ('Experience contrast in unprompted activity','Experience contrast in motor output')):
        for communication,shift,color in (('on',-.18,'#258a79'),('off',.18,'#cc6655')):
            values=[next(r for r in birth if r['parent']==p and r['communication']==communication)[metric][0] for p in parents]
            ax.bar(np.arange(4)+shift,values,.34,label='communication '+communication,color=color)
        ax.axhline(0,color='gray',linewidth=.5)
        ax.set_xticks(np.arange(4),['W1 / G0','W1 / G1','W2 / G0','W2 / G1'])
        ax.set_title(label+'\nafter birth reset')
        ax.set_ylabel('Integrated difference, first second')
        ax.legend(fontsize=8)
    fig.suptitle('Same cue; different prior co-occurrence histories. Four related parents, not four independent populations.',fontsize=10)
    save(fig,'retention')

    fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,sharey=True)
    for ax,parent in zip(axes.flat,parents):
        channels=read_json(WORK/'cases'/'experience'/parent/'P/normal/result.json')['extra']['channels']
        for curriculum,color in (('P','#258a79'),('Q','#ce7954')):
            prefix='birth-probe/'+parent+'/'+curriculum+'/normal/'
            signal=behavior(prefix+'A/on')['rows']
            none=behavior(prefix+'none/on')['rows']
            for symbol,style in (('B','-'),('D','--')):
                channel=channels[symbol]
                get=lambda r:sum(n['activation'] for n in r['nodes'] if n['channel']==channel)
                ax.plot([r['relative_us']/1e6 for r in signal],
                        [get(a)-get(b) for a,b in zip(signal,none)],color=color,linestyle=style,
                        label=f'{curriculum}: {symbol}')
        ax.set_title(parent)
        ax.set_xlim(0,2)
        ax.axhline(0,color='gray',linewidth=.5)
        ax.set_xlabel('Seconds after A cue')
        ax.set_ylabel('Activation minus no-cue copy')
    axes.flat[0].legend(fontsize=8,ncol=2)
    fig.suptitle('Unprompted B and D activity after birth. P learned AB/CD; Q learned AD/CB.',fontsize=11)
    save(fig,'recall')

if __name__=='__main__':run()
