"""Registered cross-version inertial-response study. Production kernels are read-only."""
import argparse
import copy
from dataclasses import replace
import gc
import gzip
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(HERE),str(HERE.parent),str(ROOT/'src')]
import spec as design
import support as s
from threemind_core import Stimulus
from threemind_kernels.registry import resolve_kernel
from threemind_runtime import ArtifactCodec
from threemind_runtime.readout_session import ReadoutSession

_sp=importlib.util.spec_from_file_location('r51m_body_functions',HERE.parent/'body_memory/study.py')
f=importlib.util.module_from_spec(_sp);_sp.loader.exec_module(f)
sys.path.insert(0,str(HERE))
NS=UUID('be832270-73bf-5dba-99c6-9f6d57bd2f70')
PROJECT=f.PROJECT
RAW_CAP=2*2**30
PREFIX='threemind.continuous-memory/'
VERSIONS=('2','3.1','5.1','5.3','6.1')
BASES=('v2','v61','v2-prequeue','v61-prequeue')

def read(p): return design.load(p)
def state(p): return ArtifactCodec.decode(Path(p).read_bytes())
def engine(kernel,config=None,image=None): return resolve_kernel(kernel).create(config,state=image,backend='native')

def freeze_check(work,calibration=False):
    frozen=read(work/'frozen.json')
    for rel,sha in frozen['sources'].items(): assert s.sha(ROOT/rel)==sha,rel
    from _threemind_native import _threemind_native as native
    assert s.sha(native.__file__)==frozen['native_sha256']
    assert read(work/'registration.json')['pending']==0
    if calibration:
        assert s.sha(work/'subjects.json')==read(work/'calibration.json')['subjects_sha256']

def record_state(path,image):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=ArtifactCodec.encode(image)
    assert ArtifactCodec.decode(raw).digest==image.digest
    return s.blob(path,raw)

def copied_materials(work):
    old=ROOT/'.work/memory-transfer-20260930/cases'
    manifest={}
    for subj in design.subjects(.018):
        if subj['variant']!='v2':continue
        for stage in design.stages(subj):
            if stage.get('sign')==0:continue
            source=design.physical_folder(old,subj,stage)
            for name in ('inputs-frames.jsonl.gz','result.json','parent-state.json.gz','trajectory.json.gz'):
                p=source/name
                if not p.exists():
                    assert name=='trajectory.json.gz';continue
                rel=p.relative_to(old);dest=work/'historical'/rel
                if dest.exists():continue
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
                assert s.sha(p)==s.sha(dest)
                manifest[dest.relative_to(work).as_posix()]={'source':str(p),'sha256':s.sha(p),'bytes':p.stat().st_size}
    return manifest

def register(work):
    assert not work.exists()
    for name in ('fixed-readout61-v1','body-transfer61-v1'):
        done=read(work.parent/name/'publication/completion.json')
        assert done['coverage']=='verified' and done['pending']==0 and not done['scientific_stop']
    s.base.resource_check(work.parent)
    assert shutil.disk_usage(work.parent).free>31.125*2**30
    work.mkdir()
    manifest=copied_materials(work)
    reference=work/'historical/revalidation-reference';reference.mkdir()
    for previous,name in (('body-memory61-v1','body-memory-cases.json'),('body-transfer61-v1','body-transfer-cases.json')):
        source=work.parent/previous/'cases.json';dest=reference/name
        shutil.copyfile(source,dest);assert s.sha(source)==s.sha(dest)
        manifest[dest.relative_to(work).as_posix()]={'source':str(source),'sha256':s.sha(source),'bytes':source.stat().st_size}
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))
    paths += [HERE.parent/'support.py',HERE.parent/'audit.py',HERE.parent/'body_memory/study.py',
              HERE.parent/'body_transfer/analyze.py',ROOT/'lab/explorations/2026-09-30-memory-transfer/materials.py',
              ROOT/'lab/explorations/2026-09-30-memory-transfer/common.py',
              ROOT/'lab/explorations/2026-10-16-mechanism-discovery/pilot_m2.py',ROOT/'lab/tools/study_lock.py',
              ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
    for package in ('threemind_core','threemind_kernels','threemind_runtime'):
        paths+=list((ROOT/'src'/package).rglob('*.py'))
    paths=sorted(set(paths))
    from _threemind_native import _threemind_native as native
    s.base.original(work/'frozen.json',{'sources':{p.relative_to(ROOT).as_posix():s.sha(p) for p in paths},
        'native_sha256':s.sha(native.__file__),'historical_evidence':manifest,
        'versions':list(VERSIONS),'formal_material_blocks':4,'independent_calibration_seed':930198})
    for p in paths:
        dest=work/'frozen-source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    from check_plan import check
    s.base.original(work/'plan-check.json',check(work/'historical',reference))
    import httpx
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,PROJECT,client=client)
        rec.register({'source_key':'r51m:inertial-reversal:20261113:v1',
            'title':'R51m：惯性感官反向响应在新旧内核中变化的原因定位','classification':'formal',
            'execution_status':'running','executor':'ai','kernels':[PREFIX+v for v in VERSIONS],
            'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'formal_material_blocks':4,'configurations':17,'teaching_subjects':320,'formal_stages':1792,
                        'calibration_not_formal':True,'production_changes':False}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R51m protocol '+lang,
                'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result={'project':PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)

def config_for(subj):
    # /2 uses its genuine declared defaults. Compare all recorded E18 keys separately.
    return resolve_kernel(subj['kernel']).configuration(subj['config'])

def observe(e):
    before=e.capture_state().digest
    nodes,graph,metrics=e.observation_nodes(),e.graph(),e.metrics()
    assert before==e.capture_state().digest
    assert len(nodes)<=2000 and metrics['edges']<=20000
    return {'time_us':e.time_us,'nodes':nodes,'graph':graph,'metrics':metrics}

def trial(work,subj,stage):
    folder=work/'subjects'/subj['key']/stage['name'];folder.mkdir(parents=True,exist_ok=False)
    parent_path=work/'subjects'/subj['key']/stage['parent']/'final.tmind' if stage['parent'] else None
    parent=state(parent_path) if parent_path else None
    e=engine(subj['kernel'],None if parent else config_for(subj),parent)
    initial=e.capture_state();record_state(folder/'initial.tmind',initial)
    assert e.time_us==stage['begin_us']
    if parent:assert parent.digest==initial.digest
    mappings=f.material.identities(subj['seed'])
    rows=design.inputs(work/'historical',subj,stage,mappings)
    if stage.get('test_patch'):
        e.reconfigure(replace(e.config,**stage['test_patch']))
        assert e.time_us==stage['begin_us']
        changed=e.capture_state();record_state(folder/'intervened.tmind',changed)
        s.base.original(folder/'intervention.json',{'method':'public same-time reconfigure',
            'before':initial.digest,'after':changed.digest,'patch':stage['test_patch'],
            'before_config':initial.to_dict()['config'],'after_config':changed.to_dict()['config']})
    events=[];deliveries=[]
    def delivered(event,entry):
        if entry:deliveries.append(entry)
    session=ReadoutSession(e,record=events.append,config=f.READERS if 'sign' in stage else {k:{'enabled':False} for k in f.READERS},event_sink=delivered)
    s.base.original(folder/'initial-observer.json',session.capture())
    index=0;points=[];start=time.monotonic()
    def queue_due():
        nonlocal index
        while index<len(rows) and rows[index]['enqueue_us']==e.time_us:
            row=rows[index]
            session.schedule([{'stimulus':Stimulus.from_dict(row['stimulus'])}],source=row['source'],
                adapter_id='registered-E18-replay',at=0,envelope_id=uuid5(NS,subj['key']+'/'+stage['name']+'/'+str(index)))
            index+=1
    def budget():
        if time.monotonic()-start>300:raise RuntimeError('stage budget; preserve in-flight')
    queue_due();points.append(observe(e))
    while e.time_us<stage['end_us']:
        target=min(stage['end_us'],((e.time_us//100000)+1)*100000,
                   rows[index]['enqueue_us'] if index<len(rows) else stage['end_us'])
        assert target>e.time_us
        session.advance_to(target,guard=budget)
        if e.life=='dead':raise RuntimeError('new subject death; preserve in-flight')
        if (e.time_us-stage['begin_us'])%100000==0:points.append(observe(e))
        queue_due()
    assert index==len(rows)
    assert len(deliveries)==len(rows) and session.bus.pending_count()==0
    if 'sign' in stage:session.host.close(e.time_us,'run_ended')
    final=e.capture_state();saved=record_state(folder/'final.tmind',final)
    s.base.original(folder/'observer.json',session.capture())
    s.base.original(folder/'input.json',{'subject':subj,'stage':stage,'frames':rows,'mappings':mappings})
    s.base.original(folder/'delivered.json.gz',deliveries,compressed=True)
    s.base.original(folder/'trajectory.json.gz',{'points':points,'events':events},compressed=True)
    result={'subject':subj['key'],'variant':subj['variant'],'kernel':subj['kernel'],'seed':subj['seed'],
        'preset':subj['preset'],'mode':subj['mode'],'stage':stage['name'],'begin_us':stage['begin_us'],'end_us':e.time_us,
        'status':'complete','parent_sha256':parent.digest if parent else None,'initial_sha256':initial.digest,
        'final_sha256':final.digest,'final_file':saved,'wall_seconds':time.monotonic()-start,
        'life':e.life,'inputs':len(rows),'targets':[mappings['A'],mappings['B']],
        'sign':stage.get('sign'),'arm':stage.get('arm'),'queue_policy':subj['queue_policy']}
    s.base.original(folder/'result.json',result)
    return result

def instrument_sequence(version,mode):
    kernel=PREFIX+version;e=engine(kernel,{'seed':930198})
    frames=[Stimulus(t,((1421,.2),(1823,.3)),.2) for t in (0,200000,700000)]
    session=ReadoutSession(e,record=lambda _:None,config=f.READERS,event_sink=lambda event,entry:None) if mode!='plain' else None
    hashes=[]
    for t in range(0,1000001,10000):
        for stim in frames:
            if stim.time_us==t:
                if session:session.schedule([{'stimulus':stim}],at=0)
                else:e.inject(stim)
        if session:session.advance_to(t)
        else:e.advance_to(t)
        if mode=='observed':observe(e)
        if t==500000 and mode in ('restored','paused'):
            saved=e.capture_state();hashes.append(saved.digest)
            raw=ArtifactCodec.encode(saved);restored=ArtifactCodec.decode(raw)
            if mode=='restored':
                observer=session.capture();e=engine(kernel,image=restored)
                session=ReadoutSession(e,record=lambda _:None,state=observer,event_sink=lambda event,entry:None)
            else:time.sleep(.01)
            assert e.capture_state().digest==saved.digest
    return e.capture_state()

def apparatus(work):
    import psutil
    freeze_check(work)
    assert not any((work/n).exists() for n in ('apparatus.json','in-flight.json','STOP'))
    results={}
    with s.base.worker_lock(work),s.base.Guard(work):
        s.base.original(work/'in-flight.json',{'phase':'apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
        for version in VERSIONS:
            hashes={}
            for mode in ('plain','observed','restored','paused'):
                image=instrument_sequence(version,mode)
                assert image.to_dict()['dynamics']==PREFIX+version
                record_state(work/'apparatus'/f'{version}-{mode}.tmind',image);hashes[mode]=image.digest
            assert len(set(hashes.values()))==1
            results[version]=hashes
        s.base.original(work/'apparatus.json',{'passed':True,'scientific_blocks':0,'versions':results})
        (work/'in-flight.json').unlink()
    s.base.original(work/'apparatus-resources.json',read(work/'resource-summary.json'))
    print('apparatus passed',flush=True)

def calibration_trial(work,version,dose,patch,tag):
    e=engine(PREFIX+version,{'seed':930198,**patch})
    initial=e.capture_state()
    e.inject(Stimulus(0,((1421,1.),(1823,1.)),dose))
    records=[];first_absent=None
    for sec in range(1201):
        # Explicit independent maintenance input; no task response is read or scored.
        for t in ((sec*1000000-500000,sec*1000000) if sec else ()):
            e.inject(Stimulus(t,((2701,1.),),.2))
        e.advance_to(sec*1000000)
        if sec==0:
            e.inject(Stimulus(0,((2701,1.),),.2));e.advance_to(0)
        graph=e.graph();mapping={n['id']:n['channel'] for n in graph['nodes']}
        edges=[x for x in graph['edges'] if {mapping[x['source']],mapping[x['target']]}=={1421,1823}]
        records.append({'seconds':sec,'weights':[x['weight'] for x in edges],
                        'edge_count':len(edges),'nodes':len(graph['nodes']),'life':e.life})
        if sec>0 and not edges and first_absent is None:first_absent=sec
        assert e.life=='active'
    folder=work/'calibration'/tag
    record_state(folder/'initial.tmind',initial);record_state(folder/'final.tmind',e.capture_state())
    result={'version':version,'dose':dose,'patch':patch,'first_absent_seconds':first_absent,'records':records}
    s.base.original(folder/'result.json',result)
    return result

def calibrate(work):
    import psutil
    freeze_check(work)
    assert read(work/'apparatus.json')['passed']
    assert not any((work/n).exists() for n in ('calibration.json','in-flight.json','STOP'))
    result={};values=[]
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        for version in ('2','6.1'):
            for dose in (.03,.1,.3):
                if (work/'STOP').exists():raise RuntimeError('calibration resource STOP')
                tag=f'{version}-{dose}'
                s.base.original(work/'in-flight.json',{'phase':'calibration','unit':tag,'pid':os.getpid(),'created':psutil.Process().create_time()})
                result[tag]=calibration_trial(work,version,dose,{},tag)
                (work/'in-flight.json').unlink()
        for dose in (.03,.1,.3):
            t=result[f'2-{dose}']['first_absent_seconds']
            if t is not None:values+=result[f'6.1-{dose}']['records'][t]['weights']
        threshold=min(.249999,max(.008001,statistics.median(values)*1.0001)) if values else .018
        matched=0;comparison=[]
        for dose in (.03,.1,.3):
            if (work/'STOP').exists():raise RuntimeError('calibration resource STOP')
            tag=f'6.1-selected-{dose}'
            s.base.original(work/'in-flight.json',{'phase':'calibration-validation','unit':tag,'pid':os.getpid(),'created':psutil.Process().create_time()})
            r=calibration_trial(work,'6.1',dose,{'prune_weight':threshold},tag)
            (work/'in-flight.json').unlink()
            old=result[f'2-{dose}']['first_absent_seconds'];new=r['first_absent_seconds']
            ok=old is not None and new is not None and .5<=new/old<=2
            matched+=ok;comparison.append({'dose':dose,'old_seconds':old,'new_seconds':new,'matched':ok})
        subjects=design.subjects(threshold);s.base.original(work/'subjects.json',subjects)
        outcome={'selected_prune_weight':threshold,'valid_weights':values,'deletion_time_matched':matched>=2,
            'comparison':comparison,'formal_answers_used':False,'subjects_sha256':s.sha(work/'subjects.json')}
        s.base.original(work/'calibration.json',outcome)
    s.base.original(work/'calibration-resources.json',read(work/'resource-summary.json'))
    print(json.dumps(outcome),flush=True)

def run(work):
    import psutil
    freeze_check(work,True)
    assert not any((work/n).exists() for n in ('summary.json','in-flight.json','STOP'))
    from measurement import baseline_check
    subjects=read(work/'subjects.json');done=0;wall=time.monotonic();base_checked=False;stop_reason=None
    prior_seconds=sum(read(work/name)['wall_seconds'] for name in ('apparatus-resources.json','calibration-resources.json'))
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for subject in subjects:
            if subject['variant'] not in BASES and not base_checked:
                base=baseline_check(work);s.base.original(work/'baseline-check.json',base);base_checked=True
                if not base['passed']:
                    stop_reason='historical/new baseline reproduction failed'
                    s.base.original(work/'STOP',{'reason':stop_reason,'complete_stages':done});break
            for stage in design.stages(subject):
                if (work/'STOP').exists():break
                assert guard.thread.is_alive();s.base.resource_check(work)
                s.base.original(work/'in-flight.json',{'subject':subject['key'],'stage':stage['name'],
                    'pid':os.getpid(),'created':psutil.Process().create_time()})
                result=trial(work,subject,stage)
                (work/'in-flight.json').unlink();done+=1
                s.base.atomic_json(work/'current.json',{'completed_stages':done,'total_stages':1792,
                    'last_subject':subject['key'],'last_stage':stage['name']})
                if time.monotonic()-wall+prior_seconds>7200:
                    s.base.original(work/'STOP',{'reason':'two-hour budget','complete_stages':done});break
                del result;gc.collect()
            print(subject['key'],done,flush=True)
            if (work/'STOP').exists():break
            if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>RAW_CAP:
                s.base.original(work/'STOP',{'reason':'originals budget','complete_stages':done});break
        if done==1792 or stop_reason:
            s.base.original(work/'summary.json',{'status':'awaiting-analysis','stages':done,'planned_stages':1792,
                'formal_material_blocks':4,'wall_seconds':time.monotonic()-wall,'scientific_stop_reason':stop_reason})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','apparatus','calibrate','run'])
    p.add_argument('--work',type=Path,required=True);a=p.parse_args()
    {'register':register,'apparatus':apparatus,'calibrate':calibrate,'run':run}[a.action](a.work.resolve())
