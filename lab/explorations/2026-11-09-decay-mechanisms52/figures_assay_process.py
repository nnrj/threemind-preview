"""Display the saved four-field process decomposition after completed analysis."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')


def main():
    load=lambda p:json.loads(p.read_text('utf-8'))
    assert load(WORK/'independent-audit-v1.json')['passed']
    data=load(WORK/'secondary-diagnostics-v1.json')
    assert all(r['distinct_numeric_outcomes']==1 for r in data['origin_diversity'])
    out=WORK/'figures/assay-process-fields'
    assert not out.with_suffix('.png').exists(),'preserve a rendered edition'
    plt.rcParams.update({'font.size':10,'svg.fonttype':'none','pdf.fonttype':42})
    fig,axes=plt.subplots(4,2,figsize=(12,9),sharex=True,constrained_layout=True)
    for col,(curve,course,title) in enumerate((('power-law','strong','Power-law / relaxation on / higher dose 1.0'),
            ('inverse-logarithmic','spaced','Inverse-logarithmic / relaxation on / spaced'))):
        record=next(r for r in data['field_processes'] if r['origin']==0 and r['curve']==curve and r['relaxation'] and r['course']==course)
        for row,field in enumerate(('activation','inhibition','direct','associative')):
            ax=axes[row,col];f=record['fields'][field]
            for stage,style in (('early','--'),('late','-')):
                for channel,color in ((0,'#3366AA'),(1,'#BB6633')):
                    ax.plot([.05*(i+1) for i in range(20)],[v[channel] for v in f[stage+'_by_frame']],
                            color=color,ls=style,lw=1.6,label=f"{'1 s' if stage=='early' else '300 s'} / output {channel}")
            ax.axhline(0,color='#777777',lw=.5);ax.set_ylabel(field.capitalize()+' difference')
            if row==0:ax.set_title(title,fontsize=11)
            if row==3:ax.set_xlabel('Time within the one-second response window (s)')
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside lower center',ncol=4,fontsize=9)
    fig.suptitle('Opposite-history difference in the cue effect, resolved by activity field\nSeed 0 shown; numeric outcomes are identical across all eight remapped birth seeds',fontsize=12)
    for ext in ('png','svg','pdf'):fig.savefig(out.with_suffix('.'+ext),dpi=190)
    plt.close(fig)


if __name__=='__main__':main()
