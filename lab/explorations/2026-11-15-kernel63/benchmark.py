"""Same-input native benchmark; separate processes retain the old binary."""
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

ROOT = Path(__file__).resolve().parents[3]
GROUPS = {'old62': (62,True,'per-connection'), 'new62': (62,True,'per-connection'),
          'matched63': (63,True,'per-connection'), 'default63': (63,False,'per-connection'),
          'proportional63': (63,False,'weight-proportional')}
KEYS = ('separate_inhibition','separate_inhibition_weights','separate_inhibition_resources',
        'separate_inhibition_learning','inhibition_updates_usage','inhibition_distribution')


def worker(variant, old):
    import psutil
    from _threemind_native import NativeLocal62
    from threemind_core import Stimulus
    from threemind_kernels.local62_config import Local62Config
    from threemind_kernels.local63_config import Local63Config
    version, updates, distribution = GROUPS[variant]
    cls=NativeLocal62
    if version==63:
        from _threemind_native import NativeLocal63
        cls=NativeLocal63
    config=(Local62Config if version==62 else Local63Config)(seed=9291280,quiescence_death_us=10**12,
        inhibition_updates_usage=updates).to_dict()
    if version==63:config['inhibition_distribution']=distribution
    if old:config.pop('inhibition_updates_usage')
    course = [Stimulus(0, tuple((60000+i, .3) for i in range(32)))]
    course += [Stimulus(i*500000, tuple((60000+(i*3+j)%32, .4) for j in range(4))) for i in range(1, 120)]
    payloads = [json.dumps(s.to_dict()) for s in course]
    rows = []
    for trial in range(6):
        e = cls(json.dumps(config), None)
        wall, cpu = time.perf_counter(), time.process_time()
        for s in payloads: e.inject(s)
        e.advance('60000000', False, False)
        elapsed, cpu_elapsed = time.perf_counter()-wall, time.process_time()-cpu
        state = json.loads(e.state_json())
        encoded = json.dumps(state, sort_keys=True, separators=(',', ':')).encode()
        for k in ('schema','dynamics','definition', 'definition_hash'):state.pop(k)
        for k in KEYS:state['config'].pop(k, None)
        normalized = json.dumps(state, sort_keys=True, separators=(',', ':')).encode()
        mem = psutil.Process().memory_info()
        rows.append({'trial':trial, 'warmup':trial==0, 'wall_seconds':elapsed, 'cpu_seconds':cpu_elapsed,
            'peak_working_set_bytes':mem.peak_wset, 'peak_commit_bytes':mem.peak_pagefile,
            'snapshot_bytes':len(encoded), 'events':state['sequence'], 'nodes':len(state['nodes']),
            'edges':len(state['edges']), 'state_sha256':hashlib.sha256(normalized).hexdigest()})
        del e;gc.collect()
    print(json.dumps({'variant':variant, 'old':old, 'trials':rows}))


def run(output, old_stage, new_stage):
    assert not output.exists()
    rows=[]
    # Each condition has a fresh process and one unscored warmup.
    for variant,old in [(k,k=='old62') for k in GROUPS]:
        env=os.environ.copy();env['PYTHONPATH']=str(old_stage if old else new_stage)+os.pathsep+str(ROOT/'src')
        command=[sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--worker',variant]
        if old:command.append('--old')
        p=subprocess.run(command,env=env,capture_output=True,text=True,check=True,timeout=300)
        result=json.loads(p.stdout);sample=result['trials'][1:]
        assert len({r['state_sha256'] for r in sample})==1
        result['summary']={key:{'median':statistics.median(r[key] for r in sample),
                               'min':min(r[key] for r in sample),'max':max(r[key] for r in sample)}
                           for key in ('wall_seconds','cpu_seconds','peak_working_set_bytes','peak_commit_bytes','snapshot_bytes','events')}
        result['microseconds_per_event']=statistics.median(r['wall_seconds']/r['events']*1e6 for r in sample)
        rows.append(result)
        print(json.dumps({'variant':variant,'old':old,**result['summary']['wall_seconds']}),flush=True)
    assert len({q['trials'][1]['state_sha256'] for q in rows[:3]})==1
    binaries={name:hashlib.sha256((folder/'_threemind_native/_threemind_native.pyd').read_bytes()).hexdigest()
              for name,folder in (('old',old_stage),('new',new_stage))}
    output.write_text(json.dumps({'same_shared_state':True,'binaries':binaries,'results':rows},indent=2),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',choices=GROUPS);p.add_argument('--old',action='store_true')
    p.add_argument('--output',type=Path);p.add_argument('--old-stage',type=Path);p.add_argument('--new-stage',type=Path)
    a=p.parse_args()
    worker(a.worker,a.old) if a.worker else run(a.output,a.old_stage.resolve(),a.new_stage.resolve())
