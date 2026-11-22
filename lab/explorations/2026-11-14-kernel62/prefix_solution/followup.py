"""Prospectively register bounded follow-up phases; never rewrite frozen runs."""
import argparse
from copy import deepcopy
import importlib.util
import itertools
import json
from pathlib import Path
import shutil
from uuid import uuid5

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r51t11_followup_study',HERE/'study.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
s=t.s
fallback=t.module('r51t11_routing',HERE/'fallback.py')
t.engine=fallback.factory(t.engine)

class TotalBudgetGuard(t.pre.Guard):
    def __init__(self,work):
        super().__init__(work)
        self.prior_seconds=sum(s.read(p)['wall_seconds'] for p in work.glob('phase-*-summary.json'))
        self.started-=self.prior_seconds

    def __exit__(self,*args):
        super().__exit__(*args)
        q=s.read(self.work/'resource-summary.json')
        q.update(prior_phase_seconds=self.prior_seconds,phase_wall_seconds=q['wall_seconds']-self.prior_seconds)
        s.base.atomic_json(self.work/'resource-summary.json',q)

t.pre.Guard=TotalBudgetGuard


def prefix_stages(work,phase,name,patch,blocks=(0,1),mask=0,seed=9291000):
    materials=s.read(work/'materials.json');out=[]
    for block in blocks:
        for cue in ('train','AB','DB'):
            key=f'short/train-{block}' if cue=='train' else f'history/s{block}/101/d1/{cue}'
            out.append({'key':f'{phase}/{name}/{block}/{cue}','group':'prefix','variant':name,
                'block':block,'cue':cue,'case':deepcopy(materials['prefix-resources62-v1/'+key]),
                'patch':patch,'mask':mask,'seed':seed,
                'parent':None if cue=='train' else f'{phase}/{name}/{block}/train'})
            if cue!='train':
                for k in ('depletion_enabled','edge_consolidation_enabled','stp_facilitation_tau_s'):
                    if k in patch:out[-1]['case']['patch'][k]=patch[k]
    return out


def scores(work,stages):
    by={}
    for stage in stages:
        if stage['group']!='prefix' or stage['cue']=='train':continue
        q=s.read(work/'cases'/stage['key']/'result.json')
        metric=q.get('process') or {'complete':False,'margin':0.0}
        by.setdefault(stage['variant'],[]).append({'key':stage['key'],'block':stage['block'],
            'cue':stage['cue'],'passed':metric['complete'] and metric['margin']>1e-6,
            'margin':metric['margin']})
    return {name:{'rows':rows,'passed_blocks':sum(all(x['passed'] for x in rows if x['block']==b)
        for b in (0,1)),'passed':len(rows)==4 and all(x['passed'] for x in rows)} for name,rows in by.items()}


def freeze(work,phase,plan,metadata):
    t.check(work)
    assert not (work/'in-flight.json').exists() and not (work/'STOP').exists()
    assert not (work/f'phase-{phase}.json').exists()
    # The analysis and phase plan are fixed and recorded before any new subject.
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*amendment.*.md'))
    sources={p.relative_to(t.ROOT).as_posix():s.sha(p) for p in paths}
    for rel in sources:
        dst=work/f'phase-{phase}-sources'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(t.ROOT/rel,dst)
    with t.pre.client_context() as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client);rec.resume_recording()
        rec.append('stage','r51t11:phase-'+phase,{'stages':plan,'selection':metadata,'sources':sources},
                   request_id=uuid5(t.NS,'phase-'+phase))
        rec.synchronize(strict=True);assert rec.status['pending']==0
    s.write(work/f'phase-{phase}.json',plan)
    s.write(work/f'phase-{phase}-selection.json',metadata)
    s.write(work/f'phase-{phase}-frozen.json',{'sha256':s.sha(work/f'phase-{phase}.json'),
                                           'sources':sources,'pending':0})
    choice=metadata.get('selected_A') or metadata.get('selected_B',{}).get('name') or metadata.get('selected',{}).get('name')
    print(json.dumps({'phase':phase,'stages':len(plan),'selected':choice,
                      'same_configuration_both':metadata.get('same_configuration_both')},ensure_ascii=False),flush=True)


def phase_b(work):
    assert s.read(work/'phase-A-summary.json')['stages']==96
    a=s.read(work/'phase-A.json');sc=scores(work,a)
    winners=[n for n,v in sc.items() if v['passed']]
    if not winners:
        print(json.dumps({'phase_A_all_negative':True,'fallback_required':True}));return
    def rank(n):
        bits=[int(n[x]) for x in (1,3,5,7)]
        return (sum(bits),bits[1],bits[2],bits[3],n)
    winner=min(winners,key=rank);patch=t.variants()[winner]
    groups=[];plan=[]
    for stable,immediate,high in itertools.product((0,1),repeat=3):
        name=f's{stable}i{immediate}h{high}'
        p=patch|{'consolidation_mode':'stability' if stable else 'adaptive-half-life',
                 'novelty_mode':'immediate' if immediate else 'arrival-window',
                 'activation_signal_threshold':.004 if high else .0004}
        stages=([x for x in a if x['variant']==winner] if (stable,immediate,high)==(1,1,1)
                else prefix_stages(work,'B',name,p))
        groups.append({'name':name,'patch':p,'new':(stable,immediate,high)!=(1,1,1),
                       'changes':stable+immediate+high,'stages':[x['key'] for x in stages]})
        if (stable,immediate,high)!=(1,1,1):plan.extend(stages)
    assert len(plan)==42
    freeze(work,'B',plan,{'selected_A':winner,'A_results':sc,'groups':groups})


def choose_b(work):
    assert s.read(work/'phase-B-summary.json')['stages']==42
    plans={x['key']:x for ph in ('A','B') for x in s.read(work/f'phase-{ph}.json')}
    meta=s.read(work/'phase-B-selection.json');rows=[]
    for g in meta['groups']:
        stages=[plans[k] for k in g['stages']]
        result=next(iter(scores(work,stages).values()))
        rows.append(g|{'result':result})
    winner=min((x for x in rows if x['result']['passed']),key=lambda x:(x['changes'],x['name']))
    return winner,rows,plans


def phase_f(work):
    assert s.read(work/'phase-A-summary.json')['stages']==96
    assert not any(v['passed'] for v in scores(work,s.read(work/'phase-A.json')).values())
    groups=[];plan=[]
    for route,weight in itertools.product(('incident','outgoing'),('base','effective')):
        name=route+'-'+weight
        patch={'research_transport':'old-inhibition','resource_precheck':True,
            'research_inhibitory_route':route,'research_inhibitory_weight':weight,
            'consolidation_mode':'stability','novelty_mode':'immediate','activation_signal_threshold':.004,
            'resource_precheck_enabled':True,'subthreshold_expiry_enabled':True}
        stages=prefix_stages(work,'F',name,patch);plan.extend(stages)
        groups.append({'name':name,'patch':patch,'stages':[x['key'] for x in stages],
                       'changes':int(route=='incident')+int(weight=='base')})
    # Independent six-second apparatus, not scientific teaching material.
    base=deepcopy(plan[0]['case']);base['end_us']=6000000
    rows=t.inputs(work,base,0x20000000,base['end_us']);checks=[]
    old_targets=t.recorder.s.TARGETS;t.recorder.s.TARGETS={v^0x20000000 for v in s.measure.TOKENS.values()}
    t.recorder.s.engine=t.engine
    with s.base.worker_lock(work),t.pre.Guard(work):
        cfg={'seed':9291199}|base['initial_config']|groups[0]['patch']
        candidate=t.engine(cfg)
        original=t.pre.r.ResearchEngine(t.pre.r.ResearchConfig(**{
            k:v for k,v in cfg.items() if k not in ('research_inhibitory_route','research_inhibitory_weight')}))
        a,_,_=t.recorder.drive(candidate,base,deepcopy(rows),mode='plain')
        b,_,_=t.recorder.drive(original,base,deepcopy(rows),mode='plain')
        def ordinary(image):
            d=deepcopy(image.to_dict())
            for k in ('schema','dynamics','definition','definition_hash'):d.pop(k,None)
            for k in ('research_inhibitory_route','research_inhibitory_weight'):d['config'].pop(k,None)
            return d
        assert ordinary(a.capture_state())==ordinary(b.capture_state())
        checks.append({'original_candidate_equivalence':True})
        for g in groups:
            hashes={}
            for mode in ('plain','observed','restored','partitioned','paused'):
                e=t.engine({'seed':9291199}|base['initial_config']|g['patch'])
                e,_,_=t.recorder.drive(e,base,deepcopy(rows),mode=mode)
                hashes[mode]=e.capture_state().digest
            assert len(set(hashes.values()))==1
            checks.append({'name':g['name'],'hashes':hashes})
    t.recorder.s.TARGETS=old_targets
    s.write(work/'fallback-apparatus.json',{'passed':True,'checks':checks})
    freeze(work,'F',plan,{'groups':groups,'reason':'all four-factor combinations failed',
                         'apparatus':checks})


def choose_f(work):
    assert s.read(work/'phase-F-summary.json')['stages']==24
    plans={x['key']:x for ph in ('A','F') for x in s.read(work/f'phase-{ph}.json')}
    rows=[]
    for g in s.read(work/'phase-F-selection.json')['groups']:
        result=next(iter(scores(work,[plans[k] for k in g['stages']]).values()))
        rows.append(g|{'result':result})
    winner=min((x for x in rows if x['result']['passed']),key=lambda x:(x['changes'],x['name']))
    return winner,rows,plans


def phase_c(work):
    winner,rows,plans=choose_b(work) if (work/'phase-B-summary.json').exists() else choose_f(work)
    groups=[];plan=[];materials=s.read(work/'materials.json')
    tau=t.r.production.Local62Config().inhibition_tau
    for resource,short in itertools.product(('101','011'),(False,True)):
        name='resource-'+resource+('-quarter-tau' if short else '-original-tau')
        patch=winner['patch']|{'inhibition_tau':tau/(4 if short else 1),
            'depletion_enabled':resource=='101','stp_facilitation_tau_s':0.0 if resource=='101' else 1.0,
            'edge_consolidation_enabled':True}
        reused=resource=='101' and not short
        prefix=[plans[k] for k in winner['stages']] if reused else prefix_stages(work,'C',name,patch)
        if not reused:plan.extend(prefix)
        persistent=[]
        for b in (0,1):
            keys={'train':f'retention/s{b}/011/paired/train','wait':f'readout/s{b}/011/paired/d300/wait',
                  'probe':f'sustain/s{b}/unchanged'}
            for cue in ('train','wait','probe'):
                key=f'C/{name}/persistent-{b}/{cue}'
                parent=None if cue=='train' else f'C/{name}/persistent-{b}/'+('train' if cue=='wait' else 'wait')
                stage={'key':key,'group':'persistent','variant':name,'block':b,'cue':cue,
                    'case':deepcopy(materials['persistent-activity61-v1/'+keys[cue]]),
                    'patch':patch,'mask':0,'seed':9291000,'parent':parent}
                persistent.append(stage);plan.append(stage)
        groups.append({'name':name,'patch':patch,'prefix':[x['key'] for x in prefix],
                       'persistent':[x['key'] for x in persistent]})
    assert len(plan)==42
    freeze(work,'C',plan,{'selected_B':winner,'B_results':rows,'groups':groups,
                         'tau_set_at_birth':True,'fixed_background_during_wait':True,
                         'complete_configuration_matched':True,
                         'prospective_amendment':(HERE/'shared-config-amendment.zh.md').read_text('utf8')})


def phase_d(work):
    assert s.read(work/'phase-C-summary.json')['stages']==42
    meta=s.read(work/'phase-C-selection.json')
    allplans={x['key']:x for ph in ('A','B','C','F') if (work/f'phase-{ph}.json').exists()
              for x in s.read(work/f'phase-{ph}.json')}
    groups=[]
    for g in meta['groups']:
        prefix=next(iter(scores(work,[allplans[k] for k in g['prefix']]).values()))
        active=[s.read(work/'cases'/k/'result.json')['process'] or {'continuous':False,'samples':0}
                for k in g['persistent'] if k.endswith('/probe')]
        groups.append(g|{'prefix_pass':prefix['passed'],'persistence_pass':all(x['continuous'] for x in active),
                         'activity':active,'prefix_result':prefix})
    common=[g for g in groups if g['prefix_pass'] and g['persistence_pass']]
    chosen=(common or [g for g in groups if g['prefix_pass']])[0]
    plan=[]
    for b,mask,seed in ((0,0x10000000,9291201),(1,0x40000000,9291202)):
        plan.extend(prefix_stages(work,'D','fresh-codes',chosen['patch'],blocks=(b,),mask=mask,seed=seed))
    freeze(work,'D',plan,{'selected':chosen,'same_configuration_both':bool(common),'groups':groups,
                         'fresh_materials':[[0,0x10000000,9291201],[1,0x40000000,9291202]]})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('phase_b','phase_c','phase_d','phase_f','run'))
    p.add_argument('--work',type=Path,required=True);p.add_argument('--phase');a=p.parse_args()
    if a.action=='run':
        for rel,sha in s.read(a.work/f'phase-{a.phase}-frozen.json')['sources'].items():assert s.sha(t.ROOT/rel)==sha,rel
        t.run(a.work,a.phase)
    else:globals()[a.action](a.work)
