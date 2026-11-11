"""Registered, bounded public-API experiments; no Core equations or defaults changed."""
import argparse
import gzip
import hashlib
import json
import math
import sys
from dataclasses import asdict, replace

from common import HERE, ROOT, WORK, Study, encoded, new_json, prepare, read_json

OLD = HERE.parent / '2026-09-29-input-rate-and-autonomy'
SOURCE = ROOT / '.work/internal-activity-20260929'
sys.path.append(str(OLD))
from calibrate import background, done
from world import Body, SPEC, WorldTrial, motor
from threemind_core import StateImage, Stimulus
from threemind_runtime.adapters import channel_id

SEEDS = (9293201, 9293202)
PARENTS = tuple((seed, arm) for seed in SEEDS for arm in ('region0', 'region1'))
LOCAL = ('normal', 'sham', 'task_edges', 'matched_edges', 'returns', 'restore', 'off')
PROTOCOLS = ('none', 'single_high', 'single_ordinary', 'massed_ordinary', 'spaced_ordinary',
             'massed_weak', 'spaced_weak', 'spaced_no_consolidation')

def name(seed, arm): return f's{seed}/{arm}'

def gzread(path): return json.loads(gzip.decompress(path.read_bytes()))

def gzwrite(path, value):
    with gzip.open(path, 'xb') as f: f.write(encoded(value))

def old_case(key):
    folder = SOURCE / 'cases' / key
    value = read_json(folder / 'result.json')
    image = StateImage(gzip.decompress((folder / 'parent-state.json.gz').read_bytes()))
    assert image.digest == value['state_sha256']
    return value | {'image': image, 'external_project': 'df63c577-3b39-4642-87c5-2e9e1b05f165'}

def warm(seed, arm): return old_case('warm/' + name(seed, arm))

def learned(seed, arm, history):
    return old_case(f'experience/{name(seed, arm)}/{history}/normal')

def symbols(seed):
    return {c: channel_id(seed, SPEC['sensory_namespace'], i) for c, i in zip('ABCD', (0, 1, 4, 5))}

def features(seed): return [channel_id(seed, 'texture-autonomy-study/1', i) for i in range(8)]

def edges(image): return [(e['source'], e['target']) for e in image.to_dict()['edges']]

def change(c, changes=None, *, action=None, targets=(), label):
    before = c.engine.capture_state()
    if changes is not None: c.engine.reconfigure(replace(c.engine.config, **changes))
    applied = []
    if action:
        valid = set(edges(before))
        applied = [tuple(e) for e in targets if tuple(e) in valid]
        c.engine.intervene(edges=applied, action=action)
    c.events.append({'key': f'research:{len(c.events)}:{label}', 'kind': 'research_intervention',
        'time_us': str(c.engine.time_us), 'payload': {'label': label, 'changes': changes, 'action': action,
        'requested_edges': list(targets), 'applied_edges': applied,
        'before': before.digest, 'after': c.engine.capture_state().digest}})
    return applied

def task_edges(image, channels):
    ids = {n['channel']: n['id'] for n in image.to_dict()['nodes']}
    a, b, d = (ids.get(channels[x]) for x in 'ABD')
    return [e for e in edges(image) if e in ((a, b), (b, a), (a, d), (d, a))]

def matched_edges(image, target, forbidden_nodes=()):
    by = {(e['source'], e['target']): e for e in image.to_dict()['edges']}
    available = set(by) - set(target)
    available = {e for e in available if not set(e) & set(forbidden_nodes)}
    selected, errors = [], []
    for edge in target:
        if not available: break
        ref = by[edge]
        score = lambda e: (abs(by[e]['weight']-ref['weight'])+abs(by[e]['stability']-ref['stability']), e)
        chosen = min(available, key=score)
        errors.append(score(chosen)[0]); selected.append(chosen); available.remove(chosen)
    assert len(selected) == len(target)
    return selected, errors

def intervene(c, condition, channels):
    image = c.engine.capture_state()
    ids = {n['channel']: n['id'] for n in image.to_dict()['nodes']}
    target = task_edges(image, channels)
    metadata = {'condition': condition, 'task_edges': target}
    if condition == 'sham':
        change(c, {}, label='sham')
        assert c.engine.capture_state().digest == image.digest
    elif condition == 'off':
        change(c, {'propagation_rate': 0, 'inhibition_diffusion_rate': 0}, label='all-communication-off')
    elif condition == 'returns':
        target = [e for e in edges(image) if e[1] == ids.get(channels['A'])]
        change(c, action='silence', targets=target, label='returns-to-cue-off')
    elif condition == 'matched_edges':
        target, errors = matched_edges(image, target, [ids.get(channels[k]) for k in 'ABD'])
        metadata['matching_errors'] = errors
        change(c, action='silence', targets=target, label='matched-edge-silence')
    elif condition in ('task_edges', 'restore'):
        change(c, action='silence', targets=target, label='task-edge-silence')
        if condition == 'restore': change(c, action='unsilence', targets=target, label='task-edge-restore')
    metadata['selected_edges'] = target
    return metadata

class Trial(WorldTrial):
    def step(self, target):
        if target > background(self.seed)[1][-1]:
            raise RuntimeError('registered telemetry replay coverage exhausted')
        return super().step(target)

def finish(c, metadata):
    energy = c.engine.capture_state().to_dict()['energy']
    assert energy['unserved_total'] == 0
    if c.engine.life == 'dead': raise RuntimeError('unexpected death: retain case and stop stage')
    return c.finish(metadata | {'energy': energy})

def probe(study, key, parent, cue, *, condition='normal', born=False, sequence=False, second=False, extra=None):
    if saved := done(study, key): return saved
    seed = parent['seed']
    c = Trial(study, key, seed, parent=parent, inherited=born)
    initial = c.engine.capture_state()
    channels = symbols(seed)
    intervention = intervene(c, condition, channels)
    start = c.engine.time_us
    body, rows, carriers = Body(.3125), [], []
    if cue: carriers.append(c.send(cue, .5, source='manual-probe'))
    c.step(start)
    while c.engine.time_us < start + 15_000_000:
        elapsed = c.engine.time_us - start
        if sequence and second and elapsed == 500_000:
            carriers.append(c.send([channels['B']], .5, source='manual-probe'))
            c.step(c.engine.time_us)
        nodes = c.engine.observation_nodes()
        control = motor(seed, nodes)
        rows.append({'relative_us': elapsed, 'nodes': nodes, 'control': control, 'body': asdict(body)})
        dt = 10_000 if elapsed < 2_000_000 else 100_000
        body.move(control, dt/1e6)
        c.advance(c.engine.time_us + dt)
    nodes = c.engine.observation_nodes()
    rows.append({'relative_us': 15_000_000, 'nodes': nodes, 'control': motor(seed,nodes), 'body': asdict(body)})
    gzwrite(c.folder/'behavior.json.gz', {'rows': rows, 'carriers': carriers, 'final_body': asdict(body)})
    return finish(c, {'stage': 'probe', 'start_state': initial.digest, 'begin_us': start,
        'cue': cue, 'sequence': sequence, 'second': second, 'born': born, 'intervention': intervention,
        'channels': channels, 'parent': parent['id'], **(extra or {})})

def localize(study):
    for seed, arm in PARENTS:
        for history in ('P','Q'):
            parent = learned(seed, arm, history)
            for condition in LOCAL:
                for cue in ('A','none'):
                    key=f'local/{name(seed,arm)}/{history}/{condition}/{cue}'
                    probe(study,key,parent,[] if cue=='none' else [symbols(seed)['A']],condition=condition,born=True,
                          extra={'family':'local','history':history,'arm':arm,'cue_name':cue})
        print(json.dumps({'stage':'local','parent':name(seed,arm),'done':True}),flush=True)

def schedule(protocol):
    if protocol=='none': return []
    if protocol.startswith('single'): return [(128, 1.0 if protocol.endswith('high') else .4)]
    times = list(range(119,129)) if protocol.startswith('massed') else [0,1,2,4,8,16,32,64,96,128]
    return [(t,.1 if protocol.endswith('weak') else .4) for t in times]

def train_memory(study, seed, protocol):
    key=f'memory/s{seed}/{protocol}/train'
    if saved:=done(study,key): return saved
    c=Trial(study,key,seed,parent=warm(seed,'region0'),inherited=False)
    begin=c.engine.time_us
    if protocol=='spaced_no_consolidation':
        change(c,{'edge_consolidation_enabled':False},label='positive-existing-edge-updates-off')
    for t,dose in schedule(protocol):
        c.advance(begin+round(t*1e6))
        c.pulse([symbols(seed)[x] for x in 'AD'],dose,0,source='controlled-experience')
    c.advance(begin+129_000_000)
    if protocol=='spaced_no_consolidation':
        change(c,{'edge_consolidation_enabled':True},label='restore-consolidation-for-retention')
    return finish(c,{'stage':'memory-training','protocol':protocol,'begin_us':begin,
                     'last_training_us':begin+128_000_000,'age_s':1,'schedule':schedule(protocol)})

def wait_memory(study,parent,age):
    if age==1: return parent
    key=parent['key'].rsplit('/',1)[0]+f'/age{age}'
    if saved:=done(study,key): return saved
    c=Trial(study,key,parent['seed'],parent=parent,inherited=False)
    c.advance(parent['extra']['last_training_us']+age*1_000_000)
    return finish(c,{'stage':'memory-wait','protocol':parent['extra']['protocol'],
                    'last_training_us':parent['extra']['last_training_us'],'age_s':age})

def memory(study):
    for seed in SEEDS:
        for protocol in PROTOCOLS:
            trained=train_memory(study,seed,protocol)
            for age in (1,30,300):
                parent=wait_memory(study,trained,age)
                conditions=[(False,'normal')]+([(True,k) for k in ('normal','returns','off')] if age==300 else [])
                for born,condition in conditions:
                    for cue in ('A','none'):
                        key=f'memory-probe/s{seed}/{protocol}/age{age}/{"birth" if born else "live"}/{condition}/{cue}'
                        probe(study,key,parent,[] if cue=='none' else [symbols(seed)['A']],condition=condition,born=born,
                              extra={'family':'memory','protocol':protocol,'age_s':age,'cue_name':cue})
            print(json.dumps({'stage':'memory','seed':seed,'protocol':protocol,'done':True}),flush=True)

def sequence(study):
    for seed,arm in PARENTS:
        for history in ('P','Q'):
            for condition in ('normal','off'):
                for first in (False,True):
                    for second in (False,True):
                        key=f'sequence/{name(seed,arm)}/{history}/{condition}/{int(first)}{int(second)}'
                        probe(study,key,learned(seed,arm,history),[symbols(seed)['A']] if first else [],
                              condition=condition,born=True,sequence=True,second=second,
                              extra={'family':'sequence','history':history,'arm':arm,'first':first})
        print(json.dumps({'stage':'sequence','parent':name(seed,arm),'done':True}),flush=True)

def sensation(body, seed, at, environment):
    pair=(('AB','CD') if environment=='P' else ('AD','CB'))[body.region]
    channels=[(symbols(seed)[s],1.0) for s in pair]
    if body.v:
        channels.append((channel_id(seed,SPEC['sensory_namespace'],8+int(body.v<0)),math.tanh(abs(body.v)/SPEC['velocity_scale'])))
    return Stimulus(at,tuple(channels),.8)

def environment_stage(study,seed,arm,route,stage,parent,body):
    key=f'environment/{name(seed,arm)}/{route}/stage{stage}'
    if saved:=done(study,key): return saved,Body(**saved['extra']['final_body'])
    c=Trial(study,key,seed,parent=parent,inherited=False)
    start=c.engine.time_us
    rows,senses=[],[]
    for elapsed in range(0,30_000_000,100_000):
        if elapsed%1_000_000==0:
            stim=sensation(body,seed,c.engine.time_us,route[stage-1])
            c.send_stimulus(stim,source='controlled-environment',payload={'frames':[stim.to_dict()],
                'body':asdict(body),'environment':route[stage-1],'adapter_version':'ring-paired-texture/1'})
            senses.append(stim.to_dict())
        c.step(c.engine.time_us)
        nodes=c.engine.observation_nodes();control=motor(seed,nodes)
        rows.append({'relative_us':elapsed,'nodes':nodes,'control':control,'body':asdict(body),'region':body.region})
        body.move(control,.1)
        c.advance(start+elapsed+100_000)
    gzwrite(c.folder/'behavior.json.gz',{'rows':rows,'senses':senses,'final_body':asdict(body)})
    result=finish(c,{'stage':'environment','route':route,'phase':stage,'arm':arm,'begin_us':start,
                    'final_body':asdict(body),'parent':parent['id']})
    return result,body

def environment(study):
    for seed,arm in PARENTS:
        for route in ('PPP','PQP','QQQ','QPQ'):
            parent,body=warm(seed,arm),Body(.3125)
            for stage in (1,2,3):
                parent,body=environment_stage(study,seed,arm,route,stage,parent,body)
                for born in ((False,True) if stage==2 else (False,)):
                    for cue in ('A','none'):
                        key=f'environment-probe/{name(seed,arm)}/{route}/stage{stage}/{"birth" if born else "live"}/{cue}'
                        probe(study,key,parent,[] if cue=='none' else [symbols(seed)['A']],born=born,
                              extra={'family':'environment','route':route,'phase':stage,'arm':arm,'cue_name':cue})
        print(json.dumps({'stage':'environment','parent':name(seed,arm),'done':True}),flush=True)

def pattern(seed,round_index):
    indices=((0,1,2,3),(0,1,2,4),(0,1,4,5),(4,5,6,7))[round_index]
    return [features(seed)[i] for i in indices]

def primer(study,seed):
    key=f'novelty/s{seed}/primer'
    if saved:=done(study,key): return saved
    c=Trial(study,key,seed,parent=warm(seed,'region0'),inherited=False)
    for ch in features(seed): c.pulse([ch],.2,1_000_000,source='texture-registration')
    for _ in range(10): c.pulse(pattern(seed,0),.4,1_000_000,source='texture-familiarization')
    return finish(c,{'stage':'texture-primer','features':features(seed)})

def novelty_stage(study,seed,condition,index,parent):
    key=f'novelty/s{seed}/{condition}/round{index}'
    if saved:=done(study,key): return saved
    c=Trial(study,key,seed,parent=parent,inherited=False)
    if condition=='novelty_off': change(c,{'local_novelty_gain':0},label='local-novelty-gain-off')
    channels=pattern(seed,index)
    before=c.engine.capture_state().to_dict()
    gzwrite(c.folder/'before-training.json.gz',before)
    first=[]
    for i in range(10):
        c.pulse(channels,.4,0,source='controlled-texture')
        if i==0:
            for _ in range(100):
                nodes=c.engine.observation_nodes()
                first.append({'relative_us':len(first)*10_000,'nodes':nodes,'control':motor(seed,nodes)})
                c.advance(c.engine.time_us+10_000)
        else: c.advance(c.engine.time_us+1_000_000)
    pre=c.engine.capture_state()
    gzwrite(c.folder/'before-erasure.json.gz',pre.to_dict())
    ids={n['id'] for n in pre.to_dict()['nodes'] if n['channel'] in channels}
    targets=[e for e in edges(pre) if set(e)<=ids]
    errors=[]
    if condition in ('erase','matched_erase'):
        if condition=='matched_erase': targets,errors=matched_edges(pre,targets,ids)
        change(c,action='disconnect_edges',targets=targets,label='post-experience-'+condition)
    gzwrite(c.folder/'first-response.json.gz',{'rows':first})
    return finish(c,{'stage':'novelty','condition':condition,'round':index,'channels':channels,
        'edges_selected':targets,'matching_errors':errors,'parent':parent['id']})

def novelty(study):
    for seed in SEEDS:
        initial=primer(study,seed)
        for condition in ('intact','erase','matched_erase','novelty_off'):
            parent=initial
            for index in range(4):
                parent=novelty_stage(study,seed,condition,index,parent)
                for cue in ('fixed','current','none'):
                    channels=[] if cue=='none' else pattern(seed,0 if cue=='fixed' else index)
                    key=f'novelty-probe/s{seed}/{condition}/round{index}/{cue}'
                    probe(study,key,parent,channels,extra={'family':'novelty','condition':condition,
                        'round':index,'cue_name':cue})
            print(json.dumps({'stage':'novelty','seed':seed,'condition':condition,'done':True}),flush=True)

def register():
    prepare()
    hashes={}
    sources=list(HERE.glob('*.py'))+list(HERE.glob('design.*.md'))+[OLD/n for n in ('world.py','calibrate.py')]
    for path in sources:
        target=WORK/'frozen-tools'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
        hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    new_json(WORK/'registration.json',{'criteria':'autonomy-criteria/1','parents':PARENTS,'files':hashes,
        'background_sha256':background(SEEDS[0])[2],'kernel_changed':False,'schedules':{k:schedule(k) for k in PROTOCOLS},
        'expected_cases':722,'minimum_effect':.0001})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('register','local','memory','sequence','environment','novelty'))
    cmd=parser.parse_args().command
    if cmd=='register': return register()
    study=Study()
    try: {'local':localize,'memory':memory,'sequence':sequence,'environment':environment,'novelty':novelty}[cmd](study)
    except Exception as exc:
        if study.active_case: study.active_case.finish({'budget_stop':True,'error':str(exc)})
        raise
    finally: study.db.close()

if __name__=='__main__': main()
