"""Bounded Ocean /3 execution; inputs, process observations and sparse snapshots."""
import argparse
import gzip
import json
import os
import shutil
import time
from pathlib import Path

import psutil

from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_contact import ContactOcean, ContactProtocol
from lab.tools.ocean_evolution_cli import RecordWriter
from threemind_runtime.codec import ArtifactCodec


def save(world, folder):
    folder.mkdir(parents=True, exist_ok=False)
    context = world.capture()
    for i, engine in world.engines.items():
        (folder / f'{i}.tmind').write_bytes(ArtifactCodec.encode(engine.capture_state()))
    write_json(folder / 'manifest.json', {'context': context})


def load(folder):
    state = read_json(folder / 'manifest.json')['context']
    images = {int(i): ArtifactCodec.decode((folder / f'{i}.tmind').read_bytes()) for i in state['core_hashes']}
    return ContactOcean(state['protocol'], state=state, images=images)


def run(world, folder, seconds, *, wall_seconds=7200, guard=None, checkpoint_s=200,
        trajectory_interval_us=1000000, activity_interval_us=200000):
    if folder.exists():
        raise ValueError('new output directory required; use a continuation directory for resume')
    if round(seconds*1e6) % world.p.period_us:
        raise ValueError('duration must contain complete samples')
    if any(v <= 0 or v % world.p.period_us for v in (trajectory_interval_us, activity_interval_us)):
        raise ValueError('observation intervals must contain complete samples')
    folder.mkdir(parents=True)
    write_json(folder/'worker.json',{'pid':os.getpid(),'started_epoch':time.time()})
    write_json(folder/'protocol.json', world.p.model_dump(by_alias=True))
    write_json(folder/'observation.json', {'trajectory_interval_us':trajectory_interval_us,
        'activity_interval_us':activity_interval_us,'input_interval_us':world.p.period_us})
    save(world, folder/'initial')
    writer = RecordWriter(folder/'inputs')
    start, end = world.time_us, world.time_us + round(seconds*1e6)
    born = time.monotonic()
    checkpoint = start + round(checkpoint_s*1e6)
    living_seconds, action_square, action_samples = 0., 0., 0
    events, status, error = [], 'observing', None
    last_check, last_progress = 0., 0.
    try:
        with gzip.open(folder/'trajectory.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as trajectories, \
             gzip.open(folder/'activity.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as activity:
            def record(row):
                writer.record(row)
                events.extend(row['events'])
            while world.time_us < end:
                now = time.monotonic()
                if now-last_check > 10:
                    last_check = now
                    if guard:
                        guard()
                    if now-born > wall_seconds or (folder.parent/'STOP').exists():
                        status='paused_budget'; break
                    if (psutil.Process().memory_info().rss > 4*2**30 or psutil.virtual_memory().available < 2*2**30
                        or shutil.disk_usage('C:/').free < 5*2**30 or shutil.disk_usage('E:/').free < 15*2**30):
                        status='paused_resources'; break
                if world.time_us % trajectory_interval_us == 0:
                    m=world.metrics()
                    if abs(m['energy_balance_error']) > max(1e-4, world.totals['environment_food']*1e-8):
                        raise RuntimeError('energy accounting mismatch')
                    m['food_positions']=world.food.tolist()
                    trajectories.write(json.dumps(m,separators=(',',':'))+'\n')
                if world.time_us % activity_interval_us == 0:
                    members=[]
                    for i in sorted(i for i,b in world.bodies.items() if b.physical)[:4]:
                        e=world.engines[i]
                        channels={c for c,v in world.senses(i)[0] if v}
                        nodes=e.observation_nodes()
                        members.append({'id':i,'nodes':[{k:n[k] for k in ('id','channel','activation','inhibition')}
                                                       for n in nodes],
                                        'direct_channels':sorted(channels),'transport':e.metrics()['transport'],
                                        'action':world.action(i)})
                    activity.write(json.dumps({'time_us':world.time_us,'members':members},separators=(',',':'))+'\n')
                world.step(record)
                living_seconds += sum(b.physical for b in world.bodies.values())*world.p.period_us/1e6
                action_square += sum(sum(float(x)**2 for x in a[:2]) for a in world.last_actions.values())
                action_samples += len(world.last_actions)
                if now-last_progress>30:
                    last_progress=now
                    progress={'time_us':world.time_us,'wall_seconds':now-born,'food':sum(b.grains for b in world.bodies.values()),
                              'alive':sum(b.physical for b in world.bodies.values()),'predations':world.totals['predations'],
                              'captures':world.totals['capture_starts'],'births':world.totals['births'],
                              'max_generation':max(b.generation for b in world.bodies.values()),
                              'radius_mm':[min(b.radius for b in world.bodies.values())*1000,
                                           max(b.radius for b in world.bodies.values())*1000]}
                    staging=folder/'progress.tmp'
                    staging.write_text(json.dumps(progress),encoding='utf-8')
                    staging.replace(folder/'progress.json')
                    print(json.dumps({'case':folder.name,**progress}),flush=True)
                if world.time_us>=checkpoint:
                    writer.flush(); save(world,folder/'checkpoints'/str(world.time_us))
                    checkpoint+=round(checkpoint_s*1e6)
                if not any(b.physical for b in world.bodies.values()):
                    # Retain inactive brains in the snapshot; physical extinction is separately named.
                    status='physical_extinction'; break
            else:
                status='horizon_paused'
    except (Exception, KeyboardInterrupt) as exc:
        status,error='paused_error',f'{type(exc).__name__}: {exc}'
    writer.flush()
    save(world,folder/'final')
    write_json(folder/'events.json',events)
    result=world.metrics()|{'status':status,'error':error,'wall_seconds':time.monotonic()-born,
        'observed_us':world.time_us-start,'living_body_s':living_seconds,
        'mean_action_square':action_square/max(1,action_samples),'food_positions':world.food.tolist()}
    write_json(folder/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('template')
    r=sub.add_parser('run'); r.add_argument('protocol',type=Path); r.add_argument('output',type=Path)
    r.add_argument('--seconds',type=float,required=True); r.add_argument('--wall-seconds',type=float,default=7200)
    q=sub.add_parser('resume'); q.add_argument('state',type=Path); q.add_argument('output',type=Path)
    q.add_argument('--seconds',type=float,required=True); q.add_argument('--wall-seconds',type=float,default=7200)
    a=p.parse_args()
    if a.command=='template': print(ContactProtocol().model_dump_json(by_alias=True,indent=2)); return
    w=load(a.state) if a.command=='resume' else ContactOcean(read_json(a.protocol))
    out=run(w,a.output,a.seconds,wall_seconds=a.wall_seconds)
    print(json.dumps({k:out[k] for k in ('status','error','observed_us','wall_seconds','living_body_s')}))


if __name__=='__main__': main()
