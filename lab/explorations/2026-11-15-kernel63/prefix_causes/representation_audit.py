"""Read-only comparison after projecting lazy fast traces to the same time.

Historical intervention setup settled fast traces at the teaching boundary.
The new diagnostic copies preserve the parent's lazy representation instead.
Projecting both formulas for inspection neither changes nor advances a subject.
"""
import argparse
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t15_repr_study',HERE/'study.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=t.s
def canonical(image):
    d=deepcopy(image.to_dict());now=int(d['time_us']);tau=d['config']['fast_tau_s']
    for edge in d['edges']:
        fast=edge.get('fast')
        if fast:
            fast['value']*=math.exp(-(now-int(fast['time_us']))/1e6/tau)
            fast['time_us']=str(now)
    for k in ('schema','dynamics','definition','definition_hash','config','audit'):d.pop(k,None)
    return d
def differences(a,b,path=''):
    if isinstance(a,dict) and isinstance(b,dict):
        for k in sorted(a.keys()|b.keys()):
            if k not in a or k not in b:yield path+'/'+k,a.get(k,'MISSING'),b.get(k,'MISSING')
            else:yield from differences(a[k],b[k],path+'/'+k)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):yield path+'/length',len(a),len(b)
        else:
            for i,(x,y) in enumerate(zip(a,b)):yield from differences(x,y,path+'/'+str(i))
    elif a!=b:yield path,a,b
def audit(work):
    rows=[]
    for row in s.read(work/'historical-comparison.json')['rows']:
        old=t.h.get(t.OLD/'cases'/row['original']/'final.rstate.gz')
        new=t.h.get(work/'cases'/row['key']/'final.rstate.gz')
        diffs=list(differences(canonical(old),canonical(new)))
        assert all(isinstance(a,(int,float)) and isinstance(b,(int,float)) for _,a,b in diffs),diffs[:10]
        maximum=max((abs(a-b) for _,a,b in diffs),default=0)
        assert maximum<1e-10,(row['key'],maximum)
        rows.append({'key':row['key'],'differences_after_projection':len(diffs),
            'max_absolute_difference':maximum,'examples':diffs[:8]})
    result={'passed':True,'comparisons':len(rows),'rows':rows,
        'max_absolute_difference':max(x['max_absolute_difference'] for x in rows),
        'explanation':'Lazy fast-trace timestamps differ after historical intervention setup; project both to the saved internal time. Remaining differences are floating-point rounding; all other physical state fields and event contents match.'}
    s.write(work/'representation-audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);audit(p.parse_args().work)
