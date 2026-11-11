"""E67 authenticated recording and matched complete-system experiments."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '2'
import numpy as np
import psutil
import torch
from lab.tools.recognition_session import RecognitionSystem
from lab.tools.centered_recognition import CenteredWorld, WORDS
from threemind_lab.config import load_env
from threemind_lab.operations_client import OperationsClient
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import atomic_json
from threemind_lab.provenance import capture_implementation
from curriculum import ARMS, DEFERRED_ARMS, KERNELS, CONFIGS, INITIAL, TEACH, CAL, DEV, FINAL, bank, initial_calibration, initial_curriculum, matched_correction, score

TITLE = 'E67 三内核形色教学与性能对照'
SOURCE = 'lab-exploration:' + HERE.name
RESOURCE = 'research:e67-shape-color-kernels'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, default=str).encode('utf-8')


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while block := f.read(1024**2): h.update(block)
    return h.hexdigest()


def fixed_json(path, value):
    path = Path(path)
    if path.exists():
        if read(path) != json.loads(encoded(value)): raise ValueError('immutable content conflict: ' + str(path))
    else: atomic_json(path, value)


def device():
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.6)
        return 'cuda'
    return 'cpu'


class Meter:
    def __init__(self, previous=None): self.values = dict(previous or {})

    @contextmanager
    def clock(self, name):
        start = time.perf_counter_ns()
        try: yield
        finally:
            self.values[name + '_ns'] = self.values.get(name + '_ns', 0) + time.perf_counter_ns() - start
            self.values[name + '_calls'] = self.values.get(name + '_calls', 0) + 1


class NativeMeter:
    """Measure native boundary calls, without changing their arguments or result."""
    def __init__(self, native, meter): self.native, self.meter = native, meter

    def __getattr__(self, name):
        value = getattr(self.native, name)
        label = {'advance': 'core', 'inject': 'core_inject', 'state_json': 'core_capture',
                 'observation_nodes_json': 'core_observation', 'metrics_json': 'core_metrics'}.get(name)
        if label is None: return value
        def call(*args, **kwargs):
            with self.meter.clock(label): return value(*args, **kwargs)
        return call


def instrument(a, meter):
    a.session.engine._engine = NativeMeter(a.session.engine._engine, meter)
    for owner, method, label in ((a.session.world, 'observe', 'sensing'),
                                (a.session.world, 'advance_physics', 'body'),
                                (a.session.stream, 'sample', 'observation'),
                                (a.words, 'predict', 'inference')):
        original = getattr(owner, method)
        def measured(*args, _call=original, _label=label, **kwargs):
            with meter.clock(_label): return _call(*args, **kwargs)
        setattr(owner, method, measured)
    return a


def optical_check():
    from itertools import product
    world = CenteredWorld(seed=91, toys=False)
    offsets = sorted(set(INITIAL+TEACH+CAL+DEV+FINAL))
    rows = []
    for shape, half in enumerate(((.14,.14,.14),(.14,.14,.15),(.13,.13,.15),(.14,.14,.15))):
        for offset in offsets:
            world.present(shape, 4, offset=offset)
            corners = [world.project(np.array(world.positions[0])+[dx,dy], z=.16+dz)
                       for dx,dy,dz in product(*[(-v,v) for v in half])]
            maximum = float(np.abs(np.stack(corners)).max())
            assert maximum < world.eye_config.center_half_width
            rows.append(dict(shape=shape, offset=offset, maximum=maximum))
    return dict(cases=rows, maximum=max(x['maximum'] for x in rows), center_half_width=.075)


def equal(a, b):
    if isinstance(a, torch.Tensor): return isinstance(b, torch.Tensor) and torch.equal(a.detach().cpu(), b.detach().cpu())
    if isinstance(a, dict): return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)): return len(a) == len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a == b


def speak(a, text, ticks, guard):
    frames = list(a.session.sensor.frames(text)) if text else []
    if len(frames) > ticks: raise ValueError('complete utterance required')
    rows = []
    for i in range(ticks):
        row = a.session.tick(frames[i] if i < len(frames) else None, guard=guard)
        row['teacher_utterance'] = text
        rows.append(row)
    return rows


def ask(a, task, guard):
    a.session.world.present(task['shape'], task['color'], offset=task['offset'])
    a.session.world.marker = None
    rows = speak(a, task['text'], 20, guard)
    indices = np.rint(np.linspace(0,19,8)).astype(int)
    x = np.stack([a.words.layout.frame(rows[i]['activity']) for i in indices])
    logits = a.words.predict(x[None])[0]
    selected = int(logits.argmax())
    result = task | dict(selected=selected, word=WORDS[selected], correct=selected == task['label'])
    rows[-1]['expression'] = dict(word=WORDS[selected], probabilities=torch.as_tensor(logits).softmax(-1).tolist(),
                                identity=a.identity, readout_profile='whole-question', steps_before=a.words.computed_updates)
    return rows, x, result


class Study:
    def __init__(self, work, *, prepare=False):
        load_env()
        self.work = Path(work).resolve()
        self.client = OperationsClient.from_environment(source='ai')
        self.client.request('GET', '/api/v2/me')
        self.storage = ResearchStorage()
        self.last_guard = 0
        if prepare: self.prepare()
        self.meta = read(self.work/'platform.json')
        self.project = self.meta['project_id']
        self.recorder = ResearchRecorder(self.work, self.project, client=self.client)
        if (self.recorder.control/'identity.json').exists(): self.recorder.resume_recording()
        else:
            self.recorder.register(dict(source_key=SOURCE, original_id='E67', title=TITLE, executor='ai',
                execution_status='running', experiment_date='2026-10-11', kernels=list(dict.fromkeys(KERNELS.values())),
                question='配平教学条件下，三内核的形状、颜色、组合成绩及计算代价有何差别？',
                protocol=(HERE/'design.zh.md').read_text(encoding='utf-8'), protocol_version=sha(HERE/'design.zh.md'),
                metadata={'source_path': HERE.relative_to(ROOT).as_posix(), 'subjects': len(ARMS), 'paired_seed': 223,
                          'complete_system': True, 'host': 'registered independent research runner'}),
                request_id=self.rid('register'))
        self.recorder.synchronize(strict=True)

    def rid(self, key): return str(uuid5(UUID(self.project), 'e67:'+key))

    def prepare(self):
        self.work.mkdir(parents=True, exist_ok=True)
        if (self.work/'platform.json').exists(): return
        listing = self.client.call('records.list', {'query': {'query': 'E67', 'limit': 100}})
        if any(r.get('original_id') == 'E67' and r['source_key'] != SOURCE for r in listing['rows']):
            raise ValueError('E67 already belongs to another study')
        existing = [p for p in self.client.request('GET','/api/v2/projects') if p['name'] == TITLE]
        if len(existing) > 1: raise ValueError('ambiguous project')
        project = existing[0] if existing else self.client.request('POST','/api/v2/projects',body={'name': TITLE})
        overview = self.client.request('GET','/api/v2/storage')
        target_id = 'managed-research-experiments'
        target = next((t for t in overview['targets'] if t['id'] == target_id), None)
        root = self.storage.writable_root()/'experiments'
        if self.work.parent != root: raise ValueError('use the managed experiments root')
        if target is None:
            self.client.request('POST','/api/v2/storage/targets',body=dict(target_id=target_id,
                name='Managed research experiments',kind='filesystem',path=str(root),expected_revision=0))
        elif Path(target['configuration']['path']).resolve() != root.resolve(): raise ValueError('target path conflict')
        existing_resource = next((r for r in overview['resources'] if r['id'] == RESOURCE),None)
        if existing_resource is None:
            self.client.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,
                target_id=target_id,relative_path=self.work.name,writer_mode='cooperative',expected_revision=0))
        self.client.request('POST','/api/v2/storage/record-evidence-grants',
                            body=dict(project_id=project['id'], resource_id=RESOURCE))
        self.project = str(project['id'])
        frozen = self.work/'source-reference'
        manifest = {}
        implementation = capture_implementation('native')
        paths = list(HERE.glob('*.py'))+list(HERE.glob('design.*.md'))+list((ROOT/'lab/tools').glob('*.py'))
        paths += [ROOT/'docs/zh/training-protocol.md', ROOT/'docs/en/training-protocol.md']
        paths += [ROOT/p for p in implementation['source_files']]
        for path in sorted(set(paths)):
            name = path.relative_to(ROOT).as_posix()
            dest = frozen/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and sha(dest) != sha(path): raise ValueError('frozen source changed before registration')
            if not dest.exists(): shutil.copy2(path,dest)
            manifest[name] = sha(path)
        fixed_json(frozen/'manifest.json', manifest)
        fixed_json(self.work/'platform.json', dict(project_id=self.project, resource_id=RESOURCE,
            experiment_source=SOURCE, implementation=implementation, source_manifest_sha256=sha(frozen/'manifest.json'),
            created_epoch=time.time(), host_cpu=psutil.cpu_count(), torch=torch.__version__, device=device(),
            gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None))
        fixed_json(self.work/'questions.json', dict(initial=initial_calibration(),
            development=bank('development',DEV,6711), final=bank('final',FINAL,6721)))
        fixed_json(self.work/'initial-curriculum.json',initial_curriculum())
        fixed_json(self.work/'optical-verification.json', optical_check())

    def close(self): self.client.close()

    def verify_sources(self):
        revision = read(self.work/'protocol-revision-3.json')
        if revision['active_arms'] != list(ARMS):raise ValueError('active arms differ from registered protocol')
        for name, digest in read(self.work/'source-reference-r3/manifest.json').items():
            if sha(ROOT/name) != digest:
                raise ValueError('registered implementation changed: '+name)

    def amend_two_arms(self):
        """Apply the user's deferral before any correction course; preserve r1/r2."""
        if any(self.work.glob('round-*-curriculum.json')):
            raise ValueError('cannot change participating arms after correction starts')
        for arm in ARMS:
            if not (self.work/'arms'/arm/'development-0/result.json').exists():
                raise ValueError('the existing initial stage must be preserved')
        previous=read(self.work/'source-reference-r2/manifest.json')
        allowed={f'lab/explorations/{HERE.name}/{name}' for name in
                 ('curriculum.py','experiment.py','replay.py','design.zh.md','design.en.md')}
        changed=[name for name,digest in previous.items() if sha(ROOT/name)!=digest]
        if set(changed)-allowed:raise ValueError('scope amendment would change subject implementation: '+str(set(changed)-allowed))
        frozen=self.work/'source-reference-r3';manifest={}
        for name in previous:
            path=ROOT/name;dest=frozen/name;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and sha(dest)!=sha(path):raise ValueError('scope freeze conflict')
            if not dest.exists():shutil.copy2(path,dest)
            manifest[name]=sha(path)
        fixed_json(frozen/'manifest.json',manifest)
        pause=read(self.work/'host-pause-20261011T2008.json')
        revision=dict(revision=3,active_arms=list(ARMS),deferred_arms=list(DEFERRED_ARMS),
            reason='用户在工期估算后决定：先完成 /2 和 /3.1，搁置 /4。两组延续已完成初教的原完整个体；后续课程取这两组错误并集。',
            unchanged='Core, peripheral, adapters, configurations, initial sources and final questions',
            changed_sources=changed,source_manifest_sha256=sha(frozen/'manifest.json'),
            deferred=dict(adaptive_checkpoint=pause['checkpoint'],adaptive_saved_lesson=pause['checkpoint_lesson'],
                          adaptive_original_clips=pause['persisted_lesson_clips'],legacy_born=False),
            correction_rounds=3,final_questions_per_arm=72,videos=2)
        fixed_json(self.work/'protocol-revision-3.json',revision)
        self.recorder.append('correction','two-arm-amendment',revision,request_id=self.rid('two-arm-amendment'))
        for lang in ('zh','en'):
            self.recorder.text(dict(request_id=self.rid('protocol-v3:'+lang),identity=self.rid('protocol-text:'+lang),
                expected_revision=2,kind='protocol',title=f'E67 两组续行；/4 搁置 / two-arm continuation {lang}',
                markdown=(HERE/f'design.{lang}.md').read_text(encoding='utf-8'),revision_reason=revision['reason']))
        for name in ('protocol-revision-3.json','source-reference-r3/manifest.json'):
            self.attach(self.work/name,'protocol')
        self.recorder.synchronize(strict=True)

    def amend_four_arms(self):
        if (self.work/'arms').exists():raise ValueError('scope amendment must precede formal birth')
        frozen=self.work/'source-reference-r2'
        manifest={}
        for name in read(self.work/'source-reference/manifest.json'):
            path=ROOT/name;dest=frozen/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists() and sha(dest)!=sha(path):raise ValueError('amendment source conflict')
            if not dest.exists():shutil.copy2(path,dest)
            manifest[name]=sha(path)
        fixed_json(frozen/'manifest.json',manifest)
        revision=dict(revision=2,subjects=len(ARMS),arms=list(ARMS),kernels=KERNELS,configuration_overrides=CONFIGS,
            reason='用户要求 /4 的两种保持方案分别作形色实验；正式出生前扩为四组，不进行额外延迟保持实验。',
            source_manifest_sha256=sha(frozen/'manifest.json'))
        fixed_json(self.work/'protocol-revision-2.json',revision)
        self.recorder.append('correction','four-arm-amendment',revision,request_id=self.rid('four-arm-amendment'))
        for arm in ARMS:
            self.recorder.append('condition','condition:'+arm,dict(kernel=KERNELS[arm],configuration=CONFIGS[arm],
                seed=223,blank=True,paired_course=True),request_id=self.rid('condition:'+arm))
        for lang in ('zh','en'):
            self.recorder.text(dict(request_id=self.rid('protocol-v2:'+lang),identity=self.rid('protocol-text:'+lang),
                expected_revision=1,kind='protocol',title=f'E67 四组事前登记 / four-arm protocol {lang}',
                markdown=(HERE/f'design.{lang}.md').read_text(encoding='utf-8'),revision_reason=revision['reason']))
        for name in ('protocol-revision-2.json','source-reference-r2/manifest.json'):
            self.attach(self.work/name,'protocol')
        self.recorder.synchronize(strict=True)

    def guard(self):
        if time.monotonic()-self.last_guard < 1: return
        self.last_guard = time.monotonic()
        if (self.work/'STOP').exists(): raise RuntimeError('requested STOP')
        if shutil.disk_usage(self.work).free < 15*2**30: raise RuntimeError('preserve 15 GiB free disk')
        if psutil.virtual_memory().available < 2*2**30: raise RuntimeError('preserve 2 GiB available RAM')

    def attach(self, path, role, stage=None):
        path = Path(path)
        name = path.relative_to(self.work).as_posix()
        self.recorder.attach(dict(logical_id='file:'+name,role=role,label=name,
            format=''.join(path.suffixes).lstrip('.') or 'opaque',byte_count=path.stat().st_size,sha256=sha(path),
            stage_key=stage,locator=dict(kind='file',resource_id=RESOURCE,member=name)), request_id=self.rid('file:'+name))

    def publish_protocol(self):
        for lang in ('zh','en'):
            self.recorder.text(dict(request_id=self.rid('protocol:'+lang),identity=self.rid('protocol-text:'+lang),
                expected_revision=0,kind='protocol',title=f'E67 事前登记 / protocol {lang}',
                markdown=(HERE/f'design.{lang}.md').read_text(encoding='utf-8')))
        for name in ('platform.json','questions.json','initial-curriculum.json','optical-verification.json','source-reference/manifest.json'):
            self.attach(self.work/name,'protocol')
        self.recorder.synchronize(strict=True)

    def finish_stage(self, folder, result):
        key = folder.relative_to(self.work).as_posix()
        fixed_json(folder/'result.json', result)
        self.recorder.append('stage',key,result,request_id=self.rid('stage:'+key))
        files = [p for p in folder.rglob('*') if p.is_file() and '.partial' not in p.parts]
        for p in files:
            role = 'checkpoint' if any(part in p.parts for part in ('system','checkpoints','birth')) else 'process'
            if p.name in ('predictions.json','result.json'): role='result'
            self.attach(p,role,key)
        self.recorder.synchronize(strict=True)
        print(json.dumps(dict(stage=key,**result),ensure_ascii=False),flush=True)
        return result


def load_system(source, meter):
    with meter.clock('restore'):
        value = RecognitionSystem.restore(source,device())
    return instrument(value,meter)


def save_system(a, path, meter):
    path=Path(path)
    with meter.clock('checkpoint_save'):
        if path.exists():
            prior=RecognitionSystem.restore(path,device())
            assert encoded(a.session.snapshot()) == encoded(prior.session.snapshot())
            assert encoded(list(a.session.history)) == encoded(list(prior.session.history))
            assert a.identity == prior.identity and a.cursor == prior.cursor and a.phase == prior.phase
            assert equal(a.words.state_dict(),prior.words.state_dict())
            assert equal(a.words.optimizer.state_dict(),prior.words.optimizer.state_dict())
            assert equal(a.words.learning_rng,prior.words.learning_rng)
            return
        partial=path.with_name(path.name+'.partial')
        if partial.exists():
            partial.rename(path.with_name(path.name+'.interrupted-'+str(time.time_ns())))
        a.save(path)


def write_clip(folder, index, rows, kind, trial, meter):
    path = folder/'clips'/f'{index:06d}.json.gz'
    with meter.clock('json_encode'):
        raw=encoded(dict(kind=kind,text=trial.get('statement') if kind=='teaching' else trial.get('text',kind),
                         trial=trial,process=rows))
    if path.exists():
        if gzip.decompress(path.read_bytes()) != raw: raise ValueError('replayed evidence differs: '+str(path))
        return
    with meter.clock('gzip'): content=gzip.compress(raw,compresslevel=1,mtime=0)
    with meter.clock('original_write'):
        path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix('.partial')
        with temp.open('wb') as f: f.write(content); f.flush(); os.fsync(f.fileno())
        temp.rename(path)


def teach(s, arm, name, source, lessons):
    folder=s.work/'arms'/arm/name
    if (folder/'result.json').exists(): return read(folder/'result.json')
    folder.mkdir(parents=True,exist_ok=True)
    progress=read(folder/'resume.json') if (folder/'resume.json').exists() else {}
    meter=Meter(progress.get('timing')); start=time.monotonic()
    if progress: a=load_system(folder/progress['checkpoint'],meter)
    elif source: a=load_system(source,meter)
    else:
        a=instrument(RecognitionSystem(identity='e67-'+arm+'-223',device=device(),
                    kernel_id=KERNELS[arm],kernel_config=CONFIGS[arm]),meter)
        save_system(a,folder/'birth',meter)
        s.recorder.append('subject','subject:'+arm,dict(identity=a.identity,kernel=a.session.engine.dynamics,
            configuration=a.session.engine.config.to_dict(),complete_birth='arms/'+arm+'/'+name+'/birth',
            seed=223,sensory_seed=91,adapter={'world':a.session.world.state()['schema'],
                'text':asdict(a.session.sensor.config),'channels':list(a.session.layout.channels),
                'readout':'threemind.calibrated-activity/1','whole_question_frames':8}),request_id=s.rid('subject:'+arm))
        s.recorder.synchronize(strict=True)
    began=progress.get('start_us',a.session.engine.time_us)
    clip_index=progress.get('clips',0); answers=progress.get('answers',[])
    previous_done=progress.get('done',0)
    for i,t in enumerate(lessons):
        if i < previous_done: continue
        if t['gap_s']:
            rows=speak(a,'',int(t['gap_s']*20),s.guard)
            write_clip(folder,clip_index,rows,'interval',t,meter); clip_index+=1
        if t['operation']=='correct-failed-question':
            rows,_,answer=ask(a,t,s.guard); answers.append(answer)
            write_clip(folder,clip_index,rows,'student-reanswer',answer,meter); clip_index+=1
        a.session.world.present(t['shape'],t['color'],offset=t['offset']); a.session.world.marker=None
        before=a.session.engine.time_us
        rows=speak(a,t['statement'],30,s.guard)
        write_clip(folder,clip_index,rows,'teaching',t|dict(start_us=before,end_us=a.session.engine.time_us),meter)
        clip_index+=1; a.cursor+=1
        if (i+1)%24==0:
            checkpoint=f'checkpoints/lesson-{i+1:04d}'
            save_system(a,folder/checkpoint,meter)
            atomic_json(folder/'resume.json',dict(done=i+1,clips=clip_index,answers=answers,
                checkpoint=checkpoint,start_us=began,timing=meter.values))
        if (i+1)%12==0:
            print(json.dumps(dict(arm=arm,stage=name,lesson=i+1,total=len(lessons),sim_s=a.session.engine.time_us/1e6)),flush=True)
    a.phase=name;save_system(a,folder/'system',meter)
    fixed_json(folder/'student-reanswers.json',answers)
    result=dict(kernel=a.session.engine.dynamics,identity=a.identity,lessons=len(lessons),clips=clip_index,
        start_us=began,end_us=a.session.engine.time_us,sim_s=(a.session.engine.time_us-began)/1e6,
        source=str(source) if source else None,timing=meter.values,wall_seconds=time.monotonic()-start,
        metrics=a.session.engine.metrics(),end_rss=psutil.Process().memory_info().rss)
    return s.finish_stage(folder,result)


def collect(s,arm,name,source,tasks):
    folder=s.work/'arms'/arm/name
    if (folder/'result.json').exists():return read(folder/'result.json')
    folder.mkdir(parents=True,exist_ok=True)
    meter=Meter();start=time.monotonic();scores=[];xs=[]
    for i,t in enumerate(tasks):
        completed=folder/'trials'/f'{i:04d}.json'
        if completed.exists():
            result=read(completed)
            with np.load(completed.with_suffix('.npz'),allow_pickle=False) as data:x=data['x']
            for key,value in result.pop('measurement',{}).items():
                meter.values[key]=meter.values.get(key,0)+value
        else:
            old_timing=dict(meter.values)
            a=load_system(source,meter)
            rows,x,result=ask(a,t,s.guard)
            write_clip(folder,i,rows,'question',result,meter)
            completed.parent.mkdir(parents=True,exist_ok=True)
            np.savez_compressed(completed.with_suffix('.npz'),x=x)
            fixed_json(completed,result | {'measurement': {k:v-old_timing.get(k,0) for k,v in meter.values.items()}})
            del a
        scores.append(result);xs.append(x)
        if (i+1)%12==0: print(json.dumps(dict(arm=arm,stage=name,questions=i+1,total=len(tasks),correct=sum(x['correct'] for x in scores))),flush=True)
    np.savez_compressed(folder/'features.npz',x=xs,y=[t['label'] for t in tasks])
    fixed_json(folder/'predictions.json',scores)
    return s.finish_stage(folder,score(scores)|dict(source=str(source),timing=meter.values,
        wall_seconds=time.monotonic()-start,clips=len(scores),sim_s=len(tasks)))


def fit(s,arm,name,source,corpora):
    folder=s.work/'arms'/arm/name
    if (folder/'result.json').exists():return read(folder/'result.json')
    folder.mkdir(parents=True,exist_ok=True);meter=Meter();start=time.monotonic()
    a=load_system(source,meter);before=encoded(a.session.snapshot());xs=[];ys=[]
    for case in corpora:
        with np.load(s.work/'arms'/arm/case/'features.npz',allow_pickle=False) as d: xs.append(d['x']);ys.append(d['y'])
    with meter.clock('calibration'):
        result=a.words.calibrate(np.concatenate(xs),np.concatenate(ys),steps=1200,check=s.guard)
    assert encoded(a.session.snapshot())==before,'instrument calibration advanced the subject'
    a.phase=name;save_system(a,folder/'system',meter)
    return s.finish_stage(folder,result|dict(source=str(source),corpora=corpora,time_us=a.session.engine.time_us,
        physical_core_unchanged=True,timing=meter.values,wall_seconds=time.monotonic()-start))


def idle(s,arm,seconds,source,previous_seconds=0):
    name=f'idle-{seconds}';folder=s.work/'arms'/arm/name
    if (folder/'result.json').exists():return read(folder/'result.json')
    folder.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    progress=read(folder/'resume.json') if (folder/'resume.json').exists() else {}
    meter=Meter(progress.get('timing'))
    a=load_system(folder/progress['checkpoint'] if progress else source,meter)
    if not progress:a.session.world.set_scene([],positions=[])
    began=progress.get('start_us',a.session.engine.time_us)
    for i in range(seconds-previous_seconds):
        if i < progress.get('done',0):continue
        rows=speak(a,'',20,s.guard)
        write_clip(folder,i,rows,'background',dict(text='无教师文字的物理背景'),meter)
        if (i+1)%60==0:
            checkpoint=f'checkpoints/second-{i+1:04d}'
            save_system(a,folder/checkpoint,meter)
            atomic_json(folder/'resume.json',dict(done=i+1,checkpoint=checkpoint,start_us=began,timing=meter.values))
        if (i+1)%15==0: print(json.dumps(dict(arm=arm,stage=name,idle_s=previous_seconds+i+1)),flush=True)
    a.phase=name;save_system(a,folder/'system',meter)
    return s.finish_stage(folder,dict(source=str(source),start_us=began,end_us=a.session.engine.time_us,
        sim_s=seconds-previous_seconds,timing=meter.values,wall_seconds=time.monotonic()-start,
        metrics=a.session.engine.metrics(),clips=seconds-previous_seconds))


def run(s):
    s.verify_sources()
    q=read(s.work/'questions.json');initial=read(s.work/'initial-curriculum.json')
    for arm in ARMS:
        base=s.work/'arms'/arm
        teach(s,arm,'initial-teaching',None,initial)
        collect(s,arm,'initial-calibration',base/'initial-teaching/system',q['initial'])
        fit(s,arm,'initial-fit',base/'initial-teaching/system',['initial-calibration'])
        collect(s,arm,'development-0',base/'initial-fit/system',q['development'])
    corpora=['initial-calibration']
    for r in range(1,4):
        plan=s.work/f'round-{r}-curriculum.json'
        if not plan.exists():
            predictions={arm:read(s.work/'arms'/arm/f'development-{r-1}'/'predictions.json') for arm in ARMS}
            fixed_json(plan,matched_correction(r,predictions))
        c=read(plan);s.attach(plan,'protocol',f'round-{r}');s.recorder.synchronize(strict=True)
        corpora.append(f'calibration-{r}')
        order=ARMS[r%len(ARMS):]+ARMS[:r%len(ARMS)]
        for arm in order:
            base=s.work/'arms'/arm
            parent=base/('initial-fit' if r==1 else f'fit-{r-1}')/'system'
            teach(s,arm,f'correction-{r}',parent,c['lessons'])
            collect(s,arm,f'calibration-{r}',base/f'correction-{r}'/'system',c['calibration'])
            fit(s,arm,f'fit-{r}',base/f'correction-{r}'/'system',corpora)
            collect(s,arm,f'development-{r}',base/f'fit-{r}'/'system',q['development'])
    for arm in ARMS:
        base=s.work/'arms'/arm
        collect(s,arm,'final',base/'fit-3/system',q['final'])
    fixed_json(s.work/'computation-complete.json',dict(arms=list(ARMS),deferred_arms=list(DEFERRED_ARMS),
        protocol_revision=3,rounds=3,status='awaiting analysis and video'))


def preflight(folder):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    result={'optics':optical_check(),'kernels':{}}
    for arm in ARMS:
        p=folder/arm;p.mkdir(exist_ok=True);meter=Meter();start=time.monotonic()
        a=instrument(RecognitionSystem(identity='e67-preflight-'+arm,device=device(),
                     kernel_id=KERNELS[arm],kernel_config=CONFIGS[arm]),meter)
        tasks=initial_calibration();rows,x,_=ask(a,tasks[0],lambda:None)
        a.words.calibrate(np.stack([x,x]),np.array([0,0]),steps=1)
        save_system(a,p/'source',meter)
        b=load_system(p/'source',meter)
        assert encoded(a.session.snapshot())==encoded(b.session.snapshot())
        ra=a.session.tick();rb=b.session.tick()
        assert encoded(ra)==encoded(rb)
        assert a.session.engine.capture_state().digest==b.session.engine.capture_state().digest
        for value in (a,b):value.words.calibrate(np.stack([x,x]),np.array([0,0]),steps=1)
        assert equal(a.words.state_dict(),b.words.state_dict())
        assert equal(a.words.optimizer.state_dict(),b.words.optimizer.state_dict())
        assert equal(a.words.learning_rng,b.words.learning_rng)
        a.session.world.set_scene([],positions=[]);a.session.tick()
        result['kernels'][arm]=dict(next_input_equal=True,next_learning_equal=True,
            blank_background_supported=True,timing=meter.values,wall_s=time.monotonic()-start,
            metrics=a.session.engine.metrics(),config=a.session.engine.config.to_dict(),
            input_hash=hashlib.sha256(encoded([r['stimulus'] for r in rows])).hexdigest())
        print(json.dumps({'preflight':arm,'wall_s':time.monotonic()-start}),flush=True)
    assert len({r['input_hash'] for r in result['kernels'].values()})==1
    fixed_json(folder/'result.json',result)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('prepare','amend','amend-two','run','preflight'))
    p.add_argument('--work',type=Path)
    args=p.parse_args()
    load_env();device()
    if args.mode=='preflight':
        preflight(args.work or ROOT/'.work/e67-preflight');return
    work=args.work or ResearchStorage().writable_root()/'experiments'/HERE.name
    s=Study(work,prepare=args.mode=='prepare')
    try:
        if args.mode=='prepare':
            s.publish_protocol();print(json.dumps({'project_id':s.project,'experiment_id':s.recorder.experiment}),flush=True)
        elif args.mode=='amend':
            s.amend_four_arms();print(json.dumps({'amended':2,'arms':ARMS}),flush=True)
        elif args.mode=='amend-two':
            with s.storage.writer(RESOURCE):s.amend_two_arms()
            print(json.dumps({'amended':3,'active_arms':ARMS,'deferred_arms':DEFERRED_ARMS}),flush=True)
        else:
            with s.storage.writer(RESOURCE): run(s)
    finally:s.close()


if __name__=='__main__':main()
