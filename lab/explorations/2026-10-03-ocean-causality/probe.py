"""Process attribution, started while ecological observations are still running."""
import argparse
import gzip
import json
import os
import time
from collections import defaultdict

import pyarrow as pa
from pyarrow import ipc

from experiment import HERE, WORK, study, simulation_budget
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_causality import select_pathways,replay,compare,local_persistent_transplant
from lab.tools.ocean_controls import naive_same_receptors
from threemind_runtime.codec import ArtifactCodec
from threemind_runtime.inheritance import birth


def records(case,begin,end):
    initial=read_json(case/'initial/manifest.json')['context']['time_us']
    interval=20000000
    for ordinal in range(max(0,(begin-initial-1)//interval),(end-initial-1)//interval+1):
        f=case/'inputs'/f'{ordinal:06d}.arrow'
        if not f.exists():
            raise RuntimeError(f'required input chunk not yet complete: {f.name}')
        with pa.memory_map(str(f),'r') as source:
            reader=ipc.open_file(source)
            for batch in range(reader.num_record_batches):
                for row in reader.get_batch(batch).to_pylist():
                    if begin<=row['time_us']<=end:
                        yield row


def probe_records(case,begin,end):
    """The formal endpoint remains 600 s; later input comes from a separate copy."""
    boundary=600000000
    yield from records(case,begin,min(end,boundary))
    if end>boundary:
        continuation=WORK/'evaluations'/f'{case.name}-600'
        yield from records(continuation,max(begin,boundary+1),end)


def run(case_name,at=200,seconds=10,*,suffix=''):
    case=WORK/'cases'/case_name
    point=case/'checkpoints'/str(at*1000000)
    if not point.exists():raise RuntimeError('checkpoint not yet saved')
    manifest=read_json(point/'manifest.json')['context']
    alive={b['id'] for b in manifest['bodies'] if b['physical']}
    recent=defaultdict(set); future=defaultdict(list)
    for row in probe_records(case,(at-1)*1000000,(at+seconds)*1000000):
        for item in row['inputs']:
            i=item['individual']
            if i not in alive:continue
            if row['time_us']<=at*1000000:
                recent[i].update(c for c,v in zip(item['channels'],item['values']) if v)
            else:
                future[i].append({'stimulus':{'time_us':str(item['time_us']),
                     'channels':list(zip(item['channels'],item['values'])),'intensity':item['intensity']},'food':item['food']})
    out=WORK/'probes'/f'{case_name}-{at}{suffix}'
    out.mkdir(parents=True,exist_ok=False)
    write_json(out/'worker.json',{'pid':os.getpid(),'started_epoch':time.time()})
    started=time.monotonic(); summary=[]
    budget=study()
    with gzip.open(out/'trajectories.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as stream:
        for i in sorted(alive):
            simulation_budget(budget)
            image=ArtifactCodec.decode((point/f'{i}.tmind').read_bytes())
            plan=select_pathways(image,recent[i])
            rows=future[i]
            if not rows:
                summary.append({'individual':i,'plan':plan,'status':'no future physical inputs'});continue
            baseline,_=replay(image,rows,gain=manifest['protocol']['projection_gain'])
            result={'individual':i,'plan':plan,'samples':len(rows),'comparisons':{}}
            def store(operation,trace):
                stream.write(json.dumps({'individual':i,'operation':operation,'trace':trace},separators=(',',':'))+'\n')
            store('sham',baseline)
            choices=[('all',[])]+([('target',plan['target_edges']),('matched',plan['matched_edges']),
                                    ('restore',plan['target_edges']),('release',plan['target_edges'])] if plan['applicable'] else [])
            for operation,edges in choices:
                trace,_=replay(image,rows,operation,edges=edges)
                result['comparisons'][operation]=compare(baseline,trace,plan['targets'])
                if operation=='release':
                    result['release_windows']={}
                    for a,b in ((0,2),(2,4),(4,10)):
                        x=[r for r in baseline if at*1000000+a*1000000 < r['time_us']+next(bd['birth_us'] for bd in manifest['bodies'] if bd['id']==i) <= at*1000000+b*1000000]
                        y=[r for r in trace if r['time_us'] in {z['time_us'] for z in x}]
                        result['release_windows'][f'{a}-{b}']=compare(x,y,plan['targets'])
                store(operation,trace)
            old,_=replay(image,rows,'experienced',reset=True)
            blank,_=replay(image,rows,'naive',reset=True)
            result['experience']=compare(old,blank,plan['targets'])
            store('experienced_birth',old);store('blank_birth',blank)
            if plan['applicable']:
                donor=birth(image); recipient=naive_same_receptors(image)
                origin=int(image.to_dict()['time_us'])
                shifted=[]
                for r in rows:
                    s=dict(r['stimulus']);s['time_us']=str(int(s['time_us'])-origin)
                    shifted.append({'stimulus':s,'food':r['food']})
                for name,edges in (('target',plan['target_edges']),('matched',plan['matched_edges'])):
                    graft=local_persistent_transplant(recipient,donor,edges)
                    trace,_=replay(graft,shifted)
                    # Normalize timestamps to the original clock for paired differences.
                    for r in trace:r['time_us']+=origin
                    result['comparisons']['transplant_'+name]=compare(old,trace,plan['targets'])
                    result['comparisons']['transplant_'+name+'_vs_blank']=compare(blank,trace,plan['targets'])
                    store('transplant_'+name,trace)
            summary.append(result)
            print(json.dumps({'case':case_name,'at':at,'individual':i,'targets':len(plan['targets']),
                'selective':result['comparisons'].get('target',{}).get('motor_mean_absolute'),
                'matched':result['comparisons'].get('matched',{}).get('motor_mean_absolute'),
                'experience':result['experience']['motor_mean_absolute']}),flush=True)
    write_json(out/'summary.json',{'case':case_name,'at_s':at,'seconds':seconds,'individuals':summary,'wall_seconds':time.monotonic()-started,
        'meaning':'same future sensory replay; not freely interacting ecological outcome; source unchanged'})
    budget.db.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('--at',type=int,default=200);p.add_argument('--seconds',type=int,default=10);p.add_argument('--suffix',default='')
    a=p.parse_args();run(a.case,a.at,a.seconds,suffix=a.suffix)
