"""Plot completed R45 records; never instantiate or advance a subject."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-relaxation/v1')
ARMS=tuple(f'{b}-{r}' for b in ('natural','raised') for r in ('default','slow','off'))


def main():
    a=json.loads((WORK/'analysis-v1.json').read_text('utf-8'))
    assert a['complete_boundaries']==2592
    out=WORK/'figures';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
        'axes.spines.top':False,'axes.spines.right':False})
    colors=['#7e858c','#256b96','#267b5c']*2
    labels=[x.replace('-','\n') for x in ARMS]
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.8))
    for ax,metric,title in zip(axes,('new','old'),('Joint accuracy on new cues','Joint accuracy on old cues')):
        for j,arm in enumerate(ARMS):
            c=a['aggregate'][arm][metric];v=100*c['correct']/c['n']
            ax.bar(j,v,width=.7,color=colors[j])
            dots=[100*r['scores'][arm][metric]['correct']/r['scores'][arm][metric]['n'] for r in a['origins']]
            ax.scatter(j+(np.arange(8)-3.5)/30,dots,color='black',s=13,alpha=.6)
            ax.text(j,v+4,f"{c['correct']}/{c['n']}",ha='center',fontsize=9)
        ax.set(ylim=(0,112),ylabel='Correct (%)',title=title)
        ax.set_xticks(range(6),labels)
    fig.suptitle('R45: half-life relaxation at original, one-tenth and zero rates')
    fig.text(.5,.012,'Dots: 8 independent origins, with two teaching histories each. Personal temporal adapters remain unchanged.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,.94))
    for ext in ('png','svg','pdf'):fig.savefig(out/f'behavior.{ext}',dpi=180)
    plt.close(fig)
    stages=('intervention','teaching-1','teaching-2','trial-023')
    fig,axes=plt.subplots(1,2,figsize=(11.5,4.8))
    for ax,boost,title in zip(axes,('natural','raised'),('Natural initial half-lives','Target connections initially raised to 300 s')):
        for rate,color in zip(('default','slow','off'),colors[:3]):
            selected=[b for b in a['branches'] if b['arm']==boost+'-'+rate]
            ys=[]
            for stage in stages:
                rows=[next(s for s in b['structure'] if s['stage']==stage) for b in selected]
                ys.append(100*sum(s['x_surviving'] for s in rows)/sum(s['x_initial'] for s in rows))
            ax.plot(range(4),ys,marker='o',label=rate,color=color)
        ax.set_xticks(range(4),['After\nintervention','After\nteaching 1','After\nteaching 2','After\n24 trials'])
        ax.set(ylim=(-3,104),ylabel='Original X-output connections surviving (%)',title=title)
        ax.legend()
    fig.suptitle('R45: persistence of initially present task connections')
    fig.tight_layout(rect=(0,0,1,.94))
    for ext in ('png','svg','pdf'):fig.savefig(out/f'connection-survival.{ext}',dpi=180)
    plt.close(fig)
    print('Two figures saved as PNG, SVG and PDF; inspect PNGs before publication.')


if __name__=='__main__':main()
