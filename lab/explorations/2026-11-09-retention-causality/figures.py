"""Scientific figures from finished records; no loading of an experimental subject."""
import json
from pathlib import Path
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1')

def main():
    a=json.loads((WORK/'analysis-v1.json').read_text('utf-8'))
    out=WORK/'figures';out.mkdir(exist_ok=True)
    scale=[]
    for w in (.025,.1,1.):
        ratio=w/.008
        scale.append(dict(initial_weight=w,exponential30_s=30*math.log2(ratio),
            exponential300_s=300*math.log2(ratio),power30_s=30*(ratio-1),
            inverse_log30_s=30/(math.e-1)*math.expm1(ratio-1)))
    scale_record=dict(classification='post-design analytic comparison across allowed weight values; no subject outcomes',
        assumptions='no further reinforcement; constant curve parameters; threshold 0.008',values=scale)
    scale_path=WORK/'candidate-scale-v1.json'
    if scale_path.exists():
        assert json.loads(scale_path.read_text('utf-8'))==scale_record
    else:
        with scale_path.open('x',encoding='utf-8') as f:json.dump(scale_record,f,sort_keys=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
    keys=['late:baseline','late:target','late:matched','late:all','early:baseline','early:target','early:all']
    colors=['#7e858c','#256b96','#a8adb2','#267b5c','#7e858c','#256b96','#267b5c']
    labels=['Late\nbaseline','Late\ntarget','Late\nmatched','Late\nall','Early\nbaseline','Early\ntarget','Early\nall']
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for ax,metric,title in [(axes[0],'clear','Joint accuracy on new cues'),(axes[1],'old','Joint accuracy on old cues')]:
        ys=[100*a['aggregate'][k][metric]['correct']/a['aggregate'][k][metric]['n'] for k in keys]
        ax.bar(range(7),ys,color=colors,width=.7)
        for i,k in enumerate(keys):
            values=[100*r['counts'][k][metric]['correct']/r['counts'][k][metric]['n'] for r in a['origins']]
            ax.scatter(np.arange(8)/30+i-.12,values,color='black',s=13,alpha=.6)
            c=a['aggregate'][k][metric];ax.text(i,min(106,ys[i]+4),f"{c['correct']}/{c['n']}",ha='center',fontsize=9)
        ax.set_xticks(range(7),labels);ax.set_ylim(0,112);ax.set_ylabel('Correct (%)');ax.set_title(title)
    fig.suptitle('R44: retention interventions with unchanged individual temporal adapters',fontsize=12)
    fig.text(.5,.012,'Dots: 8 independent origins; each combines its two teaching histories. Branches are not independent origins.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,.94))
    for ext in ('png','svg','pdf'):fig.savefig(out/f'behavior.{ext}',dpi=180)
    plt.close(fig)
    ts=np.linspace(0,160,700);w0=.025;slow=.2;fh=30/(-math.log2((.5-slow*2**(-30/300))/(1-slow)))
    curves={'Exponential, half-value 30 s':2**(-ts/30),'Exponential, half-value 300 s':2**(-ts/300),
            'Power law, half-value 30 s':1/(1+ts/30),'Inverse log, half-value 30 s':1/(1+np.log1p(ts/(30/(math.e-1)))),
            'Two exponentials, half-value 30 s':.8*2**(-ts/fh)+.2*2**(-ts/300)}
    fig,ax=plt.subplots(figsize=(8,4.8))
    for name,ys in curves.items():ax.plot(ts,ys*w0,label=name)
    ax.axhline(.008,color='black',linestyle='--',label='Deletion threshold 0.008')
    ax.axvline(72,color='#888888',linestyle=':',label='Original test end (72 s)')
    ax.set(xlabel='Internal seconds without reinforcement',ylabel='Connection weight',ylim=(0,.026),title='Mathematical candidates: initial weight 0.025')
    ax.legend(fontsize=8);fig.tight_layout()
    for ext in ('png','svg','pdf'):fig.savefig(out/f'decay-curves.{ext}',dpi=180)
    plt.close(fig)
    print('Two scientific figures saved as PNG/SVG/PDF in the study originals directory.')

if __name__=='__main__':main()
