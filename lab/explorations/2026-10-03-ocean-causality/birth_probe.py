"""Supplement to original birth probes: equal, usable finite starting reserves."""
import argparse
import gzip
import json
import os
import time
from collections import defaultdict
from experiment import WORK,study,simulation_budget
from probe import probe_records
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_causality import replay,compare,local_persistent_transplant
from lab.tools.ocean_controls import naive_same_receptors
from threemind_runtime.inheritance import birth
from threemind_runtime.codec import ArtifactCodec


def execute(group,at,*,probe_suffix=''):
    case=WORK/'cases'/f'g{group}-core';point=case/'checkpoints'/str(at*1000000)
    context=read_json(point/'manifest.json')['context']
    original=read_json(WORK/'probes'/f'g{group}-core-{at}{probe_suffix}'/'summary.json')
    plans={r['individual']:r['plan'] for r in original['individuals'] if 'comparisons' in r}
    rows=defaultdict(list)
    for record in probe_records(case,at*1000000+1,(at+10)*1000000):
        for x in record['inputs']:
            if x['individual'] in plans:
                rows[x['individual']].append({'stimulus':{'time_us':str(x['time_us']),
                    'channels':list(zip(x['channels'],x['values'])),'intensity':x['intensity']},'food':x['food']})
    out=WORK/'probes'/f'g{group}-core-{at}-balanced';out.mkdir(parents=True,exist_ok=False)
    write_json(out/'worker.json',{'pid':os.getpid(),'started_epoch':time.time()})
    started=time.monotonic();s=study();items=[]
    reserve=context['protocol']['initial_energy']
    try:
        with gzip.open(out/'trajectories.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as stream:
            for i,plan in plans.items():
                simulation_budget(s)
                image=ArtifactCodec.decode((point/f'{i}.tmind').read_bytes())
                trace={}
                for name,op in (('experienced','experienced'),('blank','naive')):
                    trace[name],_=replay(image,rows[i],op,reset=True,initial_reserve=reserve)
                donor,recipient=birth(image),naive_same_receptors(image)
                origin=int(image.to_dict()['time_us']);shifted=[]
                for row in rows[i]:
                    stimulus=dict(row['stimulus']);stimulus['time_us']=str(int(stimulus['time_us'])-origin)
                    shifted.append({'stimulus':stimulus,'food':row['food']})
                if plan['applicable']:
                    for name in ('target','matched'):
                        graft=local_persistent_transplant(recipient,donor,plan[name+'_edges'])
                        trace[name],_=replay(graft,shifted,initial_reserve=reserve)
                        for row in trace[name]:row['time_us']+=origin
                item={'individual':i,'initial_reserve':reserve,'experience':compare(trace['experienced'],trace['blank'],plan['targets']),
                      'blank_active_samples':sum(any(a>0 for n,a in row['nodes']) for row in trace['blank']),
                      'experienced_active_samples':sum(any(a>0 for n,a in row['nodes']) for row in trace['experienced']),
                      'graft':{name:compare(trace['experienced'],trace[name],plan['targets']) for name in ('target','matched') if name in trace}}
                for name,t in trace.items():stream.write(json.dumps({'individual':i,'operation':name,'trace':t},separators=(',',':'))+'\n')
                items.append(item)
        value={'case':case.name,'at_s':at,'individuals':items,'wall_seconds':time.monotonic()-started,
               'meaning':'same finite birth reserve and identical sensory/energy replay; original zero-reserve trials retained; not ecological benefit'}
        write_json(out/'summary.json',value)
        print(json.dumps({'case':case.name,'at':at,'count':len(items),'different':sum(x['experience']['motor_mean_absolute']>1e-8 for x in items),
                          'wall_seconds':value['wall_seconds']}),flush=True)
    finally:s.db.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',type=int,choices=(0,1),required=True);p.add_argument('--at',type=int,default=200)
    a=p.parse_args();execute(a.group,a.at)
