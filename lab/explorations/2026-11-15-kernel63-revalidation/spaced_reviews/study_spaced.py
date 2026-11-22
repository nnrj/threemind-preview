"""Serial, registered E43 replication; Core execution and text decoding are separate."""
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
import execute_spaced as e
import materials_spaced as mat
import measurement_spaced as measure
import features_spaced as feature
import decode_spaced as decoder
from threemind_transformer import language_assets
from allocation import disk_allocation

s=e.support.s;ROOT=mat.ROOT;read=mat.read
CAP=4*2**30
NS=UUID('f24efb92-9cc0-5977-b289-1e83a670ba99')


def allocated(folder):
    return sum(disk_allocation(p)['allocated_bytes'] for p in Path(folder).rglob('*') if p.is_file())


def previous(work):
    sys.path.insert(0,str(HERE.parent/'autonomy_original'))
    import study_original as prior
    folder=work.parent/'autonomy-original-63-rerun-v1';prior.check(folder)
    status=read(folder/'publication/completion.json')
    assert status['coverage']=='verified' and status['pending']==0 and not status['scientific_stop']
    return folder


def check(work,*,model=False):
    previous(work);frozen=read(work/'frozen.json')
    for rel,digest in frozen['sources'].items():assert s.sha(ROOT/rel)==digest,rel
    for name,digest in frozen['materials'].items():assert s.sha(work/'materials'/name)==digest,name
    for name,digest in frozen['documents'].items():assert s.sha(work/name)==digest,name
    assert read(work/'registration.json')['pending']==0
    assert language_assets.registry()['decoder']==frozen['decoder']
    if model:assert language_assets.available('decoder',verify=True)
    return frozen


def register(work):
    assert not work.exists();prior=previous(work)
    assert s.base.resource_check(work.parent)['safe'] and shutil.disk_usage(work.parent).free>37.125*2**30
    inventory=mat.inventory();cases=e.stages(inventory)
    assert language_assets.available('decoder',verify=True),'frozen local language assets unavailable'
    old_measure=read(ROOT/'.work/r51v-measurement-proof.json')
    old_features=read(ROOT/'.work/r51v-feature-proof.json')
    assert old_measure['passed'] and old_measure['measurement_source_sha256']==s.sha(measure.__file__)
    assert old_measure['historical_analysis_sha256']==s.sha(mat.OLD/'analysis-v1.json')
    assert old_features['passed'] and old_features['source_sha256']==s.sha(feature.__file__)
    for row in old_features['historical_files']:assert mat.sha(mat.OLD/row['path'])==row['sha256']
    work.mkdir();(work/'materials').mkdir()
    materials={}
    for name,info in inventory['artifacts'].items():
        source=mat.OLD/name;target=work/'materials'/name
        assert s.sha(source)==info['sha256'];shutil.copyfile(source,target)
        assert s.sha(target)==info['sha256'];materials[name]=info['sha256']
    old_costs={source['key']:allocated(mat.OLD/'cases'/source['key']) for source in inventory['sources']}
    old_costs.update({case['key']:allocated(mat.OLD/'cases'/case['key']) for case in inventory['diagnostics']})
    s.base.original(work/'inventory.json',inventory);s.base.original(work/'cases.json',cases)
    s.base.original(work/'measurement-proof.json',old_measure);s.base.original(work/'feature-proof.json',old_features)
    dependency_files=[Path(e.support.__file__),ROOT/'src/threemind_transformer/language_session.py',
        ROOT/'src/threemind_transformer/language_senses.py',ROOT/'src/threemind_transformer/language_assets.py',
        ROOT/'src/threemind_transformer/language_assets.json',ROOT/'src/threemind_transformer/language_compute.py',
        ROOT/'src/threemind_transformer/process_guard.py',ROOT/'lab/tools/spaced_reviews.py',
        ROOT/'lab/tools/language_observation.py']
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))+dependency_files
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    documents={name:s.sha(work/name) for name in ('inventory.json','cases.json','measurement-proof.json','feature-proof.json')}
    s.base.original(work/'frozen.json',{'kernel':e.KERNEL,'sources':sources,'materials':materials,
        'documents':documents,'decoder':language_assets.registry()['decoder'],
        'decoder_local_path':str(language_assets.folder('decoder')),'originals_cap_bytes':CAP,
        'historical_allocated_bytes':old_costs,'material_blocks':2,'teaching_individuals':10,
        'diagnostic_copies':490,'stages':580,'previous_completion_sha256':s.sha(prior/'publication/completion.json')})
    for rel in sources:
        target=work/'frozen-source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,target)
    s.base.load_env()
    import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
            password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
            transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,e.base.PROJECT,client=client)
        rec.register({'source_key':'r63s:spaced-reviews:20261116:v1','title':'R63s：间隔复习、连接保持与固定文字读出',
            'classification':'formal','execution_status':'running','executor':'ai','kernels':[e.KERNEL],
            'protocol':(HERE/'protocol.zh.md').read_text('utf-8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'material_blocks':2,'teaching_individuals':10,'diagnostic_copies':490,'stages':580}},
            request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-document-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R63s protocol '+lang,
                'markdown':(HERE/f'protocol.{lang}.md').read_text('utf-8')})
        rec.synchronize(strict=True)
        result={'project':e.base.PROJECT,'record':rec.experiment,'pending':rec.status['pending'],'registered_before_run':True}
        s.base.original(work/'registration.json',result)
    print(json.dumps(result),flush=True)


def inputs(work):
    assets=read(work/'materials/assets.json')
    background=[json.loads(line) for line in (work/'materials/physical-telemetry.jsonl').read_bytes().splitlines()]
    return assets,background


def parent_at(case,folder):
    if not case['parent']:return None,None
    root=folder/case['parent']
    return e.base.image(root/'final.tmind'),e.unpacked(root/'whole.json.xz')


def evidence_cost(folder,case):
    """Old-equivalent state/context/process records and added auditing are explicit."""
    names=('final.tmind','whole.json.xz','result.json','trajectory.jsonl.xz')
    parts={p.name:disk_allocation(p)['allocated_bytes'] for p in folder.iterdir() if p.is_file()}
    comparable=sum(parts[name] for name in names)
    return {'comparable_bytes':comparable,'supplemental_bytes':sum(parts.values())-comparable,
            'total_bytes':sum(parts.values()),'files':parts}


def apparatus(work):
    import psutil
    frozen=check(work);cases=read(work/'cases.json');inventory=read(work/'inventory.json')
    sources={v['key']:v for v in inventory['sources']};assets,background=inputs(work)
    assert not any((work/n).exists() for n in ('apparatus','apparatus.json','cases','STOP','in-flight.json'))
    selected=[c for c in cases if c['source']=='s17-spaced' and (c['kind']=='teach' or
        c['checkpoint']==24 and c['cue_index'] in (0,8)) or
        c['source']=='s17-frozen' and c['kind']=='teach' and c['end_us']==24000000]
    assert len(selected)==12
    started=time.monotonic();costs=[];checks=[];root=work/'apparatus/main'
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for case in selected:
            assert guard.thread.is_alive() and not (work/'STOP').exists()
            s.base.original(work/'in-flight.json',{'phase':'apparatus','unit':case['key'],'pid':os.getpid(),
                'created':psutil.Process().create_time()})
            parent,whole=parent_at(case,root)
            result,final,complete=e.execute(case,sources[case['source']],root/case['key'],assets,background,
                parent,whole,calibration=True)
            costs.append({'key':case['key'],'kind':case['kind'],**evidence_cost(root/case['key'],case),
                'wall_seconds':result['wall_seconds']})
            if case['key'] in ('s17-spaced/teach/24','s17-spaced/probe/s17-spaced-t24-p0'):
                hashes={'observed':final.digest};external={'observed':complete}
                for mode in ('plain','sparse','restored','paused'):
                    _,state,context=e.execute(case,sources[case['source']],work/'apparatus'/mode/case['key'],
                        assets,background,parent,whole,calibration=True,mode=mode)
                    hashes[mode]=state.digest;external[mode]=context
                assert len(set(hashes.values()))==1 and all(v==complete for v in external.values())
                checks.append({'key':case['key'],'hashes':hashes,'whole_states_equal':True})
            (work/'in-flight.json').unlink()
            del parent,whole,final,complete;gc.collect();print('apparatus',case['key'],flush=True)
        taught=[v for v in costs if v['kind']=='teach' and v['key'].startswith('s17-spaced/')]
        probes=[v for v in costs if v['kind']=='probe']
        reference=frozen['historical_allocated_bytes']
        teaching_comparable=sum(v['comparable_bytes'] for v in taught)
        teaching_total=sum(v['total_bytes'] for v in taught)
        probe_ratio=max(v['comparable_bytes']/reference[v['key'].split('/probe/')[1]] for v in probes)
        teaching_ratio=teaching_comparable/reference['s17-spaced']
        unit_estimate={'teaching_total':1.5*teaching_total,
            'probe_total':1.5*max(v['total_bytes'] for v in probes)}
        estimate=10*unit_estimate['teaching_total']+490*unit_estimate['probe_total']+allocated(work)+128*2**20
        course_seconds=sum(v['wall_seconds'] for v in taught)
        budget=max(teaching_ratio,probe_ratio)<2 and estimate<CAP and course_seconds<300 and not (work/'STOP').exists()
        s.base.original(work/'apparatus.json',{'passed':True,'budget_passed':budget,'costs':costs,'checks':checks,
            'estimate':unit_estimate,'estimated_full_bytes':estimate,'complete_teaching_seconds':course_seconds,
            'teaching_comparable_ratio':teaching_ratio,'probe_comparable_ratio':probe_ratio,
            'calibration_core_seed':20260725,'calibration_encoding_seed':73,'formal_individuals_created':0,
            'wall_seconds':time.monotonic()-started})
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'passed':True,'budget_passed':budget,'estimated_full_bytes':estimate}),flush=True)


def run(work):
    import psutil
    frozen=check(work);app=read(work/'apparatus.json');assert app['passed'] and app['budget_passed']
    assert not any((work/n).exists() for n in ('cases','summary.json','STOP','in-flight.json'))
    assert shutil.disk_usage(work).free>37.125*2**30
    cases=read(work/'cases.json');sources={v['key']:v for v in read(work/'inventory.json')['sources']}
    assets,background=inputs(work);started=time.monotonic();completed=0;course_costs={}
    accounted=allocated(work)+128*2**20
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for case in cases:
            if (work/'STOP').exists():break
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            s.base.original(work/'in-flight.json',{'unit':case['key'],'pid':os.getpid(),'created':psutil.Process().create_time()})
            parent,whole=parent_at(case,work/'cases');folder=work/'cases'/case['key']
            result,final,complete=e.execute(case,sources[case['source']],folder,assets,background,parent,whole)
            measured=evidence_cost(folder,case);completed+=1;accounted+=measured['total_bytes']
            cost_path=work/'costs'/f'{completed:03d}.json'
            s.base.original(cost_path,{'unit':case['key'],**measured,'wall_seconds':result['wall_seconds']})
            accounted+=disk_allocation(cost_path)['allocated_bytes']
            reason=None
            if case['kind']=='teach':
                total=course_costs.setdefault(case['source'],dict(total_bytes=0,comparable_bytes=0,wall_seconds=0.))
                for key in ('total_bytes','comparable_bytes'):total[key]+=measured[key]
                total['wall_seconds']+=result['wall_seconds']
                if case['end_us']==830000000:
                    old=frozen['historical_allocated_bytes'][case['source']]
                    if total['comparable_bytes']>=2*old:reason='equivalent teaching evidence at least twice historical'
                    elif total['total_bytes']>1.5*app['estimate']['teaching_total']:reason='teaching allocation exceeds estimate by 50%'
                    elif total['wall_seconds']>300:reason='complete teaching-unit wall budget'
            else:
                old=frozen['historical_allocated_bytes'][case['key'].split('/probe/')[1]]
                if measured['comparable_bytes']>=2*old:reason='equivalent diagnostic evidence at least twice historical'
                elif measured['total_bytes']>1.5*app['estimate']['probe_total']:reason='diagnostic allocation exceeds estimate by 50%'
            if accounted>CAP:reason='full originals budget'
            if time.monotonic()-started>7200:reason='two-hour Core and decode budget'
            s.base.atomic_json(work/'current.json',{'completed':completed,'total':580,'last':case['key']})
            (work/'in-flight.json').unlink()
            if completed%10==0:print(completed,case['key'],flush=True)
            if reason:s.base.original(work/'STOP',{'reason':reason,'complete_boundary':case['key']});break
            del parent,whole,final,complete;gc.collect()
        if completed==580:
            assert allocated(work)<=accounted<CAP
            s.base.original(work/'summary.json',{'status':'awaiting-decoding-and-analysis','stages':580,
                'teaching_individuals':10,'teaching_boundaries':90,'diagnostics':490,'material_blocks':2,
                'wall_seconds':time.monotonic()-started,'teaching_costs':course_costs})


def decode(work):
    import psutil
    check(work,model=True);summary=read(work/'summary.json');assert summary['stages']==580
    assert not any((work/n).exists() for n in ('decoding','decoding-summary.json','STOP','in-flight.json'))
    requests=[]
    for case in read(work/'cases.json'):
        if case['kind']!='probe':continue
        result=read(work/'cases'/case['key']/'result.json')
        for index in ((0,1,2,3) if case['probe'] is None else (1,)):
            requests.append({'key':case['key'],'seed':case['seed'],'window':index,
                'features':result['windows'][index]['features']})
    assert len(requests)==640
    started=time.monotonic();answers=[];batches=[]
    with s.base.worker_lock(work),s.base.Guard(work) as guard:
        s.base.atomic_json(work/'host.json',{'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv})
        for seed in mat.SEEDS:
            selected=[r for r in requests if r['seed']==seed]
            for offset in range(0,len(selected),96):
                assert guard.thread.is_alive() and not (work/'STOP').exists()
                chunk=selected[offset:offset+96];folder=work/'decoding'/f'{seed}-{offset}'
                remaining=7200-summary['wall_seconds']-(time.monotonic()-started)
                assert remaining>0
                result=decoder.decode_batch(folder,mat.protocol(seed).model_dump(),[r['features'] for r in chunk],
                    work/'materials'/f'head-{seed}.safetensors',lambda:s.base.resource_check(work),min(1800,remaining))
                answers.extend({'key':r['key'],'window':r['window'],'seed':seed,'text':a['text']}
                    for r,a in zip(chunk,result['windows'],strict=True))
                batches.append({'folder':folder.relative_to(work).as_posix(),'windows':len(chunk),
                    'elapsed_seconds':result['elapsed_seconds'],'attempts':result['compute_attempts']})
                if allocated(work)>CAP:
                    s.base.original(work/'STOP',{'reason':'full originals budget','complete_boundary':str(folder)});break
                print('decoded',len(answers),'/640',flush=True)
            if (work/'STOP').exists():break
        if len(answers)==640:
            s.base.original(work/'decoding-summary.json',{'created_engines':0,'windows':640,'answers':answers,
                'batches':batches,'wall_seconds':time.monotonic()-started})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('register','apparatus','run','decode'))
    parser.add_argument('--work',type=Path,required=True);args=parser.parse_args()
    {'register':register,'apparatus':apparatus,'run':run,'decode':decode}[args.action](args.work.resolve())
