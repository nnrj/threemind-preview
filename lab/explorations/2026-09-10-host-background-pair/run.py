"""Bounded pairing study with an uninterrupted real host recording."""
import copy
import importlib.util
import json
import random
import shutil
import sys
import time
from collections import Counter
from dataclasses import asdict,replace
from pathlib import Path
from uuid import uuid4

import psutil
from threemind_core import Config
from threemind_lab import calibration,notebooks
from threemind_lab.config import Settings
from threemind_lab.database import Database,LOCAL_USER
from threemind_lab.input_cycle import RuntimeInputs
from threemind_lab.inputs import envelope_record
from threemind_lab.protocols import RunSpec
from threemind_lab.provenance import capture_implementation
from threemind_runtime import create_engine
from threemind_runtime.calibration import CalibrationProtocol,transduction
from threemind_runtime.readout_config import TemporalReadoutConfig
from threemind_runtime.readout_session import ReadoutSession,SESSION_VERSION
from threemind_runtime.sensory import TextSensor,TextSensorConfig,TEXT_VERSION
from threemind_runtime.telemetry import HostTelemetryConfig,TelemetryEncoder,TELEMETRY_VERSION
from threemind_runtime.temporal_probe import TemporalProbeProtocol

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
WORK=ROOT/'.work/host-background-pair-20260910'
META=HERE/'platform.json'
SEEDS=[41701,41702]
SENSOR=TextSensorConfig()
READER=TemporalReadoutConfig()
HOST=HostTelemetryConfig(enabled=True)
GAP=10_000_000
WORKER='host-background-pair-owned'
BASE=HERE.parent/'2026-09-10-pair-no-punctuation/run.py'
loader=importlib.util.spec_from_file_location('pair_base',BASE)
prior=importlib.util.module_from_spec(loader);loader.loader.exec_module(prior)
for module in (prior,prior.base):
    for key in ('HERE','ROOT','WORK','META','SEEDS','SENSOR','READER','GAP','WORKER'):
        setattr(module,key,globals()[key])
encoded,sha,write_new=prior.encoded,prior.sha,prior.write_new
probe_group=prior.probe_group


def inventory(db):
    import hashlib
    projects=['2dabc73f-1f27-498b-83ae-93c4c6e10c1c','194a2f1f-4912-435b-b94e-d8ac64fe4788',
              '62fd8734-a42a-4950-84d3-496c3bded189']
    result={}
    for project in projects:
        with db.tx(project) as c:
            rows=c.execute('SELECT id,revision,state_hash,status FROM runs WHERE project_id=%s ORDER BY id',(project,)).fetchall()
            docs=c.execute('SELECT id,revision FROM research_documents WHERE project_id=%s ORDER BY id',(project,)).fetchall()
        result[project]=hashlib.sha256(encoded([rows,docs])).hexdigest()
    return result


prior.base.inventory=inventory


def curriculum():
    sentences=['甲是松子','乙是铃铛']
    later=sentences*10;random.Random(91010).shuffle(later)
    return [sentences[0]]*10+[sentences[1]]*10+later


def background(seed):
    assert (HERE/'capture-complete.json').exists(),'wait for complete host recording'
    encoder=TelemetryEncoder(seed,HOST)
    output=[]
    for line in (HERE/'host-recording.jsonl').read_text(encoding='utf-8').splitlines():
        sample=json.loads(line)
        stimulus,audit=encoder.encode(sample['measurements'],monotonic_s=sample['monotonic_s'],
                                      delivery_us=sample['elapsed_us']+1_000_000)
        output.append(dict(sample=sample,stimulus=replace(stimulus,intensity=.25) if stimulus else None,audit=audit))
    assert len(output)==415 and output[-1]['sample']['elapsed_us']>414_000_000
    return output


def prepare():
    if META.exists():raise RuntimeError('Do not overwrite a study')
    WORK.mkdir(parents=True,exist_ok=True)
    assert len(curriculum())==40 and Counter(curriculum())=={'甲是松子':20,'乙是铃铛':20}
    maps=[]
    for seed in SEEDS:
        frames=background(seed)
        assert all(r['stimulus'] is None or r['stimulus'].intensity==.25 for r in frames)
        sensor=TextSensor(seed,SENSOR)
        for group in ('forward','reverse'):
            cues,terms=probe_group(group)
            plain=transduction(sensor,CalibrationProtocol(cues=cues,terms=terms))
            contextual=transduction(sensor,CalibrationProtocol(cues=cues,
                terms=['甲是松子','乙是铃铛'] if group=='forward' else terms))
            if group=='forward':
                for key in ('terms','masks'):
                    contextual[key]={{'甲是松子':'松子','乙是铃铛':'铃铛'}.get(k,k):v for k,v in contextual[key].items()}
            maps.append(dict(seed=seed,group=group,mapping=plain,contextual=contextual))
    write_new(HERE/'curriculum.json',curriculum())
    write_new(HERE/'mapping.json',maps)
    write_new(HERE/'implementation.json',capture_implementation('native'))
    write_new(HERE/'preflight.json',dict(core=Config().to_dict(),sensor=asdict(SENSOR),reader=asdict(READER),
        host=asdict(HOST),host_frame_intensity=.25,training_intensity=.9,probe_intensity=.5,
        recording_sha256=sha(HERE/'host-recording.jsonl'),
        instrumentation_dependencies={BASE.relative_to(ROOT).as_posix():sha(BASE)}))
    db=Database(Settings.from_env().database_url)
    try:
        with db.tx() as c:size=c.execute('SELECT pg_database_size(current_database()) n').fetchone()['n']
        project=db.create_project({'id':LOCAL_USER},'宿主机背景配对：10秒间隔与分级强度（2026-09-10）')
        book=notebooks.ensure_default(db,project['id'],LOCAL_USER);note_id=str(uuid4())
        note=notebooks.save_note(db,project['id'],LOCAL_USER,note_id,dict(operation_id=str(uuid4()),
            expected_revision=0,kind='note',collection_id=str(book['id']),title='事先方案：背景0.25、教学0.9、检验0.5',
            body={'format':'markdown','text':(HERE/'protocol.md').read_text(encoding='utf-8')}))
        write_new(META,dict(project_id=str(project['id']),notebook_id=str(book['id']),protocol_note_id=note_id,
            protocol_note_hash=note['content_hash'],database_bytes_before=size,old_inventory_before=inventory(db),
            quota_start_percent=79,quota_stop_percent=81,quota_max_percent=82,
            frozen_sha256={n:sha(HERE/n) for n in ('run.py','protocol.md','curriculum.json','mapping.json',
                'implementation.json','preflight.json','host-recording.jsonl','capture.py')}))
        print('Created project',project['id'],flush=True)
    finally:db.close()


class Study(prior.Study):
    def guard(self,engine=None):
        now=time.monotonic()
        if engine is not None and now-getattr(self,'last_guard',0)<.25:return
        self.last_guard=now
        self.peak=max(self.peak,psutil.Process().memory_info().rss)
        if self.peak>1024**3 or psutil.virtual_memory().available<3*1024**3:raise MemoryError('memory limit')
        if min(shutil.disk_usage(d).free for d in ('D:/','E:/'))<15*1024**3:raise MemoryError('disk reserve')
        local=sum(p.stat().st_size for d in (HERE,WORK) for p in d.iterdir() if p.is_file())
        if self.estimated+local>192*1024**2:raise MemoryError('192 MiB compute stop')
        if self.previous+time.monotonic()-self.started>300:raise TimeoutError('300 second model budget')
        if time.monotonic()-self.started>145:raise TimeoutError('145 second seed budget')
        if engine:
            m=engine.metrics()
            if m['nodes']>512 or m['edges']>50_000:raise MemoryError('graph budget')
        if json.loads((HERE/'quota-monitor.json').read_bytes())['used_percent']>=81:raise TimeoutError('quota stop')

    def start(self,arm):
        e=create_engine(Config())
        spec=RunSpec(environment='replay' if arm=='host' else 'manual',clock='unbounded',seed=self.seed,
            config=e.config.to_dict(),text_sensor=SENSOR,structural_readout={'enabled':False},
            temporal_readout=asdict(READER),condition=arm+' / recorded host, intensity=.25 / text=.9, gap=10s')
        run=self.db.create_run(self.project,f'背景配对/{self.seed}/{arm}',spec.model_dump())
        inputs=RuntimeInputs(self.db,self.project,run['id'],e,spec,{},0)
        records=[]
        session=ReadoutSession(e,record=records.append,config={'structural_readout':{'enabled':False},
            'temporal_readout':asdict(READER)},policies=spec.source_policies,
            event_sink=lambda event,delivery: inputs.changes['delivered'].append(delivery) if delivery else None)
        session.bus=inputs.bus
        if arm=='host':
            recording_hash=sha(HERE/'host-recording.jsonl')
            for row in background(self.seed):
                stimulus=row['stimulus']
                if stimulus is None:continue
                sample=row['sample']
                env=envelope_record(uuid4(),'host-telemetry','host-telemetry',
                    {'sample_index':sample['index'],'recording_sha256':recording_hash},
                    {'seed':self.seed,'parameters':asdict(HOST),'replay':True,'frame_intensity':.25,
                     'captured_elapsed_us':sample['elapsed_us'],'feedback_delay_us':1_000_000},
                    1,len(stimulus.channels),version=TELEMETRY_VERSION)
                inputs.changes['envelopes'].append(env);inputs.schedule(env,[{'stimulus':stimulus}])
        return dict(e=e,spec=spec,run=run,inputs=inputs,session=session,records=records,revision=0,
                    arm=arm,origin=None,count=0,start_us=0)

    def probe(self,run,cp,group,fixed=False):
        self.guard()
        cues,terms=probe_group(group)
        protocol=(CalibrationProtocol(cues=cues,terms=terms,intensities=[.5,0.],route='continuation',
                    blank_us=0,learning_during_probe=True) if fixed else
                  TemporalProbeProtocol(cues=cues,intensities=[.5,0.],max_wall_seconds=60))
        request=calibration.request(self.db,self.project,run['id'],LOCAL_USER,operation_id=uuid4(),
                    protocol=protocol.model_dump(mode='json'),checkpoint_id=cp['id'])
        job=self.claim(request['job_id'])
        try:
            done=calibration.execute(self.db,job,implementation=self.impl);self.db.finish(job,result=done)
        except Exception as exc:self.db.finish(job,error=str(exc));raise
        result=calibration.result(self.db,self.project,request['id'])
        file=WORK/f"calibration-{request['id']}.json";write_new(file,result);self.refresh_budget()
        counts=Counter(r.get('classification','fixed-window') for r in result['rows'])
        print(group,'fixed' if fixed else 'temporal',dict(counts),flush=True)
        return dict(id=str(request['id']),file=file.name,artifacts=done,group=group,
                    classification_counts=counts,mode='fixed' if fixed else 'temporal')

    def execute(self):
        for arm in ('host','no-background'):
            runtime=self.start(arm);e=runtime['e'];sensor=TextSensor(self.seed,SENSOR)
            if arm=='host':self.save(runtime,'untrained',['forward','reverse'])
            for index,text in enumerate(curriculum()):
                self.guard(e)
                if e.life=='dead':break
                at=index*GAP
                assert e.time_us==at
                frames=[dict(f,stimulus=replace(f['stimulus'],time_us=at+f['stimulus'].time_us)) for f in sensor.frames(text,.9)]
                env=envelope_record(uuid4(),'text-sensor','manual-cli-text',{'text':text,'intensity':.9},
                    {'seed':self.seed,'adapter':asdict(SENSOR),'transduction':sensor.describe(text)},
                    len(frames),sum(len(f['stimulus'].channels) for f in frames),version=TEXT_VERSION)
                runtime['inputs'].changes['envelopes'].append(env);runtime['inputs'].schedule(env,frames)
                runtime['session'].advance_to(at+GAP,guard=lambda:self.guard(e))
                runtime['count']+=1
                with self.trace.open('ab') as f:f.write(encoded(dict(seed=self.seed,arm=arm,count=index+1,
                    text=text,time_us=e.time_us,metrics=e.metrics())).replace(b'\n',b'')+b'\n')
                if e.life=='dead':
                    self.save(runtime,'stopped_dead',[]);print(arm,'died',e.time_us,flush=True);break
                if index+1 in (20,40):
                    _,cp,_=self.save(runtime,'each10' if index==19 else 'each20',['forward','reverse'] if arm=='host' else [])
                    if index==39 and arm=='host':
                        for group in ('forward','reverse'):
                            self.rows[-1]['measurements'][group+'/fixed']=self.probe(runtime['run'],cp,group,True)


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    else:
        seed=int(sys.argv[2]);assert seed in SEEDS
        study,error=Study(seed),None
        try:study.execute()
        except Exception as exc:error=f'{type(exc).__name__}: {exc}';raise
        finally:study.close(error)
