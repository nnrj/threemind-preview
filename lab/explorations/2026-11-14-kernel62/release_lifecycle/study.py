"""R51t10: registered copies, complete state, passive process measurement."""
import argparse
from copy import deepcopy
from dataclasses import replace
import gc
import gzip
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location('r51t9_helpers', HERE.parent / 'prefix_resources/study_resources.py')
x = importlib.util.module_from_spec(spec); spec.loader.exec_module(x)
s, pre = x.s, x.previous
from threemind_core import StateImage, Stimulus
from threemind_kernels.local62 import Local62Config
from threemind_kernels.registry import resolve_kernel

DATA = Path('E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation')
NS = UUID('d96c782d-46e9-445e-8dba-0493020d746d')
FLAGS = {f'p{p}-f{f}': {'resource_precheck_enabled': bool(p), 'subthreshold_expiry_enabled': bool(f)}
         for p in (0, 1) for f in (0, 1)}
TAILS = ('stable-g4-r8', 'stable-g0-r08-sources0', 'default-g4-r8',
         'default-g0-r08-sources0', 'pre-old-high')
TARGETS = set(s.measure.TOKENS.values())


def native_file():
    import _threemind_native
    return next(Path(_threemind_native.__file__).parent.glob('*.pyd'))


def put(path, state):
    pre.put(path, state)


def get(path):
    return pre.get(path)


def engine(config=None, state=None, backend='native'):
    if state is not None and state.to_dict()['dynamics'].startswith('threemind.research-prefix-precheck62/'):
        return pre.r.ResearchEngine(state=state)
    return resolve_kernel('threemind.continuous-memory/6.2').create(config, state, backend=backend)


def make_plan():
    old = s.read(DATA / 'persistent-activity61-v1/cases.json')
    persistent = {c['material_key']: c for c in old if c['variant'] == 'v61'}
    prefix = s.read(DATA / 'prefix-resources62-v1/cases.json')
    stages = []
    for name, flags in FLAGS.items():
        for b in (0, 1):
            base = f'persistent/{name}/{b}'
            key = f'retention/s{b}/011/paired/train'
            stages.append(dict(key=base+'/train', group='persistent', block=b, flags=flags,
                               case=persistent[key], material_source='persistent-activity61-v1', parent=None, patch={}))
            for mode, patch in (('original', {}), ('short-inhibition', {'inhibition_tau': .2321354823145728/4})):
                for part, key in (('wait', f'readout/s{b}/011/paired/d300/wait'), ('probe', f'sustain/s{b}/unchanged')):
                    stages.append(dict(key=f'{base}/{mode}/{part}', group='persistent', block=b, flags=flags,
                                       mode=mode, case=persistent[key], material_source='persistent-activity61-v1',
                                       parent=base+'/train' if part=='wait' else f'{base}/{mode}/wait',
                                       patch=patch if part=='wait' else {}))
            base = f'prefix/{name}/{b}'
            for cue in ('train', 'AB', 'DB'):
                key = f'short/train-{b}' if cue=='train' else f'history/s{b}/101/d1/{cue}'
                stages.append(dict(key=base+'/'+cue, group='prefix', block=b, cue=cue, flags=flags,
                                   case=prefix[key], material_source='prefix-resources62-v1',
                                   parent=None if cue=='train' else base+'/train', patch=prefix[key].get('patch', {})))
    for name in TAILS:
        for b in (0, 1):
            for fix in (False, True):
                stages.append(dict(key=f'tail/{name}/{b}/fix-{int(fix)}', group='tail', block=b, variant=name,
                                   external=f'references/{name}/{b}/final.rstate.gz',
                                   patch={'subthreshold_expiry_enabled': fix}))
    for b in (0, 1):
        for fix in (False, True):
            for cue in ('AB', 'DB'):
                key = f'history/s{b}/101/d1/{cue}'
                stages.append(dict(key=f'success/{b}/fix-{int(fix)}/{cue}', group='success', block=b, cue=cue,
                                   external=f'references/pre-old-high/{b}/final.rstate.gz',
                                   case=prefix[key], material_source='prefix-resources62-v1',
                                   patch=prefix[key].get('patch', {}) | {'subthreshold_expiry_enabled': fix}))
    assert len(stages)==92
    return stages


def prepare(work):
    assert not work.exists(), 'Use a new registered work directory'
    assert s.base.resource_check(work.parent)['safe']
    assert shutil.disk_usage(work.parent).free > 29*2**30
    for batch in ('prefix-resources62-v1', 'persistent-activity61-v1', 'dynamics-function61-v1'):
        assert not (DATA/batch/'in-flight.json').exists()
        receipt=s.read(DATA/batch/'publication/completion.json')
        assert receipt['pending']==0 and receipt['coverage']=='verified'
    work.mkdir()
    plan=make_plan(); s.write(work/'plan.json', plan)
    copied=set(); refs={}
    for stage in plan:
        if 'case' not in stage: continue
        rel=Path('materials')/stage['material_source']/stage['case']['material_key']/'frames.jsonl'
        if rel in copied: continue
        source=DATA/stage['material_source']/'materials'/stage['case']['material_key']/'frames.jsonl'
        dest=work/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        assert s.sha(source)==s.sha(dest);refs[str(source)]=s.sha(source);copied.add(rel)
    for name in TAILS:
        for b in (0,1):
            source=x.folder(DATA/'prefix-resources62-v1',name,b,'train')
            image=x.state_at(source,'final')
            assert image.digest==s.read(source/'result.json')['final_sha256']
            dest=work/'references'/name/str(b);dest.mkdir(parents=True)
            put(dest/'final.rstate.gz',image)
            for p in source.iterdir():
                if p.name.startswith('final.') or p.name=='result.json': refs[str(p)]=s.sha(p)
    # Historical positives are inspected, never run or modified.
    historical=[]
    for label, batch, variant in (
        ('original-v1','persistent-activity61-v1','v1'),
        ('original-v2','persistent-activity61-v1','v2'),
        ('short-inhibition61','dynamics-function61-v1','persist-g0.24-t0.25')):
        for b in (0,1):
            source=DATA/batch/'cases'/variant/f'sustain/s{b}/unchanged'
            dest=work/'historical'/label/str(b);dest.mkdir(parents=True)
            for name in ('trajectory.json.xz','result.json','initial.tmind','final.tmind'):
                p=source/name;shutil.copyfile(p,dest/name);refs[str(p)]=s.sha(p)
            historical.append({'label':label,'block':b,'folder':dest.relative_to(work).as_posix()})
    s.write(work/'historical.json',historical);s.write(work/'external-manifest.json',refs)
    files={p.relative_to(work).as_posix():s.sha(p) for folder in ('materials','references','historical')
           for p in (work/folder).rglob('*') if p.is_file()}
    s.write(work/'reference-manifest.json',files)
    s.write(work/'initial-resources.json',s.base.resource_check(work))
    print(json.dumps({'prepared':str(work),'stages':len(plan),'reference_files':len(files)}),flush=True)


def load_inputs(work, stage, calibration=False):
    case=stage['case'];p=work/'materials'/stage['material_source']/case['material_key']/'frames.jsonl'
    rows=[json.loads(line) for line in p.read_bytes().splitlines()]
    assert rows.pop(0)['run_id']==case['old_id']
    for row in rows:
        assert row['status']=='delivered' and not row['labels']
        assert row['delivered_time_us']==row['scheduled_time_us']==row['stimulus']['time_us']
        if calibration: row['stimulus']['channels']=[[ch^0x20000000,a] for ch,a in row['stimulus']['channels']]
    return sorted(rows,key=lambda r:(int(r['source_policy']['resolved_at_us']),r['core_event_id']))


def observe(e, all_nodes=False):
    before=e.capture_state().digest
    nodes=e.observation_nodes()
    assert e.capture_state().digest==before, 'observation mutated state'
    return {'time_us':e.time_us,'nodes':nodes if all_nodes else [n for n in nodes if n['channel'] in TARGETS]}


def drive(e, case, rows, out=None, mode='observed', backend='native'):
    begin=e.time_us;end=case['end_us'];probe=case.get('probe_start_us')
    index=0;points=[];next_point=probe;started=False;changed=False;wall=time.monotonic()
    stream=None if out is None else gzip.open(out/'course.jsonl.gz','xb',compresslevel=1)
    next_course=begin
    while True:
        assert time.monotonic()-wall<300,'stage wall limit; preserve in-flight'
        if mode!='plain' and probe is None:
            observe(e,True)
        if e.life=='dead':break
        if e.time_us==probe and not started and mode!='plain': points.append(observe(e))
        while index<len(rows) and int(rows[index]['source_policy']['resolved_at_us'])==e.time_us:
            e.inject(Stimulus.from_dict(rows[index]['stimulus']));index+=1
        e.advance_to(e.time_us)
        if e.time_us==probe and not started:
            started=True
            if mode!='plain':points.append(observe(e))
            next_point+=10000
        elif started and e.time_us==next_point:
            if mode!='plain':points.append(observe(e))
            next_point+=10000
        if stream and e.time_us>=next_course:
            stream.write(json.dumps(observe(e),sort_keys=True).encode()+b'\n');next_course=e.time_us+100000
        if mode in ('restored','paused') and not changed and e.time_us>=begin+1000000:
            image=e.capture_state()
            if mode=='restored':e=engine(state=image,backend=backend)
            else:time.sleep(.01)
            assert e.capture_state().digest==image.digest;changed=True
        if e.time_us==end or e.life=='dead':break
        times=[end,e.time_us+(37000 if mode=='partitioned' else 100000)]
        if index<len(rows):times.append(int(rows[index]['source_policy']['resolved_at_us']))
        if next_point is not None:times.append(next_point)
        target=min(t for t in times if t>e.time_us);e.advance_to(target)
    if stream:stream.close()
    if e.life!='dead':assert index==len(rows)
    return e,points,index


def apparatus(work):
    assert not (work/'apparatus.json').exists()
    stage=next(q for q in s.read(work/'plan.json') if q['key']=='prefix/p0-f0/0/train')
    case=deepcopy(stage['case']);case['end_us']=2000000
    rows=[r for r in load_inputs(work,stage,True) if int(r['source_policy']['resolved_at_us'])<2000000]
    checks=[]
    for name,flags in FLAGS.items():
        hashes={};states={}
        for backend in ('reference','native'):
            for mode in ('plain','observed','partitioned','restored','paused'):
                e=engine({'seed':9291199}|case['initial_config']|flags,backend=backend)
                e,_,_=drive(e,case,rows,mode=mode,backend=backend)
                hashes[backend+'/'+mode]=e.capture_state().digest
                if mode=='plain':states[backend]=e.capture_state().to_dict()
            assert len({v for k,v in hashes.items() if k.startswith(backend+'/')})==1
        errors=[]
        def compare(a,b):
            if isinstance(a,dict):
                assert a.keys()==b.keys()
                for k in a:compare(a[k],b[k])
            elif isinstance(a,list):
                assert len(a)==len(b)
                for u,v in zip(a,b):compare(u,v)
            elif isinstance(a,(int,float)) and not isinstance(a,bool):errors.append(abs(a-b))
            else:assert a==b,(a,b)
        compare(states['reference'],states['native']);assert max(errors,default=0)<1e-10
        checks.append({'flags':name,'hashes':hashes,'max_backend_error':max(errors,default=0)})
    s.write(work/'apparatus.json',{'passed':True,'independent_codes':True,'checks':checks})
    print('Apparatus passed: four configurations, two backends, five observation modes',flush=True)


def register(work):
    assert s.read(work/'apparatus.json')['passed'] and not (work/'frozen.json').exists()
    paths=[p for p in HERE.iterdir() if p.suffix in ('.py','.md')]
    paths+=list((ROOT/'src').rglob('*.py'))
    paths+=[Path(m.__file__) for m in (x,s,pre,pre.c,pre.r,s.base)]
    paths += [Path(m.__file__) for m in tuple(sys.modules.values())
              if getattr(m,'__file__',None) and str(m.__file__).endswith('.py')
              and Path(m.__file__).is_relative_to(ROOT/'lab')]
    paths+=list((ROOT/'crates/threemind-core/src').glob('local62*'))
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    for rel in sources:
        dest=work/'frozen-source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest)
    with pre.client_context() as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client)
        rec.register({'source_key':'r51t10:release-lifecycle62:20261115:v1',
            'title':'R51t10：释放前门槛与生命周期修复后的持续活动', 'classification':'formal',
            'execution_status':'running','executor':'ai','kernels':['threemind.continuous-memory/6.2'],
            'protocol':(HERE/'protocol.zh.md').read_text('utf8'),'protocol_version':s.sha(HERE/'protocol.zh.md'),
            'required_roles':['protocol','report','note','original'],
            'metadata':{'material_blocks':2,'new_stages':92,'historical_readonly':True}},request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-doc-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R51t10 protocol '+lang,
                'markdown':(HERE/f'protocol.{lang}.md').read_text('utf8')})
        rec.synchronize(strict=True);assert rec.status['pending']==0
        s.write(work/'registration.json',{'project':s.PROJECT,'record':rec.experiment,'pending':0})
    s.write(work/'frozen.json',{'sources':sources,'native_path':str(native_file()),'native_sha256':s.sha(native_file()),
        'plan_sha256':s.sha(work/'plan.json'),'references_sha256':s.sha(work/'reference-manifest.json'),
        'original_cap':2**30,'additional_peak':4*2**30})
    print(json.dumps(s.read(work/'registration.json')),flush=True)


def check(work):
    f=s.read(work/'frozen.json')
    for rel,sha in f['sources'].items():assert s.sha(ROOT/rel)==sha,rel
    assert s.sha(Path(f['native_path']))==f['native_sha256']
    assert s.sha(native_file())==f['native_sha256'], 'loaded native runtime differs from frozen build'
    assert s.sha(work/'plan.json')==f['plan_sha256']
    assert s.sha(work/'reference-manifest.json')==f['references_sha256']
    for rel,sha in s.read(work/'reference-manifest.json').items():assert s.sha(work/rel)==sha,rel


def run(work):
    check(work)
    assert not any((work/n).exists() for n in ('STOP','in-flight.json','summary.json'))
    import psutil
    results=[];started=time.monotonic()
    with s.base.worker_lock(work),pre.Guard(work) as guard:
        host={'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv}
        s.write(work/f'host-{time.time_ns()}.json',host);s.base.atomic_json(work/'host.json',host)
        for stage in s.read(work/'plan.json'):
            out=work/'cases'/stage['key']
            if (out/'result.json').exists():
                q=s.read(out/'result.json');assert get(out/'final.rstate.gz').digest==q['final_sha256'];results.append(q);continue
            if (work/'STOP').exists():return
            size=sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
            if size>=2**30:
                s.write(work/'STOP',{'reason':'registered 1 GiB original cap','bytes':size,'epoch':time.time()})
                return
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            out.mkdir(parents=True,exist_ok=False)
            s.write(work/'in-flight.json',host|{'key':stage['key']})
            parent=None
            if 'external' in stage:parent=get(work/stage['external'])
            elif stage.get('parent'):parent=get(work/'cases'/stage['parent']/'final.rstate.gz')
            e=engine(state=parent) if parent else engine({'seed':9291000}|stage['case']['initial_config']|stage['flags'])
            before=e.capture_state();put(out/'before-intervention.rstate.gz',before)
            if stage.get('patch'):e.reconfigure(replace(e.config,**stage['patch']))
            initial=e.capture_state();put(out/'initial.rstate.gz',initial)
            t=time.monotonic();points=[];tail=[];rows=[];injected=0
            if stage['group']=='tail':
                begin=e.time_us
                for delay in (0,1,5,10,30,60,120,300):
                    e.advance_to(begin+delay*1000000);d=e.capture_state().to_dict()
                    put(out/f'tail-{delay}.rstate.gz',e.capture_state())
                    tail.append(observe(e,True)|{'requested_seconds':delay,'actual_seconds':(e.time_us-begin)/1e6,
                        'life':e.life,'active':d['active'],'quiet_since_us':d['quiet_since_us'],'transport':d['transport']})
                    if e.life=='dead':break
                s.packed(out/'tail.json.gz',tail)
            else:
                rows=load_inputs(work,stage);s.packed(out/'inputs.json.gz',rows)
                e,points,injected=drive(e,stage['case'],rows,out)
                if points:s.packed(out/'process.json.gz',points)
            final=e.capture_state();put(out/'final.rstate.gz',final)
            assert get(out/'final.rstate.gz').digest==final.digest
            q={'key':stage['key'],'group':stage['group'],'block':stage['block'],'flags':stage.get('flags'),
               'patch':stage['patch'],'parent_sha256':parent.digest if parent else None,
               'before_sha256':before.digest,'initial_sha256':initial.digest,'final_sha256':final.digest,
               'time_us':e.time_us,'life':e.life,'injected':injected,'scheduled':len(rows),
               'wall_seconds':time.monotonic()-t,'transport':final.to_dict()['transport']}
            if points:
                if len(points)==1502:q['process']=s.measure.process(stage['case'],points)
                else:q['incomplete_process']={'reason':'individual reached declared death state','samples':len(points)}
                vals=[max((n['activation'] for n in p['nodes']),default=0) for p in points]
                q['activity']={'min':min(vals),'max':max(vals),'end':vals[-1],'samples':len(vals),
                    'continuous':all(v>1e-6 for v in vals)}
            if tail:q['tail']=tail
            s.write(out/'result.json',q);results.append(q)
            (work/'in-flight.json').unlink()
            s.base.atomic_json(work/'current.json',{'complete':len(results),'total':92,'last':stage['key']})
            print(json.dumps({'complete':len(results),'key':stage['key'],'life':e.life,'seconds':round(q['wall_seconds'],2),
                              'activity':q.get('activity'),'margin':q.get('process',{}).get('signed_peak')},ensure_ascii=False),flush=True)
            del e,points,tail,rows;gc.collect()
        s.write(work/'summary.json',{'stages':len(results),'wall_seconds':time.monotonic()-started})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','apparatus','register','check','run'))
    p.add_argument('--work',type=Path,required=True);args=p.parse_args();globals()[args.action](args.work)
