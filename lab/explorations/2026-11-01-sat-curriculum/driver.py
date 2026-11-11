"""Immutable preregistration, continuous execution and boundary-only resource stops."""
from __future__ import annotations
import argparse,copy,json,os,random,sys,time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID,uuid5
import httpx,psutil,torch
from student import Student,base,ROOT,load,save,sha,make_material,balanced_cases,sat,FRAME_INDEX,LIMIT
HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-11-01-sat-curriculum/v2')
NS=UUID('b7d2dc28-3a37-45b1-a125-230d51823f13')
RESOURCE='sat-curriculum-20261101-v2'
SEED=2111100
ARMS=('normal','shuffled','random-local','walksat','quantized-rule')

def ident(key):return uuid5(NS,key)
def connection():
    base.load_env();db=urlsplit(os.environ.get('THREEMIND_DATABASE_URL',''))
    assert db.hostname in ('127.0.0.1','localhost','::1') and db.port==5433
    return base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),
        password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),
        transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai')
def manifest():
    files=[HERE/x for x in ('student.py','driver.py','test_apparatus.py','protocol.zh.md','protocol.en.md')]
    files+=[ROOT/x for x in ('lab/tools/calibrated_activity.py','lab/tools/activity_controller.py','lab/tools/study_lock.py',
       'lab/explorations/2026-11-01-sat-pilot/sat_problem.py','lab/explorations/2026-10-16-mechanism-discovery/pilot_m2.py',
       'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py','docs/zh/training-protocol.md')]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in files}
def frozen(work):
    for rel,h in load(work/'runner-manifest.json').items():
        if sha(ROOT/rel)!=h:raise RuntimeError('frozen source changed '+rel)
    if base.capture_implementation('native')!=load(work/'implementation.json'):raise RuntimeError('kernel identity changed')
def recorder(work,client):
    r=base.ResearchRecorder(work,load(work/'platform.json')['project_id'],client=client);r.resume_recording();return r
def state(work,**kw):base.atomic_json(work/'status.json',kw)
def resources(work):
    r=base.resource_check(work)
    if r['available_bytes']['commit']<7*2**30:raise RuntimeError('need 5GiB reserve plus 2GiB startup allowance')
    if r['available_bytes']['data_disk']<29*2**30:raise RuntimeError('need originals/archive/readback allowance')
    return r
def boundary(work):
    if (work/'STOP').exists():raise InterruptedError('STOP at complete boundary')
    base.resource_check(work)
    n=sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
    if n>2**30:raise InterruptedError('1GiB scientific originals budget')
def mark(work,unit):save(work/'in-flight.json',dict(unit=unit,pid=os.getpid(),created_at=psutil.Process().create_time(),epoch=time.time()))
def clear(work):(work/'in-flight.json').unlink()
def commit(folder,s,name,progress):
    value=s.checkpoint(folder,name);base.atomic_json(folder/'current.json',dict(file=name,sha256=sha(folder/name),progress=progress,time_us=s.core.time_us))
    return value

def prepare(work):
    work.mkdir(parents=True,exist_ok=True)
    with base.worker_lock(work),connection() as c:
        if (work/'platform.json').exists():raise RuntimeError('already registered')
        resources(work);validation=load(HERE/'apparatus-summary.json')
        assert validation['passed'] and validation['source_sha256']=={x:sha(HERE/x) for x in ('student.py','driver.py','test_apparatus.py')}
        name='2026-11-01 ThreeMind · 3-SAT 规范教学与时序读出 v2'
        candidates=[p for p in c.call('projects.list',{}) if p['name']==name]
        if len(candidates)>1:raise RuntimeError('ambiguous project')
        project=candidates[0] if candidates else c.request('POST','/api/v2/projects',body={'name':name})
        save(work/'platform.json',dict(project_id=project['id'],resource_id=RESOURCE))
        r=base.ResearchRecorder(work,project['id'],client=c)
        r.register(dict(source_key='sat-curriculum:20261101:v2',title=name,classification='development',execution_status='running',
            executor='ai',kernels=[base.KERNEL],protocol=(HERE/'protocol.zh.md').read_text(encoding='utf-8-sig'),
            protocol_version=base.digest(manifest()),required_roles=['protocol','report','note'],
            metadata=dict(work=str(work),independent_pairs=8,students=16,authorization='2026-11-01 explicit rerun under training protocol',half_life_changed=False)),request_id=ident('register'))
        r.synchronize(strict=True)
        c.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,target_id='managed-research-experiments',
            relative_path='2026-11-01-sat-curriculum/v2',registered_work_path=str(work),writer_mode='cooperative',expected_revision=0),
            headers={'X-ThreeMind-Request-ID':str(ident('resource'))})
        c.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=project['id'],resource_id=RESOURCE),
            headers={'X-ThreeMind-Request-ID':str(ident('grant'))})
        save(work/'runner-manifest.json',manifest());save(work/'implementation.json',base.capture_implementation('native'))
        for rel in manifest():r.save_original('frozen/'+rel,(ROOT/rel).read_bytes())
        r.save_original('apparatus/summary.json',(HERE/'apparatus-summary.json').read_bytes())
        for origin in range(8):save(work/f'material/o{origin}.json',make_material(SEED+origin))
        for lang in ('zh','en'):
            r.text(dict(request_id=str(ident('protocol-'+lang)),identity=str(ident('protocol-doc-'+lang)),expected_revision=0,
                kind='protocol',title='3-SAT curriculum v2 '+lang,markdown=(HERE/f'protocol.{lang}.md').read_text(encoding='utf-8-sig')))
        r.synchronize(strict=True);state(work,state='registered',origins_completed=0)
        print(json.dumps(dict(project=project['id'],record=r.experiment,pending=r.status['pending'])),flush=True)

def development(s,m):
    cases=balanced_cases(m['development_examples'],0,4,s.rng)
    rows=s.sample(cases);results=[s.solve(p,limit=24) for p in m['dev_problems']]
    errors=[r['condition'] for r in rows if r['question']['prediction']!=r['label']]
    for p,result in zip(m['dev_problems'],results):
        a=result['initial_assignment'][:]
        for st in result['steps']:
            for v,b,q in zip(st['candidates'],st['breaks'],st['queries']):
                if q['prediction']!=int(b!=0) and len(errors)<16:
                    errors.append(dict(category=min(b,3),problem_id=p['id'],assignment=a[:],variable=v,break_count=b,clause_index=st['clause']))
            a=st['assignment'][:]
    errors=errors[:16]
    correct=sum(r['question']['prediction']==r['label'] for r in rows)
    solved=sum(r['solved'] for r in results)
    return dict(local_questions=rows,sat_results=results,local_correct=correct,local_n=len(rows),sat_solved=solved,sat_n=4,
                errors=errors,ready=correct==16 and not errors and solved>=3)

def training_unit(s,m,folder,stage,history,previous=None):
    errors=previous['errors'] if previous else None
    teaching=s.curriculum(m['examples'],history,'initial' if stage==0 else f'correction-{stage}',errors)
    save(folder/f'teaching-{stage}.json.gz',teaching)
    cases=balanced_cases(m['examples'],2+stage,12,s.rng)
    if errors:
        cases=errors+[m['development_examples'][c][4+stage] | {'category':c} for c in range(4)]+cases
    s.rng.shuffle(cases)
    rows=s.sample(cases)
    receipt=s.fit(folder,f'samples-{stage}.json.gz',rows);save(folder/f'fit-{stage}.json',receipt)
    dev=development(s,m);save(folder/f'dev-{stage}.json.gz',dev)
    s.cursor=dict(stage='development-complete',cycle=stage,ready=dev['ready'])
    return dev

def rule_baseline(p):
    a,rng=sat.begin_problem(p);initial=a[:];steps=[];start=time.perf_counter()
    for k in range(LIMIT):
        bad=sat.unsatisfied(p['clauses'],a)
        if not bad:break
        ci=rng.choice(bad);vs=[abs(x)-1 for x in p['clauses'][ci]];rng.shuffle(vs)
        bs=[sat.break_count(p['clauses'],a,v) for v in vs]
        selected,noise=sat.choose([int(b==0) for b in bs],rng,.25)
        a[vs[selected]]=not a[vs[selected]]
        steps.append(dict(step=k,clause=ci,candidates=vs,breaks=bs,selected=selected,noise=noise,assignment=a[:]))
    solved=sat.verify_witness(p['n'],p['clauses'],a)
    return dict(initial_assignment=initial,final_assignment=a,solved=solved,outcome='SAT' if solved else 'UNKNOWN',flips=len(steps),steps=steps,wall_seconds=time.perf_counter()-start)

def run(work):
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    with base.worker_lock(work):
        frozen(work);resources(work)
        if any((work/x).exists() for x in ('STOP','in-flight.json')):raise RuntimeError('unresolved marker; no blind rerun')
        if load(work/'status.json')['state']=='awaiting-analysis':raise RuntimeError('already computed')
        base.atomic_json(work/'host.json',dict(pid=os.getpid(),created_at=psutil.Process().create_time(),command=sys.argv))
        try:
            with base.Guard(work):
                for origin in range(8):
                    m=load(work/f'material/o{origin}.json')
                    for arm in ARMS:
                        folder=work/f'origins/o{origin}/{arm}';folder.mkdir(parents=True,exist_ok=True)
                        if (folder/'done.json').exists():continue
                        s=None;progress=dict(stage='training',cycle=0,test=0)
                        if arm in ('normal','shuffled'):
                            if (folder/'current.json').exists():
                                current=load(folder/'current.json')
                                assert sha(folder/current['file'])==current['sha256']
                                s=Student.restore(folder,load(folder/current['file']));progress=current['progress']
                            else:
                                boundary(work);mark(work,f'o{origin}/{arm}/birth')
                                s=Student(SEED+origin,f'sat-v2-o{origin}-{arm}')
                                commit(folder,s,'whole-birth.json.gz',progress);clear(work)
                            while progress['stage']=='training':
                                cycle=progress['cycle'];boundary(work);mark(work,f'o{origin}/{arm}/training-{cycle}')
                                previous=load(folder/f'dev-{cycle-1}.json.gz') if cycle else None
                                dev=training_unit(s,m,folder,cycle,arm,previous)
                                # One complete correction/review cycle is mandatory, even if initial development is perfect.
                                finished=(cycle>=1 and dev['ready']) or cycle==3
                                progress=dict(stage='testing' if finished else 'training',cycle=cycle+1,test=0)
                                commit(folder,s,f'whole-training-{cycle}.json.gz',progress);clear(work)
                                state(work,state='running',origin=origin,arm=arm,phase='training',cycles_completed=cycle+1)
                                print(json.dumps(dict(origin=origin,arm=arm,cycle=cycle,local=f"{dev['local_correct']}/16",dev_sat=f"{dev['sat_solved']}/4",next=progress['stage'])),flush=True)
                        else:
                            progress=dict(stage='testing',test=len(list(folder.glob('result-*.json.gz'))))
                        for i in range(progress['test'],len(m['tests'])):
                            boundary(work);mark(work,f'o{origin}/{arm}/test-{i}');p=m['tests'][i]
                            before=base.digest(s.state()) if s else None
                            r=s.solve(p) if s else rule_baseline(p) if arm=='quantized-rule' else sat.baseline(p,arm,LIMIT)
                            r.update(origin=origin,arm=arm,problem_id=p['id'],kind=p['kind'],n=p['n'],before_sha256=before)
                            if s:
                                s.cursor=dict(stage='final-test',completed=i+1)
                                r['after_sha256']=base.digest(s.state())
                            save(folder/f'result-{i:03d}.json.gz',r)
                            if s:
                                progress=dict(stage='testing',cycle=progress['cycle'],test=i+1)
                                commit(folder,s,f'whole-test-{i+1:03d}.json.gz',progress)
                            clear(work);state(work,state='running',origin=origin,arm=arm,phase='final-test',tests_completed=i+1)
                        save(folder/'done.json',dict(tests=26,final_internal_us=s.core.time_us if s else None))
                    print(json.dumps(dict(origin=origin,complete=True)),flush=True)
            state(work,state='awaiting-analysis',origins_completed=8)
        except InterruptedError as exc:
            if not (work/'STOP').exists():save(work/'STOP',dict(reason=str(exc),epoch=time.time()))
            state(work,state='paused-complete-boundary',reason=str(exc))
        except Exception as exc:
            state(work,state='failed-preserve-in-flight',error=repr(exc));raise

def status(work):
    r={'resources':base.resource_check(work),'work':str(work)}
    for name in ('status.json','host.json','STOP','in-flight.json'):
        if (work/name).exists():r[name]=load(work/name)
    h=r.get('host.json')
    if h:r['host_alive']=psutil.pid_exists(h['pid']) and abs(psutil.Process(h['pid']).create_time()-h['created_at'])<.01
    print(json.dumps(r,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare','run','status'));p.add_argument('--work',type=Path,default=WORK)
    a=p.parse_args();globals()[a.command](a.work.resolve())
