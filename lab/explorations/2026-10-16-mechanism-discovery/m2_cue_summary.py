"""Descriptive tables, figure and storage only; frozen D1/D2 scores unchanged."""
import argparse
import gzip
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pilot_m2 as m
from m5_confirm_summary import inventory


def build(work):
    a=m.read(work/'analysis-v1.json')
    assert a['independent_origins']==8 and m.read(work/'audit-v1.json')['passed']
    conditions={k:sum(all(h['conditions'][k] for h in u['histories']) for u in a['units'])
                for k in a['units'][0]['histories'][0]['conditions']}
    cells={};scale=[]
    for origin in range(8):
        folder=work/'units'/f'o{origin}';r=m.read(folder/'result.json')
        for row in r['diagnostics']:
            key=row['arm']+'/'+row['cue']
            cells.setdefault(key,[]).append((1-2*row['history'])*row['probe']['first'])
        parent=json.loads(gzip.decompress((folder/'h0-lesson16.json.gz').read_bytes()))
        final=json.loads(gzip.decompress((folder/'h0-intact-strong-final.json.gz').read_bytes()))
        scale.append({'origin':origin,'parent_seconds':parent['time_us']/1e6,'final_seconds':final['time_us']/1e6,
                      'parent_nodes':len(parent['model']['nodes']),'parent_edges':len(parent['model']['edges']),
                      'final_nodes':len(final['model']['nodes']),'final_edges':len(final['model']['edges'])})
    return {'schema':'threemind.m2-cue-descriptive-summary/1','verdict':a['verdict'],
            'independent_origins':8,'qualifying_origins':a['D1_qualifying_origins'],
            'conditions_both_histories_by_origin':conditions,'cells':{k:{'n_nested_histories':len(v),
                'mean_signed_endpoint':statistics.mean(v),'min':min(v),'max':max(v),
                'directionally_correct':sum(x>1e-4 for x in v)} for k,v in cells.items()},
            'D2_history_counts':a['D2_history_counts'],'D2_source_counts':a['D2_source_counts'],
            'scale':scale,'statistics_note':'Nested histories are descriptive; independent N is 8.'}


def figure(work,summary):
    path=work/'figure-v1.png'
    if path.exists():raise FileExistsError(path)
    a=m.read(work/'analysis-v1.json')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    for u in a['units']:
        ys=[statistics.mean(h['signed_'+kind] for h in u['histories']) for kind in ('weak','strong')]
        axes[0].plot([0,1],ys,'o-',alpha=.65,label=f"Origin {u['origin']}")
    axes[0].axhline(1e-4,color='black',linestyle='--',label='Frozen correct-response threshold')
    axes[0].set_xticks([0,1],['Cue 0.4','Cue 0.8'])
    axes[0].set_ylabel('Signed A-B at 110 ms (two histories averaged)')
    axes[0].set_title('Same-parent paired cue comparison')
    arms=['intact','silenced','restored','untaught']
    vals=[summary['cells'][arm+'/strong']['directionally_correct'] for arm in arms]
    bars=axes[1].bar(range(4),vals,color=['#2563eb','#64748b','#0d9488','#a1a1aa'])
    axes[1].bar_label(bars,labels=[f'{v}/16 histories' for v in vals],padding=3)
    axes[1].set_xticks(range(4),['Intact','All edges\nsilenced','Restored','Age-matched\nuntaught'])
    axes[1].set_ylim(0,19);axes[1].set_title('Strong-cue expression and registered controls')
    axes[1].set_ylabel('Descriptive nested-history count; independent N = 8')
    fig.suptitle(f"M2 fixed-parent cue diagnosis | D1 {a['verdict']} ({a['D1_qualifying_origins']}/8 origins)")
    fig.savefig(path,dpi=150);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);w=p.parse_args().work
    assert m.read(w/'status.json')['state']=='awaiting-analysis'
    result=build(w);m.original(w/'summary-v1.json',result)
    figure(w,result);storage=inventory(w);m.original(w/'storage-inventory-v1.json',storage)
    print(json.dumps({'summary':result,'storage':storage}))
