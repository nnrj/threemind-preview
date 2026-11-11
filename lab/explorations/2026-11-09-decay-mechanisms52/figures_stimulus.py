"""Render verified R46b outcomes and full temporal processes, without a Core."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/stimulus-v1')
FIELDS=('activation','inhibition','direct','associative')
CURVES=('exponential','inverse-logarithmic','power-law')
COLORS=('#4267A9','#B05B29','#3C8555')

def read(path):return json.loads(path.read_text('utf-8'))
def save(fig,path):
    for suffix in ('png','svg','pdf'):
        dest=path.with_suffix('.'+suffix);assert not dest.exists()
        fig.savefig(dest,dpi=180)
    plt.close(fig)

def main():
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=960)
    assert read(WORK/'independent-audit-v1.json')['passed']
    data=read(WORK/'analysis-v1.json');folder=WORK/'figures';folder.mkdir(exist_ok=True)
    assert not list(folder.glob('stimulus-*.png'))
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','pdf.fonttype':42})
    labels=['Exp / on','Exp / off','Log / on','Log / off','Power / on','Power / off']
    families=(('strong-gain','A. Dedicated strong-stimulus gain'),
              ('novelty-gain','B. Connection novelty gain'),
              ('overall-intensity','C. Overall intensity at equal actual drive'))
    fig,axes=plt.subplots(1,3,figsize=(13.2,5.2),constrained_layout=True)
    for ax,(family,title) in zip(axes,families):
        values=np.array([[c['counts'][family][f] for f in ('immediate','structure','activity')] for c in data['conditions']])
        ax.imshow(values,vmin=0,vmax=8,cmap='Blues',aspect='auto')
        ax.set_xticks(range(3),['Immediate\nweight gain','300-s\nstructural benefit','300-s\nactivity benefit'])
        ax.set_yticks(range(6),labels);ax.set_title(title,loc='left',fontsize=10)
        for i in range(6):
            for j in range(3):
                ax.text(j,i,f'{values[i,j]}/8',ha='center',va='center',color='white' if values[i,j]>=5 else '#222222',fontweight='bold')
                if values[i,j]>=6:ax.add_patch(plt.Rectangle((j-.48,i-.48),.96,.96,fill=False,edgecolor='#1A4D20',linewidth=2))
    fig.suptitle('Eight varied input conditions per setting; green border = preregistered 6/8 threshold\nStructural benefit and activity benefit are separate measurements',fontsize=12)
    save(fig,folder/'stimulus-gain-outcomes')

    fig,axes=plt.subplots(4,2,figsize=(12,10),sharex=True,constrained_layout=True)
    t=np.arange(1,21)*.05
    for j,(active,control,title) in enumerate((('strong-intensity','strong-gain-zero','Dedicated strong-stimulus gain'),
                                              ('arrival-novelty','arrival-gain-zero','Connection novelty gain'))):
        for curve,color in zip(CURVES,COLORS):
            row=next(r for r in data['origins'] if r['origin']==0 and r['curve']==curve and not r['relaxation'])
            for arm,style,width in ((active,'-',1.8),(control,'--',1.3)):
                v=row['arms'][arm]['effect']['300']
                for i,field in enumerate(FIELDS):
                    axes[i,j].plot(t,v[i::4],color=color,ls=style,lw=width,label=curve+(' / gain' if arm==active else ' / gain zero'))
                    axes[i,j].set_ylabel(field.capitalize()+' cue effect');axes[i,j].axhline(0,color='#999999',lw=.4)
                    axes[i,j].grid(alpha=.2)
        axes[0,j].set_title(title);axes[-1,j].set_xlabel('Seconds after cue')
    handles,legends=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,legends,loc='outside lower center',ncol=3,fontsize=9)
    fig.suptitle('Complete 300-s temporal cue effects: profile 0, relaxation off\nCue-minus-omission changes; solid = normal gain, dashed = gain zero',fontsize=12)
    save(fig,folder/'stimulus-temporal-fields')

    fig,axes=plt.subplots(1,2,figsize=(11,5),constrained_layout=True)
    for ax,(family,title) in zip(axes,families[:2]):
        limit=0.
        for curve,color in zip(CURVES,COLORS):
            for relax,marker in ((True,'o'),(False,'x')):
                rows=[r['comparisons'][family]['structure'] for r in data['origins'] if r['curve']==curve and r['relaxation']==relax]
                x=[r['control'] for r in rows];y=[r['active'] for r in rows];limit=max(limit,max(x+y))
                ax.scatter(x,y,s=45,marker=marker,color=color,label=curve+(' / on' if relax else ' / off'),alpha=.75)
        limit=max(limit*1.05,.001);ax.plot([0,limit],[0,limit],ls=':',color='#666666')
        ax.set(xlim=(-.02*limit,limit),ylim=(-.02*limit,limit),xlabel='Gain-zero mean connection weight',ylabel='Normal-gain mean connection weight',title=title)
        ax.grid(alpha=.2)
    axes[1].legend(fontsize=8)
    fig.suptitle('300-s weights in all eight input profiles; missing original connections count as zero')
    save(fig,folder/'stimulus-retained-weights')
    with (folder/'render-manifest.json').open('x',encoding='utf-8') as out:
        json.dump(dict(profile_for_temporal_illustration=0,relaxation_for_illustration=False,
                       selected_before_full_results=True,figures=3,formats=['png','svg','pdf']),out)
    print(json.dumps(dict(figures=3,formats=['png','svg','pdf'])))

if __name__=='__main__':main()
