"""Declared context experiments with genuine /5.1; no production modifications."""
from __future__ import annotations

import argparse
import copy
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid5

import httpx
import numpy as np
import psutil
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'lab/explorations/2026-10-16-mechanism-discovery'))
import pilot_m2 as base
from lab.tools.calibrated_activity import CalibratedActivity

WORK = Path('E:/ThreeMindData/experiments/2026-11-09-context-revision/v1')
RESOURCE = 'context-revision-20261109-v1'
NS = UUID('91193156-48d6-5cda-a497-4ad5f71fb72c')
N = 8
SEED = 26110900
INDEX = np.rint(np.linspace(0, 19, 8)).astype(int).tolist()
PORTS = dict(sound=('S0', 'S1'), vision=('V0', 'V1'), action=('A0', 'A1', 'AO'))
WORDS = dict(sound=('sound-0', 'sound-1'), vision=('view-0', 'view-1'), action=('exit-0', 'exit-1', 'observe'))
SYMBOLS = ('K', 'N', 'Z0', 'Z1', 'Z2', 'Z3', 'W', 'X0', 'X1', 'D0', 'D1', 'S0', 'S1', 'V0', 'V1', 'A0', 'A1', 'AO')
ARMS = ('intact', 'sham', 'target', 'matched', 'restored', 'view-blocked', 'forced-view')
POLICY = dict(reserve_gib=dict(commit=5, ram=4, system_disk=5, data_disk=25),
              private_bytes=3*2**30, originals_bytes=2*2**30, wall_seconds=14400,
              startup_commit_bytes=8*2**30, poll_seconds=1, pause='complete-boundary-only')


def ident(s): return uuid5(NS, s)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
    raw = Path(p).read_bytes()
    return json.loads(gzip.decompress(raw) if str(p).endswith('.gz') else raw)
def save(p, v): return base.original(Path(p), v, compressed=str(p).endswith('.gz'))
def tup(v): return tuple(tup(x) for x in v) if isinstance(v, list) else v


def tensor_hash(value):
    h = hashlib.sha256()
    def visit(x):
        if torch.is_tensor(x):
            a = x.detach().cpu().contiguous()
            h.update(str(a.dtype).encode()); h.update(str(tuple(a.shape)).encode()); h.update(a.numpy().tobytes())
        elif isinstance(x, dict):
            for k in sorted(x, key=str): h.update(str(k).encode()); visit(x[k])
        elif isinstance(x, (list, tuple)):
            h.update(str(len(x)).encode())
            for v in x: visit(v)
        else: h.update(base.encoded(x))
    visit(value)
    return h.hexdigest()


def deterministic():
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)


class Student:
    def __init__(self, seed, identity):
        self.seed, self.identity = seed, identity
        self.rng = random.Random(seed)
        self.mapping = dict(zip(SYMBOLS, self.rng.sample(range(1, 2**32), len(SYMBOLS))))
        self.core = base.create_engine(base.Local51Config(seed=seed, energy_seed=seed ^ 0x1634AB),
                                      kernel_id=base.KERNEL, backend='native')
        self.adapters = {k: CalibratedActivity([self.mapping[x] for x in ports], WORDS[k], identity+':'+k,
                                               seed=seed+j) for j, (k, ports) in enumerate(PORTS.items())}
        self.next_background = 0
        self.input_digest, self.input_count = base.digest([]), 0
        self.recent, self.samples = [], []
        self.world = dict(kind='two-context-world/1', actual=None, observed=False, exit=None, query_used=False)
        self.cursor, self.parent = dict(stage='birth'), None
        self.adapter_refs, self.frozen_digest = {}, None
        self.activity_sum, self.activity_n = {s: 0. for s in SYMBOLS}, 0
        self.calibration_valid = False

    def adapter_digest(self):
        return tensor_hash({k: [r.state_dict(), r.optimizer.state_dict(), r.learning_rng,
                               r.computed_updates, r.committed_updates] for k, r in self.adapters.items()})

    def state(self):
        return dict(schema='threemind.context-whole/1', seed=self.seed, identity=self.identity,
                    core=self.core.capture_state().to_dict(), mapping=self.mapping,
                    rng=json.loads(base.encoded(self.rng.getstate())), torch_rng=torch.get_rng_state().tolist(),
                    next_background=self.next_background, input_digest=self.input_digest, input_count=self.input_count,
                    recent=copy.deepcopy(self.recent), samples=copy.deepcopy(self.samples), world=copy.deepcopy(self.world),
                    cursor=copy.deepcopy(self.cursor), parent=copy.deepcopy(self.parent), adapter_refs=self.adapter_refs,
                    adapter_digest=self.adapter_digest(), frozen_digest=self.frozen_digest,
                    activity_sum=self.activity_sum.copy(), activity_n=self.activity_n,
                    calibration_valid=self.calibration_valid,
                    body=dict(type='discrete-observation-and-exit', state=copy.deepcopy(self.world)),
                    actuator=dict(outputs=list(WORDS['action']), last=self.world.get('exit')))

    def checkpoint(self, work, path):
        digest = self.adapter_digest()
        if not self.adapter_refs or next(iter(self.adapter_refs.values()))['bundle_digest'] != digest:
            refs = {}
            for k, r in self.adapters.items():
                rel = f'adapters/{digest}/{k}'
                folder = work/rel
                if not folder.exists(): r.save(folder)
                refs[k] = dict(path=rel, bundle_digest=digest, files={p.name: sha(p) for p in folder.iterdir()})
            self.adapter_refs = refs
        return save(work/path, self.state())

    @classmethod
    def restore(cls, work, value):
        s = cls.__new__(cls)
        for k in ('seed', 'identity', 'mapping', 'next_background', 'input_digest', 'input_count', 'recent', 'samples',
                  'world', 'cursor', 'parent', 'adapter_refs', 'frozen_digest', 'activity_sum', 'activity_n', 'calibration_valid'):
            setattr(s, k, copy.deepcopy(value[k]))
        s.core = base.create_engine(state=base.StateImage.from_dict(value['core']), kernel_id=base.KERNEL, backend='native')
        s.rng = random.Random(); s.rng.setstate(tup(value['rng']))
        s.adapters = {}
        for k, ref in value['adapter_refs'].items():
            for name, expected in ref['files'].items():
                if sha(work/ref['path']/name) != expected: raise RuntimeError('adapter original changed')
            s.adapters[k] = CalibratedActivity.restore(work/ref['path'])
        torch.set_rng_state(torch.tensor(value['torch_rng'], dtype=torch.uint8))
        if base.digest(s.state()) != base.digest(value): raise RuntimeError('whole-state restoration mismatch')
        return s

    def inject(self, t, values, events):
        row = dict(time_us=t, channels=[[self.mapping[k], float(v)] for k, v in values.items()], intensity=1.)
        self.core.inject(base.Stimulus(t, tuple(tuple(x) for x in row['channels']), 1.))
        self.input_digest = base.digest([self.input_digest, row]); self.input_count += 1
        events.append(row)

    def advance(self, end, events):
        if end < self.core.time_us: raise RuntimeError('simulation reversal')
        while self.next_background <= end:
            self.inject(self.next_background, {'K': .2}, events)
            self.next_background += 500_000
        self.core.advance_to(end)
        if self.core.life == 'dead': raise RuntimeError('new subject death; retain in-flight')

    def window(self, values, *, observed=False):
        start = self.core.time_us; events = []
        self.advance(start, events)  # background precedes simultaneous declared task event
        if values: self.inject(start, values, events)
        frames = {k: [] for k in PORTS}; raw = []
        for i in range(20):
            self.advance(start+(i+1)*50_000, events)
            nodes = self.core.observation_nodes()
            if any(n['channel'] not in self.mapping.values() for n in nodes):
                raise RuntimeError('undeclared anonymous port')
            by = {n['channel']: n for n in nodes}
            raw.append({name: {f: by.get(c, {}).get(f, 0.) for f in ('activation','inhibition','direct','associative')}
                        for name, c in self.mapping.items()})
            for k, r in self.adapters.items():
                declared = [n for n in nodes if n['channel'] in r.layout.index]
                frames[k].append(r.layout.frame(dict(nodes=declared)).tolist())
            if observed:
                before = self.core.capture_state().to_dict()
                self.core.metrics(); self.core.graph(); self.core.observation_nodes(); self.core.capture_state()
                if before != self.core.capture_state().to_dict(): raise RuntimeError('observation altered Core')
        logits = {k: r.predict([[frames[k][i] for i in INDEX]])[0].tolist() for k, r in self.adapters.items()}
        result = dict(start_us=start, end_us=self.core.time_us, events=events, frames=frames, raw=raw,
                      frame_times_us=[start+(i+1)*50_000 for i in range(20)], indices=INDEX,
                      logits=logits, predictions={k: int(np.argmax(v)) for k, v in logits.items()})
        self.recent = (self.recent+[copy.deepcopy(result)])[-2:]
        if self.frozen_digest and self.adapter_digest() != self.frozen_digest: raise RuntimeError('frozen adapter changed')
        return result

    def lesson(self, cues, category, amplitude=.4):
        start = self.core.time_us; events = []
        outputs = ('AO',) if category == 2 else (f'S{category}', f'V{category}', f'A{category}')
        for i in range(5):
            t = start+i*250_000; self.advance(t, events)
            self.inject(t, dict.fromkeys(tuple(cues)+outputs, amplitude), events)
            for j in range(1,6):
                self.advance(t+j*50_000,events)
                by={n['channel']:n for n in self.core.observation_nodes()}
                for name,c in self.mapping.items():self.activity_sum[name]+=by.get(c,{}).get('activation',0.)
                self.activity_n+=1
        self.advance(start+1_500_000, events)
        return dict(start_us=start, end_us=self.core.time_us, cues=list(cues), category=category, events=events,
                    teacher_control=True, outputs=list(outputs), amplitude=amplitude)


def old_pairs(): return [(('Z0',),0), (('Z1',),1), (('Z2',),0), (('Z3',),1), (('W',),2)]


def new_pairs(history):
    return old_pairs()+[(('X0',),history),(('X1',),1-history),(('D0',),0),(('D1',),1),
                        (('Z0','Z1'),2),(('X0','X1'),2)]


def teach(s, pairs, initial, *, errors=()):
    start = s.core.time_us; rows = []; waits = []; correction_asks = []
    for e in errors:
        q = s.window(e['values']); correction_asks.append(dict(case=e, question=q))
        rows.append(s.lesson(e['cues'], e['label']))
        rows.append(s.lesson(e['cues'], e['label'], .36))
    dense = 8 if initial else 2
    for cycle in range(dense+3):
        gap = 0 if cycle < dense else (2,6,18)[cycle-dense]
        events=[]; begin=s.core.time_us; s.advance(begin+gap*1_000_000,events)
        waits.append(dict(start_us=begin,end_us=s.core.time_us,events=events))
        order = copy.deepcopy(pairs); s.rng.shuffle(order)
        for cues,label in order:
            rows.append(s.lesson(cues,label))
            if len(cues)==2 and label==2:
                actual = (cycle+s.seed) % 2
                s.world.update(actual=actual,observed=True,query_used=True,exit=2)
                rows.append(s.lesson((f'D{actual}',),actual))
    return dict(start_us=start,end_us=s.core.time_us,initial=initial,dense_cycles=dense,
                waits=waits,lessons=rows,correction_questions=correction_asks)


def calibration_cases(seed, stage, dev=False):
    rng=random.Random(seed+301+stage)
    dose=(.72,.88) if dev else (.7,.8,.9)
    rows=[]
    for cues,label in old_pairs():
        for d in dose:
            for _ in range(1 if dev else (4 if label==2 else 2)):
                rows.append(dict(cues=list(cues),values=dict.fromkeys(cues,d),label=label))
    rng.shuffle(rows)
    return rows


def calibrate_unit(s, stage, previous):
    teaching=teach(s,old_pairs(),stage==0,errors=previous.get('errors',[]) if previous else [])
    samples=[]
    for e in calibration_cases(s.seed,stage): samples.append(dict(case=e,question=s.window(e['values'])))
    s.samples.extend(samples)
    if len(s.samples)>1024: raise RuntimeError('registered calibration capacity')
    before=s.core.capture_state().to_dict();fits={}
    for k,r in s.adapters.items():
        usable=[a for a in s.samples if k=='action' or a['case']['label']<2]
        fits[k]=r.continue_calibration([[a['question']['frames'][k][i] for i in INDEX] for a in usable],
                                       [a['case']['label'] for a in usable],steps=1200)
    if before!=s.core.capture_state().to_dict(): raise RuntimeError('fitting altered simulation')
    dev=[];errors=[]
    for e in calibration_cases(s.seed,stage,True):
        q=s.window(e['values']); heads=('action',) if e['label']==2 else tuple(PORTS)
        correct=all(q['predictions'][k]==e['label'] for k in heads)
        dev.append(dict(case=e,question=q,correct=correct))
        if not correct: errors.append(e)
    fraction=sum(x['correct'] for x in dev)/len(dev)
    s.calibration_valid=fraction>=.9
    return dict(teaching=teaching,new_samples=samples,fits=fits,development=dev,errors=errors,
                correct=sum(x['correct'] for x in dev),n=len(dev),ready=not errors,valid=s.calibration_valid)


def materials(seed, history, final):
    rng=random.Random(seed+4400+(0 if final else 900))
    doses=(.76,.84) if final else (.72,.88)
    rows=[]
    for j in range(4):
        rows.append(dict(kind='old',cue=f'Z{j}',expected=j%2,actual=j%2,dose=doses[j%2],distractor=0.))
    for j in range(8 if final else 4):
        cue=j%2;expected=cue^history;conflict=(j//2)%2
        rows.append(dict(kind='clear',cue=f'X{cue}',expected=expected,actual=expected^conflict,
                         conflict=bool(conflict),dose=doses[(j//4)%2],distractor=.04 if final and j>=4 else 0.))
    for j in range(12 if final else 4):
        rows.append(dict(kind='ambiguous',cue='mixed',expected=2,actual=j%2,dose=doses[(j//2)%2],
                         distractor=.04 if final and j>=6 else 0.))
    rng.shuffle(rows)
    for j,r in enumerate(rows):r['id']=('final' if final else 'development')+f'-{j:03d}'
    return rows


def sensory(case):
    dose=case['dose']-case['distractor']
    values={'X0':dose/2,'X1':dose/2} if case['kind']=='ambiguous' else {case['cue']:dose}
    if case['distractor']:values['N']=case['distractor']
    return values


def feedback(world, action, mode):
    # Environment function receives only physical world and action; no correct-answer or history argument.
    show=world['automatic_view'] or mode=='forced-view' or action==2
    if mode=='view-blocked' and not world['automatic_view']:show=False
    return {f"D{world['actual']}":world['view_strength']} if show else {}


def trial(s,case,mode='intact',observed=False):
    start=s.core.time_us
    s.world=dict(kind='two-context-world/1',actual=case['actual'],automatic_view=case['kind']=='clear',
                 view_strength=case['dose'],observed=False,exit=None,query_used=False)
    first=s.window(sensory(case),observed=observed);action=first['predictions']['action']
    s.world['query_used']=action==2;s.world['exit']=action
    values=feedback(s.world,action,mode) if case['kind']!='old' else {}
    s.world['observed']=bool(values)
    second=s.window(values,observed=observed);s.world['exit']=second['predictions']['action']
    events=[];s.advance(s.core.time_us+1_000_000,events)
    return dict(case=case,mode=mode,start_us=start,end_us=s.core.time_us,first=first,second=second,
                world=copy.deepcopy(s.world),feedback=values,tail_events=events)


def new_unit(s,history,stage,previous):
    errors=[]
    if previous:
        for r in previous['development']:
            c=r['case'];p=r['first']['predictions'];e=c['expected']
            heads=('action',) if e==2 else tuple(PORTS)
            if any(p[k]!=e for k in heads):
                errors.append(dict(cues=['X0','X1'] if c['kind']=='ambiguous' else [c['cue']],
                                   values=sensory(c),label=e))
    teaching=teach(s,new_pairs(history),stage==0,errors=errors)
    dev=[trial(s,c) for c in materials(s.seed,history,False)]
    def good(r):
        c=r['case'];p=r['first']['predictions'];q=r['second']['predictions'];e=c['expected']
        if e==2:return p['action']==2 and all(q[k]==c['actual'] for k in PORTS)
        return all(p[k]==e for k in PORTS) and (c['kind']=='old' or all(q[k]==c['actual'] for k in PORTS))
    return dict(teaching=teaching,development=dev,ready=all(good(r) for r in dev),correct=sum(map(good,dev)),n=len(dev))


def intervention(s,arm):
    before=s.core.capture_state().to_dict();g=s.core.graph()
    by={n['channel']:n['id'] for n in g['nodes']};reverse={n['id']:k for k,c in s.mapping.items() for n in g['nodes'] if n['channel']==c}
    outs={by[s.mapping[x]] for p in PORTS.values() for x in p if s.mapping[x] in by}
    selected={}
    for key,names in [('target',('X0','X1','D0','D1')),('matched',('Z0','Z1','Z2','Z3'))]:
        ids={by[s.mapping[x]] for x in names if s.mapping[x] in by}
        selected[key]=[e for e in g['edges'] if e['source'] in ids and e['target'] in outs]
    def degree(es):
        return sorted([[sum(e['source']==n for e in g['edges']),sum(e['target']==n for e in g['edges'])]
                       for edge in es for n in (edge['source'],edge['target'])])
    def mean(es,key):
        if not es:return None
        if key=='weight':return float(np.mean([e['weight'] for e in es]))
        return float(np.mean([s.activity_sum[reverse[e['source']]]/max(1,s.activity_n) for e in es]))
    wt={k:mean(es,'weight') for k,es in selected.items()};act={k:mean(es,'activity') for k,es in selected.items()}
    wr=abs(wt['target']-wt['matched']) if all(v is not None for v in wt.values()) else None
    ar=abs(act['target']-act['matched']) if all(v is not None for v in act.values()) else None
    valid=bool(selected['target']) and len(selected['target'])==len(selected['matched']) and degree(selected['target'])==degree(selected['matched']) and wr<=.05 and ar<=.05
    es=selected['matched' if arm=='matched' else 'target'] if arm in ('target','matched','restored') else []
    pairs=[[e['source'],e['target']] for e in es]
    if pairs:s.core.intervene(edges=pairs,action='silence')
    if arm=='restored' and pairs:s.core.intervene(edges=pairs,action='restore')
    after=s.core.capture_state().to_dict()
    a,b=copy.deepcopy(before),copy.deepcopy(after);a.pop('silenced_edges',None);b.pop('silenced_edges',None)
    if a!=b:raise RuntimeError('intervention changed undeclared fields')
    if arm in ('restored','sham','intact') and before!=after:raise RuntimeError('restoration is not exact')
    return dict(arm=arm,pairs=pairs,target=selected['target'],matched=selected['matched'],weight_residual=wr,
                activity_residual=ar,degrees={k:degree(v) for k,v in selected.items()},matching_valid=valid,
                before_core_sha256=base.digest(before),after_core_sha256=base.digest(after))


class Guard(base.Guard):
    def watch(self):
        while not self.stop.is_set():
            try:
                self.last=base.resource_check(self.work);private=psutil.Process().memory_info().private
                self.peak_private=max(self.peak_private,private)
                for k,v in self.last['available_bytes'].items():self.minimum[k]=min(v,self.minimum.get(k,v))
                if private>POLICY['private_bytes']:raise RuntimeError('3 GiB private host budget')
                if time.monotonic()-self.started>POLICY['wall_seconds']:raise RuntimeError('4 hour host budget')
            except Exception as exc:
                try:
                    with (self.work/'STOP').open('x',encoding='utf-8') as f:json.dump(dict(reason=str(exc),epoch=time.time(),last=self.last,policy=POLICY),f)
                except FileExistsError:pass
                return
            self.stop.wait(1)


def connection():
    base.load_env();db=urlsplit(os.environ.get('THREEMIND_DATABASE_URL',''))
    if db.hostname not in ('localhost','127.0.0.1','::1') or db.port!=5433:raise RuntimeError('local database required')
    return base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai')


def manifest():
    paths=[p for p in HERE.iterdir() if p.name in ('experiment.py','analyze.py','test_apparatus.py','protocol.zh.md','protocol.en.md')]
    paths+=[ROOT/p for p in ('lab/tools/activity_controller.py','lab/tools/calibrated_activity.py','lab/tools/study_lock.py',
                             'lab/explorations/2026-10-16-mechanism-discovery/pilot_m2.py',
                             'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py','docs/zh/training-protocol.md')]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}


def frozen(work):
    for rel,h in load(work/'runner-manifest.json').items():
        if sha(ROOT/rel)!=h:raise RuntimeError('frozen source differs '+rel)
    if base.capture_implementation('native')!=load(work/'implementation.json'):raise RuntimeError('implementation differs')


def prepare(work):
    work.mkdir(parents=True,exist_ok=True)
    with base.worker_lock(work),connection() as c:
        if (work/'platform.json').exists():raise RuntimeError('already registered')
        rsc=base.resource_check(work)
        if rsc['available_bytes']['commit']<POLICY['startup_commit_bytes'] or rsc['available_bytes']['data_disk']<31*2**30:raise RuntimeError('startup allowance')
        receipt=load(work/'instrument/verified.json')
        instrument=load(work/receipt['summary'])
        if sha(work/receipt['summary'])!=receipt['sha256']:raise RuntimeError('apparatus receipt mismatch')
        if not instrument['passed'] or instrument['source_manifest']!=manifest():raise RuntimeError('current apparatus has not passed')
        name='2026-11-09 ThreeMind · 情境判断、证据修正与主动观察 v1'
        candidates=[p for p in c.call('projects.list',{}) if p['name']==name]
        if len(candidates)>1:raise RuntimeError('ambiguous registration')
        p=candidates[0] if candidates else c.request('POST','/api/v2/projects',body=dict(name=name))
        save(work/'platform.json',dict(project_id=p['id'],resource_id=RESOURCE))
        r=base.ResearchRecorder(work,p['id'],client=c)
        r.register(dict(source_key='context-revision:20261109:v1',title=name,classification='development',execution_status='running',
            executor='ai',kernels=[base.KERNEL],protocol=(HERE/'protocol.zh.md').read_text('utf-8'),protocol_version=base.digest(manifest()),
            required_roles=['protocol','report','note'],metadata=dict(independent_origins=N,work=str(work),policy=POLICY,
            authorization='2026-11-09 explicit user authorization; obey training protocol; conflicts require permission')),
            request_id=ident('register'))
        r.synchronize(strict=True)
        c.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,target_id='managed-research-experiments',
            relative_path='2026-11-09-context-revision/v1',registered_work_path=str(work),writer_mode='cooperative',expected_revision=0),
            headers={'X-ThreeMind-Request-ID':str(ident('resource'))})
        c.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=p['id'],resource_id=RESOURCE),
            headers={'X-ThreeMind-Request-ID':str(ident('grant'))})
        save(work/'runner-manifest.json',manifest());save(work/'implementation.json',base.capture_implementation('native'));save(work/'policy.json',POLICY)
        for rel in manifest():r.save_original('frozen/'+rel,(ROOT/rel).read_bytes())
        for i in range(N):
            for h in range(2):save(work/f'material/o{i}-h{h}.json',materials(SEED+i,h,True))
        for lang in ('zh','en'):
            r.text(dict(request_id=str(ident('protocol-'+lang)),identity=str(ident('protocol-doc-'+lang)),expected_revision=0,
                kind='protocol',title='Context revision v1 '+lang,markdown=(HERE/f'protocol.{lang}.md').read_text('utf-8')))
        r.synchronize(strict=True)
        save(work/'registration.json',dict(project=p['id'],record=r.experiment,pending=r.status['pending'],source_manifest=manifest()))
        base.atomic_json(work/'status.json',dict(state='registered',origins_completed=0))
        print(json.dumps(load(work/'registration.json')),flush=True)


def boundary(work):
    if (work/'STOP').exists():raise InterruptedError('complete-boundary pause')
    base.resource_check(work)
    if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>POLICY['originals_bytes']:raise InterruptedError('originals budget')


def unit(work,key,student,fn):
    boundary(work)
    before=student.state();mark=work/'in-flight.json'
    save(mark,dict(key=key,pid=os.getpid(),created_at=psutil.Process().create_time(),time_us=student.core.time_us,
                   before_sha256=base.digest(before)))
    result=fn()
    student.cursor=dict(unit=key)
    path=f'{key}/whole.json.gz';receipt=student.checkpoint(work,path)
    save(work/f'{key}/result.json.gz',result)
    save(work/f'{key}/complete.json',dict(state_file=path,sha256=receipt['sha256'],before_sha256=base.digest(before),
        after_sha256=base.digest(student.state()),start_us=before['core']['time_us'],end_us=student.core.time_us,
        result_sha256=sha(work/f'{key}/result.json.gz')))
    base.atomic_json(work/'current.json',dict(unit=key,state_file=path,sha256=receipt['sha256'],time_us=student.core.time_us))
    mark.unlink()
    print(json.dumps(dict(unit=key,time_us=student.core.time_us,result={k:result[k] for k in ('ready','correct','n','valid') if k in result})),flush=True)
    return result


def run(work):
    deterministic()
    with base.worker_lock(work):
        frozen(work);boundary(work)
        resources=base.resource_check(work)
        if resources['available_bytes']['commit']<POLICY['startup_commit_bytes'] or resources['available_bytes']['data_disk']<31*2**30:
            raise RuntimeError('startup allowance no longer sufficient')
        if (work/'in-flight.json').exists():raise RuntimeError('orphaned in-flight; inspect, do not replay')
        if load(work/'status.json')['state']!='registered':raise RuntimeError('not a fresh registered study; explicit continuation required')
        host=dict(pid=os.getpid(),created_at=psutil.Process().create_time(),command=psutil.Process().cmdline())
        save(work/'host.json',host)
        base.atomic_json(work/'status.json',dict(state='running',origins_completed=0))
        with Guard(work):
            for i in range(N):
                s=Student(SEED+i,f'context-o{i}');s.checkpoint(work,f'origins/o{i}/birth.json.gz')
                previous=None
                for stage in range(3):
                    if previous and previous['ready']:break
                    previous=unit(work,f'origins/o{i}/calibration-{stage}',s,lambda stage=stage:calibrate_unit(s,stage,previous))
                s.frozen_digest=s.adapter_digest()
                s.checkpoint(work,f'origins/o{i}/interface-parent.json.gz')
                parent=load(work/f'origins/o{i}/interface-parent.json.gz')
                del s;gc.collect()
                for h in range(2):
                    s=Student.restore(work,parent)
                    s.identity=f'context-o{i}-h{h}';s.parent=dict(path=f'origins/o{i}/interface-parent.json.gz',sha256=sha(work/f'origins/o{i}/interface-parent.json.gz'),reason='opposite teaching history',time_us=s.core.time_us)
                    previous=None
                    for stage in range(3):
                        if previous and previous['ready']:break
                        previous=unit(work,f'origins/o{i}/h{h}/teaching-{stage}',s,lambda stage=stage:new_unit(s,h,stage,previous))
                    path=f'origins/o{i}/h{h}/test-parent.json.gz';s.checkpoint(work,path);test_parent=load(work/path)
                    print(json.dumps(dict(branch_notice=dict(origin=i,history=h,parent=path,time_us=s.core.time_us,arms=ARMS))),flush=True)
                    del s;gc.collect()
                    for arm in ARMS:
                        s=Student.restore(work,test_parent);s.identity=f'context-o{i}-h{h}-{arm}'
                        s.parent=dict(path=path,sha256=sha(work/path),time_us=s.core.time_us,reason='declared causal branch',arm=arm)
                        unit(work,f'origins/o{i}/h{h}/{arm}/intervention',s,lambda:intervention(s,arm))
                        for j,case in enumerate(load(work/f'material/o{i}-h{h}.json')):
                            unit(work,f'origins/o{i}/h{h}/{arm}/trial-{j:03d}',s,lambda case=case:trial(s,case,arm))
                        del s;gc.collect()
                base.atomic_json(work/'status.json',dict(state='running',origins_completed=i+1))
            base.atomic_json(work/'status.json',dict(state='awaiting-analysis',origins_completed=N))


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare','run','status'));p.add_argument('--work',type=Path,default=WORK)
    a=p.parse_args();work=a.work.resolve()
    if a.command=='prepare':prepare(work)
    elif a.command=='run':run(work)
    else:print(json.dumps(dict(status=load(work/'status.json') if (work/'status.json').exists() else None,
                              stop=(work/'STOP').exists(),in_flight=(work/'in-flight.json').exists(),resources=base.resource_check(work))))


if __name__=='__main__':main()
