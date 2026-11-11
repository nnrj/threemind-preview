"""Single-pass process summaries; independent worlds, not frames, are replicates."""
import argparse
import gzip
import json
import math
from pathlib import Path
import numpy as np
import pyarrow as pa
from pyarrow import ipc
from experiment import WORK
from lab.tools.ocean_cli import read_json,write_json


def trajectories(case):
    with gzip.open(case/'trajectory.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:yield json.loads(line)
    yield read_json(case/'result.json')


def analyze(case):
    output=case/'process-summary.json'
    if output.exists():return read_json(output)
    result=read_json(case/'result.json')
    initial=read_json(case/'initial/manifest.json')['context']
    start=initial['time_us']; protocol=initial['protocol']
    first={b['id']:b for b in initial['bodies']}
    food0=sum(b['grains'] for b in first.values())
    counters={'gradient_samples':0,'toward':0,'gradient_cosine':0.,'gradient_speed_m_s':0.,
              'action_samples':0,'step_change':0.,'lag_cosine':0.,'lag_samples':0,
              'gradient_action_cosine':0.,'gradient_action_samples':0}
    prior={}
    for f in sorted((case/'inputs').glob('*.arrow')):
        with pa.memory_map(str(f),'r') as stream:
            r=ipc.open_file(stream)
            for k in range(r.num_record_batches):
                for row in r.get_batch(k).to_pylist():
                    for x in row['inputs']:
                        raw=x['raw'];a=np.asarray(x['action']);i=x['individual']
                        grad=np.array([raw[1]-raw[3],raw[2]-raw[4]])
                        velocity=np.asarray(raw[5:7])*.03
                        ng,nv=np.linalg.norm(grad),np.linalg.norm(velocity)
                        if ng>1e-10 and nv>1e-10:
                            cosine=float(grad@velocity/(ng*nv))
                            counters['gradient_samples']+=1;counters['toward']+=int(cosine>0)
                            counters['gradient_cosine']+=cosine
                            counters['gradient_speed_m_s']+=float(grad@velocity/ng)
                        if i in prior:
                            old,oldg,t=prior[i]
                            if row['time_us']-t==protocol['period_us']:
                                counters['action_samples']+=1
                                counters['step_change']+=float(np.abs(a-old).mean())
                                den=np.linalg.norm(a)*np.linalg.norm(old)
                                if den>1e-12:
                                    counters['lag_cosine']+=float(a@old/den);counters['lag_samples']+=1
                                den=np.linalg.norm(a[:2])*np.linalg.norm(oldg)
                                if den>1e-12:
                                    counters['gradient_action_cosine']+=float(a[:2]@oldg/den)
                                    counters['gradient_action_samples']+=1
                        prior[i]=a,grad,row['time_us']
    series=[]
    for row in trajectories(case):
        series.append({'time_s':(row['time_us']-start)/1e6,'food':sum(b['grains'] for b in row['members'])-food0,
                       'alive':sum(b['physical'] for b in row['members']),
                       'predations':row['totals']['predations']-initial['totals']['predations'],
                       'births':row['totals']['births']-initial['totals']['births']})
    new_food=sum(b['grains'] for b in result['members'])-food0
    value={'case':case.name,'start_s':start/1e6,'observed_s':result['observed_us']/1e6,'status':result['status'],
           'food':new_food,'living_body_s':result['living_body_s'],
           'food_per_body_minute':60*new_food/max(result['living_body_s'],1e-12),
           'alive':series[-1]['alive'],'predations':series[-1]['predations'],'births':series[-1]['births'],
           'capture_breaks':result['totals']['capture_breaks']-initial['totals']['capture_breaks'],
           'action_mean_square_xy':result['mean_action_square'],
           'body_heat':result['totals']['body_heat']-initial['totals']['body_heat'],
           'motor_energy':sum(b['motor_energy']-first.get(b['id'],{}).get('motor_energy',0) for b in result['members']),
           'gradient_cosine':counters['gradient_cosine']/max(1,counters['gradient_samples']),
           'toward_fraction':counters['toward']/max(1,counters['gradient_samples']),
           'gradient_speed_m_s':counters['gradient_speed_m_s']/max(1,counters['gradient_samples']),
           'gradient_action_cosine':counters['gradient_action_cosine']/max(1,counters['gradient_action_samples']),
           'action_step_change':counters['step_change']/max(1,counters['action_samples']),
           'action_lag_cosine':counters['lag_cosine']/max(1,counters['lag_samples']),
           'counters':counters,'series':series,
           'interpretation':'Descriptive motion/field association only. Gradient is an observer calculation, never Core input. Samples and individuals are not independent-world replicates.'}
    write_json(output,value)
    return value


def closed_pairs(group):
    root=WORK/'closed-loop';base=root/f'g{group}-sham'
    allframes={r['time_us']:{b['id']:b for b in r['members']} for r in trajectories(base)}
    values=[];side=read_json(base/'protocol.json')['side_m']
    for op in ('target','matched','history-strength-zero','region','region-matched'):
        case=root/f'g{group}-{op}';ds=[];rows=[]
        if not (case/'result.json').exists():continue
        for row in trajectories(case):
            original=allframes[row['time_us']]
            distances=[];food=0;captured=0
            for b in row['members']:
                ref=original.get(b['id'])
                if ref is None or b['birth_us']>200000000:continue
                if ref['physical'] and b['physical']:
                    delta=(np.asarray(b['position'])-ref['position']+side/2)%side-side/2
                    distances.append(float(np.linalg.norm(delta)))
                food+=b['grains']-ref['grains'];captured+=b['captured']-ref['captured']
            rows.append({'elapsed_s':(row['time_us']-200000000)/1e6,'position_mean_m':float(np.mean(distances)) if distances else None,
                         'position_max_m':max(distances,default=None),'source_individual_food_difference':food,
                         'source_individual_capture_difference':captured})
            ds+=distances
        values.append({'operation':op,'mean_position_difference_m':float(np.mean(ds)) if ds else None,'series':rows})
    out=root/f'g{group}-paired-process-v{len(values)}.json'
    if not out.exists():write_json(out,values)
    return values


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--closed',action='store_true');a=p.parse_args()
    root=WORK/('closed-loop' if a.closed else 'cases')
    for case in sorted(root.iterdir()):
        if case.is_dir() and (case/'result.json').exists():
            r=analyze(case);print(json.dumps({k:v for k,v in r.items() if k not in ('series','counters','interpretation')}),flush=True)
    if a.closed:
        for g in (0,1):
            if all((root/f'g{g}-{op}'/'result.json').exists() for op in ('sham','target','matched','history-strength-zero')):
                closed_pairs(g)
