"""Serial, registered host for the original-scale E15 replication on 6.1."""
import argparse
from collections import Counter
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import execute_original as e
import measurement_original as m
mat=e.materials;s=e.s;ROOT=mat.ROOT;read=mat.read
NS=UUID('415cb66b-47e1-5d3e-b1b6-73d820aa2980')
CAP=4*2**30
disk_allocation=e.support.compact.x.disk_allocation


def previous(work):
    sys.path.insert(0,str(HERE.parent/'memory_timescales'))
    import comparable_budget_v3 as prior
    folder=work.parent/'memory-timescales61-v1'
    prior.check(folder)
    completion=read(folder/'publication/completion.json')
    assert completion['coverage']=='verified' and completion['pending']==0 and not completion['scientific_stop']
    return folder


def check(work):
    previous(work)
    frozen=read(work/'frozen.json')
    for rel,sha in frozen['sources'].items():assert s.sha(ROOT/rel)==sha,rel
    for rel,sha in frozen['materials'].items():assert s.sha(work/rel)==sha,rel
    assert s.sha(work/'cases.json')==frozen['cases_sha256']
    assert read(work/'registration.json')['pending']==0
    return frozen


def cost(folder,case):
    names={'final.tmind','whole.json.xz','trajectory.json.xz','result.json',
           'inputs.json.xz','scheduled.json.xz','delivered.json.xz'}
    if case['historical_details'].get('stage')=='novelty':names.add('milestones.zip')
    parts={p.name:disk_allocation(p)['allocated_bytes'] for p in folder.iterdir() if p.is_file()}
    comparable=sum(parts[n] for n in names)
    return {'comparable_bytes':comparable,'supplemental_bytes':sum(parts.values())-comparable,
            'total_bytes':sum(parts.values()),'files':parts}


def register(work,exported):
    assert not work.exists()
    prior=previous(work)
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>37.125*2**30
    inventory=mat.inventory();cases=inventory['cases'];exports=read(exported/'manifest.json')
    assert exports['total_frames']==23552 and len(exports['inputs'])==826 and exports['created_engines']==0
    proof=read(ROOT/'.work/r51u-measurement-check.json')
    assert proof['passed'] and proof['historical_decision']['meets_all']
    assert proof['measurement_source_sha256']==s.sha(m.__file__)
    work.mkdir();materials={};old_costs={}
    for case,row in zip(cases,exports['inputs']):
        assert case['key']==row['key']
        source=exported/case['key']/'frames.jsonl'
        assert s.sha(source)==row['sha256'] and len(mat.normalize(source.read_bytes(),case))==row['frames']
        target=work/'materials'/case['key'];target.mkdir(parents=True)
        for name in ('frames.jsonl','receipt.json'):
            shutil.copyfile(source.with_name(name),target/name)
            materials[(target/name).relative_to(work).as_posix()]=s.sha(target/name)
        old_costs[case['key']]=e.support.allocated(mat.SOURCES[case['source']][0]/'cases'/case['old_key'])
    s.base.original(work/'cases.json',cases)
    s.base.original(work/'material-export.json',exports)
    s.base.original(work/'measurement-check.json',proof)
    dependencies=[Path(e.support.__file__),ROOT/'src/threemind_runtime/inheritance.py',
                  ROOT/'src/threemind_runtime/energy_supply.py',ROOT/'src/threemind_kernels/local61.py',
                  ROOT/'src/threemind_kernels/local61_config.py',ROOT/'src/threemind_kernels/local61_native.py']
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))+dependencies
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    s.base.original(work/'frozen.json',{'kernel':e.KERNEL,'sources':sources,'materials':materials,
        'cases_sha256':s.sha(work/'cases.json'),'old_allocated_bytes':old_costs,'originals_cap_bytes':CAP,
        'material_parents':4,'wiring_blocks':2,'ancestry':inventory['ancestry'],
        'previous_completion_sha256':s.sha(prior/'publication/completion.json')})
    for rel in sources:
        target=work/'frozen-source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,target)
    s.base.load_env()
    import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r51u:original-autonomy:20261114:v1','title':'R51u：早期自主活动判据与经历保持',
            'classification':'formal','execution_status':'running','executor':'ai','kernels':[e.KERNEL],
            'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'wiring_blocks':2,'related_parents':4,'material_reconstruction_stages':24,'main_stages':802}},
            request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R51u protocol '+lang,
                'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)


def apparatus_cases(cases):
    by={c['key']:c for c in cases};wanted=set()
    parent='s9293201/region0'
    for history in ('P','Q'):
        for condition in (m.LOCAL if history=='P' else ('normal',)):
            for cue in ('A','none'):wanted.add(f'main/local/{parent}/{history}/{condition}/{cue}')
    for condition in ('normal','off'):
        for cues in ('00','01','10','11'):wanted.add(f'main/sequence/{parent}/P/{condition}/{cues}')
    for route in ('PPP','PQP'):
        for mode in ('live','birth'):
            for cue in ('A','none'):wanted.add(f'main/environment-probe/{parent}/{route}/stage2/{mode}/{cue}')
    wanted.add('main/memory-probe/s9293201/spaced_no_consolidation/age300/birth/off/A')
    for condition in ('intact','erase','matched_erase','novelty_off'):
        wanted.add(f'main/novelty-probe/s9293201/{condition}/round0/fixed')
    for key in list(wanted):
        current=by[key]
        while current['parent']:
            wanted.add(current['parent']);current=by[current['parent']]
    return [c for c in cases if c['key'] in wanted]


def source_state(case,root):
    folder=root/case['parent'] if case['parent'] else None
    return (e.base.image(folder/'final.tmind'),e.unpacked(folder/'whole.json.xz')) if folder else (None,None)


def apparatus(work):
    import psutil
    frozen=check(work);cases=read(work/'cases.json');selected=apparatus_cases(cases)
    assert not any((work/n).exists() for n in ('apparatus','apparatus.json','cases','STOP','in-flight.json'))
    began=time.monotonic();costs=[];checks=[];root=work/'apparatus/main'
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for index,case in enumerate(selected):
            assert guard.thread.is_alive() and not (work/'STOP').exists()
            s.base.original(work/'in-flight.json',{'phase':'apparatus','unit':case['key'],
                'pid':os.getpid(),'created':psutil.Process().create_time()})
            parent,whole=source_state(case,root)
            result,final,complete=e.execute(case,root/case['key'],work/'materials',parent,whole,calibration=True)
            costs.append({'key':case['key'],**cost(root/case['key'],case),
                          'historical_actual_bytes':frozen['old_allocated_bytes'][case['key']]})
            if case['key'] in ('main/local/s9293201/region0/P/normal/A','main/environment/s9293201/region0/PPP/stage1'):
                hashes={'observed':final.digest};wholes={'observed':complete}
                for mode in ('plain','sparse','restored','paused'):
                    _,image,external=e.execute(case,work/'apparatus'/mode/case['key'],work/'materials',parent,whole,
                                               mode=mode,calibration=True)
                    hashes[mode]=image.digest;wholes[mode]=external
                assert len(set(hashes.values()))==1 and all(v==complete for v in wholes.values())
                checks.append({'key':case['key'],'mode_hashes':hashes,'whole_states_equal':True})
            s.base.atomic_json(work/'apparatus-current.json',{'completed':index+1,'total':len(selected),'last':case['key']})
            (work/'in-flight.json').unlink()
            if (index+1)%8==0:print('apparatus',index+1,'/',len(selected),flush=True)
            del parent,whole,complete,final;gc.collect()
        for cue in ('A','none'):
            prefix=root/'main/local/s9293201/region0/P'
            normal=read(prefix/'normal'/cue/'result.json')
            for name in ('sham','restore'):
                other=read(prefix/name/cue/'result.json')
                assert normal['final_sha256']==other['final_sha256']
                assert e.unpacked(prefix/'normal'/cue/'trajectory.json.xz')['rows']==e.unpacked(prefix/name/ cue/'trajectory.json.xz')['rows']
        ratios=[c['comparable_bytes']/c['historical_actual_bytes'] for c in costs]
        full_ratios=[c['total_bytes']/c['historical_actual_bytes'] for c in costs]
        factor=max(1.5,max(ratios));full_factor=max(1.5,max(full_ratios))
        estimate=sum(frozen['old_allocated_bytes'].values())*full_factor+e.support.allocated(work)
        budget=max(ratios)<2 and estimate<CAP and not (work/'STOP').exists()
        s.base.original(work/'apparatus.json',{'passed':True,'budget_passed':budget,'calibration_seed':9293299,
            'channel_xor':0x20000000,'stages':len(selected),'additional_mode_checks':8,'checks':checks,
            'costs':costs,'comparable_factor':factor,'full_factor':full_factor,'estimated_full_bytes':estimate,
            'formal_individuals_created':0,'wall_seconds':time.monotonic()-began})
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True,'budget_passed':budget,'stages':len(selected),
                     'maximum_comparable_ratio':max(ratios),'estimated_full_bytes':estimate}),flush=True)


def run(work):
    import psutil
    frozen=check(work);app=read(work/'apparatus.json')
    assert app['passed'] and app['budget_passed']
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    assert shutil.disk_usage(work).free>25*2**30+3*CAP+128*2**20
    cases=read(work/'cases.json');began=time.monotonic();completed=0
    accounted=e.support.allocated(work)+128*1024  # bounded root bookkeeping, including the final summary
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for case in cases:
            if (work/'STOP').exists():break
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            s.base.original(work/'in-flight.json',{'unit':case['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            parent,whole=source_state(case,work/'cases')
            folder=work/'cases'/case['key']
            result,state,external=e.execute(case,folder,work/'materials',parent,whole)
            measured=cost(folder,case);old=frozen['old_allocated_bytes'][case['key']];completed+=1
            cost_path=work/'costs'/f'{completed:03d}.json'
            s.base.original(cost_path,{'unit':case['key'],**measured,
                'historical_allocated_bytes':old,'expected_comparable_bytes':app['comparable_factor']*old,
                'allocation_method':'FileStandardInfo','wall_seconds':result['wall_seconds']})
            accounted+=measured['total_bytes']+disk_allocation(cost_path)['allocated_bytes']
            s.base.atomic_json(work/'current.json',{'completed':completed,'total':len(cases),'last':case['key']})
            (work/'in-flight.json').unlink()
            reason=('comparable allocation at least twice historical' if measured['comparable_bytes']>=2*old else
                'comparable allocation exceeds estimate by 50%' if measured['comparable_bytes']>1.5*app['comparable_factor']*old else
                'two-hour batch budget' if time.monotonic()-began>7200 else None)
            if accounted>CAP:reason='full originals budget'
            if completed%16==0:print(completed,case['key'],flush=True)
            if reason:s.base.original(work/'STOP',{'reason':reason,'complete_boundary':case['key']});break
            del parent,whole,state,external;gc.collect()
        if completed==len(cases):
            assert e.support.allocated(work)<=accounted<CAP
            s.base.original(work/'summary.json',{'status':'awaiting-analysis','stages':826,'material_reconstruction':24,
                'main_stages':802,'diagnostics':672,'closed_loop_stages':48,'wiring_blocks':2,'material_parents':4,
                'wall_seconds':time.monotonic()-began})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('register','apparatus','run'))
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--exported',type=Path,default=ROOT/'.work/r51u-materials')
    args=parser.parse_args();work=args.work.resolve()
    if args.action=='register':register(work,args.exported.resolve())
    else:{'apparatus':apparatus,'run':run}[args.action](work)
