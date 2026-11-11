"""Offline validity checks; never create simulation results or change acceptance thresholds."""
import math
from collections import Counter
from analyze import area,rows,save
from experiment import PARENTS,name,symbols
from world import SPEC,motor

def sequence_additivity():
    output=[]
    for seed,arm in PARENTS:
        for history in ('P','Q'):
            for condition in ('normal','off'):
                prefix=f'sequence/{name(seed,arm)}/{history}/{condition}'
                cells={k:rows(prefix+'/'+k) for k in ('00','01','10','11')}
                residuals=[]
                for index,actual in enumerate(cells['11']):
                    maps={k:{n['id']:n['activation'] for n in series[index]['nodes']} for k,series in cells.items()}
                    ids=set().union(*(set(v) for v in maps.values()))
                    synthetic=[{'id':i,'activation':maps['10'].get(i,0)+maps['01'].get(i,0)-maps['00'].get(i,0)} for i in sorted(ids)]
                    residuals.append({'relative_us':actual['relative_us'],
                        'motor_residual':actual['control']-motor(seed,synthetic),
                        'node_l1':math.fsum(abs(maps['11'].get(n['id'],0)-n['activation']) for n in synthetic)})
                output.append({'parent':name(seed,arm),'history':history,'condition':condition,
                    'motor_nonlinearity_inside_core':area(residuals,lambda r:r['motor_residual'],500000,1500000),
                    'node_nonlinearity_l1':area(residuals,lambda r:r['node_l1'],500000,1500000)})
    return save('sequence-additivity-check.json',{'purpose':'Exclude nonlinear motor adapter alone as the interaction source',
        'added_after':'registered sequential runs, before final decision; no threshold changes','rows':output})

if __name__=='__main__':
    import json
    print(json.dumps(sequence_additivity()),flush=True)
