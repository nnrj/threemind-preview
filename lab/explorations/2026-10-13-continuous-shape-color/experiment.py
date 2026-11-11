"""E68: a single continuous complete individual per arm, no test rollback.

Only open_current() restores, and only the latest clean durable boundary. A
dirty operation cannot be replayed automatically. Stage calls hold the same
objects; they have no source-checkpoint argument.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import gzip
import io
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
sys.path.insert(0, str(ROOT/'src'))
os.environ.setdefault('NO_PROXY', '127.0.0.1,localhost,::1')
from common import (Meter, instrument, device, encoded, read, sha, fixed_json,
                    optical_check, speak, ask)
import numpy as np
import psutil
from lab.tools.recognition_session import RecognitionSystem
from threemind_lab.config import load_env
from threemind_lab.operations_client import OperationsClient
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.research_storage import ResearchStorage
from threemind_lab.storage_files import atomic_json
from threemind_lab.provenance import capture_implementation
from curriculum import ARMS, KERNELS, CONFIGS, DEV, FINAL, bank, initial_calibration, initial_curriculum, matched_correction, score

TITLE = 'E68 连续形色教学与测验（/2、/3.1）'
SOURCE = 'lab-exploration:'+HERE.name
RESOURCE = 'research:e68-continuous-shape-color'


class BoundaryPause(RuntimeError): pass
class ContinuityUncertain(RuntimeError): pass


def put(path, content):
    """Immutable, fsynced original; a conflict never authorizes recomputation."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content: raise ValueError('original conflict: '+str(path))
        return
    temp = path.with_name(path.name+'.partial')
    with temp.open('xb') as f:
        f.write(content); f.flush(); os.fsync(f.fileno())
    temp.rename(path)


def files_manifest(folder):
    return {p.relative_to(folder).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(folder.rglob('*')) if p.is_file()}


class Study:
    def __init__(self, work, *, prepare=False):
        load_env(); self.work = Path(work).resolve(); self.storage = ResearchStorage()
        self.client = OperationsClient.from_environment(source='ai')
        self.client.client.timeout = 120
        if prepare: self.prepare()
        self.meta = read(self.work/'platform.json'); self.project = self.meta['project_id']
        self.recorder = ResearchRecorder(self.work, self.project, client=self.client)
        if (self.recorder.control/'identity.json').exists(): self.recorder.resume_recording()
        else:
            self.recorder.register(dict(source_key=SOURCE, original_id='E68', title=TITLE,
                executor='ai', execution_status='running', experiment_date='2026-10-13',
                kernels=[KERNELS[a] for a in ARMS],
                question='同一个体连续教学、测验与纠错下，/2与/3.1的形色成绩和成本有何差别？',
                protocol=(HERE/'design.zh.md').read_text(encoding='utf-8'),
                protocol_version=sha(HERE/'design.zh.md'),
                metadata=dict(source_path=HERE.relative_to(ROOT).as_posix(), continuous=True,
                    seed=223, rollback_authorized=False, peripheral_selection='last-state')),
                request_id=self.rid('register'))
            self.recorder.synchronize(strict=True)

    def rid(self, key): return str(uuid5(UUID(self.project), 'e68:'+key))

    def prepare(self):
        self.client.request('GET', '/api/v2/me')
        self.work.mkdir(parents=True, exist_ok=True)
        if (self.work/'platform.json').exists(): return
        listing = self.client.call('records.list', {'query': {'query':'E68', 'limit':100}})
        if any(x.get('original_id') == 'E68' and x['source_key'] != SOURCE for x in listing['rows']):
            raise ValueError('E68 already allocated to a different study')
        projects = [p for p in self.client.request('GET','/api/v2/projects') if p['name'] == TITLE]
        if len(projects) > 1: raise ValueError('ambiguous project')
        project = projects[0] if projects else self.client.request('POST','/api/v2/projects',body={'name':TITLE})
        self.project = str(project['id'])
        root = self.storage.writable_root()/'experiments'
        if self.work.parent != root: raise ValueError('managed experiments root required')
        overview = self.client.request('GET','/api/v2/storage')
        target = next(t for t in overview['targets'] if t['id'] == 'managed-research-experiments')
        if Path(target['configuration']['path']).resolve() != root.resolve(): raise ValueError('storage root mismatch')
        if not any(r['id'] == RESOURCE for r in overview['resources']):
            self.client.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,
                target_id=target['id'],relative_path=self.work.name,writer_mode='cooperative',expected_revision=0))
        self.client.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=self.project,resource_id=RESOURCE))
        implementation = capture_implementation('native')
        paths = list(HERE.glob('*.py'))+list(HERE.glob('design.*.md'))+list((ROOT/'lab/tools').glob('*.py'))
        paths += [ROOT/'docs/zh/training-protocol.md', ROOT/'docs/en/training-protocol.md']
        paths += [ROOT/p for p in implementation['source_files']]
        frozen = self.work/'source-reference'; manifest = {}
        for path in sorted(set(paths)):
            name = path.relative_to(ROOT).as_posix(); dest = frozen/name
            put(dest,path.read_bytes()); manifest[name] = sha(path)
        fixed_json(frozen/'manifest.json',manifest)
        fixed_json(self.work/'platform.json',dict(project_id=self.project,resource_id=RESOURCE,
            source_key=SOURCE,created_epoch=time.time(),implementation=implementation,
            manifest_sha256=sha(frozen/'manifest.json'),device=device()))
        fixed_json(self.work/'questions.json',dict(initial=initial_calibration(),
            development=bank('development',DEV,6711),final=bank('final',FINAL,6721)))
        fixed_json(self.work/'initial-curriculum.json',initial_curriculum())
        fixed_json(self.work/'optical-verification.json',optical_check())

    def verify_sources(self):
        for name, digest in read(self.work/'source-reference/manifest.json').items():
            if sha(ROOT/name) != digest: raise ValueError('frozen implementation changed: '+name)

    def attach(self, path, role='process', stage=None):
        path = Path(path); name = path.relative_to(self.work).as_posix()
        self.recorder.attach(dict(logical_id='file:'+name,role=role,label=name,
            format=''.join(path.suffixes).lstrip('.') or 'opaque',byte_count=path.stat().st_size,
            sha256=sha(path),stage_key=stage,locator=dict(kind='file',resource_id=RESOURCE,member=name)),
            request_id=self.rid('file:'+name))

    def publish_protocol(self):
        for lang in ('zh','en'):
            self.recorder.text(dict(request_id=self.rid('protocol:'+lang),identity=self.rid('protocol-text:'+lang),
                expected_revision=0,kind='protocol',title='E68 连续形色事前登记 / Continuous protocol '+lang,
                markdown=(HERE/f'design.{lang}.md').read_text(encoding='utf-8')))
        for a in ARMS:
            self.recorder.append('condition','arm:'+a,dict(arm=a,kernel=KERNELS[a],seed=223,
                continuous=True,rollback_authorized=False),request_id=self.rid('arm:'+a))
        for name in ('platform.json','questions.json','initial-curriculum.json','optical-verification.json','source-reference/manifest.json'):
            self.attach(self.work/name,'protocol')
        self.recorder.synchronize(strict=True)

    def sync(self):
        status = self.recorder.synchronize()
        atomic_json(self.work/'sync-status.json',status)

    def close(self): self.client.close()


class ContinuousArm:
    def __init__(self, study, arm, *, engineering=False):
        self.s, self.arm = study, arm
        self.base = study.work/'arms'/arm; self.base.mkdir(parents=True,exist_ok=True)
        self.latest = self.base/'latest.json'; self.flight = self.base/'in-flight.json'
        self.a = None; self.meter = Meter(); self.pointer = None; self.engineering = engineering
        self.open_current()

    def open_current(self):
        # An uncommitted experience cannot be undone merely because a checkpoint exists.
        if self.flight.exists():
            raise ContinuityUncertain('Incomplete operation: '+str(self.flight)+'; ask user before recovery')
        if self.latest.exists():
            p = read(self.latest); folder = self.base/p['checkpoint']
            if files_manifest(folder) != p['files']: raise ValueError('latest full state is missing or changed')
            with self.meter.clock('restore'):
                self.a = RecognitionSystem.restore(folder,device())
            if self.a.identity != p['identity'] or self.a.session.engine.time_us != p['end_us']:
                raise ValueError('latest subject identity/time mismatch')
            self.pointer = p; self.meter = Meter(p['timing'])
            instrument(self.a,self.meter)
            return
        if any(self.base.iterdir()):
            raise ContinuityUncertain('Subject files without latest complete boundary; cannot create another birth')
        identity=('engineering-e68-' if self.engineering else 'e68-')+self.arm+'-223'
        self.a = instrument(RecognitionSystem(identity=identity,device=device(),
            kernel_id=KERNELS[self.arm],kernel_config=CONFIGS[self.arm]),self.meter)
        blank=self.a.session.engine.metrics()
        if (self.a.session.engine.time_us != 0 or blank['nodes'] != 0 or blank['edges'] != 0 or
            self.a.words.computed_updates != 0 or self.a.words.committed_updates != 0 or
            len(self.a.session.history) != 0 or self.a.words.learning_rng is not None):
            raise ValueError('fresh blank Core and personal peripheral required')
        self.commit('birth',None,0)
        fixed_json(self.base/'blank-birth.json',dict(identity=identity,time_us=0,nodes=0,edges=0,
            peripheral_computed_updates=0,peripheral_committed_updates=0,recent_history=0,
            previous_subject=None,engineering=self.engineering,boundary=self.pointer['boundary_sha256']))
        self.s.recorder.append('subject','subject:'+self.arm,dict(identity=self.a.identity,
            kernel=self.a.session.engine.dynamics,configuration=self.a.session.engine.config.to_dict(),
            birth=self.pointer['checkpoint'],seed=223,sensory_seed=91,
            world=self.a.session.world.state()['schema'],text=asdict(self.a.session.sensor.config),
            channels=list(self.a.session.layout.channels),peripheral='threemind.calibrated-activity/1',
            selection='last-state',continuous=True),request_id=self.s.rid('subject:'+self.arm))

    def guard(self):
        """Only called before a complete unit; a STOP never interrupts a tick."""
        if (self.s.work/'STOP').exists(): raise BoundaryPause('STOP requested at current complete boundary')
        if shutil.disk_usage(self.s.work).free < 25*2**30: raise BoundaryPause('reserve 25GiB disk')
        if psutil.virtual_memory().available < 2*2**30: raise BoundaryPause('reserve 2GiB available memory')

    def commit(self, key, previous, start_us):
        seq = 0 if previous is None else previous['sequence']+1
        folder = self.base/'boundaries'/f'{seq:06d}'
        self.a.cursor = seq; self.a.phase = key
        with self.meter.clock('checkpoint_save'):
            self.a.save(folder,compresslevel=1)
            # Flush every member before publishing the boundary cursor.
            for p in folder.rglob('*'):
                if p.is_file():
                    with p.open('r+b') as f: os.fsync(f.fileno())
        state = dict(sequence=seq,key=key,identity=self.a.identity,start_us=start_us,
            end_us=self.a.session.engine.time_us,computed_updates=self.a.words.computed_updates,
            committed_updates=self.a.words.committed_updates,
            parent=previous['boundary_sha256'] if previous else None,
            checkpoint=folder.relative_to(self.base).as_posix(),files=files_manifest(folder),
            timing=dict(self.meter.values))
        assert state['end_us'] >= start_us
        assert state['computed_updates'] == state['committed_updates'], 'peripheral rollback forbidden'
        state['boundary_sha256'] = __import__('hashlib').sha256(encoded(state)).hexdigest()
        fixed_json(self.base/'chain'/f'{seq:06d}.json',state)
        atomic_json(self.latest,state); self.pointer = state
        if self.flight.exists(): self.flight.unlink()
        atomic_json(self.s.work/'progress.json',dict(pid=os.getpid(),arm=self.arm,key=key,
            sequence=seq,sim_s=state['end_us']/1e6,updated_epoch=time.time(),
            free_disk_GiB=shutil.disk_usage(self.s.work).free/2**30,rss=psutil.Process().memory_info().rss))

    def unit(self, key, operation):
        self.guard(); previous = self.pointer; before = self.a.session.engine.time_us
        if before != previous['end_us']: raise ContinuityUncertain('live time differs from current boundary')
        atomic_json(self.flight,dict(key=key,parent=previous['boundary_sha256'],start_us=before,pid=os.getpid()))
        value = operation()
        self.commit(key,previous,before)
        return value

    def stage_completed(self, name): return (self.base/name/'result.json').exists()

    def start_stage(self,name):
        folder = self.base/name; folder.mkdir(parents=True,exist_ok=True)
        path = folder/'start.json'
        if not path.exists():
            fixed_json(path,dict(identity=self.a.identity,start_us=self.a.session.engine.time_us,
                sequence=self.pointer['sequence'],boundary_sha256=self.pointer['boundary_sha256'],
                timing=dict(self.meter.values),wall_epoch=time.time()))
        start = read(path)
        return folder,start

    def completed_units(self,name):
        prefix=name+':'
        return [read(p) for p in sorted((self.base/'chain').glob('*.json')) if read(p)['key'].startswith(prefix)]

    def finish_stage(self, name, result):
        folder=self.base/name; began=read(folder/'start.json')
        result |= dict(identity=self.a.identity,kernel=self.a.session.engine.dynamics,
            start_us=began['start_us'],end_us=self.a.session.engine.time_us,
            sim_s=(self.a.session.engine.time_us-began['start_us'])/1e6,
            start_sequence=began['sequence'],end_sequence=self.pointer['sequence'],
            start_boundary=began['boundary_sha256'],end_boundary=self.pointer['boundary_sha256'],
            checkpoint=self.pointer['checkpoint'],
            timing={k:v-began['timing'].get(k,0) for k,v in self.meter.values.items()},
            wall_seconds=time.time()-began['wall_epoch'],metrics=self.a.session.engine.metrics())
        fixed_json(folder/'result.json',result)
        key='arms/'+self.arm+'/'+name
        self.s.recorder.append('stage',key,result,request_id=self.s.rid('stage:'+key))
        # Original detailed boundary states remain indexed by their immutable chain.
        for path in folder.rglob('*'):
            if path.is_file(): self.s.attach(path,'result' if path.name in ('result.json','predictions.json') else 'process',key)
        for path in (self.base/self.pointer['checkpoint']).rglob('*'):
            if path.is_file(): self.s.attach(path,'checkpoint',key)
        for p in sorted((self.base/'chain').glob('*.json')):
            n=int(p.stem)
            if began['sequence'] < n <= self.pointer['sequence']: self.s.attach(p,'process',key)
        self.s.sync()
        print(json.dumps(dict(arm=self.arm,stage=name,end_us=result['end_us'],score=result.get('correct'),n=result.get('n')),ensure_ascii=False),flush=True)
        return result

    def clip(self,folder,i,rows,kind,trial):
        with self.meter.clock('json_encode'):
            raw=encoded(dict(kind=kind,text=trial.get('statement') if kind=='teaching' else trial.get('text',kind),trial=trial,process=rows))
        with self.meter.clock('gzip'): data=gzip.compress(raw,compresslevel=1,mtime=0)
        with self.meter.clock('original_write'): put(folder/'clips'/f'{i:06d}.json.gz',data)

    def teach(self,name,lessons):
        if self.stage_completed(name): return read(self.base/name/'result.json')
        folder,begin=self.start_stage(name)
        operations=[]
        for t in lessons:
            if t['gap_s']: operations.append(('interval',t))
            if t['operation']=='correct-failed-question': operations.append(('student-reanswer',t))
            operations.append(('teaching',t))
        done=len(self.completed_units(name))
        for i,(kind,t) in enumerate(operations):
            if i < done: continue
            def perform(i=i,kind=kind,t=t):
                before=self.a.session.engine.time_us
                if kind=='interval': rows=speak(self.a,'',round(t['gap_s']*20),lambda:None); result=t
                elif kind=='student-reanswer': rows,_,result=ask(self.a,t,lambda:None)
                else:
                    self.a.session.world.present(t['shape'],t['color'],offset=t['offset']);self.a.session.world.marker=None
                    rows=speak(self.a,t['statement'],30,lambda:None);result=t
                result=result|dict(start_us=before,end_us=self.a.session.engine.time_us,identity=self.a.identity)
                self.clip(folder,i,rows,kind,result)
                fixed_json(folder/'units'/f'{i:06d}.json',result|dict(kind=kind))
            self.unit(f'{name}:{i:06d}',perform)
        return self.finish_stage(name,dict(lessons=len(lessons),clips=len(operations)))

    def collect(self,name,tasks):
        if self.stage_completed(name): return read(self.base/name/'result.json')
        folder,begin=self.start_stage(name); done=len(self.completed_units(name))
        for i,t in enumerate(tasks):
            if i < done: continue
            def perform(i=i,t=t):
                before=self.a.session.engine.time_us
                rows,x,result=ask(self.a,t,lambda:None)
                result |= dict(start_us=before,end_us=self.a.session.engine.time_us,identity=self.a.identity)
                self.clip(folder,i,rows,'question',result)
                stream=io.BytesIO();np.savez_compressed(stream,x=x)
                put(folder/'trials'/f'{i:04d}.npz',stream.getvalue())
                fixed_json(folder/'trials'/f'{i:04d}.json',result)
            self.unit(f'{name}:{i:06d}',perform)
        results=[read(folder/'trials'/f'{i:04d}.json') for i in range(len(tasks))]
        xs=[]
        for i in range(len(tasks)):
            with np.load(folder/'trials'/f'{i:04d}.npz',allow_pickle=False) as d: xs.append(d['x'])
        stream=io.BytesIO();np.savez_compressed(stream,x=xs,y=[t['label'] for t in tasks])
        put(folder/'features.npz',stream.getvalue());fixed_json(folder/'predictions.json',results)
        return self.finish_stage(name,score(results)|dict(clips=len(tasks)))

    def fit(self,name,corpora):
        if self.stage_completed(name): return read(self.base/name/'result.json')
        folder,begin=self.start_stage(name);xs=[];ys=[]
        for stage in corpora:
            with np.load(self.base/stage/'features.npz',allow_pickle=False) as d: xs.append(d['x']);ys.append(d['y'])
        x,y=np.concatenate(xs),np.concatenate(ys)
        done=len(self.completed_units(name)); core_before=self.a.session.engine.time_us
        for i in range(12):
            if i < done: continue
            def perform(i=i):
                with self.meter.clock('calibration'):
                    result=self.a.words.continue_calibration(x,y,steps=100)
                assert self.a.session.engine.time_us==core_before
                fixed_json(folder/'blocks'/f'{i:04d}.json',result)
            self.unit(f'{name}:{i:06d}',perform)
        result=read(folder/'blocks/0011.json')|dict(updates=1200,corpora=corpora,
            time_us=self.a.session.engine.time_us,physical_core_unchanged=True)
        return self.finish_stage(name,result)


def run(study):
    study.verify_sources()
    # Birth/open only once; no stage receives a restore path or an old source.
    arms={a:ContinuousArm(study,a) for a in ARMS};study.sync()
    q=read(study.work/'questions.json');initial=read(study.work/'initial-curriculum.json')
    for a in arms.values():
        a.teach('initial-teaching',initial)
        a.collect('initial-calibration',q['initial'])
        a.fit('initial-fit',['initial-calibration'])
        a.collect('development-0',q['development'])
    corpora=['initial-calibration']
    for r in range(1,4):
        path=study.work/f'round-{r}-curriculum.json'
        if not path.exists():
            predictions={a:read(arms[a].base/f'development-{r-1}/predictions.json') for a in ARMS}
            fixed_json(path,matched_correction(r,predictions))
        course=read(path);study.attach(path,'protocol');study.sync()
        corpora.append(f'calibration-{r}')
        for key in ARMS[r%2:]+ARMS[:r%2]:
            a=arms[key]
            a.teach(f'correction-{r}',course['lessons'])
            a.collect(f'calibration-{r}',course['calibration'])
            a.fit(f'fit-{r}',corpora)
            a.collect(f'development-{r}',q['development'])
    for a in arms.values(): a.collect('final',q['final'])
    fixed_json(study.work/'computation-complete.json',dict(arms=list(ARMS),continuous=True,
        rollback_count=0,final_boundaries={k:v.pointer['boundary_sha256'] for k,v in arms.items()},
        status='awaiting independent evidence audit, replay and report'))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','run'))
    p.add_argument('--work',type=Path);args=p.parse_args();load_env()
    work=args.work or ResearchStorage().writable_root()/'experiments'/HERE.name
    s=Study(work,prepare=args.action=='prepare')
    try:
        with s.storage.writer(RESOURCE):
            if args.action=='prepare': s.publish_protocol()
            else:
                if (work/'computation-complete.json').exists(): raise ValueError('computation already complete; export only')
                atomic_json(work/'host-status.json',dict(phase='running',pid=os.getpid(),updated_epoch=time.time()))
                try: run(s)
                except BaseException as exc:
                    phase='paused' if isinstance(exc,BoundaryPause) else 'attention-required'
                    atomic_json(work/'host-status.json',dict(phase=phase,pid=os.getpid(),updated_epoch=time.time(),
                        error=type(exc).__name__+': '+str(exc),automatic_rollback=False))
                    raise
                atomic_json(work/'host-status.json',dict(phase='simulation-completed',pid=os.getpid(),updated_epoch=time.time()))
    finally: s.close()


if __name__=='__main__': main()
