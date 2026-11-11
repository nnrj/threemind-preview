"""Summarize measured ancestry/consumption; no world replay or Core queries."""
import gzip
import json
from pathlib import Path
import statistics

from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json,write_json


def analyze():
    cases=sorted(p.parent for p in (WORK/'cases').glob('*/result.json'))
    if not cases:raise RuntimeError('no completed/paused evidence')
    results=[read_json(p/'result.json') for p in cases]
    end=results[-1];members={b['id']:b for b in end['members']}
    events=[e for p in cases for e in read_json(p/'events.json')]
    births=[e for e in events if e['kind']=='birth']
    captures=[e for e in events if e['kind']=='body_engulfed']
    if any(e['method']!='enclosure' for e in captures):raise RuntimeError('non-enclosure consumption')
    if any(b['controller']!='core' for b in members.values()):raise RuntimeError('non-Core participant')
    if any(read_json(p/'protocol.json')['capture_enabled'] for p in cases):raise RuntimeError('contact enabled')
    def ancestry(b):
        out=[b]
        while out[-1]['parent'] in members:out.append(members[out[-1]['parent']])
        return list(reversed(out))
    alive=[b for b in members.values() if b['physical']]
    deepest=min(alive or list(members.values()),key=lambda b:(-b['generation'],b['id']))
    chain=ancestry(deepest)
    captures=[e|{'predator_radius_mm':members[e['predator']]['radius']*1000,
                  'prey_radius_mm':members[e['individual']]['radius']*1000,
                  'predator_generation':members[e['predator']]['generation'],
                  'prey_generation':members[e['individual']]['generation']} for e in captures]
    changes=[(members[e['individual']]['radius']-members[e['parent']]['radius'])*1000 for e in births]
    points=[]
    for folder in cases:
        with gzip.open(folder/'trajectory.jsonl.gz','rt',encoding='utf-8') as f:
            for line in f:
                row=json.loads(line)
                if row['time_us']%1000000:continue
                live=[b for b in row['members'] if b['physical']]
                sizes=[b['radius']*1000 for b in live]
                points.append({'s':row['time_us']/1e6,'alive':len(live),'food':row['nutrient_count'],
                    'captures':sum(b['captured'] for b in row['members']),
                    'births':sum(b['parent'] is not None for b in row['members']),
                    'highest_generation':max(b['generation'] for b in row['members']),
                    'radius_min':min(sizes,default=0),'radius_median':statistics.median(sizes) if sizes else 0,
                    'radius_max':max(sizes,default=0)})
    summary={'seconds':end['time_us']/1e6,'status':end['status'],'error':end['error'],
        'wall_seconds':sum(r['wall_seconds'] for r in results),'founders':53,'total_bodies':len(members),
        'alive':len(alive),'births':len(births),'captures':captures,
        'powered_bodies':sum(b['storage']>0 for b in alive),
        'body_unserved':sum(b['body_unserved'] for b in members.values()),
        'failure_counts':{reason:sum(b.get('body_failure')==reason for b in members.values())
            for reason in sorted({b.get('body_failure') for b in members.values() if b.get('body_failure')})},
        'max_generation':max(b['generation'] for b in members.values()),
        'food_eaten':sum(b['grains'] for b in members.values()),'remaining_food':end['nutrient_count'],
        'radii_change':{'larger':sum(x>1e-10 for x in changes),'smaller':sum(x< -1e-10 for x in changes),
                        'same':sum(abs(x)<=1e-10 for x in changes)},
        'alive_generations':{str(g):sum(b['generation']==g for b in alive) for g in sorted({b['generation'] for b in alive})},
        'sample_lineage':[{k:b[k] for k in ('id','parent','generation','radius','shell','elongation','birth_us','physical','captured')} for b in chain],
        'energy_error':end['energy_balance_error'],'totals':end.get('totals'),
        'segments':[{'name':p.name,'seconds':r['observed_us']/1e6,'status':r['status']} for p,r in zip(cases,results)]}
    write_json(WORK/'analysis.json',summary);write_json(WORK/'population-process.json',points)
    # Standard scientific plots, using actual samples, not illustrative animations.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,6),constrained_layout=True)
    xs=[p['s'] for p in points]
    for key,label in [('alive','Living bodies'),('births','Cumulative births')]:axes[0,0].plot(xs,[p[key] for p in points],label=label)
    axes[0,0].legend();axes[0,0].set_title('Population and births')
    axes[0,1].plot(xs,[p['captures'] for p in points]);axes[0,1].set_title('Complete-enclosure consumption')
    for key,label in [('radius_min','Minimum'),('radius_median','Median'),('radius_max','Maximum')]:axes[1,0].plot(xs,[p[key] for p in points],label=label)
    axes[1,0].legend();axes[1,0].set_title('Living-body equivalent radius (mm)')
    axes[1,1].plot(xs,[p['highest_generation'] for p in points]);axes[1,1].set_title('Highest generation born')
    for ax in axes.flat:ax.set_xlabel('Simulation seconds');ax.grid(alpha=.2)
    (HERE/'figures').mkdir(exist_ok=True);fig.savefig(HERE/'figures/process.png',dpi=140);plt.close(fig)
    return summary


if __name__=='__main__':print(json.dumps(analyze(),ensure_ascii=False))
