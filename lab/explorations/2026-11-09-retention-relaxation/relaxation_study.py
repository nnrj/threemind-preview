"""R45: existing per-instance half-life relaxation configuration, six conditions."""
from __future__ import annotations
import argparse
import copy
import gc
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from uuid import UUID, uuid5

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
R44=HERE.parent/'2026-11-09-retention-causality'
spec=importlib.util.spec_from_file_location('r44_retention_study',R44/'study.py')
rc=importlib.util.module_from_spec(spec);spec.loader.exec_module(rc)
old,base=rc.old,rc.base
load,save,sha,psutil=rc.load,rc.save,rc.sha,rc.psutil
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-retention-relaxation/v1')
RESOURCE='retention-relaxation-20261109-v1'
NS=UUID('2e3fd739-0fae-563e-8222-6a15bccecd54')
RATES={'default':.125,'slow':.0125,'off':0.}
ARMS=tuple(f'{boost}-{rate}' for boost in ('natural','raised') for rate in RATES)
POLICY=dict(rc.POLICY,wall_seconds=21600)
N=8


def ident(key):return uuid5(NS,key)
connection=old.connection


def manifest():
    files=('relaxation_study.py','test_relaxation.py','analyze_relaxation.py','protocol.zh.md','protocol.en.md')
    return {**rc.manifest(),**{(HERE/n).relative_to(ROOT).as_posix():sha(HERE/n) for n in files}}


def projected_graph(core):
    g=core.graph()
    # These are current physical quantities. Storage timestamps are not measurements.
    nodes={x['id']:{k:x[k] for k in ('activation','inhibition','direct','associative','support','half_life','reserve','fatigue','salience')} for x in g['nodes']}
    edges={(x['source'],x['target']):{k:x[k] for k in ('weight','half_life','stability','eligibility')} for x in g['edges']}
    return nodes,edges


def graph_error(a,b):
    assert [set(x) for x in a]==[set(x) for x in b]
    return max(abs(a[j][key][f]-b[j][key][f]) for j in (0,1) for key in a[j] for f in a[j][key])


def intervene(s,arm,work):
    boost,rate=arm.split('-');before=s.state();boost_receipt=None
    if boost=='raised':
        changed,boost_receipt=rc.patch_half_life(before,'target')
        s.core=base.create_engine(state=base.StateImage.from_dict(changed['core']),kernel_id=base.KERNEL,backend='native')
        assert s.state()==changed
    before_api=s.state();g=projected_graph(s.core)
    cfg=s.core.config.to_dict();cfg['memory_half_life_decay_rate']=RATES[rate]
    s.core.reconfigure(type(s.core.config)(**cfg))
    after=s.state();error=graph_error(g,projected_graph(s.core))
    assert error<1e-12
    assert after['core']['time_us']==before['core']['time_us']
    assert after['core']['queue']==before['core']['queue']
    assert after['core']['config']==cfg
    for key in before:
        if key!='core':assert after[key]==before[key],key
    return dict(arm=arm,rate=RATES[rate],boost=boost,boost_receipt=boost_receipt,
        before_sha256=base.digest(before),before_api_sha256=base.digest(before_api),after_sha256=base.digest(after),
        max_current_physical_change_at_reconfigure=error,
        api='existing NativeContinuousEngine.reconfigure; no source/default change',
        scope='node and directed-connection half-life relaxation; ordinary weight/support decay and learning remain enabled')


class Guard(old.Guard):
    def watch(self):
        while not self.stop.is_set():
            try:
                self.last=base.resource_check(self.work);private=psutil.Process().memory_info().private
                self.peak_private=max(self.peak_private,private)
                for k,v in self.last['available_bytes'].items():self.minimum[k]=min(v,self.minimum.get(k,v))
                if private>POLICY['private_bytes']:raise RuntimeError('3 GiB private budget')
                if time.monotonic()-self.started>POLICY['wall_seconds']:raise RuntimeError('6 hour scientific host budget')
            except Exception as exc:
                try:
                    with (self.work/'STOP').open('x',encoding='utf-8') as f:json.dump(dict(reason=str(exc),epoch=time.time(),last=self.last,policy=POLICY),f)
                except FileExistsError:pass
                return
            self.stop.wait(1)


def frozen(work):
    for rel,h in load(work/'runner-manifest.json').items():assert sha(ROOT/rel)==h,rel
    assert base.capture_implementation('native')==load(work/'implementation.json')


def prepare(work):
    work.mkdir(parents=True,exist_ok=True)
    with base.worker_lock(work),connection() as c:
        assert not (work/'registration.json').exists()
        rsc=base.resource_check(work)
        assert rsc['available_bytes']['commit']>=8*2**30 and rsc['available_bytes']['data_disk']>=34*2**30
        inst=load(work/'instrument/verified.json');assert inst['passed'] and inst['manifest']==manifest()
        rc.copy_inputs(work)
        name='2026-11-09 ThreeMind · 保持半衰期回落速度对照 v1'
        found=[p for p in c.call('projects.list',{}) if p['name']==name];assert len(found)<=1
        project=found[0] if found else c.request('POST','/api/v2/projects',body=dict(name=name))
        save(work/'platform.json',dict(project_id=project['id'],resource_id=RESOURCE))
        r=base.ResearchRecorder(work,project['id'],client=c)
        r.register(dict(source_key='retention-relaxation:20261109:v1',title=name,classification='development',execution_status='running',executor='ai',
            kernels=[base.KERNEL],protocol=(HERE/'protocol.zh.md').read_text('utf-8'),protocol_version=base.digest(manifest()),required_roles=['protocol','report','note'],
            metadata=dict(independent_origins=N,reused_origins=True,work=str(work),policy=POLICY,
                authorization='2026-11-09 user explicitly requested slowing or disabling half-life relaxation in an experiment')),
            request_id=ident('register'))
        r.synchronize(strict=True)
        c.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,target_id='managed-research-experiments',relative_path='2026-11-09-retention-relaxation/v1',registered_work_path=str(work),writer_mode='cooperative',expected_revision=0),headers={'X-ThreeMind-Request-ID':str(ident('resource'))})
        c.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=project['id'],resource_id=RESOURCE),headers={'X-ThreeMind-Request-ID':str(ident('grant'))})
        save(work/'runner-manifest.json',manifest());save(work/'implementation.json',base.capture_implementation('native'));save(work/'policy.json',POLICY)
        for rel in manifest():r.save_original('frozen/'+rel,(ROOT/rel).read_bytes())
        for lang in ('zh','en'):
            r.text(dict(request_id=str(ident('protocol-'+lang)),identity=str(ident('protocol-doc-'+lang)),expected_revision=0,kind='protocol',title='Half-life relaxation '+lang,markdown=(HERE/f'protocol.{lang}.md').read_text('utf-8')))
        r.synchronize(strict=True);readback=[]
        for lang in ('zh','en'):
            body=c.request('GET',f"/api/v2/projects/{project['id']}/research-documents/{ident('protocol-doc-'+lang)}")
            assert len(body['spec']['blocks'])==1 and body['spec']['blocks'][0]['markdown']==(HERE/f'protocol.{lang}.md').read_text('utf-8')
            readback.append(dict(language=lang,text_equal=True,revision=body['revision']))
        save(work/'registration.json',dict(project=project['id'],record=r.experiment,pending=r.status['pending'],protocol_readback=readback))
        base.atomic_json(work/'status.json',dict(state='registered',branches_completed=0))
        print(json.dumps(load(work/'registration.json')),flush=True)


def run(work):
    old.deterministic()
    with base.worker_lock(work):
        frozen(work);rc.boundary(work)
        assert load(work/'status.json')==dict(state='registered',branches_completed=0)
        assert not (work/'in-flight.json').exists()
        # Serial scientific execution, checked against the exact existing host.
        host44=load(rc.WORK/'host.json')
        assert not (psutil.pid_exists(host44['pid']) and psutil.Process(host44['pid']).create_time()==host44['created_at'])
        assert load(rc.WORK/'status.json')==dict(state='awaiting-analysis',branches_completed=112)
        resources=base.resource_check(work)
        assert resources['available_bytes']['commit']>=8*2**30 and resources['available_bytes']['data_disk']>=34*2**30
        save(work/'host.json',dict(pid=os.getpid(),created_at=psutil.Process().create_time(),command=psutil.Process().cmdline()))
        completed=0;base.atomic_json(work/'status.json',dict(state='running',branches_completed=0))
        with Guard(work):
            for i in range(N):
                for h in (0,1):
                    src=work/f'reference/origins/o{i}/h{h}';path=src/'teaching-0/whole.json.gz';parent=load(path)
                    for arm in ARMS:
                        key=f'origins/o{i}/h{h}/{arm}';s=old.Student.restore(work,parent)
                        s.identity=f'relaxation-o{i}-h{h}-{arm}'
                        s.parent=dict(path=path.relative_to(work).as_posix(),sha256=sha(path),time_us=s.core.time_us,reason='declared relaxation comparison copy',arm=arm)
                        s.checkpoint(work,key+'/parent.json.gz')
                        rc.unit(work,key+'/intervention',s,lambda:intervene(s,arm,work))
                        for stage in (1,2):
                            previous=load(src/f'teaching-{stage-1}/result.json.gz')
                            rc.unit(work,key+f'/teaching-{stage}',s,lambda stage=stage,previous=previous:old.new_unit(s,h,stage,previous))
                        s.checkpoint(work,key+'/test-parent.json.gz')
                        for j,case in enumerate(load(work/f'reference/material/o{i}-h{h}.json')):
                            rc.unit(work,key+f'/trial-{j:03d}',s,lambda case=case:old.trial(s,case))
                        del s;gc.collect();completed+=1
                        base.atomic_json(work/'status.json',dict(state='running',branches_completed=completed,last=key))
            base.atomic_json(work/'status.json',dict(state='awaiting-analysis',branches_completed=completed))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('prepare','run','status'));p.add_argument('--work',type=Path,default=WORK)
    a=p.parse_args();work=a.work.resolve()
    if a.command=='prepare':prepare(work)
    elif a.command=='run':run(work)
    else:print(json.dumps(dict(status=load(work/'status.json') if (work/'status.json').exists() else None,stop=(work/'STOP').exists(),inflight=(work/'in-flight.json').exists(),resources=base.resource_check(work))))
