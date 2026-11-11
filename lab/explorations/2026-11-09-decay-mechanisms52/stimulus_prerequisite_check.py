"""Prospective engineering checks before additional stimulus-mechanism research.

Not scientific N, not teaching of an existing individual, and not a retention
result. Runs only after the current scientific host has exited safely. Every
operation is an explicit input/advance on a separately named temporary fixture.
"""
from dataclasses import replace
from pathlib import Path
import hashlib, importlib.util, json, sys, time
import psutil
from threemind_core import Stimulus
from threemind_kernels.local52 import Local52Config,Local52Engine

ROOT=Path(__file__).resolve().parents[3]
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')
OUTPUT=ROOT/'.work/r46-stimulus-prerequisite-v1'

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
def save(name,v):
    with (OUTPUT/name).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)

def observed(core):
    state=core.capture_state().to_dict();graph=core.graph()
    assert core.capture_state().to_dict()==state,'observation mutated engineering state'
    return dict(state=state,state_hash=digest(state),graph=graph)

def immediate(config,amplitude,intensity):
    core=Local52Engine(config);birth=observed(core)
    event=Stimulus(0,((11,amplitude),(12,amplitude)),intensity=intensity)
    core.inject(event);core.advance_to(0)
    return dict(birth=birth,inputs=[event.to_dict()],after=observed(core))

def novelty(config):
    core=Local52Engine(config);birth=observed(core)
    inputs=[]
    for t,channels in [(0,((11,.8),(12,.8))),(50_000,((11,.6),(13,.6)))]:
        event=Stimulus(t,channels,intensity=1.)
        core.inject(event);core.advance_to(t);inputs.append(event.to_dict())
    pending=observed(core)
    core.advance_to(110_000)
    return dict(birth=birth,inputs=inputs,pending=pending,after=observed(core))

def by_channel(result):
    return {n['channel']:n for n in result['after']['state']['nodes']}

def target_weights(result,channels=(11,12)):
    state=result['after']['state'];ids={n['id'] for n in state['nodes'] if n['channel'] in channels}
    return sorted(e['weight'] for e in state['edges'] if e['source'] in ids and e['target'] in ids)

def main():
    host=read(WORK/'host.json')
    if psutil.pid_exists(host['pid']):
        p=psutil.Process(host['pid'])
        assert p.create_time()!=host['created_at'],'scientific host is still running; keep execution serial'
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=1920)
    assert not any((WORK/n).exists() for n in ('STOP','in-flight.json'))
    assert not OUTPUT.exists(),'preserve previous engineering outputs'
    guardpath=ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py'
    spec=importlib.util.spec_from_file_location('r46_prerequisite_resources',guardpath)
    guard=importlib.util.module_from_spec(spec);sys.modules[spec.name]=guard;spec.loader.exec_module(guard)
    guard.check_resources(WORK,limits=guard.Limits(5,4,5,25))
    OUTPUT.mkdir();started=time.monotonic();rows=[]
    save('prospective-checks.json',dict(scientific_n=0,
        purpose='Verify separate intensity, first-contact and arrival-window novelty manipulations before registration.',
        expected=['Equal-drive intensity crossing preserves immediate activation while increasing fatigue and birth weight.',
            'Removing only first_gain reduces first-contact birth weight with equal activation.',
            'Connected-endpoint birth opens an arrival window and yields greater target weight than zero local novelty gain.'],
        curves=['exponential','inverse-logarithmic','power-law'],relaxation=[True,False],
        immediate_per_channel_drive=.4,novelty_events=[[0,11,12,.8],[50000,11,13,.6]],
        novelty_readout_us=110000,wall_budget_seconds=30,permanent_source_changes=False))
    for curve in ('exponential','inverse-logarithmic','power-law'):
        for relaxation in (True,False):
            assert time.monotonic()-started<30,'engineering wall budget exceeded'
            guard.check_resources(WORK,limits=guard.Limits(5,4,5,25))
            config=Local52Config(seed=261109900,energy_seed=261109901,decay_curve=curve,
                retention_relaxation_enabled=relaxation)
            normal=immediate(config,.4,1.);strong=immediate(config,.2,2.)
            first_off=immediate(replace(config,first_gain=0.),.4,1.)
            a,b,z=by_channel(normal),by_channel(strong),by_channel(first_off)
            weights=target_weights(normal);strong_weights=target_weights(strong);off_weights=target_weights(first_off)
            strong_pass=all(a[c]['activation']==b[c]['activation'] and a[c]['fatigue']==0 and b[c]['fatigue']>0 for c in (11,12))
            strong_pass=strong_pass and len(weights)==len(strong_weights)==2 and all(s>w for s,w in zip(strong_weights,weights))
            first_pass=all(a[c]['activation']==z[c]['activation'] for c in (11,12))
            first_pass=first_pass and len(off_weights)==2 and all(w>q for w,q in zip(weights,off_weights))
            novel=novelty(config);novel_off=novelty(replace(config,local_novelty_gain=0.))
            ids={n['id'] for n in novel['pending']['state']['nodes'] if n['channel'] in (11,13)}
            pending=[e for e in novel['pending']['state']['edges'] if e['source'] in ids and e['target'] in ids]
            nw=target_weights(novel,(11,13));zw=target_weights(novel_off,(11,13))
            novelty_pass=len(pending)==2 and all(e['novelty_deadline_us'] is not None for e in pending)
            novelty_pass=novelty_pass and len(nw)==len(zw)==2 and all(x>y for x,y in zip(nw,zw))
            item=dict(curve=curve,relaxation=relaxation,strong_pass=strong_pass,first_contact_pass=first_pass,
                arrival_novelty_pass=novelty_pass,immediate_weights=dict(normal=weights,strong=strong_weights,first_gain_zero=off_weights),
                arrival_weights=dict(normal=nw,novelty_gain_zero=zw))
            save(curve+'-'+str(int(relaxation))+'.json',dict(result=item,
                fixtures=dict(normal=normal,strong=strong,first_gain_zero=first_off,novelty=novel,novelty_gain_zero=novel_off)))
            rows.append(item)
    out=dict(scientific_n=0,passed=all(r[k] for r in rows for k in ('strong_pass','first_contact_pass','arrival_novelty_pass')),
        wall_seconds=time.monotonic()-started,rows=rows,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    save('result.json',out);print(json.dumps(out))

if __name__=='__main__':main()
