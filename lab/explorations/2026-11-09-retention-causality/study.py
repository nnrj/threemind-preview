"""R44: declared edge-retention interventions in complete R43 research copies."""
from __future__ import annotations
import argparse
import copy
import gc
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
R43=ROOT/'lab/explorations/2026-11-09-context-revision'
sys.path.insert(0,str(R43))
import experiment as old
base=old.base
psutil=old.psutil
load,save,sha=old.load,old.save,old.sha
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1')
SOURCE=old.WORK
RESOURCE='retention-causality-20261109-v1'
NS=UUID('ae9fb548-1ac7-51f9-9f4e-78f1c32cbe98')
N=8
ARMS={'late':('baseline','target','matched','all'), 'early':('baseline','target','all')}
POLICY=dict(old.POLICY,originals_bytes=3*2**30,wall_seconds=14400)
TARGET_H=300.0

def ident(key):return uuid5(NS,key)

def manifest():
    files=[HERE/name for name in ('study.py','test_apparatus.py','analyze.py','source_audit.py','protocol.zh.md','protocol.en.md')]
    result={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    result.update(old.manifest())
    return result

connection=old.connection

def decay(w,h,dt,c):
    lower=c['memory_half_life_min_s'];r=c['memory_half_life_decay_rate']
    end=max(lower,h-r*dt)
    falling=min(dt,(h-lower)/r) if r>0 else 0.
    integral=(math.log(h/end)/r if falling>0 else 0.)+(dt-falling)/end
    return w*math.exp(-math.log(2)*integral),end

def crossing(w,h,floor,c):
    if w<=floor:return 0.
    need=math.log(w/floor)/math.log(2);r=c['memory_half_life_decay_rate'];lower=c['memory_half_life_min_s']
    if not r:return need*h
    fall=math.log(h/lower)/r
    return h*-math.expm1(-r*need)/r if need<=fall else (h-lower)/r+(need-fall)*lower

def names(state):
    rev={v:k for k,v in state['mapping'].items()}
    return {n['id']:rev[n['channel']] for n in state['core']['nodes']}

def selected(state,arm):
    ns=names(state);ports=set(sum(old.PORTS.values(),()))
    cues={'X0','X1','D0','D1'} if arm=='target' else {'Z0','Z1','Z2','Z3'}
    return [(e['source'],e['target']) for e in state['core']['edges'] if arm=='all' or
        ((ns[e['source']] in cues and ns[e['target']] in ports) or
         (ns[e['target']] in cues and ns[e['source']] in ports))]

def patch_half_life(state,arm):
    """Change H at current simulated time; preserve current physical weights exactly.

    Saved weights are lazy values at state_us. Re-encode those two saved fields
    without settling any other field or moving a clock. Recompute only expiry
    deadlines for changed edges. This is an explicit intervention, not observation.
    """
    out=copy.deepcopy(state);c=out['core'];now=int(c['time_us']);cfg=c['config']
    keys=set(selected(state,arm)) if arm!='baseline' else set()
    rows=[];new_deadlines={}
    for e in c['edges']:
        key=(e['source'],e['target'])
        if key not in keys:continue
        before=copy.deepcopy(e);dt=(now-int(e['state_us']))/1e6
        w,h=decay(e['weight'],e['half_life'],dt,cfg)
        current_h=max(TARGET_H,h)
        saved_h=current_h+cfg['memory_half_life_decay_rate']*dt
        factor,_=decay(1.,saved_h,dt,cfg)
        e['weight']=w/factor;e['half_life']=saved_h
        actual_w,actual_h=decay(e['weight'],e['half_life'],dt,cfg)
        assert abs(actual_w-w)<1e-14 and abs(actual_h-current_h)<1e-10
        assert 0<=e['weight']<=1 and saved_h<=cfg['memory_half_life_max_s']
        floor=cfg['dormant_prune_weight'] if e['sleeping'] else cfg['prune_weight']
        deadline=now+max(1,math.ceil(crossing(w,current_h,floor,cfg)*1e6)+1)
        new_deadlines[(2,*key)]=str(deadline)
        rows.append(dict(key=list(key),before=before,after=copy.deepcopy(e),current_weight=w,
                         previous_current_h=h,current_h=actual_h,deadline_us=str(deadline)))
    for timer in c['timers']:
        key=tuple(timer[:3])
        if key in new_deadlines:timer[3]=new_deadlines.pop(key)
    assert not new_deadlines
    c['timers'].sort(key=lambda t:(int(t[3]),tuple(t[:3])))
    if arm=='baseline':assert out==state
    return out,dict(arm=arm,current_time_us=str(now),target_half_life_s=TARGET_H,connections=rows,
        operation='edge half-life intervention; current weights and all other physical state unchanged; saved weight representation and expiry timers adjusted')

def current_edge_measure(state):
    c=state['core'];now=int(c['time_us']);ns=names(state)
    return [dict(source=ns[e['source']],target=ns[e['target']],key=[e['source'],e['target']],
        weight=decay(e['weight'],e['half_life'],(now-int(e['state_us']))/1e6,c['config'])[0],
        half_life=decay(e['weight'],e['half_life'],(now-int(e['state_us']))/1e6,c['config'])[1],
        last_pass_us=e['last_pass_us'],sleeping=e['sleeping']) for e in c['edges']]

def intervene(student,arm,work):
    before=student.state();changed,receipt=patch_half_life(before,arm)
    student.core=base.create_engine(state=base.StateImage.from_dict(changed['core']),kernel_id=base.KERNEL,backend='native')
    assert student.state()==changed
    receipt.update(before_sha256=base.digest(before),after_sha256=base.digest(changed))
    return receipt

class Guard(old.Guard):
    def watch(self):
        while not self.stop.is_set():
            try:
                self.last=base.resource_check(self.work);private=psutil.Process().memory_info().private
                self.peak_private=max(self.peak_private,private)
                for k,v in self.last['available_bytes'].items():self.minimum[k]=min(v,self.minimum.get(k,v))
                if private>POLICY['private_bytes']:raise RuntimeError('3 GiB private budget')
                if time.monotonic()-self.started>POLICY['wall_seconds']:raise RuntimeError('4 hour scientific host budget')
            except Exception as exc:
                try:
                    with (self.work/'STOP').open('x',encoding='utf-8') as f:json.dump(dict(reason=str(exc),epoch=time.time(),last=self.last,policy=POLICY),f)
                except FileExistsError:pass
                return
            self.stop.wait(1)

def boundary(work):
    if (work/'STOP').exists():raise InterruptedError('complete boundary pause')
    base.resource_check(work)
    if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>POLICY['originals_bytes']:raise InterruptedError('originals budget exceeded')

def unit(work,key,s,fn):
    boundary(work);before=s.state();mark=work/'in-flight.json'
    save(mark,dict(key=key,pid=os.getpid(),created_at=psutil.Process().create_time(),time_us=s.core.time_us,before_sha256=base.digest(before)))
    result=fn();s.cursor=dict(unit=key)
    result['edge_measure']=current_edge_measure(s.state())
    rel=f'{key}/whole.json.gz';receipt=s.checkpoint(work,rel)
    save(work/f'{key}/result.json.gz',result)
    save(work/f'{key}/complete.json',dict(state_file=rel,sha256=receipt['sha256'],before_sha256=base.digest(before),after_sha256=base.digest(s.state()),
        start_us=before['core']['time_us'],end_us=s.core.time_us,result_sha256=sha(work/f'{key}/result.json.gz')))
    base.atomic_json(work/'current.json',dict(unit=key,state_file=rel,sha256=receipt['sha256'],time_us=s.core.time_us))
    mark.unlink();print(json.dumps(dict(unit=key,time_us=s.core.time_us)),flush=True)
    return result

def copy_inputs(work):
    entries={}
    def cp(rel,dest=None):
        src=SOURCE/rel;out=work/(dest or 'reference/'+rel)
        out.parent.mkdir(parents=True,exist_ok=True)
        raw=src.read_bytes()
        if out.exists():assert out.read_bytes()==raw
        else:
            with out.open('xb') as f:f.write(raw)
        entries[rel]=dict(source_sha256=sha(src),copied_path=out.relative_to(work).as_posix(),bytes=len(raw))
    cp('publication/completion.json')
    for i in range(N):
        for h in (0,1):
            prefix=f'origins/o{i}/h{h}'
            cp(prefix+'/test-parent.json.gz');cp(prefix+'/teaching-0/whole.json.gz')
            for j in range(3):cp(prefix+f'/teaching-{j}/result.json.gz')
            cp(f'material/o{i}-h{h}.json')
            for j in range(24):cp(prefix+f'/intact/trial-{j:03d}/result.json.gz')
            state=load(SOURCE/(prefix+'/test-parent.json.gz'))
            for ref in state['adapter_refs'].values():
                for name in ref['files']:
                    rel=ref['path']+'/'+name
                    if rel not in entries:cp(rel,rel)
    save(work/'source-manifest.json',dict(source=str(SOURCE),classification='reused R43 origins and material; mechanistic follow-up, not independent confirmation',files=entries))

def prepare(work):
    work.mkdir(parents=True,exist_ok=True)
    with base.worker_lock(work),old.connection() as c:
        if (work/'registration.json').exists():raise RuntimeError('already registered')
        resources=base.resource_check(work)
        assert resources['available_bytes']['commit']>=8*2**30 and resources['available_bytes']['data_disk']>=34*2**30
        audit=load(work/'instrument/verified.json')
        assert audit['passed'] and audit['manifest']==manifest()
        copy_inputs(work)
        name='2026-11-09 ThreeMind · 连接保持的因果检验 v1'
        matches=[p for p in c.call('projects.list',{}) if p['name']==name]
        assert len(matches)<=1
        project=matches[0] if matches else c.request('POST','/api/v2/projects',body=dict(name=name))
        save(work/'platform.json',dict(project_id=project['id'],resource_id=RESOURCE))
        r=base.ResearchRecorder(work,project['id'],client=c)
        r.register(dict(source_key='retention-causality:20261109:v1',title=name,classification='development',execution_status='running',executor='ai',
            kernels=[base.KERNEL],protocol=(HERE/'protocol.zh.md').read_text('utf-8'),protocol_version=base.digest(manifest()),required_roles=['protocol','report','note'],
            metadata=dict(independent_origins=N,reused_origins=True,work=str(work),policy=POLICY,
                authorization='2026-11-09 user: 好的，开始研究，以确定是否应该改进衰减规则，以及如何改进。')),
            request_id=ident('register'))
        r.synchronize(strict=True)
        c.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,target_id='managed-research-experiments',relative_path='2026-11-09-retention-causality/v1',registered_work_path=str(work),writer_mode='cooperative',expected_revision=0),headers={'X-ThreeMind-Request-ID':str(ident('resource'))})
        c.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=project['id'],resource_id=RESOURCE),headers={'X-ThreeMind-Request-ID':str(ident('grant'))})
        save(work/'runner-manifest.json',manifest());save(work/'implementation.json',base.capture_implementation('native'));save(work/'policy.json',POLICY)
        for rel in manifest():r.save_original('frozen/'+rel,(ROOT/rel).read_bytes())
        for lang in ('zh','en'):
            r.text(dict(request_id=str(ident('protocol-'+lang)),identity=str(ident('protocol-doc-'+lang)),expected_revision=0,kind='protocol',title='Retention causality '+lang,markdown=(HERE/f'protocol.{lang}.md').read_text('utf-8')))
        r.synchronize(strict=True)
        readback=[]
        for lang in ('zh','en'):
            doc=str(ident('protocol-doc-'+lang))
            body=c.request('GET',f"/api/v2/projects/{project['id']}/research-documents/{doc}")
            assert len(body['spec']['blocks'])==1
            assert body['spec']['blocks'][0]['markdown']==(HERE/f'protocol.{lang}.md').read_text('utf-8')
            readback.append(dict(language=lang,id=doc,revision=body['revision'],text_equal=True))
        save(work/'protocol-readback.json',readback)
        save(work/'registration.json',dict(project=project['id'],record=r.experiment,pending=r.status['pending'],source_manifest=manifest()))
        base.atomic_json(work/'status.json',dict(state='registered',branches_completed=0))
        print(json.dumps(load(work/'registration.json')),flush=True)

def frozen(work):
    assert manifest()==load(work/'runner-manifest.json')
    assert base.capture_implementation('native')==load(work/'implementation.json')

def run(work):
    old.deterministic()
    with base.worker_lock(work):
        frozen(work);boundary(work)
        assert not (work/'in-flight.json').exists()
        assert load(work/'status.json')['state']=='registered','fresh start only; do not replay'
        r=base.resource_check(work);assert r['available_bytes']['commit']>=8*2**30
        save(work/'host.json',dict(pid=os.getpid(),created_at=psutil.Process().create_time(),command=psutil.Process().cmdline()))
        completed=0;base.atomic_json(work/'status.json',dict(state='running',branches_completed=0))
        with Guard(work):
            for phase,arms in ARMS.items():
                for i in range(N):
                    for h in (0,1):
                        src=work/f'reference/origins/o{i}/h{h}'
                        parent_path=src/('test-parent.json.gz' if phase=='late' else 'teaching-0/whole.json.gz')
                        parent=load(parent_path)
                        for arm in arms:
                            key=f'{phase}/o{i}/h{h}/{arm}';s=old.Student.restore(work,parent)
                            s.identity=f'retention-{phase}-o{i}-h{h}-{arm}'
                            s.parent=dict(path=parent_path.relative_to(work).as_posix(),sha256=sha(parent_path),time_us=s.core.time_us,reason='declared retention intervention copy',phase=phase,arm=arm)
                            s.checkpoint(work,key+'/parent.json.gz')
                            unit(work,key+'/intervention',s,lambda:intervene(s,arm,work))
                            if phase=='early':
                                for stage in (1,2):
                                    previous=load(src/f'teaching-{stage-1}/result.json.gz')
                                    result=unit(work,key+f'/teaching-{stage}',s,lambda stage=stage,previous=previous:old.new_unit(s,h,stage,previous))
                                    if arm=='baseline':
                                        reference=load(src/f'teaching-{stage}/result.json.gz')
                                        assert {k:v for k,v in result.items() if k!='edge_measure'}==reference,'baseline teaching replay differs'
                                if arm=='baseline':assert s.state()['core']==load(src/'test-parent.json.gz')['core'],'baseline Core differs after replay'
                            s.checkpoint(work,key+'/test-parent.json.gz')
                            for j,case in enumerate(load(work/f'reference/material/o{i}-h{h}.json')):
                                result=unit(work,key+f'/trial-{j:03d}',s,lambda case=case:old.trial(s,case))
                                if arm=='baseline':
                                    reference=load(src/f'intact/trial-{j:03d}/result.json.gz')
                                    assert {k:v for k,v in result.items() if k!='edge_measure'}==reference,'baseline trial differs'
                            del s;gc.collect();completed+=1
                            base.atomic_json(work/'status.json',dict(state='running',branches_completed=completed,last=key))
            base.atomic_json(work/'status.json',dict(state='awaiting-analysis',branches_completed=completed))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare','run','status'));p.add_argument('--work',type=Path,default=WORK)
    args=p.parse_args();work=args.work.resolve()
    if args.command=='prepare':prepare(work)
    elif args.command=='run':run(work)
    else:print(json.dumps(dict(status=load(work/'status.json') if (work/'status.json').exists() else None,in_flight=(work/'in-flight.json').exists(),stop=(work/'STOP').exists(),resources=base.resource_check(work))))
