"""R51t15: reconstruct the historical positive condition on 6.3 and isolate its causes."""
import argparse
from copy import deepcopy
import gc
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
spec = importlib.util.spec_from_file_location('r51t15_material_helpers', HERE.parent.parent / '2026-11-14-kernel62/prefix_solution/study.py')
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
s, h, recorder, pre = t.s, t.h, t.recorder, t.pre
from threemind_kernels.local63 import KERNEL_ID, Local63Config
from threemind_kernels.registry import resolve_kernel

NS = UUID('7772a8fa-cc77-52ac-a9dd-be76887ede8b')
OLD = t.DATA / 'prefix-solution62-v1'
spec_r=importlib.util.spec_from_file_location('r51t15_research',HERE/'research.py')
r=importlib.util.module_from_spec(spec_r);sys.modules[spec_r.name]=r;spec_r.loader.exec_module(r)

def engine(config=None,state=None,backend='reference'):
    return r.ResearchEngine(state=state) if state is not None else r.ResearchEngine(r.ResearchConfig(**config))

def patch(profile,name):
    base={'inhibition_distribution':'weight-proportional','inhibition_updates_usage':False,
        'consolidation_mode':'stability','novelty_mode':'immediate',
        'activation_signal_threshold':.004,'inhibition_signal_threshold':.0004,
        'resource_precheck_enabled':True,'subthreshold_expiry_enabled':True,'depletion_enabled':True,
        'edge_consolidation_enabled':True,'stp_facilitation_tau_s':0.0,
        'activation_weight_reinforcement_enabled':True,'inhibition_weight_reinforcement_enabled':True,
        'research_legacy_emission':False,'research_learning_component':'full'}
    if name in ('legacy-positive','usage-on') or name.startswith('component-'):
        base.update(research_bypass_inhibition_resources=True,separate_inhibition_resources=False,
            inhibitory_learning_enabled=False,inhibition_signal_threshold=0.0)
        if name=='legacy-positive':base['research_legacy_emission']=True
        if name=='usage-on':base['inhibition_updates_usage']=True
        if name.startswith('component-'):
            base.update(inhibitory_learning_enabled=True,research_learning_component=name.removeprefix('component-'))
        return base
    resource,learning,gate=name.split('-')
    return base|{'separate_inhibition_resources':resource=='independent',
        'research_bypass_inhibition_resources':resource=='bypass',
        'inhibitory_learning_enabled':learning=='l1',
        'inhibition_signal_threshold':.0004 if gate=='g1' else 0.0}

GROUPS=[f'{resource}-l{learning}-g{gate}' for resource in ('shared','independent','bypass')
        for learning in (0,1) for gate in (0,1)]
PHASE_A=('legacy-positive','bypass-l0-g0','usage-on')
COMPONENTS=('weight','fast','eligibility','stability','retention','touch')


def measure(case,points,mask):
    result=t.measure(case,points,mask)
    if case.get('cue') not in ('AB','DB'): result.pop('margin',None)
    return result

def stages(cases, phase, profile, name, fresh=False):
    rows = []
    for block in (0, 1):
        parent = f'{phase}/{profile}/{name}/{block}/train'
        for cue in ('train', 'AB', 'DB'):
            key = f'short/train-{block}' if cue == 'train' else f'history/s{block}/101/d1/{cue}'
            case = deepcopy(cases['prefix-resources62-v1/' + key])
            rows.append({'key': f'{phase}/{profile}/{name}/{block}/{cue}', 'group': 'prefix',
                         'profile': profile, 'variant': name, 'block': block, 'cue': cue,
                         'case': case, 'patch': patch(profile, name),
                         'mask': (0x00400000 if block == 0 else 0x00200000) if fresh else 0,
                         'seed': 9291271 + block if fresh else 9291000,
                         'parent': None if cue == 'train' else parent})
    return rows


def prepare(work):
    assert not work.exists()
    assert s.read(OLD / 'publication/completion.json')['pending'] == 0
    assert s.base.resource_check(OLD)['safe'] and shutil.disk_usage(OLD).free > 27 * 2**30
    work.mkdir()
    shutil.copytree(OLD / 'materials', work / 'materials')
    shutil.copyfile(OLD / 'materials.json', work / 'materials.json')
    shutil.copyfile(OLD / 'publication/completion.json', work / 'prior-delivery.json')
    refs = {p.relative_to(work).as_posix(): s.sha(p) for p in (work / 'materials').rglob('*') if p.is_file()}
    s.write(work / 'reference-manifest.json', refs)
    cases = s.read(work / 'materials.json')
    plan = [q for name in PHASE_A for q in stages(cases, 'A', 'S', name)]
    assert len(plan) == 18
    s.write(work / 'phase-A.json', plan)
    s.write(work / 'initial-resources.json', s.base.resource_check(work))
    print(json.dumps({'prepared': str(work), 'stages': len(plan)}), flush=True)


def normalized(image):
    d=deepcopy(image.to_dict())
    for k in ('schema','dynamics','definition','definition_hash','config'):d.pop(k,None)
    return d

def apparatus(work):
    assert not (work/'apparatus.json').exists()
    plan=s.read(work/'phase-A.json');recorder.s.engine=engine
    recorder.s.TARGETS={x^0x10000000 for x in s.measure.TOKENS.values()}
    conditions=list(PHASE_A)+GROUPS+[f'component-{x}' for x in ('none',)+COMPONENTS]
    checks=[]
    with s.base.worker_lock(work),pre.Guard(work):
        for name in dict.fromkeys(conditions):
            case=deepcopy(plan[0]['case']);case['end_us']=6000000
            inputs=t.inputs(work,case,0x10000000,case['end_us'])
            cfg={'seed':9291269}|case['initial_config']|patch('S',name)
            hashes={}
            for mode in ('plain','observed','restored','partitioned','paused'):
                e=engine(cfg);e,_,_=recorder.drive(e,case,deepcopy(inputs),mode=mode)
                hashes[mode]=e.capture_state().digest
            assert len(set(hashes.values()))==1,name
            checks.append({'variant':name,'same_complete_state':True,'hashes':hashes})
            if name in ('shared-l1-g1','independent-l1-g1'):
                cfg0={k:v for k,v in cfg.items() if not k.startswith('research_')}
                plain=resolve_kernel(KERNEL_ID).create(Local63Config(**cfg0),backend='reference')
                plain,_,_=recorder.drive(plain,case,deepcopy(inputs),mode='plain')
                assert normalized(plain.capture_state())==normalized(e.capture_state())
            if name=='component-none':
                baseline=engine({'seed':9291269}|case['initial_config']|patch('S','bypass-l0-g0'))
                baseline,_,_=recorder.drive(baseline,case,deepcopy(inputs),mode='plain')
                assert normalized(baseline.capture_state())==normalized(e.capture_state())
    s.write(work/'apparatus.json',{'passed':True,'checks':checks,'production_matched':True,'component_none_matched':True})
    shutil.copyfile(work/'resource-summary.json',work/'apparatus-resources.json')
    print(json.dumps({'apparatus_passed':True,'conditions':len(checks)}),flush=True)


def register(work):
    assert s.read(work / 'apparatus.json')['passed'] and not (work / 'frozen.json').exists()
    import _threemind_native
    paths = list((ROOT / 'src').rglob('*.py')) + list((ROOT / 'crates').rglob('*.rs'))
    paths += list((ROOT / 'crates/threemind-core/src').glob('*defaults.json'))
    paths += list(HERE.glob('*.py')) + list(HERE.glob('protocol.*.md'))
    paths += [Path(m.__file__) for m in tuple(sys.modules.values()) if getattr(m, '__file__', None)
              and str(m.__file__).endswith('.py') and Path(m.__file__).is_relative_to(ROOT / 'lab')]
    sources = {p.relative_to(ROOT).as_posix(): s.sha(p) for p in paths}
    for rel in sources:
        out = work / 'frozen-source' / rel; out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, out)
    with pre.client_context() as client:
        rec = s.base.ResearchRecorder(work, s.PROJECT, client=client)
        rec.register({'source_key': 'r51t15:prefix-causes63:20261115:v1',
            'title': 'R51t15：6.3前缀恢复组合及具体作用定位', 'classification': 'formal',
            'execution_status': 'running', 'executor': 'ai', 'kernels': [KERNEL_ID],
            'protocol': (HERE / 'protocol.zh.md').read_text('utf8'), 'protocol_version': s.sha(HERE / 'protocol.zh.md'),
            'required_roles': ['protocol', 'report', 'note', 'original'],
            'metadata': {'material_blocks': 2, 'stage_cap': 132, 'phase_a_stages': 18,
                         'isolated_research_kernel':r.KERNEL_ID,'defaults_unchanged':True}}, request_id=uuid5(NS, 'register'))
        for lang in ('zh', 'en'):
            rec.text({'identity': str(uuid5(NS, 'protocol-doc-' + lang)), 'request_id': str(uuid5(NS, 'protocol-' + lang)),
                      'expected_revision': 0, 'kind': 'protocol', 'title': 'R51t15 protocol ' + lang,
                      'markdown': (HERE / f'protocol.{lang}.md').read_text('utf8')})
        rec.append('stage', 'r51t15:phase-a', {'stages': s.read(work / 'phase-A.json')}, request_id=uuid5(NS, 'phase-a'))
        rec.synchronize(strict=True); assert rec.status['pending'] == 0
        s.write(work / 'registration.json', {'project': s.PROJECT, 'record': rec.experiment, 'pending': 0})
    s.write(work / 'frozen.json', {'sources': sources, 'native_sha256': s.sha(Path(_threemind_native._threemind_native.__file__)),
                                  'plan_sha256': s.sha(work / 'phase-A.json'),
                                  'references_sha256': s.sha(work / 'reference-manifest.json')})
    print(json.dumps(s.read(work / 'registration.json')), flush=True)


def check(work):
    import _threemind_native
    f = s.read(work / 'frozen.json')
    assert s.sha(Path(_threemind_native._threemind_native.__file__)) == f['native_sha256']
    for rel, sha in f['sources'].items():
        assert s.sha(ROOT / rel) == sha, rel
    assert s.sha(work / 'phase-A.json') == f['plan_sha256']
    assert s.sha(work / 'reference-manifest.json') == f['references_sha256']
    for rel, sha in s.read(work / 'reference-manifest.json').items():
        assert s.sha(work / rel) == sha, rel


def run(work, phase):
    import psutil
    check(work)
    plan = s.read(work / f'phase-{phase}.json')
    if phase != 'A':
        assert s.sha(work / f'phase-{phase}.json') == s.read(work / f'phase-{phase}-frozen.json')['sha256']
    assert not any((work / n).exists() for n in ('STOP', 'in-flight.json', f'phase-{phase}-summary.json'))
    started = time.monotonic()-sum(s.read(p)['wall_seconds'] for p in work.glob('phase-*-summary.json')); results = []; recorder.ACTIVE_WORK = work; recorder.s.engine = engine
    phase_started=time.monotonic()
    with s.base.worker_lock(work), pre.Guard(work) as guard:
        host = {'pid': os.getpid(), 'created': psutil.Process().create_time(), 'command': sys.argv}
        s.write(work / f'host-{phase}.json', host); s.base.atomic_json(work / 'host.json', host)
        for stage in plan:
            out = work / 'cases' / stage['key']
            if (out / 'result.json').exists():
                q = s.read(out / 'result.json'); assert h.get(out / 'final.rstate.gz').digest == q['final_sha256']
                results.append(q); continue
            if (work / 'STOP').exists(): return
            if time.monotonic()-started > 7200:
                s.write(work / 'STOP', {'reason':'registered two-hour host cap'}); return
            assert guard.thread.is_alive() and s.base.resource_check(work)['safe']
            if sum(p.stat().st_size for p in work.rglob('*') if p.is_file()) > 512 * 2**20:
                s.write(work / 'STOP', {'reason': 'registered originals cap'}); return
            out.mkdir(parents=True, exist_ok=False); s.write(work / 'in-flight.json', host | {'key': stage['key']})
            parent = h.get(work / 'cases' / stage['parent'] / 'final.rstate.gz') if stage['parent'] else None
            e = engine(state=parent) if parent else engine({'seed': stage['seed']} | stage['case']['initial_config'] | stage['patch'])
            initial = e.capture_state(); h.put(out / 'initial.rstate.gz', initial)
            # Historical resource fields already match the declared complete configuration.
            assert all(getattr(e.config, k) == v for k, v in stage['patch'].items())
            inputs = t.inputs(work, stage['case'], stage['mask']); s.packed(out / 'inputs.json.gz', inputs)
            recorder.s.TARGETS = {v ^ stage['mask'] for v in s.measure.TOKENS.values()}
            wall, cpu = time.perf_counter(), time.process_time()
            e, points, injected = recorder.drive(e, stage['case'], inputs, out)
            elapsed, cpu_elapsed = time.perf_counter() - wall, time.process_time() - cpu
            final = e.capture_state(); h.put(out / 'final.rstate.gz', final)
            assert h.get(out / 'final.rstate.gz').digest == final.digest
            if points: s.packed(out / 'process.json.gz', points)
            result = {k: stage[k] for k in ('key', 'group', 'profile', 'variant', 'block', 'cue')}
            result.update(parent_sha256=parent.digest if parent else None, initial_sha256=initial.digest,
                final_sha256=final.digest, time_us=e.time_us, life=e.life, injected=injected, scheduled=len(inputs),
                wall_seconds=elapsed, cpu_seconds=cpu_elapsed, snapshot_bytes=len(final.payload),
                process=measure(stage['case'], points, stage['mask']) if points else None)
            s.write(out / 'result.json', result); results.append(result); (work / 'in-flight.json').unlink()
            s.base.atomic_json(work / 'current.json', {'phase': phase, 'complete': len(results), 'total': len(plan), 'last': stage['key']})
            print(json.dumps({'complete': len(results), 'total': len(plan), 'key': stage['key'],
                              'seconds': round(elapsed, 2), 'process': result['process']}), flush=True)
            del e, points, inputs; gc.collect()
            if elapsed > 300:
                s.write(work / 'STOP', {'reason':'registered per-stage time cap','completed':stage['key']});return
        s.write(work / f'phase-{phase}-summary.json', {'stages': len(results), 'wall_seconds': time.monotonic() - phase_started})
    shutil.copyfile(work / 'resource-summary.json', work / f'phase-{phase}-resources.json')


def scores(work):
    groups={}
    for p in sorted(work.glob('phase-*.json')):
        if p.name.count('-')!=1:continue
        for stage in s.read(p):
            if stage.get('validation'):continue
            if stage['cue']=='train':continue
            out=work/'cases'/stage['key']/'result.json'
            if not out.exists():continue
            q=s.read(out);m=q['process']
            groups.setdefault(stage['variant'],[]).append({'key':stage['key'],'block':stage['block'],
                'cue':stage['cue'],'margin':m['margin'],'passed':m['complete'] and m['margin']>1e-6})
    return {k:{'rows':v,'passed':len(v)==4 and all(x['passed'] for x in v),
               'passed_blocks':sum(all(x['passed'] for x in v if x['block']==b) for b in (0,1))}
            for k,v in groups.items()}

def freeze(work,phase,plan,decision):
    check(work);assert not (work/f'phase-{phase}.json').exists()
    with pre.client_context() as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client);rec.resume_recording()
        rec.append('stage','r51t15:phase-'+phase,{'decision':decision,'stages':plan},request_id=uuid5(NS,'phase-'+phase))
        rec.synchronize(strict=True);assert rec.status['pending']==0
    s.write(work/f'phase-{phase}.json',plan)
    s.write(work/f'phase-{phase}-frozen.json',{'sha256':s.sha(work/f'phase-{phase}.json'),'decision':decision})

def select(work):
    check(work);cases=s.read(work/'materials.json');sc=scores(work)
    if not (work/'phase-B.json').exists():
        assert s.read(work/'phase-A-summary.json')['stages']==18
        spec_h=importlib.util.spec_from_file_location('r51t15_historical',HERE/'historical.py')
        hist=importlib.util.module_from_spec(spec_h);spec_h.loader.exec_module(hist)
        s.write(work/'historical-comparison.json',hist.verify(work))
        if not sc['legacy-positive']['passed'] or not sc['bypass-l0-g0']['passed']:
            s.write(work/'positive-control-failed.json',sc)
            raise RuntimeError('Positive reconstruction failed; preserve all states before further diagnosis')
        plan=[q for name in GROUPS if name!='bypass-l0-g0' for q in stages(cases,'B','S',name)]
        freeze(work,'B',plan,{'positive_controls':sc,'factorial_remaining':66});return
    assert s.read(work/'phase-B-summary.json')['stages']==66
    if not (work/'selection.json').exists():
        winners=[n for n in GROUPS if sc[n]['passed']]
        # Prefer retaining inhibitory learning, then avoiding resource bypass.
        def rank(n):
            resource,l,g=n.split('-')
            return (l=='l0',resource=='bypass',g=='g0',('shared','independent','bypass').index(resource),n)
        chosen=min(winners,key=rank)
        differing=[]
        for name in GROUPS:
            if sc[name]['passed']:continue
            left,right=chosen.split('-'),name.split('-')
            if sum(a!=b for a,b in zip(left,right))==1:
                index=next(i for i,(a,b) in enumerate(zip(left,right)) if a!=b)
                differing.append(({1:0,0:1,2:2}[index],name))
        control=min(differing)[1] if differing else 'usage-on'
        component_test=sc['bypass-l0-g0']['passed'] and not sc['bypass-l1-g0']['passed']
        choice={'chosen':chosen,'matched_failure':control,'component_test':component_test,'scores':sc}
        s.write(work/'selection.json',choice)
        if component_test:
            plan=[q for name in COMPONENTS for q in stages(cases,'C','S','component-'+name)]
            freeze(work,'C',plan,{'test':'restore one inhibitory learning component at a time','baseline':'bypass-l0-g0'})
        plan=[q for name in (chosen,control) for q in stages(cases,'D','S',name,True)]
        # Keep new-encoding groups distinct from the exploratory two-block scores.
        for q in plan:q['validation']=True
        freeze(work,'D',plan,choice)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','apparatus','register','check','run','select'))
    p.add_argument('--work',type=Path,required=True);p.add_argument('--phase',default='A');a=p.parse_args()
    run(a.work,a.phase) if a.action=='run' else globals()[a.action](a.work)
