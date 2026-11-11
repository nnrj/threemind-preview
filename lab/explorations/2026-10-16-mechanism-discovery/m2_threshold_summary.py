"""Descriptive postprocessing only; never changes frozen P1/P2 scores or loads Core."""
import argparse
import gzip
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import pilot_m2 as m
from m5_confirm_summary import inventory


def build(work):
    a=m.read(work/'analysis-v1.json');audit=m.read(work/'audit-v1.json')
    assert a['independent_origins']==8 and audit['passed']
    cells={};residuals=[];scale=[];errors=[]
    for origin in range(8):
        folder=work/'units'/f'o{origin}';raw=m.read(folder/'result.json')
        for h in raw['histories']:
            for delay in h['delays']:
                residuals.extend(pair['residual'] for pair in delay['selection']['pairs'])
            for row in h['tests']:
                key=f"d{row['delay']}/{row['arm']}/{row['dose']:.2f}"
                value=(1-2*h['history'])*row['probe']['first']
                cells.setdefault(key,[]).append(value)
                if row['prediction']['direction']!=row['probe']['direction']:
                    errors.append({'origin':origin,'history':h['history'],'delay':row['delay'],
                                   'arm':row['arm'],'dose':row['dose'],'novel':row['novel'],
                                   'predicted':row['prediction']['direction'],'actual':row['probe']['direction']})
        parent=json.loads(gzip.decompress((folder/'h0-lesson16.json.gz').read_bytes()))
        final=json.loads(gzip.decompress((folder/'h0-d2-intact-q0.73-final.json.gz').read_bytes()))
        scale.append({'origin':origin,'parent_seconds':parent['time_us']/1e6,'end_seconds':final['time_us']/1e6,
                      'parent_nodes':len(parent['model']['nodes']),'parent_edges':len(parent['model']['edges']),
                      'end_nodes':len(final['model']['nodes']),'end_edges':len(final['model']['edges'])})
    conditions={key:sum(all(h['conditions'][key] for h in u['histories']) for u in a['units'])
                for key in a['units'][0]['histories'][0]['conditions']}
    return {'schema':'threemind.m2-threshold-descriptive-summary/1','goals':a['goals'],'verdict':a['verdict'],
            'independent_origins':8,'novel_correct':a['novel_correct'],'novel_predictions':a['novel_predictions'],
            'all_correct':a['all_correct'],'all_predictions':a['all_predictions'],
            'P2_conditions_both_histories_by_origin':conditions,
            'cells':{key:{'nested_histories':len(v),'mean_signed_endpoint':statistics.mean(v),'min':min(v),'max':max(v),
                          'expressing':sum(x>1e-4 for x in v)} for key,v in cells.items()},
            'matching':{'pairs':len(residuals),'maximum_absolute_residual_per_feature':
                        [max(r[i] for r in residuals) for i in range(7)],
                        'features':['weight','source_outdegree','source_indegree','target_outdegree','target_indegree','source_activation','target_activation']},
            'prediction_errors':errors,'scale':scale,
            'statistics_note':'Histories, delays, doses and intervention copies are nested. N=8 independently born origins. This is exploration, not confirmation.',
            'timing_scope':'Host resource-summary includes simulation, Python, copying, observation, saving and API. No pure-Core timer was instrumented.'}


def figure(work,s):
    path=work/'figure-v1.png'
    if path.exists():raise FileExistsError(path)
    fig,axes=plt.subplots(1,2,figsize=(13,4.8),constrained_layout=True)
    doses=[.47,.57,.63,.73]
    for delay,marker in [(0,'o'),(2,'s')]:
        vals=[s['cells'][f'd{delay}/intact/{q:.2f}']['mean_signed_endpoint'] for q in doses]
        axes[0].plot(doses,vals,marker+'-',label=f'Delay {delay} s (16 nested histories)')
    axes[0].axhline(.0001,color='gray',linestyle='--',label='Frozen expression threshold')
    axes[0].set_xlabel('Previously untested cue dose');axes[0].set_ylabel('Signed A-B response at 110 ms')
    axes[0].set_title(f"P1: {s['novel_correct']}/{s['novel_predictions']} predictions correct")
    axes[0].legend(fontsize=8)
    arms=['intact','target-full','matched-full','target-empty','matched-empty','restored']
    labels=['Intact','Target\nfull','Matched\nfull','Target\nempty','Matched\nempty','Restored']
    for i,q in enumerate((.55,.8)):
        vals=[s['cells'][f'd0/{arm}/{q:.2f}']['mean_signed_endpoint'] for arm in arms]
        axes[1].bar([j+(i-.5)*.38 for j in range(6)],vals,.38,label=f'Cue {q:.2f}')
    axes[1].set_xticks(range(6),labels,fontsize=8);axes[1].set_ylabel('Signed response; 16 nested histories per bar')
    axes[1].set_title(f"P2: {s['goals']['P2']['qualified']}/8 origins satisfy all causal conditions")
    axes[1].legend(fontsize=8)
    fig.suptitle(f"M2 local release threshold | {s['verdict']} | independent N = 8")
    fig.savefig(path,dpi=150);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
    assert m.read(w/'status.json')['state']=='awaiting-analysis'
    result=build(w);m.original(w/'summary-v1.json',result);figure(w,result)
    storage=inventory(w);assert storage['science_whole_snapshots']==1736
    m.original(w/'storage-inventory-v1.json',storage)
    print(json.dumps({'summary':result,'storage':storage}))
