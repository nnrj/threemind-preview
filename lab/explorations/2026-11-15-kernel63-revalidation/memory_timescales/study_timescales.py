"""Registered E12 replication using saved research copies and one scientific worker."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import execute_timescales as e
import measurement_timescales as m
mat=e.materials
s=e.s
ROOT=mat.ROOT
NS=UUID('28ede8f8-895d-5684-8b9e-13f411aa9995')
CAP=4*2**30


def read(path):
    path=Path(path)
    if path.exists():return mat.read(path)
    assert path.name=='intervention.json'
    return e.unpacked(path.with_suffix('.json.xz'))


def campaign_decision(work,decisions):
    old=read(work.parent/'memory-timescales61-v1/analysis.json')['decisions']
    fields=('default_retention_passed','stored_memory_passed','prefix_preserved_or_extended','sustained_mechanism_passed')
    lost=[name for name in fields if old[name] and not decisions[name]]
    return {'historical_targets':{name:old[name] for name in fields},
        'new_targets':{name:decisions[name] for name in fields},
        'original_joint_expectation_passed':not decisions['scientific_stop'],
        'newly_lost_positive_targets':lost,'scientific_stop':bool(lost),
        'known_negative_targets_remain_reported':True}


def check(work):
    prior=work.parent/'body-recovery-63-rerun-v1'
    e.support.check(prior)
    completion=read(prior/'publication/completion.json')
    assert completion['coverage']=='verified' and completion['pending']==0 and not completion['scientific_stop']
    frozen=read(work/'frozen.json')
    for rel,sha in frozen['sources'].items():assert s.sha(ROOT/rel)==sha,rel
    for rel,sha in frozen['materials'].items():assert s.sha(work/rel)==sha,rel
    assert s.sha(work/'cases.json')==frozen['cases_sha256']
    assert read(work/'registration.json')['pending']==0
    for name,digest in frozen['historical_reference'].items():
        assert s.sha(work.parent/'memory-timescales61-v1'/name)==digest,name
    return frozen


def register(work,exported):
    assert not work.exists()
    previous=work.parent/'body-recovery-63-rerun-v1';e.support.check(previous)
    completion=read(previous/'publication/completion.json')
    assert completion['coverage']=='verified' and completion['pending']==0 and not completion['scientific_stop']
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>37.125*2**30
    cases=mat.inventory();exports=read(exported/'manifest.json')
    assert exports['total_frames']==41248 and len(exports['inputs'])==592 and exports['created_engines']==0
    from verify_measurement_timescales import check as check_measurement
    proof=check_measurement();assert proof['passed'] and not proof['historical_stop']
    assert proof['measurement_source_sha256']==s.sha(m.__file__)
    history=work.parent/'memory-timescales61-v1'
    old=read(history/'analysis.json')['decisions']
    assert old['default_retention_passed'] and old['stored_memory_passed']
    assert not old['prefix_preserved_or_extended'] and not old['sustained_mechanism_passed']
    work.mkdir();materials={};old_costs={};legacy_costs={}
    for case,row in zip(cases,exports['inputs']):
        assert case['key']==row['key']
        src=exported/case['key']/'frames.jsonl'
        assert s.sha(src)==row['sha256'] and len(mat.normalize(src.read_bytes(),case))==row['frames']
        dest=work/'materials'/case['key'];dest.mkdir(parents=True)
        for name in ('frames.jsonl','receipt.json'):
            shutil.copyfile(src.with_name(name),dest/name)
            materials[(dest/name).relative_to(work).as_posix()]=s.sha(dest/name)
        assert read(mat.OLD/'cases'/case['key']/'result.json')['kernel']=='threemind.continuous-memory/1'
        legacy_costs[case['key']]=e.support.allocated(mat.OLD/'cases'/case['key'])
        old_costs[case['key']]=e.support.allocated(history/'cases'/case['key'])
        assert old_costs[case['key']]>0
    s.base.original(work/'cases.json',cases)
    s.base.original(work/'material-export.json',exports)
    s.base.original(work/'measurement-check.json',proof)
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in list(HERE.glob('*.py'))+list(HERE.glob('*.md'))}
    sources[Path(e.support.__file__).relative_to(ROOT).as_posix()]=s.sha(e.support.__file__)
    s.base.original(work/'frozen.json',{'kernel':mat.KERNEL,'sources':sources,'materials':materials,
        'cases_sha256':s.sha(work/'cases.json'),'old_allocated_bytes':old_costs,
        'originals_cap_bytes':CAP,'independent_material_blocks':2,
        'cost_reference':'complete recorded stages in historical memory-timescales61-v1',
        'legacy_1_bytes':legacy_costs,
        'historical_reference':{n:s.sha(history/n) for n in ('analysis.json','audit.json','publication/completion.json')},
        'previous_completion_sha256':s.sha(previous/'publication/completion.json')})
    for rel in sources:
        target=work/'frozen-source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,target)
    s.base.load_env()
    import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r63q:memory-timescales:20261116:v1','title':'R63q：突触资源、易化与连接强化',
            'classification':'formal','execution_status':'running','executor':'ai','kernels':[mat.KERNEL],
            'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'material_blocks':2,'teaching_references':34,'stages':592,'diagnostics':510}},
            request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R63q protocol '+lang,
                'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)


def apparatus(work):
    import psutil
    frozen=check(work);cases={c['key']:c for c in read(work/'cases.json')}
    assert not any((work/n).exists() for n in ('apparatus.json','apparatus','cases','STOP','in-flight.json'))
    start=time.monotonic();costs=[];checks=[]
    with s.base.worker_lock(work),s.base.Guard(work):
        s.base.original(work/'in-flight.json',{'phase':'apparatus','pid':os.getpid(),'created':psutil.Process().create_time()})
        def execute(key,parent=None,reader=None,mode='observed',suffix='main'):
            folder=work/'apparatus'/suffix/key
            result,state,observer=e.execute(cases[key],folder,work/'materials',parent,reader,calibration=True,mode=mode)
            if suffix=='main':costs.append({'key':key,'allocated_bytes':e.support.allocated(folder),'historical_actual_bytes':frozen['old_allocated_bytes'][key]})
            return result,state,observer
        for bits in m.BITS:
            root=f'retention/s0/{bits}/paired'
            _,parent,reader=execute(root+'/train')
            for cue in ('A','D'):
                result,final,observer=execute(root+'/d300/'+cue,parent,reader)
                if bits=='101' and cue=='A':
                    hashes={'observed':final.digest};reader_states={'observed':observer}
                    for mode in ('plain','sparse','restored','paused'):
                        _,state,ob=execute(root+'/d300/'+cue,parent,reader,mode=mode,suffix=mode)
                        hashes[mode]=state.digest;reader_states[mode]=ob
                    assert len(set(hashes.values()))==1
                    assert all(v==observer for v in reader_states.values())
                    checks.append({'key':root+'/d300/'+cue,'mode_hashes':hashes,'observers_equal':True})
            print('apparatus DFL',bits,flush=True)
            del parent,reader;gc.collect()
        _,parent,reader=execute('short/train-0')
        _,warm,wr=execute('short/s0/101/warm',parent,reader)
        for cue in ('AB','DB'):execute('short/s0/101/g1/'+cue,warm,wr)
        for cue in ('AB','DB'):execute('history/s0/101/d1/'+cue,parent,reader)
        ratios=[c['allocated_bytes']/c['historical_actual_bytes'] for c in costs]
        factor=1.5;estimated=sum(frozen['old_allocated_bytes'].values())*factor+e.support.allocated(work)+128*2**20
        budget=max(ratios)<2 and estimated<CAP
        s.base.original(work/'apparatus.json',{'passed':True,'budget_passed':budget,'calibration_seed':9291099,
            'channel_xor':0x20000000,'checks':checks,'costs':costs,'estimate_factor':factor,
            'estimated_total_allocated_bytes':estimated,'wall_seconds':time.monotonic()-start,'formal_individuals_created':0})
        (work/'in-flight.json').unlink()
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True,'budget_passed':budget,'estimated_total_bytes':estimated,'maximum_stage_ratio':max(ratios)}),flush=True)


def run(work):
    import psutil
    frozen=check(work);app=read(work/'apparatus.json');assert app['passed'] and app['budget_passed']
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    cases=read(work/'cases.json');start=time.monotonic();completed=0
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for c in cases:
            if (work/'STOP').exists():break
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            s.base.original(work/'in-flight.json',{'unit':c['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            source=work/'cases'/c['parent'] if c['parent'] else None
            parent=e.base.image(source/'final.tmind') if source else None
            reader=e.unpacked(source/'observer.json.xz') if source else None
            folder=work/'cases'/c['key']
            result,state,observer=e.execute(c,folder,work/'materials',parent,reader)
            size=e.support.allocated(folder);old=frozen['old_allocated_bytes'][c['key']]
            completed+=1
            s.base.original(work/'costs'/f'{completed:03d}.json',{'unit':c['key'],'allocated_bytes':size,
                'historical_allocated_bytes':old,'expected_allocated_bytes':app['estimate_factor']*old,
                'allocation_method':'FileStandardInfo','wall_seconds':result['wall_seconds']})
            s.base.atomic_json(work/'current.json',{'completed':completed,'total':len(cases),'last':c['key']})
            (work/'in-flight.json').unlink()
            reason=('actual comparable stage allocation at least twice historical' if size>=2*old else
                    'stage allocation exceeds frozen estimate by 50%' if size>1.5*app['estimate_factor']*old else
                    'two-hour batch budget' if time.monotonic()-start>7200 else None)
            if e.support.allocated(work)>CAP:reason='full originals budget'
            if completed%16==0:print(completed,c['key'],flush=True)
            if reason:s.base.original(work/'STOP',{'reason':reason,'complete_boundary':c['key']});break
            del parent,reader,state,observer;gc.collect()
        if completed==len(cases):s.base.original(work/'summary.json',{'status':'awaiting-analysis','stages':592,
            'teaching_references':34,'diagnostics':510,'material_blocks':2,'wall_seconds':time.monotonic()-start})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','apparatus','run'))
    p.add_argument('--work',type=Path,required=True);p.add_argument('--exported',type=Path,default=ROOT/'.work/r51t-materials')
    a=p.parse_args();work=a.work.resolve()
    if a.action=='register':register(work,a.exported.resolve())
    else:{'apparatus':apparatus,'run':run}[a.action](work)
