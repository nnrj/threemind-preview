"""Bounded observation harness. No patched dynamics, mapping or scheduler."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import time
import types
import zipfile
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

import psutil
from threemind_core import Config, StateImage, Stimulus
from threemind_lab import notebooks
from threemind_lab.config import Settings
from threemind_lab.database import Database, LOCAL_USER
from threemind_lab.provenance import capture_implementation
from threemind_runtime import create_engine
from threemind_runtime.host import Runtime
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.sensory import TextSensor, TextSensorConfig

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / '.work/time-comparison-20260910'
META = HERE / 'platform.json'
LEGACY = WORK / 'legacy'
SEEDS = (41701, 41702)
REFERENCE_US = 100_000
DIALOGUE = ['甲是松子。','乙是铃铛。','丙问甲，谁是铃铛？甲说：乙是铃铛。',
 '丙问乙，谁是松子？乙说：甲是松子。','甲对乙说：我是松子，你是铃铛。',
 '乙对甲说：我是铃铛，你是松子。','谁是松子？甲是松子。','谁是铃铛？乙是铃铛。',
 '松子是谁？松子是甲。','铃铛是谁？铃铛是乙。']


def encoded(value):
    return json.dumps(value, ensure_ascii=False, default=str, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def save(path, value, *, exclusive=True):
    with path.open('xb' if exclusive else 'wb') as stream:
        stream.write(encoded(value) + b'\n')


def load_legacy():
    if 'frozen_time_v3.runtime' in sys.modules:
        return sys.modules['frozen_time_v3.runtime']
    package = types.ModuleType('frozen_time_v3')
    package.__path__ = []
    sys.modules[package.__name__] = package
    for name in ('model', 'frames', 'attention', 'runtime'):
        raw = (LEGACY / (name + '.py')).read_bytes()
        expected = subprocess.check_output(['git', 'show', f'97d8592:core/threemind/{name}.py'], cwd=ROOT)
        if raw != expected:
            raise RuntimeError('Legacy source differs from Git; stop without changing it')
        module = types.ModuleType('frozen_time_v3.' + name)
        module.__file__ = f'git:97d8592:core/threemind/{name}.py'
        sys.modules[module.__name__] = module
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)  # Fixed local Git bytes, no rewriting.
    return sys.modules['frozen_time_v3.runtime']


def old_engine(seed, state=None):
    module = load_legacy()
    model = sys.modules['frozen_time_v3.model']
    package = model.ModelPackage(model.ModelManifest(), consciousness_id=f'time-study-{seed}',
        state=copy.deepcopy(state) if state else {})
    return module.ConsciousnessRuntime(package, config=module.RuntimeConfig())


def old_enqueue(engine, stimulus, due_epoch):
    frame = sys.modules['frozen_time_v3.frames'].SensoryFrame(
        'manual', dict(stimulus.channels), stimulus.intensity)
    receipt = engine.enqueue_frame(frame, adapter_id='common-frozen-sensor',
        delay_epochs=due_epoch - engine.input_queue_status()['input_epoch'] - 1)
    assert receipt['first_due_epoch'] == due_epoch


def old_dynamic(engine):
    state = engine.state_dict()
    keys = ('tick','life_state','death_reason','nodes','edges','sensory_seed','receptor_index',
      'next_node_id','recent','unresponsive_ticks','last_total_activation','energy_reserve',
      'energy_supplied_total','energy_consumed_total','energy_starved_ticks','input_epoch','input_sequence')
    return {key: copy.deepcopy(state[key]) for key in keys}


def snapshot(engine, version, t_us):
    if version == 'legacy':
        channels = {v: k for k, v in engine.receptor_index.items()}
        nodes = [dict(id=n['id'],channel=channels[n['id']],activation=n['activation'],inhibition=n['inhibition'])
                 for n in engine.nodes.values()]
        life, edges, tick = engine.life_state, len(engine.edges), engine.tick
    else:
        nodes = engine.observation_nodes()
        life, edges, tick = engine.life, engine.metrics()['edges'], None
    nodes.sort(key=lambda n: n['id'])
    a = [n['activation'] for n in nodes]
    return dict(time_us=t_us, tick=tick, life=life, edges=edges,
      columns=['id','channel','activation','inhibition'],
      nodes=[[n[k] for k in ['id','channel','activation','inhibition']] for n in nodes],
      active=sum(x > 0 for x in a), total=sum(a), spread=max(a, default=0)-min(a, default=0))


def old_inventory(db):
    rows = {}
    for project in ('194a2f1f-4912-435b-b94e-d8ac64fe4788','a9bd83bb-3d57-4eab-859d-68312f6b2b17'):
        with db.tx(project) as c:
            runs = c.execute('SELECT id,revision,state_hash,status FROM runs WHERE project_id=%s ORDER BY id',(project,)).fetchall()
            docs = c.execute('SELECT id,revision FROM research_documents WHERE project_id=%s ORDER BY id',(project,)).fetchall()
            notes = c.execute('SELECT id,revision FROM notes WHERE project_id=%s ORDER BY id',(project,)).fetchall()
        rows[project] = dict(hash=digest(dict(runs=runs,documents=docs,notes=notes)),
                             counts=dict(runs=len(runs),documents=len(docs),notes=len(notes)))
    return rows


def resources(db=None):
    value = dict(rss=psutil.Process().memory_info().rss,available=psutil.virtual_memory().available,
      disk_free={d:shutil.disk_usage(d+':/').free for d in ('D','E')},
      local_bytes=sum(p.stat().st_size for directory in (HERE,WORK) for p in directory.rglob('*') if p.is_file()))
    if db:
        with db.tx() as c:
            value['database_bytes'] = c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
    return value


class Guard:
    def __init__(self):
        self.start = time.monotonic()
        self.last = 0
        self.peak_rss = 0
        self.last_sample = None

    def check(self, engine=None, version=None):
        if time.monotonic() - self.start > 180:
            raise RuntimeError('Per-process 180 second deadline')
        if engine is not None:
            n, e = (len(engine.nodes),len(engine.edges)) if version == 'legacy' else (
                engine.metrics()['nodes'],engine.metrics()['edges'])
            if n > 256 or e > 50_000:
                raise RuntimeError('Graph observation budget reached; dynamics are not truncated')
        if time.monotonic() - self.last < 1:
            return
        self.last = time.monotonic()
        r = resources()
        self.last_sample = r
        self.peak_rss = max(self.peak_rss, r['rss'])
        if r['rss'] > 1024**3 or r['available'] < 3*1024**3 or min(r['disk_free'].values()) < 15*1024**3:
            raise RuntimeError('Memory or disk reserve reached')
        if r['local_bytes'] > 400*1024**2:
            raise RuntimeError('Local evidence budget reached')


def prepare():
    if META.exists():
        raise RuntimeError('Study already exists; never overwrite a previous experiment')
    WORK.mkdir(parents=True, exist_ok=True)
    LEGACY.mkdir(exist_ok=True)
    sources = {}
    for name in ('model','frames','attention','runtime','manager'):
        path = f'core/threemind/{name}.py'
        raw = subprocess.check_output(['git','show',f'97d8592:{path}'],cwd=ROOT)
        (LEGACY/(name+'.py')).write_bytes(raw)
        sources[path] = hashlib.sha256(raw).hexdigest()
    old = old_engine(41701)  # Import/constructor feasibility, no training.
    manifest = dict(legacy_revision='97d8592',legacy_sources=sources,
      legacy_config=asdict(old.config),current_config=asdict(Config()),sensor=asdict(TextSensorConfig()),
      current_implementation=capture_implementation('native'))
    save(HERE/'implementation.json', manifest)
    course = {}
    for group in ('pair','dialogue'):
        sentences = DIALOGUE[:2]*2 if group == 'pair' else DIALOGUE
        texts = [s for s in sentences for _ in range(20)]
        for seed in SEEDS:
            frames = []
            for i,text in enumerate(texts):
                parts = list(TextSensor(seed).frames(text))
                assert len(parts) == 1, 'Stop: common schedule requires actual one-frame carriers'
                s = replace(parts[0]['stimulus'],time_us=(1+i*8)*REFERENCE_US)
                frames.append(dict(text=text,epoch=1+i*8,stimulus=s.to_dict()))
            course[f'{group}-{seed}'] = frames
    save(HERE/'inputs.json',course)
    with zipfile.ZipFile(WORK/'frozen-sources.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
        for name in sources:
            z.write(LEGACY/Path(name).name,'legacy/'+name)
        for name in manifest['current_implementation']['source_files']:
            z.write(ROOT/name,'current/'+name)
    db = Database(Settings.from_env().database_url)
    try:
        before = resources(db)
        inventory = old_inventory(db)
        project = db.create_project({'id':LOCAL_USER}, '时间与活动节律：旧V3／当前内核第一阶段对照')
        book = notebooks.ensure_default(db,project['id'],LOCAL_USER)
        note_id = str(uuid4())
        note = notebooks.save_note(db,project['id'],LOCAL_USER,note_id,dict(operation_id=str(uuid4()),
          expected_revision=0,kind='note',collection_id=str(book['id']),title='实验设计：不改内核的时间对照',
          body={'format':'markdown','text':(HERE/'protocol.md').read_text(encoding='utf-8')}))
        save(META,dict(project_id=str(project['id']),notebook_id=str(book['id']),protocol_note_id=note_id,
          note_hash=note['content_hash'],resources_before=before,previous_projects=inventory,
          frozen_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                        (HERE/'run.py',HERE/'protocol.md',HERE/'implementation.json',HERE/'inputs.json')},
          quota=dict(used_percent_start=73,stop_new_at=77,max_at=78)))
        print(json.dumps(dict(project_id=str(project['id']),resources=before,legacy_import='unchanged-success')))
    finally:
        db.close()


def diagnostic():
    guard = Guard()
    result = {'scope':'diagnostics only; no training-state edits'}
    controls = []
    for n in (1,5):
        old, new = old_engine(41701), create_engine()
        for i in range(n):
            s = Stimulus(REFERENCE_US, ((900001,1.),), 1. if i == 0 else 0.)
            old_enqueue(old,s,1)
            new.inject(s)
        old.step(); new.advance_to(REFERENCE_US)
        controls.append(dict(frames=n,old=snapshot(old,'legacy',REFERENCE_US),
                             current=snapshot(new,'current',REFERENCE_US)))
    result['same_epoch_frames'] = controls
    # Both engines see the same absolute input timestamps, in the same order.
    cue = Stimulus(100_000, ((1001,.8),(1002,.6)), 1.)
    current = {}
    for mode in ('single','fine','realtime','scaled','pause_restore'):
        e = create_engine(); e.inject(cue)
        clock = Runtime(e,clock=mode if mode in ('realtime','scaled') else 'unbounded',speed=20)
        start = time.monotonic()
        horizons = [1_600_000] if mode == 'single' else range(10_000,1_600_001,10_000)
        pause_hash = None
        for t in horizons:
            guard.check()
            if mode in ('realtime','scaled'):
                clock.pace(t)
            e.advance_to(t)
            if mode != 'single':
                e.observation_nodes()
            if mode == 'pause_restore' and t == 800_000:
                state = e.capture_state(); time.sleep(.05)
                assert e.capture_state().digest == state.digest
                e = create_engine(state=state)
                pause_hash = state.digest
        current[mode] = dict(hash=e.capture_state().digest,wall_seconds=time.monotonic()-start,pause_hash=pause_hash)
    result['current_controls'] = current
    assert len({v['hash'] for v in current.values()}) == 1, 'Current host/observation invariance failed; stop'
    olds = {}
    for mode in ('batch','single','host_wait','pause_restore'):
        e = old_engine(41701); old_enqueue(e,cue,1)
        start = time.monotonic()
        if mode == 'batch': e.step(ticks=16)
        else:
            for i in range(16):
                guard.check()
                if mode == 'host_wait': time.sleep(.005)
                e.step()
                if mode == 'pause_restore' and i == 7:
                    before = old_dynamic(e); e.pause(); time.sleep(.05); e.step(ticks=3)
                    assert old_dynamic(e) == before
                    e.resume(); e = old_engine(41701,copy.deepcopy(e.state_dict()))
        olds[mode] = dict(hash=digest(old_dynamic(e)),wall_seconds=time.monotonic()-start)
    result['legacy_controls'] = olds
    assert len({v['hash'] for v in olds.values()}) == 1, 'Legacy host/restore invariance failed; stop'
    result['peak_rss'] = guard.peak_rss
    save(HERE/'diagnostics.json',result)
    print('diagnostics passed',flush=True)


def write_state(path, engine, version):
    payload = encoded(engine.state_dict()) if version == 'legacy' else engine.capture_state().payload
    with gzip.open(path,'xb') as stream: stream.write(payload)
    return hashlib.sha256(payload).hexdigest()


def training(group, seed, version):
    guard = Guard()
    key = f'{group}-{seed}-{version}'
    course = json.loads((HERE/'inputs.json').read_bytes())[f'{group}-{seed}']
    e = old_engine(seed) if version == 'legacy' else create_engine()
    for row in course:
        s = Stimulus.from_dict(row['stimulus'])
        if version == 'legacy': old_enqueue(e,s,row['epoch'])
        else: e.inject(s)
    end_epoch = len(course)*8
    trace = WORK/(key+'-trace.jsonl.gz')
    samples = []
    with gzip.open(trace,'xb') as stream:
        for epoch in range(1,end_epoch+1):
            guard.check(e,version)
            if version == 'legacy': e.step()
            else: e.advance_to(epoch*REFERENCE_US)
            row = snapshot(e,version,epoch*REFERENCE_US)
            stream.write(encoded({'phase':'training',**row})+b'\n')
    checkpoint = WORK/(key+'-trained.json.gz')
    source_hash = write_state(checkpoint,e,version)
    state = copy.deepcopy(e.state_dict()) if version == 'legacy' else e.capture_state()
    result = dict(group=group,seed=seed,version=version,training_count=len(course),
      trained=snapshot(e,version,end_epoch*REFERENCE_US),checkpoint_sha256=source_hash,continuations={})
    for branch in ('no_input','cue'):
        tail = old_engine(seed,state) if version == 'legacy' else create_engine(state=state)
        records = []
        session = None
        if branch == 'cue':
            frames = list(TextSensor(seed).frames('甲'))
            assert len(frames) == 1
            if version == 'legacy': old_enqueue(tail,frames[0]['stimulus'],end_epoch+1)
            else:
                session = ReadoutSession(tail,record=records.append,config={'structural_readout':{'enabled':False}})
                session.schedule(frames,at=(end_epoch+1)*REFERENCE_US,envelope_id=f'time-{key}-cue')
        branch_samples = []
        spacing = REFERENCE_US if version == 'legacy' else 10_000
        with gzip.open(WORK/(key+'-'+branch+'.jsonl.gz'),'xb') as stream:
            initial = snapshot(tail,version,end_epoch*REFERENCE_US)
            stream.write(encoded(initial)+b'\n'); branch_samples.append(initial)
            for offset in range(spacing,12_000_001,spacing):
                guard.check(tail,version)
                target = end_epoch*REFERENCE_US+offset
                if version == 'legacy': tail.step()
                elif session: session.advance_to(target)
                else: tail.advance_to(target)
                row = snapshot(tail,version,target)
                stream.write(encoded(row)+b'\n'); branch_samples.append(row)
                if row['life'] == 'dead': break
        if records:
            save(WORK/(key+'-temporal-readouts.json'),records)
        endpoint_hash = write_state(WORK/(key+'-'+branch+'-final.json.gz'),tail,version)
        last = branch_samples[-1]
        late = [s for s in branch_samples if s['time_us'] >= end_epoch*REFERENCE_US+11_000_000]
        means = [s['total']/max(1,len(s['nodes'])) for s in late]
        result['continuations'][branch] = dict(last=last,samples=len(branch_samples),
          first_all_zero_us=next((s['time_us'] for s in branch_samples if s['active']==0),None),
          late_mean_range=[min(means),max(means)] if means else None,
          late_spread_range=[min(s['spread'] for s in late),max(s['spread'] for s in late)] if late else None,
          final_state_sha256=endpoint_hash,reader_records=len(records))
    # Read-only capture and continuation cannot change the source engine.
    assert source_hash == (hashlib.sha256(encoded(e.state_dict())).hexdigest() if version == 'legacy'
                           else hashlib.sha256(e.capture_state().payload).hexdigest())
    result.update(wall_seconds=time.monotonic()-guard.start,peak_rss=guard.peak_rss,resources=resources())
    save(WORK/(key+'-summary.json'),result)
    print(json.dumps({k:result[k] for k in ('group','seed','version','training_count','wall_seconds','peak_rss')}),flush=True)


def launch(args):
    meta = json.loads(META.read_bytes())
    for name, sha in meta['frozen_hashes'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == sha, 'Frozen study file changed'
    db = Database(Settings.from_env().database_url)
    try:
        r = resources(db)
        growth = max(0,r['database_bytes']-meta['resources_before']['database_bytes']) + r['local_bytes']
        if growth > 400*1024**2: raise RuntimeError('Combined storage guard reached')
    finally: db.close()
    spent = sum(json.loads(p.read_bytes())['wall_seconds'] for p in WORK.glob('*-summary.json'))
    if spent >= 720: raise RuntimeError('Cumulative computation limit reached')
    label = '-'.join(args)
    with (WORK/(label+'.log')).open('xb') as log:
        command = [sys.executable,str(HERE/'run.py'),*args]
        completed = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,
            timeout=min(180,720-spent),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if completed.returncode: raise RuntimeError(f'Study process stopped: {label}; inspect its bounded log, do not retry')
    print((WORK/(label+'.log')).read_text(encoding='utf-8'),flush=True)


if __name__ == '__main__':
    command, *args = sys.argv[1:]
    if command == 'prepare': prepare()
    elif command == 'diagnostic': diagnostic()
    elif command == 'train': training(args[0],int(args[1]),args[2])
    elif command == 'launch': launch(args)
    else: raise ValueError('Unknown stage')
