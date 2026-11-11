"""Owned, budgeted temporal experiment. Core and sensory defaults are unchanged."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import time
import unicodedata
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

import psutil
from psycopg.types.json import Jsonb
from threemind_core import Config
from threemind_lab import calibration, notebooks
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Database
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.inputs import envelope_record
from threemind_lab.protocols import RunSpec
from threemind_lab.provenance import capture_implementation
from threemind_runtime import create_engine
from threemind_runtime.calibration import CalibrationProtocol, transduction
from threemind_runtime.readout_config import TemporalReadoutConfig
from threemind_runtime.readout_session import ReadoutSession, SESSION_VERSION
from threemind_runtime.sensory import TEXT_VERSION, TextSensor, TextSensorConfig
from threemind_runtime.temporal_probe import TemporalProbeProtocol

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = ROOT / '.work' / 'temporal-repetition-20260910'
META = HERE / 'platform.json'
WORKER = 'temporal-repetition-20260910-owned'
SEEDS = [41701, 41702, 41703, 41704]
SENSOR = TextSensorConfig()
READER = TemporalReadoutConfig()
GAP = 800_000
OLD = 'a9bd83bb-3d57-4eab-859d-68312f6b2b17'
DIALOGUE = ['甲是松子。', '乙是铃铛。', '丙问甲，谁是铃铛？甲说：乙是铃铛。',
 '丙问乙，谁是松子？乙说：甲是松子。', '甲对乙说：我是松子，你是铃铛。',
 '乙对甲说：我是铃铛，你是松子。', '谁是松子？甲是松子。', '谁是铃铛？乙是铃铛。',
 '松子是谁？松子是甲。', '铃铛是谁？铃铛是乙。']
FAMILY = ['C的父亲是B。', 'B的父亲是A。', 'C的爷爷是A。', '父亲的父亲是爷爷。',
 'F的父亲是E。', 'E的父亲是D。', 'F的爷爷是D。']
HELD = ['Z的父亲是Y。', 'Y的父亲是X。', 'W的父亲是V。', 'V的父亲是U。']
CROSSED = ['Z的父亲是Y。', 'Y的父亲是U。', 'W的父亲是V。', 'V的父亲是X。']

def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False).encode()

def write_new(path, value):
    with path.open('xb') as f:
        f.write(encoded(value))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def blocks(sentences, rounds=3, repeats=20, stage='dialogue'):
    return [dict(text=s, sweep=i, repetitions=repeats, stage=stage)
            for i in range(1, rounds+1) for s in sentences]

def curriculum():
    common = blocks(DIALOGUE) + blocks(FAMILY, stage='family') + blocks(DIALOGUE, 1, 5, 'review')
    return dict(common=common, normal=common+blocks(HELD, stage='held'),
                crossed=common+blocks(CROSSED, stage='held'),
                swapped=blocks([s.replace('松子','TEMP').replace('铃铛','松子').replace('TEMP','铃铛') for s in DIALOGUE]))

def probe_group(group):
    if group == 'pair':
        return ['甲', '乙'], ['松子', '铃铛']
    if group == 'who':
        return ['谁是松子？', '谁是铃铛？', '松子是谁？', '铃铛是谁？'], ['甲', '乙']
    names, terms = (['C','F'], ['A','B','D','E']) if group == 'seen_family' else (['Z','W'], ['X','Y','U','V'])
    return [n+s for n in names for s in ['的爷爷是谁？','的父亲是谁？','']], terms

def inventory(db):
    with db.tx(OLD) as c:
        heads = c.execute('SELECT id,revision,state_hash,status FROM runs WHERE project_id=%s ORDER BY id', (OLD,)).fetchall()
        docs = c.execute('SELECT id,revision FROM research_documents WHERE project_id=%s ORDER BY id', (OLD,)).fetchall()
        notes = c.execute('SELECT id,revision FROM notes WHERE project_id=%s ORDER BY id', (OLD,)).fetchall()
    return hashlib.sha256(encoded(dict(runs=heads,documents=docs,notes=notes))).hexdigest()

def preflight():
    WORK.mkdir(parents=True, exist_ok=True)
    course = curriculum()
    maps = []
    for name, items in course.items():
        seen = Counter()
        for item in items:
            assert item['text'].endswith('。') and '【' not in item['text']
            assert item['repetitions'] >= 10 or seen[item['text']] >= 60
            seen[item['text']] += item['repetitions']
        assert sum(seen.values()) == {'common':1070,'normal':1310,'crossed':1310,'swapped':600}[name]
    for seed in SEEDS:
        sensor = TextSensor(seed, SENSOR)
        for text in {b['text'] for items in course.values() for b in items}:
            assert sensor.normalize(text) == unicodedata.normalize('NFKC',text)
            assert len(list(sensor.frames(text))) == 1
        for group in ['pair','who','seen_family','family']:
            cues, terms = probe_group(group)
            maps.append(dict(seed=seed,group=group,mapping=transduction(sensor,CalibrationProtocol(cues=cues,terms=terms))))
    # Instrumentation must not modify dynamics, including at the finer observation boundaries.
    plain, observed = create_engine(Config()), create_engine(Config())
    session = ReadoutSession(observed,record=lambda r: None,
             config={'structural_readout':{'enabled':False},'temporal_readout':asdict(READER)})
    sensor = TextSensor(SEEDS[0], SENSOR)
    for i in range(3):
        frames = list(sensor.frames(DIALOGUE[0]))
        for f in frames:
            plain.inject(replace(f['stimulus'],time_us=i*GAP+f['stimulus'].time_us))
        session.schedule(frames)
        plain.advance_to((i+1)*GAP)
        session.advance_to((i+1)*GAP)
    assert plain.capture_state().digest == observed.capture_state().digest, 'reader changed dynamics'
    write_new(HERE/'curriculum.json',course)
    write_new(HERE/'mapping.json',maps)
    write_new(HERE/'implementation.json',capture_implementation('native'))
    write_new(HERE/'preflight.json',dict(sensor=asdict(SENSOR),reader=asdict(READER),
       core=Config().to_dict(),observational_equivalence=True,preflight_deliveries=3,
       available_ram=psutil.virtual_memory().available,
       free_disks={d:shutil.disk_usage(d).free for d in ['D:/','E:/']}))
    print('Preflight passed: exact carriers/repetitions, default mapping, observer/Core equivalence.',flush=True)

def init():
    if META.exists():
        raise RuntimeError('study already initialized')
    db = Database(Settings.from_env().database_url)
    try:
        with db.tx() as c:
            before = c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        old = inventory(db)
        project = db.create_project({'id':LOCAL_USER}, '时序收敛复验：逐句20次与未见家系（2026-09-10）')
        book = notebooks.ensure_default(db,project['id'],LOCAL_USER)
        note_id = str(uuid4())
        note = notebooks.save_note(db,project['id'],LOCAL_USER,note_id,dict(
          operation_id=str(uuid4()),expected_revision=0,kind='note',collection_id=str(book['id']),
          title='实验设计：逐句20次，时序收敛与终态激活排序',
          body={'format':'markdown','text':(HERE/'protocol.md').read_text(encoding='utf-8')}))
        write_new(META,dict(project_id=str(project['id']),notebook_id=str(book['id']),
          protocol_note_id=note_id,protocol_note_hash=note['content_hash'],database_bytes_before=before,
          old_inventory_before=old,quota_start_percent=72,quota_stop_percent=90,
          frozen_sha256={n:sha(HERE/n) for n in ['run.py','protocol.md','curriculum.json','mapping.json','implementation.json','preflight.json']}))
        print('Created isolated project and protocol note:',project['id'],flush=True)
    finally:
        db.close()

class Study:
    def __init__(self, seed):
        self.seed, self.started, self.peak = seed,time.monotonic(),0
        self.meta = json.loads(META.read_bytes())
        for name,value in self.meta['frozen_sha256'].items():
            assert sha(HERE/name) == value, f'frozen file changed: {name}'
        self.path = WORK/f'seed-{seed}-results.json'
        self.trace = WORK/f'seed-{seed}-trace.jsonl'
        if self.path.exists() or self.trace.exists():
            raise RuntimeError('existing seed evidence cannot be overwritten')
        self.project = self.meta['project_id']
        self.db = Database(Settings.from_env().database_url)
        self.impl = capture_implementation('native')
        expected = json.loads((HERE/'implementation.json').read_bytes())
        for k in ['source_sha256','native_binary_sha256']:
            assert self.impl[k] == expected[k], f'implementation changed: {k}'
        self.cap = {'executor':str(Path(__file__).relative_to(ROOT)),'scope':self.project,
          'features':{k:{'state':'available'} for k in ['worker.core','worker.probe_calibration_v1','worker.temporal_probe_v1']}}
        self.db.announce_worker(WORKER,self.cap)
        self.previous = sum(json.loads(p.read_bytes())['elapsed_s'] for p in WORK.glob('seed-*-results.json'))
        self.rows, self.estimated = [],0
        self.refresh_budget()

    def refresh_budget(self):
        with self.db.tx(self.project) as c:
            physical = c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        self.estimated = max(0, physical-self.meta['database_bytes_before'])

    def guard(self, engine=None):
        self.peak = max(self.peak,psutil.Process().memory_info().rss)
        if self.peak > 2*1024**3 or psutil.virtual_memory().available < 3*1024**3:
            raise MemoryError('memory reserve')
        if min(shutil.disk_usage('D:/').free,shutil.disk_usage(WORK).free) < 15*1024**3:
            raise MemoryError('disk reserve')
        local = sum(p.stat().st_size for directory in [WORK,HERE] for p in directory.iterdir() if p.is_file())
        if self.estimated+local > 3*1024**3:
            raise MemoryError('3 GiB computation stop; 1 GiB reserved for publication')
        if self.previous+time.monotonic()-self.started > 1800:
            raise TimeoutError('30 minute cumulative computation budget')
        if engine and (engine.metrics()['nodes'] > 2000 or engine.metrics()['edges'] > 100000):
            raise MemoryError('network budget')
        q = HERE/'quota-monitor.json'
        if q.exists() and json.loads(q.read_bytes())['used_percent'] >= self.meta['quota_stop_percent']:
            raise TimeoutError('account allowance stop')

    def claim(self, job_id):
        self.db.announce_worker(WORKER,self.cap)
        with self.db.tx(self.project) as c:
            job = c.execute("UPDATE jobs SET status='leased',worker_id=%s,generation=generation+1,attempts=attempts+1,lease_until=clock_timestamp()+interval '5 minutes' WHERE id=%s AND project_id=%s AND status='pending' RETURNING *",(WORKER,job_id,self.project)).fetchone()
            if not job: raise RuntimeError('owned job unavailable')
            c.execute('INSERT INTO job_assignments(project_id,job_id,generation,worker_id,required_features,capabilities) VALUES(%s,%s,%s,%s,%s,%s)',(self.project,job_id,job['generation'],WORKER,job['required_features'],Jsonb(self.cap)))
        return job

    def probe(self, run, cp, group, fixed=False):
        self.guard()
        cues,terms = probe_group(group)
        protocol = (CalibrationProtocol(cues=cues,terms=terms,intensities=[1.0],route='continuation',blank_us=0,learning_during_probe=True)
                    if fixed else TemporalProbeProtocol(cues=cues,intensities=[1.0,0.0],max_wall_seconds=180))
        requested = calibration.request(self.db,self.project,run['id'],LOCAL_USER,
                    operation_id=uuid4(),protocol=protocol.model_dump(mode='json'),checkpoint_id=cp['id'])
        job = self.claim(requested['job_id'])
        try:
            completion = calibration.execute(self.db,job,implementation=self.impl)
            self.db.finish(job,result=completion)
        except Exception as exc:
            self.db.finish(job,error=str(exc))
            raise
        result = calibration.result(self.db,self.project,requested['id'])
        file = WORK/f"calibration-{requested['id']}.json"
        write_new(file,result)
        self.refresh_budget()
        counts = Counter(r.get('classification','fixed-window') for r in result['rows'])
        print(f'  {group}/{"fixed" if fixed else "temporal"}: {dict(counts)}',flush=True)
        return dict(id=str(requested['id']),file=file.name,artifacts=completion,group=group,
                    classification_counts=counts,mode='fixed' if fixed else 'temporal')

    def start(self, arm, image=None, inherited=None, origin=None):
        e = create_engine(state=image) if image else create_engine(Config())
        spec = RunSpec(environment='manual',clock='unbounded',duration_s=None,seed=self.seed,
                       config=e.config.to_dict(),text_sensor=SENSOR,structural_readout={'enabled':False},temporal_readout=asdict(READER))
        run = self.db.create_run(self.project,f'时序/逐句20次/{self.seed}/{arm}',spec.model_dump())
        records = []
        context = dict(initialized=True,start_us=str(e.time_us),origin=origin)
        inputs = RuntimeInputs(self.db,self.project,run['id'],e,spec,context,e.time_us,initial_image=image.to_dict() if image else None)
        reader_state = copy.deepcopy(inherited)
        if reader_state: reader_state['run_id'] = str(run['id'])
        session = ReadoutSession(e,record=records.append,
          state={'schema':SESSION_VERSION,'session_id':str(run['id']),'readouts':reader_state},
          config={'structural_readout':{'enabled':False},'temporal_readout':asdict(READER)},
          policies=spec.source_policies,
          event_sink=lambda event,delivery: inputs.changes['delivered'].append(delivery) if delivery and delivery.get('envelope_id') else None)
        session.bus = inputs.bus  # One authoritative bus owns both DB receipts and reader delivery boundaries.
        return dict(e=e,spec=spec,run=run,inputs=inputs,session=session,records=records,revision=0,
                    arm=arm,origin=origin,count=1070 if image else 0,start_us=e.time_us)

    def save(self, runtime, label, groups):
        e,inputs,session = runtime['e'],runtime['inputs'],runtime['session']
        image = e.capture_state()
        context = dict(initialized=True,protocol=runtime['spec'].model_dump(),
          start_us=str(runtime['start_us']),end_us=str(e.time_us),input_bus=inputs.bus.capture(),
          input_bus_run_id=str(runtime['run']['id']),readouts=session.host.capture(),implementation=self.impl,
          source_enabled=True,exploration=dict(stage=label,seed=self.seed,arm=runtime['arm'],
                    count=runtime['count'],gap_us=GAP,origin=runtime['origin']))
        cp = self.db.save_checkpoint(self.project,runtime['run']['id'],image,expected_revision=runtime['revision'],
             status='completed',observations=[e.metrics()],events=runtime['records'],
             input_changes=inputs.take_changes(),context=context)
        runtime['revision'] += 1
        runtime['records'].clear()
        self.refresh_budget()
        row = dict(seed=self.seed,arm=runtime['arm'],stage=label,count=runtime['count'],
              run_id=str(runtime['run']['id']),checkpoint_id=str(cp['id']),source_hash=image.digest,
              metrics=e.metrics(),measurements={})
        self.rows.append(row)
        for group in groups:
            row['measurements'][group] = self.probe(runtime['run'],cp,group)
        if label == 'final' and runtime['arm'] == 'normal':
            for group in ['pair','family']:
                row['measurements'][group+'/fixed'] = self.probe(runtime['run'],cp,group,fixed=True)
        assert e.capture_state().digest == image.digest
        print(f"seed {self.seed} {runtime['arm']} {label}: {runtime['count']} inputs, {time.monotonic()-self.started:.1f}s, {self.estimated/2**20:.1f} MiB DB growth",flush=True)
        return image,cp,context

    def teach(self, runtime, items, milestones):
        sensor,e = TextSensor(self.seed,SENSOR),runtime['e']
        last = None
        for block in items:
            for rep in range(1,block['repetitions']+1):
                self.guard(e)
                if e.life == 'dead': raise RuntimeError('training died; no resurrection')
                text,at = block['text'],e.time_us
                frames = [dict(f,stimulus=replace(f['stimulus'],time_us=at+f['stimulus'].time_us)) for f in sensor.frames(text)]
                env = envelope_record(uuid4(),'text-sensor','manual-cli-text',{'text':text,'intensity':1},
                      {'seed':self.seed,'adapter':asdict(SENSOR),'transduction':sensor.describe(text)},
                      len(frames),sum(len(f['stimulus'].channels) for f in frames),version=TEXT_VERSION)
                runtime['inputs'].changes['envelopes'].append(env)
                runtime['inputs'].schedule(env,frames)
                runtime['session'].advance_to(at+GAP)
                runtime['count'] += 1
                if rep == block['repetitions']:
                    with self.trace.open('ab') as f:
                        f.write(json.dumps(dict(seed=self.seed,arm=runtime['arm'],count=runtime['count'],
                          block=block,metrics=e.metrics()),ensure_ascii=False,allow_nan=False).encode()+b'\n')
                if runtime['count'] in milestones:
                    label,groups = milestones[runtime['count']]
                    last = self.save(runtime,label,groups)
            if runtime['count']%100 == 0:
                self.refresh_budget()
                print(f"seed {self.seed} {runtime['arm']}: {runtime['count']} inputs",flush=True)
        return last

    def execute(self):
        course = curriculum()
        normal = self.start('normal')
        stages = {40:('pair_20_each',['pair']),200:('dialogue_1',['pair','who']),
                  600:('dialogue_3',['pair','who']),1070:('review',['seen_family'])}
        image,cp,context = self.teach(normal,course['common'],stages)
        origin = dict(run_id=str(normal['run']['id']),checkpoint_id=str(cp['id']),source_hash=image.digest,
                      inheritance='complete state continuation including readout baseline')
        self.teach(normal,course['normal'][len(course['common']):],{1310:('final',['pair','who','family'])})
        crossed = self.start('crossed',image,context['readouts'],origin)
        self.teach(crossed,course['crossed'][len(course['common']):],{1310:('final',['family'])})
        if self.seed in SEEDS[:2]:
            swapped = self.start('swapped')
            self.teach(swapped,course['swapped'],{k:v for k,v in stages.items() if k<=600})

    def close(self, error=None):
        self.refresh_budget()
        after = inventory(self.db)
        write_new(self.path,dict(seed=self.seed,rows=self.rows,elapsed_s=time.monotonic()-self.started,
          peak_rss=self.peak,estimated_database_growth=self.estimated,error=error,
          old_inventory_after=after,old_unchanged=after==self.meta['old_inventory_before']))
        self.db.close()
        assert after == self.meta['old_inventory_before'], 'old experiment metadata changed'

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('phase',choices=['preflight','init','seed'])
    p.add_argument('--seed',type=int,choices=SEEDS)
    args = p.parse_args()
    if args.phase in ['preflight','init']:
        globals()[args.phase]()
    else:
        if args.seed is None: p.error('--seed required')
        study,error = Study(args.seed),None
        try:
            study.execute()
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            study.close(error)
