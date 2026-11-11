"""Registered causal copies and no-Core SAT controls; no production edits."""
from __future__ import annotations
import argparse, copy, gc, json, os, random, shutil, sys, time
from pathlib import Path
from uuid import UUID, uuid5
import numpy as np
import psutil
import torch
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
V2=ROOT/'lab/explorations/2026-11-01-sat-curriculum'
sys.path.insert(0,str(V2))
from student import Student,base,load,save,sha,sat,FRAME_INDEX,tensor_hash
from lab.tools.calibrated_activity import CalibratedActivity
import driver as old
from host_budget import Guard
WORK=Path('E:/ThreeMindData/experiments/2026-11-01-sat-core-exclusion/v1')
PARENT=Path('E:/ThreeMindData/experiments/2026-11-01-sat-curriculum/v2')
RESOURCE='sat-core-exclusion-20261101-v1'
NS=UUID('e3ed6085-d0eb-459c-885f-7974f1d1afda')
ARMS=('intact','restored','blank-core','relay-fixed','template-fixed','constant-fixed','relay-trained','constant-trained','quantized-rule','random-local','walksat')
LIVE=ARMS[:3]
TRAINED=('relay-trained','constant-trained')
def ident(s):return uuid5(NS,s)
def connection():return old.connection()
def state(work,**kw):base.atomic_json(work/'status.json',kw)
def resources(work):
    r=base.resource_check(work)
    if r['available_bytes']['commit']<8*2**30:raise RuntimeError('need 8 GiB available commit at startup')
    return r

def boundary(work):
    if (work/'STOP').exists():raise InterruptedError('complete-boundary STOP')
    base.resource_check(work)
    if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>2**30:raise InterruptedError('1 GiB originals budget')

def mark(work,unit):save(work/'in-flight.json',dict(unit=unit,pid=os.getpid(),created_at=psutil.Process().create_time()))
def clear(work):(work/'in-flight.json').unlink()
def manifest():
    refs={**old.manifest(),V2.relative_to(ROOT).as_posix()+'/host_budget.py':sha(V2/'host_budget.py')}
    for n in ('study.py','test_apparatus.py','protocol.zh.md','protocol.en.md'):
        p=HERE/n;refs[p.relative_to(ROOT).as_posix()]=sha(p)
    return refs

def frozen(work):
    for rel,h in load(work/'runner-manifest.json').items():
        if sha(ROOT/rel)!=h:raise RuntimeError('frozen source changed '+rel)
    if base.capture_implementation('native')!=load(work/'implementation.json'):raise RuntimeError('kernel implementation changed')
    for row in load(work/'parents-manifest.json'):
        if sha(Path(row['source']))!=row['sha256'] or sha(work/row['copy'])!=row['sha256']:raise RuntimeError('parent changed')

def recorder(work,c):return old.recorder(work,c)
def relay(channel,layout,background,constant=False):
    x=np.zeros((20,len(layout.channels),4),dtype=np.float32)
    if not constant:
        x[:,layout.index[channel],0]=.8;x[:,layout.index[channel],2]=.8
        x[:,layout.index[background],0]=.2;x[:,layout.index[background],2]=.2
    return x.reshape(20,-1).tolist()

def create_templates(seed):
    rows={}
    for c in range(4):
        s=Student(seed,f'naive-instrument-{seed}-{c}');before=s.state()
        q=s.question(c)
        assert before['input_count']==0 and s.reader.committed_updates==0
        rows[str(s.mapping['C'+str(c)])]=dict(frames=q['frames'],question=q,before=before,after=s.state())
    return rows

def prepare(work):
    work.mkdir(parents=True,exist_ok=True)
    with base.worker_lock(work),connection() as c:
        if (work/'platform.json').exists():raise RuntimeError('already registered')
        resources(work)
        check=load(HERE/'apparatus-summary.json')
        assert check['passed'] and check['source_sha256']=={n:sha(HERE/n) for n in ('study.py','test_apparatus.py')}
        name='2026-11-01 ThreeMind · SAT Core必要性排除 v3'
        projects=[p for p in c.call('projects.list',{}) if p['name']==name]
        assert len(projects)<=1
        project=projects[0] if projects else c.request('POST','/api/v2/projects',body={'name':name})
        save(work/'platform.json',dict(project_id=project['id'],resource_id=RESOURCE))
        r=base.ResearchRecorder(work,project['id'],client=c)
        r.register(dict(source_key='sat-core-exclusion:20261101:v1',title=name,classification='development',execution_status='running',
            executor='ai',kernels=[base.KERNEL],protocol=(HERE/'protocol.zh.md').read_text('utf-8'),protocol_version=base.digest(manifest()),
            required_roles=['protocol','report','note'],metadata=dict(work=str(work),independent_origins=8,arms=list(ARMS),
            authorization='explicit user request for Core exclusion experiments',parent_resource='sat-curriculum-20261101-v2',half_life_changed=False)),request_id=ident('register'))
        r.synchronize(strict=True)
        c.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,target_id='managed-research-experiments',
            relative_path='2026-11-01-sat-core-exclusion/v1',registered_work_path=str(work),writer_mode='cooperative',expected_revision=0),headers={'X-ThreeMind-Request-ID':str(ident('resource'))})
        c.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=project['id'],resource_id=RESOURCE),headers={'X-ThreeMind-Request-ID':str(ident('grant'))})
        save(work/'runner-manifest.json',manifest());save(work/'implementation.json',base.capture_implementation('native'))
        for rel in manifest():r.save_original('frozen/'+rel,(ROOT/rel).read_bytes())
        r.save_original('apparatus-summary.json',(HERE/'apparatus-summary.json').read_bytes())
        parent_rows=[];preflight=[]
        for i in range(8):
            src=PARENT/f'origins/o{i}/normal';dst=work/f'parents/o{i}'
            end=load(src/'whole-test-026.json.gz');birth=load(src/'whole-birth.json.gz')
            refs=['whole-test-026.json.gz','whole-birth.json.gz']+end['sample_refs']
            for s in (end,birth):refs.extend(s['reader_ref']['path']+'/'+n for n in s['reader_ref']['files'])
            for rel in dict.fromkeys(refs):
                target=dst/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src/rel,target)
                parent_rows.append(dict(source=str(src/rel),copy=target.relative_to(work).as_posix(),sha256=sha(target)))
            preflight.append(dict(origin=i,seed=end['seed'],age_us=end['core']['time_us'],nodes=len(end['core']['nodes']),edges=len(end['core']['edges']),reader_digest=end['reader_digest']))
            m=sat.material(3111200+i)
            original=load(PARENT/f'material/o{i}.json')
            canon=lambda f:tuple(sorted(tuple(sorted(c)) for c in f['clauses']))
            used={canon(f) for k in ('training','development','dev_problems','tests') for f in original[k] if f.get('kind')!='unsatisfiable-sentinel'}
            assert not used.intersection(canon(f) for f in m['tests'] if f['kind']=='satisfiable')
            rng=random.Random(3111300+i);probes=list(range(4))*16;rng.shuffle(probes)
            save(work/f'material/o{i}.json',dict(seed=3111200+i,tests=m['tests'],probes=probes))
        save(work/'parents-manifest.json',parent_rows);save(work/'parent-preflight.json',preflight)
        for lang in ('zh','en'):
            r.text(dict(request_id=str(ident('protocol-'+lang)),identity=str(ident('protocol-doc-'+lang)),expected_revision=0,
              kind='protocol',title='SAT Core exclusion v3 '+lang,markdown=(HERE/f'protocol.{lang}.md').read_text('utf-8')))
        r.synchronize(strict=True);state(work,state='registered',origins_completed=0)
        print(json.dumps(dict(project=project['id'],record=r.experiment,pending=r.status['pending'])),flush=True)

class Branch:
    def __init__(self,work,origin,mode):
        self.mode,self.origin=mode,origin;self.branch_id=f'sat-v3-o{origin}-{mode}'
        self.parentdir=work/f'parents/o{origin}';parent=load(self.parentdir/'whole-test-026.json.gz')
        self.parent_sha=sha(self.parentdir/'whole-test-026.json.gz');self.mapping=parent['mapping'];self.seed=parent['seed']
        self.s=None;self.templates={};self.clock=0;self.world=None;self.recent=[];self.samples=[];self.reader_ref=None;self.chain=base.digest([]);self.count=0
        self.intervention={'parent':self.parent_sha,'parent_age_us':parent['core']['time_us'],'mode':mode}
        if mode in LIVE:
            self.s=Student.restore(self.parentdir,parent)
            before=self.s.state()
            if mode in ('restored','blank-core'):
                self.s.core=base.create_engine(base.Local51Config(seed=self.seed,energy_seed=self.seed^0x1634AB),kernel_id=base.KERNEL,backend='native')
                if mode=='restored':
                    self.s.core=base.create_engine(state=base.StateImage.from_dict(parent['core']),kernel_id=base.KERNEL,backend='native')
                    assert base.digest(before)==base.digest(self.s.state())
                else:
                    self.s.next_background=0;self.s.input_digest=base.digest([]);self.s.input_count=0
                    self.intervention['new_core_age_us']=0
            self.s.sample_refs=[f"../../../parents/o{origin}/{rel}" for rel in parent["sample_refs"]]
            self.reader=self.s.reader
        else:
            self.reader=CalibratedActivity(list(self.mapping.values()),('prefer','avoid'),self.branch_id,seed=self.seed) if mode in TRAINED else CalibratedActivity.restore(self.parentdir/parent['reader_ref']['path'])
            if mode=='template-fixed':self.templates=load(work/f'templates/o{origin}.json.gz')
        self.initial_reader=self.reader_digest()
    def reader_digest(self):
        return tensor_hash([self.reader.state_dict(),self.reader.optimizer.state_dict(),self.reader.learning_rng,self.reader.computed_updates,self.reader.committed_updates])
    def frames(self,category):
        channel=self.mapping['C'+str(category)]
        if self.mode=='template-fixed':return self.templates[str(channel)]['frames']
        return relay(channel,self.reader.layout,self.mapping['K'],self.mode.startswith('constant'))
    def question(self,c):
        if type(c) is not int or c not in range(4):raise ValueError('only input category is permitted')
        if self.s:
            q=self.s.question(c)
        else:
            frames=self.frames(c);logits=self.reader.predict([[frames[i] for i in FRAME_INDEX]])[0].tolist()
            q=dict(start_us=self.clock,end_us=self.clock+1_000_000,category=c,frames=frames,selected_indices=FRAME_INDEX,
                   frame_times_us=[self.clock+(i+1)*50_000 for i in range(20)],logits=logits,prediction=int(np.argmax(logits)),
                   score=int(np.argmax(logits)==0),input=dict(channel=self.mapping['C'+str(c)],amplitude=.8),activity_source=self.mode)
            self.clock+=1_000_000
        self.count+=1;self.chain=base.digest([self.chain,{'category':c,'start_us':q['start_us'],'end_us':q['end_us'],'prediction':q['prediction']}]);self.recent=(self.recent+[q])[-3:]
        return q
    def checkpoint(self,folder,name,progress):
        digest=self.reader_digest()
        if self.reader_ref is None or self.reader_ref['digest']!=digest:
            rel=f'readers/{self.reader.committed_updates:06d}-{digest[:12]}'
            if not (folder/rel).exists():self.reader.save(folder/rel)
            self.reader_ref=dict(path=rel,digest=digest,files={p.name:sha(p) for p in (folder/rel).iterdir()})
        if self.s:self.s.reader_ref=self.reader_ref
        value=dict(schema='sat-core-exclusion-branch/1',branch_id=self.branch_id,mode=self.mode,origin=self.origin,parent_sha=self.parent_sha,
            seed=self.seed,mapping=self.mapping,intervention=self.intervention,initial_reader=self.initial_reader,
            student=self.s.state() if self.s else None,clock=self.clock,world=self.world,recent=self.recent,samples=self.samples,
            reader_ref=self.reader_ref,chain=self.chain,count=self.count,torch_rng=torch.get_rng_state().tolist(),progress=progress)
        save(folder/name,value);base.atomic_json(folder/'current.json',dict(file=name,sha256=sha(folder/name),progress=progress))
        return value
    @classmethod
    def restore(cls,work,folder,value):
        b=cls.__new__(cls)
        for k in ('branch_id','mode','origin','parent_sha','seed','mapping','intervention','initial_reader','clock','world','recent','samples','reader_ref','chain','count'):setattr(b,k,value[k])
        b.parentdir=work/f'parents/o{b.origin}';b.templates=load(work/f'templates/o{b.origin}.json.gz') if b.mode=='template-fixed' else {}
        for n,h in b.reader_ref['files'].items():assert sha(folder/b.reader_ref['path']/n)==h
        b.s=Student.restore(folder,value['student']) if value['student'] else None
        b.reader=b.s.reader if b.s else CalibratedActivity.restore(folder/b.reader_ref['path'])
        torch.set_rng_state(torch.tensor(value['torch_rng'],dtype=torch.uint8))
        assert b.reader_digest()==b.reader_ref['digest']
        return b
    def fit_stage(self,folder,stage):
        parent=load(self.parentdir/'whole-test-026.json.gz');oldrows=load(self.parentdir/parent['sample_refs'][stage])
        rows=[dict(frames=self.frames(r['condition']['category']),label=r['label'],condition=r['condition'],original_question_start=r['question']['start_us']) for r in oldrows]
        rel=f'samples-{stage}.json.gz';save(folder/rel,rows);self.samples.append(rel)
        allrows=[r for p in self.samples for r in load(folder/p)]
        fit=self.reader.continue_calibration([[r['frames'][i] for i in FRAME_INDEX] for r in allrows],[r['label'] for r in allrows],steps=1200)
        dev=[self.question(c) for c in list(range(4))*4]
        save(folder/f'fit-{stage}.json',dict(receipt=fit,development=[{'category':q['category'],'prediction':q['prediction']} for q in dev],
             errors=[q['category'] for q in dev if q['prediction']!=int(q['category']!=0)],source_samples=parent['sample_refs'][stage]))
    def solve(self,p):
        a,rng=sat.begin_problem(p);initial=a[:];steps=[];start=time.perf_counter()
        for k in range(96):
            bad=sat.unsatisfied(p['clauses'],a)
            if not bad:break
            ci=rng.choice(bad);vs=[abs(x)-1 for x in p['clauses'][ci]];rng.shuffle(vs)
            bs=[sat.break_count(p['clauses'],a,v) for v in vs];queries=[self.question(min(b,3)) for b in bs]
            selected,noise=sat.choose([q['score'] for q in queries],rng,.25);a[vs[selected]]=not a[vs[selected]]
            steps.append(dict(step=k,clause=ci,candidates=vs,breaks=bs,queries=queries,selected=selected,noise=noise,assignment=a[:]))
            self.world=dict(problem_id=p['id'],assignment=a[:],environment_rng=json.loads(base.encoded(rng.getstate())),step=k+1)
            if self.s:self.s.world=self.world
        solved=sat.verify_witness(p['n'],p['clauses'],a)
        return dict(initial_assignment=initial,final_assignment=a,solved=solved,outcome='SAT' if solved else 'UNKNOWN',flips=len(steps),steps=steps,wall_seconds=time.perf_counter()-start)

def run(work):
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    with base.worker_lock(work):
        frozen(work);resources(work)
        if any((work/x).exists() for x in ('STOP','in-flight.json')):raise RuntimeError('unresolved marker')
        if load(work/'status.json')['state']=='awaiting-analysis':raise RuntimeError('already computed')
        base.atomic_json(work/'host.json',dict(pid=os.getpid(),created_at=psutil.Process().create_time(),command=sys.argv))
        try:
            with Guard(work):
                for o in range(8):
                    m=load(work/f'material/o{o}.json')
                    if not (work/f'templates/o{o}.json.gz').exists():
                        boundary(work);mark(work,f'o{o}/instrument');save(work/f'templates/o{o}.json.gz',create_templates(2111100+o));clear(work)
                    for arm in ARMS:
                        folder=work/f'origins/o{o}/{arm}';folder.mkdir(parents=True,exist_ok=True)
                        if (folder/'done.json').exists():continue
                        progress=dict(stage='fit' if arm in TRAINED else 'probe',cycle=0,test=0);b=None
                        if arm in ARMS[:8]:
                            if (folder/'current.json').exists():
                                current=load(folder/'current.json');assert sha(folder/current['file'])==current['sha256']
                                value=load(folder/current['file']);b=Branch.restore(work,folder,value);progress=value['progress']
                            else:
                                boundary(work);mark(work,f'o{o}/{arm}/birth');b=Branch(work,o,arm);b.checkpoint(folder,'whole-start.json.gz',progress);clear(work)
                            while progress['stage']=='fit':
                                stage=progress['cycle'];boundary(work);mark(work,f'o{o}/{arm}/fit-{stage}');b.fit_stage(folder,stage)
                                progress=dict(stage='probe' if stage==3 else 'fit',cycle=stage+1,test=0)
                                b.checkpoint(folder,f'whole-fit-{stage}.json.gz',progress);clear(work)
                            if progress['stage']=='probe':
                                boundary(work);mark(work,f'o{o}/{arm}/probe');rows=[b.question(c) for c in m['probes']]
                                save(folder/'probes.json.gz',rows);progress=dict(stage='test',cycle=progress['cycle'],test=0)
                                b.checkpoint(folder,'whole-probes.json.gz',progress);clear(work)
                        else:progress=dict(stage='test',test=len(list(folder.glob('result-*.json.gz'))))
                        for j in range(progress['test'],len(m['tests'])):
                            boundary(work);mark(work,f'o{o}/{arm}/test-{j}');p=m['tests'][j]
                            before=load(folder/'current.json')['sha256'] if b else None
                            r=b.solve(p) if b else old.rule_baseline(p) if arm=='quantized-rule' else sat.baseline(p,arm,96)
                            r.update(origin=o,arm=arm,problem_id=p['id'],kind=p['kind'],before_checkpoint_sha256=before)
                            save(folder/f'result-{j:03d}.json.gz',r)
                            if b:
                                progress=dict(stage='test',cycle=progress['cycle'],test=j+1);b.checkpoint(folder,f'whole-test-{j+1:03d}.json.gz',progress)
                            clear(work);state(work,state='running',origin=o,arm=arm,tests_completed=j+1)
                        save(folder/'done.json',dict(tests=26,reader_digest=b.reader_digest() if b else None))
                        print(json.dumps(dict(origin=o,arm=arm,completed=True)),flush=True)
                        del b;gc.collect()
                state(work,state='awaiting-analysis',origins_completed=8)
        except InterruptedError as exc:
            if not (work/'STOP').exists():save(work/'STOP',dict(reason=str(exc),epoch=time.time()))
            state(work,state='paused-complete-boundary',reason=str(exc))
        except Exception as exc:
            state(work,state='failed-preserve-in-flight',error=repr(exc));raise

def status(work):return old.status(work)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','status']);p.add_argument('--work',type=Path,default=WORK)
    a=p.parse_args();globals()[a.command](a.work.resolve())