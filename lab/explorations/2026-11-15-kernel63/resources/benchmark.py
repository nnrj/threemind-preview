"""Prechange/new native 6.3 comparison in isolated processes."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]

def worker(distribution,separate,old):
    import psutil
    from _threemind_native import NativeLocal63
    from threemind_core import Stimulus
    from threemind_kernels.local63_config import Local63Config
    config=Local63Config(seed=9291280,quiescence_death_us=10**12,
        inhibition_distribution=distribution,separate_inhibition_resources=separate).to_dict()
    if old:config.pop('separate_inhibition_resources')
    course=[Stimulus(0,tuple((60000+i,.3) for i in range(32)))]
    course += [Stimulus(i*500000,tuple((60000+(i*3+j)%32,.4) for j in range(4))) for i in range(1,120)]
    payloads=[json.dumps(q.to_dict()) for q in course];rows=[]
    for trial in range(6):
        e=NativeLocal63(json.dumps(config),None)
        wall,cpu=time.perf_counter(),time.process_time()
        for q in payloads:e.inject(q)
        e.advance('60000000',False,False)
        elapsed,cpu_elapsed=time.perf_counter()-wall,time.process_time()-cpu
        state=json.loads(e.state_json());encoded=json.dumps(state,sort_keys=True,separators=(',',':')).encode()
        for k in ('definition','definition_hash'):state.pop(k)
        state['config'].pop('separate_inhibition_resources',None)
        numerical=json.dumps(state,sort_keys=True,separators=(',',':')).encode();mem=psutil.Process().memory_info()
        rows.append({'trial':trial,'warmup':trial==0,'wall_seconds':elapsed,'cpu_seconds':cpu_elapsed,
            'peak_working_set_bytes':mem.peak_wset,'peak_commit_bytes':mem.peak_pagefile,
            'snapshot_bytes':len(encoded),'events':state['sequence'],'nodes':len(state['nodes']),
            'edges':len(state['edges']),'state_sha256':hashlib.sha256(numerical).hexdigest()})
        del e;gc.collect()
    print(json.dumps({'distribution':distribution,'separate':separate,'old':old,'trials':rows}))

def run(output,old_stage,new_stage):
    assert not output.exists();rows=[]
    for distribution in ('per-connection','weight-proportional'):
        for old,separate in ((True,False),(False,False),(False,True)):
            env=os.environ.copy();env['PYTHONPATH']=str(old_stage if old else new_stage)+os.pathsep+str(ROOT/'src')
            command=[sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--worker',distribution]
            if separate:command.append('--separate')
            if old:command.append('--old')
            p=subprocess.run(command,env=env,capture_output=True,text=True,check=True,timeout=300)
            q=json.loads(p.stdout);sample=q['trials'][1:]
            assert len({r['state_sha256'] for r in sample})==1
            q['summary']={k:{'median':statistics.median(r[k] for r in sample),'min':min(r[k] for r in sample),
                              'max':max(r[k] for r in sample)}
                          for k in ('wall_seconds','cpu_seconds','peak_working_set_bytes','peak_commit_bytes','snapshot_bytes','events')}
            rows.append(q);print(json.dumps({k:q[k] for k in ('distribution','separate','old','summary')}),flush=True)
        assert rows[-3]['trials'][1]['state_sha256']==rows[-2]['trials'][1]['state_sha256']
    binaries={k:hashlib.sha256((folder/'_threemind_native/_threemind_native.pyd').read_bytes()).hexdigest()
              for k,folder in (('old',old_stage),('new',new_stage))}
    output.write_text(json.dumps({'same_shared_state':True,'binaries':binaries,'results':rows},indent=2),encoding='utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',choices=('per-connection','weight-proportional'))
    p.add_argument('--old',action='store_true');p.add_argument('--separate',action='store_true')
    p.add_argument('--output',type=Path);p.add_argument('--old-stage',type=Path);p.add_argument('--new-stage',type=Path)
    a=p.parse_args()
    worker(a.worker,a.separate,a.old) if a.worker else run(a.output,a.old_stage.resolve(),a.new_stage.resolve())
