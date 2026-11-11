"""Descriptive output after frozen scoring/audit; no subject loading."""
import argparse,gzip,json,statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pilot_m2 as m
from m5_confirm_summary import inventory


def build(work):
    a=m.read(work/'analysis-v1.json');u=m.read(work/'audit-v1.json');assert u['passed']
    cells={};errors=[];scale=[]
    for origin in range(8):
        folder=work/'units'/f'o{origin}';v=m.read(folder/'result.json')
        for h in v['histories']:
            for row in h['tests']:
                key=f"d{row['delay']}/q{row['dose']:.2f}";sign=1-2*h['history']
                cells.setdefault(key,[]).append(sign*row['probe']['first'])
                if row['comparison']['direction']!=row['probe']['direction']:
                    errors.append({'origin':origin,'history':h['history'],'delay':row['delay'],'dose':row['dose'],
                                   'old_prediction':row['comparison']['direction'],'actual':row['probe']['direction']})
        p=json.loads(gzip.decompress((folder/'h0-lesson16.json.gz').read_bytes()))
        f=json.loads(gzip.decompress((folder/'h0-d1.5-q0.77-final.json.gz').read_bytes()))
        scale.append({'origin':origin,'parent_seconds':p['time_us']/1e6,'maximum_end_seconds':f['time_us']/1e6,
                      'parent_nodes':len(p['model']['nodes']),'parent_edges':len(p['model']['edges']),
                      'end_nodes':len(f['model']['nodes']),'end_edges':len(f['model']['edges'])})
    return {'schema':'threemind.m2-gain-descriptive/1','independent_origins':8,
            'cells':{k:{'n_nested_histories':len(v),'signed_mean':statistics.mean(v),'min':min(v),'max':max(v),
                        'expressing':sum(x>1e-4 for x in v)} for k,v in cells.items()},
            'old_formula_errors':errors,'scale':scale,
            'timing_scope':'total host includes simulation, observation, whole-state I/O and API; pure Core not separately timed'}


def figure(work,s):
    p=work/'figure-v1.png';assert not p.exists()
    a=m.read(work/'analysis-v1.json')
    fig,axes=plt.subplots(1,2,figsize=(11,4.4),constrained_layout=True)
    doses=[.51,.59,.65,.77]
    for delay,marker in ((.5,'o'),(1.5,'s')):
        values=[s['cells'][f'd{delay}/q{q:.2f}']['signed_mean'] for q in doses]
        axes[0].plot(doses,values,marker+'-',label=f'{delay}s wait')
    axes[0].set(xlabel='New cue intensity',ylabel='History-signed response at 110ms',title='New conditions: measured response')
    axes[0].axhline(.0001,color='gray',linestyle='--');axes[0].legend()
    values=[a['old_predictor_correct'],a['correct']]
    axes[1].bar(['Original formula','Gain-aware formula'],values,color=['#999999','#256c98'])
    axes[1].set(ylim=(0,175),ylabel='Correct predictions / 160 nested tests',title='Frozen same-test comparison')
    for i,k in enumerate(values):axes[1].text(i,k+3,f'{k}/160',ha='center')
    fig.suptitle(f"M2 prospective prediction: {a['qualified']}/8 independent origins qualified")
    fig.savefig(p,dpi=150);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
    s=build(w);m.original(w/'summary-v1.json',s);figure(w,s)
    v=inventory(w);assert v['science_whole_snapshots']==648;m.original(w/'storage-inventory-v1.json',v)
    print(json.dumps({'summary':s,'storage':v}))
