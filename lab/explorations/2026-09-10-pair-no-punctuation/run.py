"""Dedicated two-sentence study, reusing the existing evidence/reader path."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import zipfile
from collections import Counter
from dataclasses import asdict,replace
from pathlib import Path
from uuid import uuid4

import psutil
from threemind_core import Config
from threemind_lab import calibration,notebooks
from threemind_lab.config import Settings
from threemind_lab.database import Database,LOCAL_USER
from threemind_lab.provenance import capture_implementation
from threemind_runtime import create_engine
from threemind_runtime.calibration import CalibrationProtocol,transduction
from threemind_runtime.readout_config import TemporalReadoutConfig
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.sensory import TextSensor,TextSensorConfig
from threemind_runtime.temporal_probe import TemporalProbeProtocol

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
WORK=ROOT/'.work/pair-no-punctuation-20260910'
META=HERE/'platform.json'
SEEDS=[41701,41702,41703]
SENSOR=TextSensorConfig()
READER=TemporalReadoutConfig()
GAP=800_000
WORKER='pair-no-punctuation-20260910-owned'
BASE=HERE.parent/'2026-09-10-temporal-repetition/run.py'
loader=importlib.util.spec_from_file_location('prior_temporal_study',BASE)
base=importlib.util.module_from_spec(loader);loader.loader.exec_module(base)
for key in ('HERE','ROOT','WORK','META','SEEDS','SENSOR','READER','GAP','WORKER'):
    setattr(base,key,globals()[key])
encoded,write_new,sha=base.encoded,base.write_new,base.sha


def probe_group(group):
    if group=='forward':return ['甲是','乙是','甲','乙'],['松子','铃铛']
    if group=='reverse':return ['松子','铃铛'],['甲','乙']
    raise ValueError(group)


def curriculum():
    return {arm:[dict(text=text,repetitions=20,sweep=sweep) for sweep in range(1,11) for text in sentences]
            for arm,sentences in [('AB',['甲是松子','乙是铃铛']),('BA',['乙是铃铛','甲是松子'])]}


def inventory(db):
    evidence={}
    for project in ('194a2f1f-4912-435b-b94e-d8ac64fe4788','62fd8734-a42a-4950-84d3-496c3bded189',
                    'a9bd83bb-3d57-4eab-859d-68312f6b2b17'):
        with db.tx(project) as c:
            runs=c.execute('SELECT id,revision,state_hash,status FROM runs WHERE project_id=%s ORDER BY id',(project,)).fetchall()
            docs=c.execute('SELECT id,revision FROM research_documents WHERE project_id=%s ORDER BY id',(project,)).fetchall()
            notes=c.execute('SELECT id,revision FROM notes WHERE project_id=%s ORDER BY id',(project,)).fetchall()
        evidence[project]=hashlib.sha256(encoded(dict(runs=runs,documents=docs,notes=notes))).hexdigest()
    return evidence


base.inventory=inventory
base.probe_group=probe_group


def prepare():
    if META.exists():raise RuntimeError('Existing study cannot be overwritten')
    WORK.mkdir(parents=True,exist_ok=True)
    course=curriculum();maps=[]
    for arm,blocks in course.items():
        assert Counter(b['text'] for b in blocks)=={'甲是松子':10,'乙是铃铛':10}
        assert all(b['repetitions']==20 for b in blocks)
    for seed in SEEDS:
        sensor=TextSensor(seed,SENSOR)
        for text in ['甲是松子','乙是铃铛','甲是','乙是','甲','乙','松子','铃铛']:
            assert sensor.normalize(text)==text and len(list(sensor.frames(text)))==1
        for group in ('forward','reverse'):
            cues,terms=probe_group(group)
            plain=transduction(sensor,CalibrationProtocol(cues=cues,terms=terms))
            contextual=transduction(sensor,CalibrationProtocol(cues=cues,
                    terms=['甲是松子','乙是铃铛'] if group=='forward' else terms))
            if group=='forward':
                for field in ('terms','masks','coverage'):
                    contextual[field]={term:contextual[field][sentence]
                            for term,sentence in [('松子','甲是松子'),('铃铛','乙是铃铛')]}
            maps.append(dict(seed=seed,group=group,mapping=plain,contextual=contextual))
    plain,observed=create_engine(),create_engine()
    session=ReadoutSession(observed,record=lambda r:None,
                          config={'structural_readout':{'enabled':False},'temporal_readout':asdict(READER)})
    for i in range(3):
        frames=list(TextSensor(SEEDS[0]).frames('甲是松子'))
        plain.inject(replace(frames[0]['stimulus'],time_us=i*GAP))
        session.schedule(frames)
        plain.advance_to((i+1)*GAP);session.advance_to((i+1)*GAP)
    assert plain.capture_state().digest==observed.capture_state().digest
    implementation=capture_implementation('native')
    write_new(HERE/'curriculum.json',course)
    write_new(HERE/'mapping.json',maps)
    write_new(HERE/'implementation.json',implementation)
    write_new(HERE/'preflight.json',dict(core=Config().to_dict(),sensor=asdict(SENSOR),reader=asdict(READER),
        observer_equivalence=True,only_exact_unpunctuated_carriers=True,available_ram=psutil.virtual_memory().available,
        free_disks={d:shutil.disk_usage(d).free for d in ['D:/','E:/']},
        instrumentation_dependencies={BASE.relative_to(ROOT).as_posix():sha(BASE)}))
    with zipfile.ZipFile(HERE/'implementation-source.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for name in implementation['source_files']:archive.write(ROOT/name,name)
        archive.write(BASE,BASE.relative_to(ROOT).as_posix())
    db=Database(Settings.from_env().database_url)
    try:
        with db.tx() as c:before=c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        old=inventory(db)
        project=db.create_project({'id':LOCAL_USER},'松子铃铛：无标点单独配对与时序终态（2026-09-10）')
        book=notebooks.ensure_default(db,project['id'],LOCAL_USER)
        note_id=str(uuid4())
        note=notebooks.save_note(db,project['id'],LOCAL_USER,note_id,dict(operation_id=str(uuid4()),
            expected_revision=0,kind='note',collection_id=str(book['id']),
            title='实验设计：两句无标点，各200次，六个时序检验',
            body={'format':'markdown','text':(HERE/'protocol.md').read_text(encoding='utf-8')}))
        write_new(META,dict(project_id=str(project['id']),notebook_id=str(book['id']),protocol_note_id=note_id,
            protocol_note_hash=note['content_hash'],database_bytes_before=before,old_inventory_before=old,
            quota_start_percent=77,quota_stop_percent=81,quota_max_percent=82,
            frozen_sha256={n:sha(HERE/n) for n in ('run.py','protocol.md','curriculum.json','mapping.json',
                                                 'implementation.json','preflight.json')}))
        print(encoded(dict(project_id=str(project['id']),database_bytes=before,
              sensor_defaults=asdict(SENSOR),observer_equivalence=True)).decode(),flush=True)
    finally:db.close()


class Study(base.Study):
    def __init__(self,seed):
        super().__init__(seed)
        deps=json.loads((HERE/'preflight.json').read_bytes())['instrumentation_dependencies']
        assert all(sha(ROOT/n)==h for n,h in deps.items())

    def guard(self,engine=None):
        self.peak=max(self.peak,psutil.Process().memory_info().rss)
        if self.peak>1024**3 or psutil.virtual_memory().available<3*1024**3:
            raise MemoryError('Memory reserve')
        if min(shutil.disk_usage(d).free for d in ('D:/','E:/'))<15*1024**3:
            raise MemoryError('Disk reserve')
        local=sum(p.stat().st_size for d in (HERE,WORK) for p in d.iterdir() if p.is_file())
        if self.estimated+local>384*1024**2:raise MemoryError('384 MiB computation stop')
        if self.previous+time.monotonic()-self.started>600:raise TimeoutError('600 second cumulative budget')
        if time.monotonic()-self.started>175:raise TimeoutError('175 second soft process deadline')
        if engine:
            m=engine.metrics()
            if m['nodes']>256 or m['edges']>50_000:raise MemoryError('Graph observation budget')
        q=HERE/'quota-monitor.json'
        if q.exists() and json.loads(q.read_bytes())['used_percent']>=81:raise TimeoutError('Quota stop')

    def probe(self,run,cp,group,fixed=False):
        self.guard()
        cues,terms=probe_group(group)
        protocol=(CalibrationProtocol(cues=cues,terms=terms,intensities=[1.,0.],route='continuation',
                   blank_us=0,learning_during_probe=True) if fixed else
                  TemporalProbeProtocol(cues=cues,intensities=[1.,0.],max_wall_seconds=60))
        request=calibration.request(self.db,self.project,run['id'],LOCAL_USER,operation_id=uuid4(),
                      protocol=protocol.model_dump(mode='json'),checkpoint_id=cp['id'])
        job=self.claim(request['job_id'])
        try:
            completion=calibration.execute(self.db,job,implementation=self.impl)
            self.db.finish(job,result=completion)
        except Exception as exc:
            self.db.finish(job,error=str(exc));raise
        result=calibration.result(self.db,self.project,request['id'])
        file=WORK/f"calibration-{request['id']}.json";write_new(file,result)
        self.refresh_budget()
        counts=Counter(r.get('classification','fixed-window') for r in result['rows'])
        print(f'  {group}/{"fixed" if fixed else "temporal"}: {dict(counts)}',flush=True)
        if any(r.get('classification')=='not_observed' for r in result['rows']):
            # Preserve the result and let the caller keep this case identifiable.
            print('  Measurement contains not_observed; reason retained.',flush=True)
        return dict(id=str(request['id']),file=file.name,artifacts=completion,group=group,
                    classification_counts=counts,mode='fixed' if fixed else 'temporal')

    def execute(self):
        for arm,blocks in curriculum().items():
            runtime=self.start(arm)
            if arm=='AB':self.save(runtime,'untrained',['forward','reverse'])
            image,cp,context=self.teach(runtime,blocks,{40:('each20',['forward','reverse']),
                                                       400:('each200',['forward','reverse'])})
            row=self.rows[-1]
            for group in ('forward','reverse'):
                row['measurements'][group+'/fixed']=self.probe(runtime['run'],cp,group,fixed=True)
            assert runtime['e'].capture_state().digest==image.digest


def supervise(seed):
    result=WORK/f'seed-{seed}-results.json';log=WORK/f'seed-{seed}.log'
    if result.exists() or log.exists():raise RuntimeError('Never rerun existing evidence in place')
    previous=sum(json.loads(p.read_bytes())['elapsed_s'] for p in WORK.glob('seed-*-results.json'))
    if previous>=600:raise RuntimeError('Cumulative computation limit')
    owned={};started=time.monotonic();parent=None
    with log.open('xb') as stream:
        child=subprocess.Popen([sys.executable,str(HERE/'run.py'),'seed',str(seed)],
            stdout=stream,stderr=subprocess.STDOUT,cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            parent=psutil.Process(child.pid)
            while child.poll() is None:
                try:
                    for p in [parent,*parent.children(recursive=True)]:owned[(p.pid,p.create_time())]=p
                    rss=sum(p.memory_info().rss for p in owned.values() if p.is_running())
                except psutil.NoSuchProcess:
                    continue
                if time.monotonic()-started>min(180,600-previous) or rss>1.5*1024**3:
                    raise TimeoutError('Owned process tree budget reached')
                if psutil.virtual_memory().available<3*1024**3:raise MemoryError('Host reserve')
                time.sleep(.5)
            if child.returncode:raise RuntimeError('Study stopped; inspect '+str(log))
        except BaseException:
            for p in reversed(list(owned.values())):
                try:p.kill()
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            child.wait(timeout=10)
            raise
    print(log.read_text(encoding='utf-8'),flush=True)


if __name__=='__main__':
    phase=sys.argv[1]
    if phase=='prepare':prepare()
    elif phase=='supervise':supervise(int(sys.argv[2]))
    elif phase=='seed':
        seed=int(sys.argv[2]);assert seed in SEEDS
        study,error=Study(seed),None
        try:study.execute()
        except Exception as exc:error=f'{type(exc).__name__}: {exc}';raise
        finally:study.close(error)
    else:raise ValueError(phase)
