"""Post-completion plots, scale and allocated-storage inventory; no simulation."""
import argparse
import gzip
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import m3_confirm_spec as spec
import pilot_m2 as m
from m5_confirm_summary import inventory


def summarize(work):
    a=m.read(work/'analysis-v1.json');audit=m.read(work/'audit-v1.json')
    assert audit['passed'] and a['independent_origins']==spec.N
    scale=[]
    for o in range(spec.N):
        for name in ('h0-parent','h1-parent',*(s+'-stage3' for s in spec.SEQUENCES)):
            value=json.loads(gzip.decompress((work/'units'/f'o{o}'/'threemind'/(name+'.json.gz')).read_bytes()))
            scale.append({'origin':o,'boundary':name,'time_seconds':value['time_us']/1e6,
                          'nodes':len(value['model']['nodes']),'edges':len(value['model']['edges'])})
    rows=[{'system':k,'criterion_counts':a['systems'][k]['criterion_counts'],
           'joint_count':a['systems'][k]['joint_count'],'joint_proportion_95':a['systems'][k]['joint_proportion_95'],
           'cohort_all_four':a['systems'][k]['cohort_all_four']} for k in spec.KINDS]
    return {'schema':'threemind.m3-confirmation-summary/1','verdict':a['verdict'],'valid':a['valid'],
            'origins':spec.N,'rows':rows,'paired_comparisons':a['paired_comparisons'],
            'scale':scale,'audit_counts':audit['counts'],'matching_maximum':audit['maximum_rnn_matching_residual']}


def plot(summary,path):
    if path.exists():raise FileExistsError(path)
    counts=np.array([r['criterion_counts']+[r['joint_count']] for r in summary['rows']])
    fig,ax=plt.subplots(figsize=(11,4.4),constrained_layout=True)
    im=ax.imshow(counts/spec.N,vmin=0,vmax=1,cmap='Blues',aspect='auto')
    ax.set_xticks(range(5),['C1\nHistory effect','C2\nSelective cause','C3\nTemporal interaction','C4\nClosed-loop adaptation','All four\nsame origin'])
    ax.set_yticks(range(5),['Reactive','Finite state','Local Hebbian','Fixed RNN + reader','ThreeMind'])
    for i in range(5):
        for j in range(5):ax.text(j,i,f'{counts[i,j]}/{spec.N}',ha='center',va='center',color='white' if counts[i,j]>spec.N/2 else 'black')
    ax.set_title('M3 independent confirmation | 64 new paired origins | four frozen operational criteria')
    fig.colorbar(im,ax=ax,label='Fraction of origins passing')
    fig.savefig(path,dpi=160);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);work=p.parse_args().work
    summary=summarize(work);m.original(work/'summary-v1.json',summary);plot(summary,work/'figure-v1.png')
    storage=inventory(work);m.original(work/'storage-inventory-v1.json',storage)
    print(json.dumps({'verdict':summary['verdict'],'rows':summary['rows'],
                      'scale':{k:sorted(set(v[k] for v in summary['scale'])) for k in ('time_seconds','nodes','edges')},
                      'storage':storage}))
