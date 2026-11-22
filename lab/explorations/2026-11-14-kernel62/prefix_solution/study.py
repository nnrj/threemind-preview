"""R51t11 bounded research execution, separate from production kernels."""
import argparse
from copy import deepcopy
import gc
import importlib.util
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'src'))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
r=module('r51t11_research',HERE/'research.py')
recorder=module('r51t11_recording',HERE.parent/'release_lifecycle/recording_v2.py')
h=recorder.s;s=h.s;pre=h.pre
DATA=h.DATA;OLD=DATA/'release-lifecycle62-v1-r1'
NS=UUID('92376b53-5ec7-4de5-ad50-2c4e34992022')


def variants():
    return {f'n{n}r{b}l{l}g{g}':{'research_normalize_inhibition':bool(n),
            'research_bypass_inhibition_resources':bool(b),'inhibitory_learning_enabled':not bool(l),
            'inhibition_signal_threshold':0.0 if g else None,'consolidation_mode':'stability',
            'novelty_mode':'immediate','activation_signal_threshold':.004,
            'resource_precheck_enabled':True,'subthreshold_expiry_enabled':True}
            for n,b,l,g in itertools.product((0,1),repeat=4)}


def engine(config=None,state=None,backend='reference'):
    if state is not None:
        ident=state.to_dict()['dynamics']
        if ident==r.KERNEL_ID:return r.ResearchEngine(state=state)
        if ident.startswith('threemind.research-prefix-precheck62/'):
            return pre.r.ResearchEngine(state=state)
        return h.engine(state=state,backend=backend)
    return r.ResearchEngine(r.ResearchConfig(**config))


def normalized(image):
    d=deepcopy(image.to_dict())
    for k in ('schema','dynamics','definition','definition_hash'):d.pop(k,None)
    for k in ('research_normalize_inhibition','research_bypass_inhibition_resources'):d['config'].pop(k,None)
    return d


def inputs(work,case,mask=0,end=None):
    path=work/'materials'/case['source']/case['material_key']/'frames.jsonl'
    rows=[json.loads(line) for line in path.read_bytes().splitlines()]
    assert rows.pop(0)['run_id']==case['old_id']
    for row in rows:
        assert row['status']=='delivered' and not row['labels']
        assert row['stimulus']['time_us']==row['delivered_time_us']==row['scheduled_time_us']
        if mask:row['stimulus']['channels']=[[ch^mask,value] for ch,value in row['stimulus']['channels']]
    return sorted((row for row in rows if end is None or int(row['source_policy']['resolved_at_us'])<end),
                  key=lambda row:(int(row['source_policy']['resolved_at_us']),row['core_event_id']))


def prepare(work):
    assert not work.exists()
    assert s.read(OLD/'publication/completion.json')['pending']==0
    assert s.base.resource_check(OLD)['safe'] and shutil.disk_usage(OLD).free>29*2**30
    work.mkdir();oldplan=s.read(OLD/'plan.json');cases={}
    for stage in oldplan:
        if stage['group'] not in ('prefix','persistent'):continue
        c=deepcopy(stage['case']);c['source']=stage['material_source']
        cases[c['source']+'/'+c['material_key']]=c
    s.write(work/'materials.json',cases)
    refs={}
    for c in cases.values():
        source=OLD/'materials'/c['source']/c['material_key']/'frames.jsonl'
        target=work/'materials'/c['source']/c['material_key']/'frames.jsonl'
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        refs[target.relative_to(work).as_posix()]=s.sha(source)
    s.write(work/'reference-manifest.json',refs)
    s.write(work/'initial-resources.json',s.base.resource_check(work))
    stages=[]
    for name,patch in variants().items():
        for block in (0,1):
            parent=f'A/{name}/{block}/train'
            for cue in ('train','AB','DB'):
                key=f'short/train-{block}' if cue=='train' else f'history/s{block}/101/d1/{cue}'
                case=deepcopy(cases['prefix-resources62-v1/'+key])
                stages.append({'key':f'A/{name}/{block}/{cue}','group':'prefix','variant':name,
                    'block':block,'cue':cue,'case':case,'patch':patch,'mask':0,'seed':9291000,
                    'parent':None if cue=='train' else parent})
    assert len(stages)==96;s.write(work/'phase-A.json',stages)
    print(json.dumps({'prepared':str(work),'stages':96,'material_files':len(refs)}),flush=True)


def apparatus(work):
    assert not (work/'apparatus.json').exists()
    base=deepcopy(s.read(work/'phase-A.json')[0]['case']);base['end_us']=6000000
    rows=inputs(work,base,0x20000000,base['end_us'])
    checks=[];old_targets=recorder.s.TARGETS
    recorder.s.TARGETS={ch^0x20000000 for ch in old_targets};recorder.s.engine=engine
    with s.base.worker_lock(work),pre.Guard(work):
        cfg={'seed':9291199}|base['initial_config']|variants()['n0r0l0g0']
        candidate=engine(cfg);prod=r.production.Local62Engine(r.production.Local62Config(**{
            k:v for k,v in cfg.items() if not k.startswith('research_')}))
        a,_,_=recorder.drive(candidate,base,deepcopy(rows),mode='plain')
        b,_,_=recorder.drive(prod,base,deepcopy(rows),mode='plain')
        assert normalized(a.capture_state())==normalized(b.capture_state())
        checks.append({'production_equivalence':True})
        for name,patch in variants().items():
            hashes={};times={}
            for mode in ('plain','observed','restored','partitioned','paused'):
                start=time.monotonic();e=engine({'seed':9291199}|base['initial_config']|patch)
                e,_,_=recorder.drive(e,base,deepcopy(rows),mode=mode)
                hashes[mode]=e.capture_state().digest;times[mode]=time.monotonic()-start
            assert len(set(hashes.values()))==1,name
            checks.append({'variant':name,'same_complete_state':True,'hashes':hashes,'wall_seconds':times})
    recorder.s.TARGETS=old_targets
    s.write(work/'apparatus.json',{'passed':True,'independent_codes':True,'checks':checks})
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'apparatus_passed':True,'configurations':16,'modes':5}),flush=True)


def register(work):
    assert s.read(work/'apparatus.json')['passed'] and not (work/'frozen.json').exists()
    paths=list(HERE.glob('*.py'))+list(HERE.glob('protocol.*.md'))+list((ROOT/'src').rglob('*.py'))
    paths+=[Path(m.__file__) for m in tuple(sys.modules.values()) if getattr(m,'__file__',None)
            and str(m.__file__).endswith('.py') and Path(m.__file__).is_relative_to(ROOT/'lab')]
    sources={p.relative_to(ROOT).as_posix():s.sha(p) for p in paths}
    for rel in sources:
        dest=work/'frozen-source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest)
    with pre.client_context() as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client)
        rec.register({'source_key':'r51t11:prefix-solution62:20261115:v1',
            'title':'R51t11：前缀区分的可实施恢复方案','classification':'formal','execution_status':'running',
            'executor':'ai','kernels':[r.KERNEL_ID],'protocol':(HERE/'protocol.zh.md').read_text('utf8'),
            'protocol_version':s.sha(HERE/'protocol.zh.md'),'required_roles':['protocol','report','note','original'],
            'metadata':{'material_blocks':2,'stage_cap':192,'phase_a_stages':96,'production_unchanged':True}},
            request_id=uuid5(NS,'register'))
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(NS,'protocol-doc-'+lang)),'request_id':str(uuid5(NS,'protocol-'+lang)),
                'expected_revision':0,'kind':'protocol','title':'R51t11 protocol '+lang,
                'markdown':(HERE/f'protocol.{lang}.md').read_text('utf8')})
        rec.append('stage','r51t11:phase-a',{'stages':s.read(work/'phase-A.json')},request_id=uuid5(NS,'phase-a'))
        rec.synchronize(strict=True);assert rec.status['pending']==0
        s.write(work/'registration.json',{'project':s.PROJECT,'record':rec.experiment,'pending':0})
    s.write(work/'frozen.json',{'sources':sources,'phase_a_sha256':s.sha(work/'phase-A.json'),
                             'references_sha256':s.sha(work/'reference-manifest.json')})
    print(json.dumps(s.read(work/'registration.json')),flush=True)


def check(work):
    f=s.read(work/'frozen.json')
    for rel,hsh in f['sources'].items():assert s.sha(ROOT/rel)==hsh,rel
    assert s.sha(work/'phase-A.json')==f['phase_a_sha256']
    assert s.sha(work/'reference-manifest.json')==f['references_sha256']
    for rel,hsh in s.read(work/'reference-manifest.json').items():assert s.sha(work/rel)==hsh,rel


def measure(case,points,mask):
    targets={k:v^mask for k,v in s.measure.TOKENS.items()}
    start=case['probe_start_us']+round(case['gap_s']*1e6)
    correct='C' if case['cue']=='AB' else 'E'
    if case['swap']:correct='E' if correct=='C' else 'C'
    wrong='E' if correct=='C' else 'C'
    peaks={k:max((n['activation'] for p in points if p['time_us']>=start for n in p['nodes'] if n['channel']==targets[k]),default=0)
           for k in (correct,wrong)}
    maximum=[max((n['activation'] for n in p['nodes']),default=0) for p in points]
    return {'margin':peaks[correct]-peaks[wrong],'complete':len(points)==1502,'samples':len(points),
            'minimum':min(maximum,default=0),'maximum':max(maximum,default=0),'end':maximum[-1] if maximum else 0,
            'continuous':len(points)==1502 and all(v>1e-6 for v in maximum),
            'saturation_fraction':sum(n['activation']>=.95 for p in points for n in p['nodes'])/
                max(1,sum(len(p['nodes']) for p in points))}


def run(work,phase):
    import psutil
    check(work)
    plan=s.read(work/f'phase-{phase}.json')
    if phase!='A':
        frozen=s.read(work/f'phase-{phase}-frozen.json');assert s.sha(work/f'phase-{phase}.json')==frozen['sha256']
    assert not any((work/n).exists() for n in ('STOP','in-flight.json',f'phase-{phase}-summary.json'))
    results=[];started=time.monotonic();recorder.ACTIVE_WORK=work
    with s.base.worker_lock(work),pre.Guard(work) as guard:
        host={'pid':os.getpid(),'created':psutil.Process().create_time(),'command':sys.argv}
        s.write(work/f'host-{phase}.json',host);s.base.atomic_json(work/'host.json',host)
        for stage in plan:
            out=work/'cases'/stage['key']
            if (out/'result.json').exists():
                q=s.read(out/'result.json');assert h.get(out/'final.rstate.gz').digest==q['final_sha256'];results.append(q);continue
            if (work/'STOP').exists():return
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>=2**30:
                s.write(work/'STOP',{'reason':'registered original cap'});return
            out.mkdir(parents=True,exist_ok=False);s.write(work/'in-flight.json',host|{'key':stage['key']})
            parent=h.get(work/'cases'/stage['parent']/'final.rstate.gz') if stage.get('parent') else None
            if parent:e=engine(state=parent)
            else:e=engine({'seed':stage['seed']}|stage['case']['initial_config']|stage['patch'])
            # Existing diagnostic material may declare a case-specific patch.
            patch=stage['case'].get('patch',{})
            before=e.capture_state();h.put(out/'before-intervention.rstate.gz',before)
            if patch:
                from dataclasses import replace
                e.reconfigure(replace(e.config,**patch))
            initial=e.capture_state();h.put(out/'initial.rstate.gz',initial)
            rows=inputs(work,stage['case'],stage['mask']);s.packed(out/'inputs.json.gz',rows)
            recorder.s.TARGETS={v^stage['mask'] for v in s.measure.TOKENS.values()}
            t=time.monotonic();e,points,n=recorder.drive(e,stage['case'],rows,out)
            final=e.capture_state();h.put(out/'final.rstate.gz',final)
            assert h.get(out/'final.rstate.gz').digest==final.digest
            if points:s.packed(out/'process.json.gz',points)
            result={'key':stage['key'],'group':stage['group'],'variant':stage['variant'],'block':stage['block'],
                    'cue':stage['cue'],'patch':patch,'parent_sha256':parent.digest if parent else None,
                    'before_sha256':before.digest,'initial_sha256':initial.digest,'final_sha256':final.digest,
                    'time_us':e.time_us,'life':e.life,'injected':n,'scheduled':len(rows),
                    'wall_seconds':time.monotonic()-t,'process':measure(stage['case'],points,stage['mask']) if points else None}
            s.write(out/'result.json',result);results.append(result);(work/'in-flight.json').unlink()
            s.base.atomic_json(work/'current.json',{'phase':phase,'complete':len(results),'total':len(plan),'last':stage['key']})
            print(json.dumps({'complete':len(results),'total':len(plan),'key':stage['key'],
                              'seconds':round(result['wall_seconds'],2),'process':result['process']}),flush=True)
            del e,points,rows;gc.collect()
        s.write(work/f'phase-{phase}-summary.json',{'stages':len(results),'wall_seconds':time.monotonic()-started})
    shutil.copyfile(work/'resource-summary.json',work/f'phase-{phase}-resources.json')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','apparatus','register','check','run'))
    p.add_argument('--work',type=Path,required=True);p.add_argument('--phase',default='A');a=p.parse_args()
    run(a.work,a.phase) if a.action=='run' else globals()[a.action](a.work)
