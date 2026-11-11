"""Read causal traces once; include direction, brief peaks and clean unprompted intervals."""
import gzip
import json
from collections import defaultdict

import numpy as np
from experiment import WORK
from probe import probe_records
from lab.tools.ocean_cli import read_json,write_json


def analyze(folder):
    summary=read_json(folder/'summary.json')
    case,at,seconds=summary['case'],summary['at_s'],summary['seconds']
    plans={r['individual']:r['plan'] for r in summary['individuals'] if 'comparisons' in r}
    rowmap=defaultdict(dict)
    for row in probe_records(WORK/'cases'/case,(at-1)*1000000,(at+seconds)*1000000):
        for x in row['inputs']:
            if x['individual'] in plans:rowmap[x['individual']][x['time_us']]=x
    data=defaultdict(dict)
    with gzip.open(folder/'trajectories.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            value=json.loads(line);data[value['individual']][value['operation']]=value['trace']
    out=[]
    for i,traces in data.items():
        sham=traces['sham']; plan=plans[i]; lookup=rowmap[i]
        error=max((max(abs(a-b) for a,b in zip(r['action'],lookup[r['time_us']]['action'])) for r in sham),default=0)
        if error>1e-12:raise RuntimeError(f'sham actions do not reproduce actual source: {i}: {error}')
        result={'individual':i,'sham_action_max_error':error,'windows':{}}
        target_nodes=plan['targets'];target_channels=set(plan.get('target_channels',[]))
        first=min((t for t,x in lookup.items() if t>=sham[0]['time_us'] and target_channels.intersection(x['channels'])),default=None)
        result['first_direct_target_after_probe_us']=first
        for name in ('target','matched','all','release'):
            if name not in traces:continue
            trace=traces[name]
            values=[];signed=[];clean=[]
            for a,b in zip(sham,trace):
                values.append(max(abs(x-y) for x,y in zip(a['action'],b['action'])))
                na,nb=dict(a['nodes']),dict(b['nodes'])
                signed.append(sum(na.get(n,0)-nb.get(n,0) for n in target_nodes))
                if first is None or a['time_us']<first:clean.append((values[-1],signed[-1]))
            result[name]={'motor_peak':max(values,default=0),'target_signed_mean':float(np.mean(signed)),
                          'clean_prefix_samples':len(clean),'clean_motor_peak':max((v[0] for v in clean),default=None),
                          'clean_target_signed_mean':float(np.mean([v[1] for v in clean])) if clean else None}
        for low,high in ((0,1),(1,5),(5,10)):
            a=traces['experienced_birth'];b=traces['blank_birth'];start=a[0]['time_us']
            ds=[np.abs(np.asarray(x['action'])-y['action']).mean() for x,y in zip(a,b) if low*1e6<=x['time_us']-start<high*1e6]
            result['windows'][f'{low}-{high}']=float(np.mean(ds)) if ds else None
        out.append(result)
    value={'case':case,'at':at,'individuals':out,'note':'clean prefix ends at first direct input to any selected target; negative differences retained'}
    write_json(folder/'process-analysis.json',value)
    print(json.dumps(value),flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('probe');a=p.parse_args();analyze(WORK/'probes'/a.probe)
