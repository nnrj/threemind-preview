"""Retrospective passive visualization: ending contrast across the two prefix processes."""
import argparse
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import study_resources as x
s=x.s


def run(work):
    assert s.read(work/'final-audit.json')['passed']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names=('pre-old-high','stable-g4-r8','stable-g0-r08','default-g0-r08')
    labels=('Earlier successful pre-release screen','Stability: original thresholds and recovery',
            'Stability: zero connection threshold\nand fast recovery',
            'Default retention: zero connection threshold\nand fast recovery')
    rows=[];fig,axes=plt.subplots(2,2,figsize=(11,6.5),constrained_layout=True)
    for ax,name,label in zip(axes.flat,names,labels):
        for block in (0,1):
            traces=[]
            for cue in ('AB','DB'):
                points=s.unpack(x.folder(work,name,block,cue)/'process.json.gz')
                start=points[0]['time_us'];values=[]
                for point in points:
                    v={n['channel']:n['activation'] for n in point['nodes']}
                    # Exchange the sign with the curriculum so positive always denotes the A-taught ending.
                    delta=(v.get(s.measure.TOKENS['C'],0)-v.get(s.measure.TOKENS['E'],0))*(-1 if block else 1)
                    values.append(((point['time_us']-start)/1e6,delta))
                traces.append(values)
                if block==0:
                    ax.plot([p[0] for p in values],[p[1] for p in values],label=cue,
                        color='#1764ab' if cue=='AB' else '#d06a16',linewidth=1.5,
                        linestyle='-' if cue=='AB' else '--')
            separated=[(a[0],a[1]-b[1]) for a,b in zip(*traces)]
            rows.append({'variant':name,'block':block,
                'max_prefix_contrast_before_B':max(abs(v) for t,v in separated if t<1),
                'max_prefix_contrast_after_B':max(abs(v) for t,v in separated if t>=1)})
        ax.axvline(1,color='grey',linewidth=.8,linestyle=':');ax.axhline(0,color='grey',linewidth=.6)
        ax.set_title(label,fontsize=10);ax.set_xlabel('Seconds after the first cue')
        ax.set_ylabel('Ending activation difference');ax.ticklabel_format(axis='y',style='sci',scilimits=(-2,2))
        ax.legend(frameon=False);ax.set_xlim(0,15)
    out=work/'figures';out.mkdir(exist_ok=True)
    fig.savefig(out/'prefix-process-comparison-v2.png',dpi=180)
    fig.savefig(out/'prefix-process-comparison-v2.svg');plt.close(fig)
    s.write(work/'process-contrast-v2.json',{'status':'retrospective descriptive analysis; original score unchanged; shorter figure labels',
        'displayed_block':0,'ordinate':'C activation minus E activation in displayed block 0; C is the A-taught ending.',
        'prior_sha256':s.sha(work/'process-contrast.json'),
        'rows':rows,'figure':'figures/prefix-process-comparison-v2.png'})
    print(json.dumps({'process_contrast':rows}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
