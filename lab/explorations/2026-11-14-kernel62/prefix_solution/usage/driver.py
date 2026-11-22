"""Bounded additional comparisons of inhibitory usage records; own identity."""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
from uuid import uuid5

HERE=Path(__file__).resolve().parent;PARENT=HERE.parent
spec=importlib.util.spec_from_file_location('r51t11_usage_followup',PARENT/'followup.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
t=f.t;s=t.s
u=t.module('r51t11_usage_research',PARENT/'usage_research.py')
previous=t.engine

def engine(config=None,state=None,backend='reference'):
    if state is not None and state.to_dict()['dynamics']==u.KERNEL_ID:return u.ResearchEngine(state=state)
    if config is not None and 'research_inhibition_marks_usage' in config:return u.ResearchEngine(u.ResearchConfig(**config))
    return previous(config=config,state=state,backend=backend)

t.engine=engine


def check(work):
    for rel,sha in s.read(work/'usage-extension-frozen.json')['sources'].items():assert s.sha(t.ROOT/rel)==sha,rel


def prepare(work):
    assert (work/'phase-D-summary.json').exists() and (work/'audit.json').exists()
    assert s.read(work/'audit.json')['passed']
    assert not any((work/n).exists() for n in ('in-flight.json','STOP','usage-extension-frozen.json'))
    assert s.read(work/'phase-A-summary.json')['stages']==96
    groups=[];plan=[]
    for name,reference in (('current-path','n0r0l1g0'),('normalized-path','n1r1l1g1')):
        patch=t.variants()[reference]|{'research_inhibition_marks_usage':False}
        stages=f.prefix_stages(work,'E',name,patch);plan.extend(stages)
        groups.append({'name':name,'reference_A':reference,'patch':patch,'stages':[q['key'] for q in stages]})
    base=deepcopy(plan[0]['case']);base['end_us']=6000000
    rows=t.inputs(work,base,0x20000000,base['end_us']);checks=[]
    old_targets=t.recorder.s.TARGETS;t.recorder.s.TARGETS={v^0x20000000 for v in s.measure.TOKENS.values()}
    t.recorder.s.engine=engine
    with s.base.worker_lock(work),t.pre.Guard(work):
        for g in groups:
            cfg={'seed':9291299}|base['initial_config']|g['patch']|{'research_inhibition_marks_usage':True}
            a=engine(cfg);b=previous(config={k:v for k,v in cfg.items() if k!='research_inhibition_marks_usage'})
            a,_,_=t.recorder.drive(a,base,deepcopy(rows),mode='plain')
            b,_,_=t.recorder.drive(b,base,deepcopy(rows),mode='plain')
            def norm(image):
                d=deepcopy(image.to_dict())
                for k in ('schema','dynamics','definition','definition_hash'):d.pop(k,None)
                d['config'].pop('research_inhibition_marks_usage',None);return d
            assert norm(a.capture_state())==norm(b.capture_state())
            for enabled in (False,True):
                hashes={}
                for mode in ('plain','observed','restored','partitioned','paused'):
                    e=engine(cfg|{'research_inhibition_marks_usage':enabled})
                    e,_,_=t.recorder.drive(e,base,deepcopy(rows),mode=mode)
                    hashes[mode]=e.capture_state().digest
                assert len(set(hashes.values()))==1
                checks.append({'group':g['name'],'usage_record':enabled,'hashes':hashes,'reference_equivalent':True})
    t.recorder.s.TARGETS=old_targets
    s.write(work/'usage-apparatus.json',{'passed':True,'checks':checks})
    paths=[Path(__file__),PARENT/'usage_research.py',PARENT/'usage-amendment.zh.md',PARENT/'usage-amendment.en.md']
    sources={p.relative_to(t.ROOT).as_posix():s.sha(p) for p in paths}
    with t.pre.client_context() as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            rec.text({'identity':str(uuid5(t.NS,'usage-protocol-doc-'+lang)),
                'request_id':str(uuid5(t.NS,'usage-protocol-'+lang)),'expected_revision':0,
                'kind':'protocol','title':'R51t11 inhibitory usage extension '+lang,
                'markdown':(PARENT/f'usage-amendment.{lang}.md').read_text('utf8')})
        rec.append('stage','r51t11:usage-sources',{'sources':sources,'apparatus_passed':True},
                   request_id=uuid5(t.NS,'usage-sources'))
        rec.synchronize(strict=True);assert rec.status['pending']==0
    for rel in sources:
        dest=work/'usage-extension-source'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(t.ROOT/rel,dest)
    s.write(work/'usage-extension-frozen.json',{'sources':sources,'pending':0})
    f.freeze(work,'E',plan,{'groups':groups,'matched_A_controls':True,'independent_apparatus':checks})


def plan_validation(work):
    check(work);assert s.read(work/'phase-E-summary.json')['stages']==12
    plan=s.read(work/'phase-E.json');scores=f.scores(work,plan)
    groups=s.read(work/'phase-E-selection.json')['groups']
    chosen=next((g for g in groups if scores[g['name']]['passed']),None)
    s.write(work/'usage-selection.json',{'chosen':chosen,'scores':scores})
    if chosen is None:
        print(json.dumps({'usage_hypothesis_passed':False,'retaining_phase_F_solution':True}),flush=True);return
    patch=chosen['patch'];materials=s.read(work/'materials.json');stages=[]
    for b in (0,1):
        keys={'train':f'retention/s{b}/011/paired/train','wait':f'readout/s{b}/011/paired/d300/wait',
              'probe':f'sustain/s{b}/unchanged'}
        for cue in ('train','wait','probe'):
            case=deepcopy(materials['persistent-activity61-v1/'+keys[cue]])
            # Match the successful prefix subject's complete 101 configuration.
            case['initial_config']={'depletion_enabled':True,'edge_consolidation_enabled':True,'stp_facilitation_tau_s':0.0}
            stages.append({'key':f'G/{chosen["name"]}/{b}/{cue}','group':'persistent',
                'variant':chosen['name'],'block':b,'cue':cue,'case':case,'patch':patch,'mask':0,'seed':9291000,
                'parent':None if cue=='train' else f'G/{chosen["name"]}/{b}/'+('train' if cue=='wait' else 'wait')})
    f.freeze(work,'G',stages,{'selected_E':chosen,'complete_configuration_matches_E':True})
    fresh=[]
    for b,mask,seed in ((0,0x08000000,9291221),(1,0x04000000,9291222)):
        fresh.extend(f.prefix_stages(work,'H',chosen['name'],patch,blocks=(b,),mask=mask,seed=seed))
    f.freeze(work,'H',fresh,{'selected_E':chosen,'fresh_materials':[[0,0x08000000,9291221],[1,0x04000000,9291222]]})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','plan_validation','run'))
    p.add_argument('--work',type=Path,required=True);p.add_argument('--phase');a=p.parse_args()
    if a.action=='run':
        check(a.work)
        for rel,sha in s.read(a.work/f'phase-{a.phase}-frozen.json')['sources'].items():assert s.sha(t.ROOT/rel)==sha,rel
        t.run(a.work,a.phase)
    else:globals()[a.action](a.work)
