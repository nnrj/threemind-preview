"""Alternating native trials: disabled optional pools versus absent pool support."""
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

def worker(shared_only):
    import psutil
    from _threemind_native import NativeLocal63
    from threemind_core import Stimulus
    from threemind_kernels.local63_config import Local63Config
    for line in sys.stdin:
        q=json.loads(line);n=q['nodes']
        config=Local63Config(seed=9291288,quiescence_death_us=10**12,
            inhibition_distribution=q['distribution'],inhibition_bypasses_resources=q['bypass'],
            separate_inhibition_resources=False).to_dict()
        if shared_only:config.pop('separate_inhibition_resources')
        course=[Stimulus(0,tuple((60000+i,.3) for i in range(n)))]
        course += [Stimulus(i*500000,tuple((60000+(i*3+j)%n,.4) for j in range(4))) for i in range(1,120)]
        payloads=[json.dumps(x.to_dict()) for x in course]
        gc.collect();e=NativeLocal63(json.dumps(config),None)
        wall,cpu=time.perf_counter(),time.process_time()
        for x in payloads:e.inject(x)
        e.advance('60000000',False,False)
        elapsed,cpu_elapsed=time.perf_counter()-wall,time.process_time()-cpu
        state=json.loads(e.state_json());size=len(json.dumps(state,sort_keys=True,separators=(',',':')).encode())
        for k in ('definition','definition_hash'):state.pop(k)
        state['config'].pop('separate_inhibition_resources',None)
        encoded=json.dumps(state,sort_keys=True,separators=(',',':')).encode();mem=psutil.Process().memory_info()
        result=q|{'shared_only':shared_only,'wall_seconds':elapsed,'cpu_seconds':cpu_elapsed,
            'peak_working_set_bytes':mem.peak_wset,'peak_commit_bytes':mem.peak_pagefile,
            'snapshot_bytes':size,'events':state['sequence'],'final_nodes':len(state['nodes']),
            'edges':len(state['edges']),'state_sha256':hashlib.sha256(encoded).hexdigest()}
        print(json.dumps(result),flush=True)
        del e,state,encoded

def run(output,baseline_stage,current_stage):
    assert not output.exists()
    processes={};all_rows=[];summaries=[]
    try:
        for kind,stage in [('baseline',baseline_stage),('current',current_stage)]:
            env=os.environ.copy();env['PYTHONPATH']=str(stage.resolve())+os.pathsep+str(ROOT/'src')
            command=[sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--worker']
            if kind=='baseline':command+=['--shared-only']
            processes[kind]=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,text=True,encoding='utf8',env=env)
        def trial(condition,index):
            pair={}
            for kind in (('baseline','current') if index%2==0 else ('current','baseline')):
                p=processes[kind];p.stdin.write(json.dumps(condition|{'trial':index})+'\n');p.stdin.flush()
                line=p.stdout.readline()
                if not line:raise RuntimeError(p.stderr.read())
                row=json.loads(line);row['build']=kind;all_rows.append(row);pair[kind]=row
            assert pair['baseline']['state_sha256']==pair['current']['state_sha256'],pair
            return pair
        def summarize(pairs):
            result={kind:{key:statistics.median(p[kind][key] for p in pairs)
                for key in ('wall_seconds','cpu_seconds','peak_working_set_bytes','peak_commit_bytes','snapshot_bytes')}
                for kind in ('baseline','current')}
            result['wall_ratio']=result['current']['wall_seconds']/result['baseline']['wall_seconds']
            result['cpu_ratio']=result['current']['cpu_seconds']/result['baseline']['cpu_seconds']
            return result
        for n in (32,128):
            for distribution in ('per-connection','weight-proportional'):
                for bypass in (True,False):
                    condition={'nodes':n,'distribution':distribution,'bypass':bypass}
                    trial(condition,0)
                    first=summarize([trial(condition,i) for i in range(1,6)])
                    repeat=summarize([trial(condition,i) for i in range(6,11)]) if first['wall_ratio']>1.2 else None
                    item=condition|{'first':first,'repeat':repeat,
                        'large_degradation':repeat is not None and repeat['wall_ratio']>1.2}
                    summaries.append(item);print(json.dumps(item),flush=True)
                    output.with_suffix('.progress.json').write_text(json.dumps({'results':summaries,'trials':all_rows},indent=2),encoding='utf8')
        binaries={kind:hashlib.sha256((stage/'_threemind_native/_threemind_native.pyd').read_bytes()).hexdigest()
            for kind,stage in [('baseline',baseline_stage),('current',current_stage)]}
        output.write_text(json.dumps({'same_numerical_states':True,'binaries':binaries,'results':summaries,
            'retain_optional_pool':not any(q['large_degradation'] for q in summaries),'trials':all_rows},indent=2),encoding='utf8')
    finally:
        for p in processes.values():
            p.stdin.close();p.wait(timeout=30)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--shared-only',action='store_true')
    p.add_argument('--output',type=Path);p.add_argument('--baseline-stage',type=Path);p.add_argument('--current-stage',type=Path)
    a=p.parse_args();worker(a.shared_only) if a.worker else run(a.output,a.baseline_stage,a.current_stage)
