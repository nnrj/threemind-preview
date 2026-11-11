"""Bounded preregistered closure execution using the existing research API."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid5

import closure_rig as g
import pilot_m2 as m

HERE = Path(__file__).resolve().parent
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/closure-v1')
NS = UUID('c12ca0bc-dbe9-4a39-b69d-fab5736fcfb7')
ARMS = ('intact', 'sham', 'target-bundle', 'matched-bundle', 'persistent', 'fast', 'restored')
CUES = ('X', 'Y', 'XY', 'Z', 'W', 'ZW')


def save(folder, name, rig):
    p = folder/(name+'.json.gz')
    receipt = m.original(p, rig.save(), compressed=True)
    return {'path': p.name, 'time_us': rig.time, **receipt}


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered')
        title = '2026-10-16 机制发现 · 明确结项追加验证 X1–X3'
        found = [p for p in client.call('projects.list', {}) if p['name'] == title]
        if len(found) > 1: raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': title})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-closure-v1-20261016'}
        m.original(work/'platform.json', platform)
        paths = [Path(__file__), HERE/'closure_rig.py', HERE/'closure_analyze.py', HERE/'closure_protocol.zh.md',
                 HERE/'closure_protocol.en.md', HERE/'pilot_m2.py', HERE/'pilot_m3.py', HERE/'pilot_m1.py',
                 m.ROOT/'lab/tools/study_lock.py',
                 m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        for p in paths: m.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:closure-v1:20261016', 'title': title,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (HERE/'closure_protocol.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol','report','note'],
                    'metadata': {'work': str(work), 'X1_origins': 8, 'X2_origins': 32, 'X3_origins': 8,
                                 'Core_changed': False, 'E69_resumed': False}}, request_id=uuid5(NS,'register'))
        r.synchronize(strict=True)
        client.request('POST','/api/v2/storage/resources',body={'resource_id':platform['resource_id'],
            'target_id':'managed-research-experiments','relative_path':'2026-10-16-mechanism-discovery/closure-v1',
            'registered_work_path':str(work),'writer_mode':'cooperative','expected_revision':0},
            headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'resource'))})
        client.request('POST','/api/v2/storage/record-evidence-grants',body={'project_id':project['id'],
            'resource_id':platform['resource_id']},headers={'X-ThreeMind-Request-ID':str(uuid5(NS,'grant'))})
        for lang in ('zh','en'):
            r.text({'request_id':str(uuid5(NS,'protocol:'+lang)),'identity':str(uuid5(NS,'doc:'+lang)),
                    'expected_revision':0,'kind':'protocol','title':'Goal closure v1 '+lang,
                    'markdown':(HERE/f'closure_protocol.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(m.encoded(platform | {'record':r.experiment,'status':r.status}).decode(),flush=True)


def x1(folder, origin):
    seed = g.case_seed('X1',origin)
    parents, matches = {}, {}
    for history in (0,1):
        p = g.Rig('threemind',seed)
        records = g.teaching(p,history,(.36,.40,.44,.48)[origin//2])
        save(folder,f'parent-h{history}-before-settlement',p)
        g.settle(p)
        save(folder,f'parent-h{history}',p)
        parents[history] = p
        matches[history] = g.matching(p,records)
        m.original(folder/f'teaching-observation-h{history}.json',records)
    m.original(folder/'matching.json',matches)
    if not all(v['passed'] for v in matches.values()):
        return {'package':'X1','origin':origin,'valid':False,'matching':matches,'trials':[]}
    trials = []
    for history in (0,1):
        parent, donor = parents[history], parents[1-history]
        for arm in ARMS:
            if arm == 'intact': child, receipt = parent.fork(arm), {'arm':arm}
            elif arm == 'sham': child,receipt = g.transfer(parent,parent)
            elif arm == 'matched-bundle': child,receipt = g.transfer(parent,donor,'ZW')
            else:
                child,receipt = g.transfer(parent,donor,mode=arm if arm in ('persistent','fast') else 'bundle')
                if arm == 'restored': child,_ = g.transfer(child,parent)
            initial = child.save()
            comparable = copy.deepcopy(initial); comparable['branch'] = parent.branch
            if arm in ('intact','sham','restored') and comparable != parent.save():
                raise RuntimeError('sham/reversal differs from intact whole state')
            m.original(folder/f'h{history}-{arm}-intervention.json',receipt)
            save(folder,f'h{history}-{arm}-initial',child)
            for cue in CUES:
                c = child.fork(cue)
                result = g.probe(c,cue,gate=True)
                checkpoint = save(folder,f'h{history}-{arm}-{cue}-final',c)
                goal = (-1 if history == 0 else 1) # donor X and recipient Z have the same output sign
                trials.append({'history':history,'arm':arm,'cue':cue,'goal':goal,
                               'success': result['choice'] == goal,'result':result,'checkpoint':checkpoint})
    return {'package':'X1','origin':origin,'valid':True,'matching':matches,'trials':trials}


def relearn(rig, history):
    rows=[]; run=0; criterion=17
    for lesson in range(1,17):
        start=rig.time
        # Keep real experience: all lessons and all intervening probes remain in this life.
        rig.tick(start,dict.fromkeys('XYA' if history==0 else 'XYB',.4))
        rig.advance(start+2_000_000,{start+j*500_000:{'K':.2} for j in range(1,5)})
        result=g.probe(rig,'X',.8)
        correct=(1 if history==0 else -1)*result['first']>1e-4
        run=run+1 if correct else 0
        rows.append({'lesson':lesson,'correct':correct,'result':result})
        if run>=2:
            criterion=lesson
            break
    return {'rounds':criterion,'censored':criterion==17,'lessons':rows}


def x2(folder, origin, delay):
    seed=g.case_seed('X2',origin,delay)
    histories=[]
    for history in (0,1):
        p=g.Rig('threemind',seed,'S'); g.teaching(p,history,delay=delay)
        save(folder,f'h{history}-parent',p)
        graph=p.model.graph(); nodes={n['channel']:n['id'] for n in graph['nodes']}
        associated='A' if history==0 else 'B'
        edges=[e for e in graph['edges'] if e['source'] in {nodes.get(p.channels[s]) for s in 'XY'}
               and e['target']==nodes.get(p.channels[associated])]
        tests={}
        for name,cue,dose in (('none','',0),('weak','X',.4),('strong','X',.8),('joint','XY',.8)):
            child=p.fork(name); result=g.probe(child,cue,dose)
            tests[name]=result | {'checkpoint':save(folder,f'h{history}-{name}-final',child)}
        learned=p.fork('relearning'); learn_result=relearn(learned,history)
        save(folder,f'h{history}-relearning-final',learned)
        naive=g.Rig('threemind',seed,'S'); g.teaching(naive,history,delay=delay,trained=False)
        save(folder,f'h{history}-age-matched-untrained',naive)
        naive_result=relearn(naive,history); save(folder,f'h{history}-naive-relearning-final',naive)
        histories.append({'history':history,'target_edges':edges,'tests':tests,
                          'relearning':learn_result,'untrained':naive_result})
    return {'package':'X2','origin':origin,'delay':delay,'valid':True,'histories':histories}


def x3(folder, origin, kind):
    seed=g.case_seed('X3',origin)
    history_tests=[]
    for history in (0,1):
        p=g.Rig(kind,seed); records=g.teaching(p,history)
        save(folder,f'h{history}-parent',p)
        selection=g.rnn_selection(p,records) if kind=='fixed-rnn-reader' else None
        m.original(folder/f'h{history}-selection.json',selection or {'kind':kind,'defined_by':'declared XY/ZW interfaces'})
        cells={}
        for arm in ('intact','sham','target','matched','restored','all'):
            c,receipt=g.intervene(p,arm,selection)
            m.original(folder/f'h{history}-{arm}-intervention.json',receipt)
            save(folder,f'h{history}-{arm}-initial',c)
            for cue in ('X',''):
                child=c.fork(cue or 'none')
                result=g.probe(child,cue)
                save(folder,f'h{history}-{arm}-{cue or "none"}-final',child)
                cells[arm+'-'+(cue or 'none')]=result
        temporal={}
        for arm in ('intact','all'):
            for first,second in (('',''),('X',''),('','Y'),('X','Y')):
                c,_=g.intervene(p,arm,selection)
                result=g.probe(c,first,second=second)
                name=arm+'-'+(first or '0')+(second or '0')
                temporal[name]=result
                save(folder,f'h{history}-temporal-{name}',c)
        history_tests.append({'history':history,'selection':selection,'cells':cells,'temporal':temporal})
    # Distinct continuous closed-loop lives. No diagnostic result is fed back into them.
    worlds={}
    for sequence in ('PPP','PQP','QQQ','QPQ'):
        r=g.Rig(kind,seed); r.tick(0,{'K':.2})
        save(folder,sequence+'-birth',r)
        stages=[]
        for index,env in enumerate(sequence):
            start=r.save()
            stage=g.ring_stage(r,env)
            save(folder,f'{sequence}-stage{index+1}',r)
            diagnostics={}
            for cue in ('X',''):
                c=r.fork('uniform-diagnostic-'+(cue or 'none'))
                c.body={'x':.3125,'v':0.,'gate':0}
                diagnostics[cue or 'none']=g.probe(c,cue)
                save(folder,f'{sequence}-stage{index+1}-diagnostic-{cue or "none"}',c)
            if index==1:
                replay=g.Rig.restore(start); replay_reverse=g.Rig.restore(start); closed_reverse=g.Rig.restore(start)
                replay_report=g.ring_stage(replay,env,replay=stage['input_frames'])
                replay_reverse_report=g.ring_stage(replay_reverse,env,sign=-1,replay=stage['input_frames'])
                reverse_report=g.ring_stage(closed_reverse,env,sign=-1)
                for name,child in (('replay',replay),('replay-reversed',replay_reverse),('closed-reversed',closed_reverse)):
                    save(folder,f'{sequence}-stage2-{name}',child)
                stage['loop_audit']={'replay_model_equal': replay.save()['model']==r.save()['model'],
                    'reversed_replay_model_equal': replay.save()['model']==replay_reverse.save()['model'],
                    'closed_reversal_inputs_differ': reverse_report['input_frames']!=stage['input_frames'],
                    'closed_reversal_model_differs':closed_reverse.save()['model']!=r.save()['model'],
                    'replay':replay_report,'reversed_replay':replay_reverse_report,'closed_reversed':reverse_report}
            stages.append({'world':stage,'diagnostics':diagnostics})
        worlds[sequence]=stages
    return {'package':'X3','origin':origin,'kind':kind,'valid':True,
            'histories':history_tests,'worlds':worlds}


def apparatus(work):
    with m.worker_lock(work):
        m.frozen_check(work); m.resource_check(work)
        if any((work/x).exists() for x in ('apparatus.json','apparatus-in-flight.json')):
            raise RuntimeError('apparatus already attempted')
        m.original(work/'apparatus-in-flight.json',{'pid':os.getpid(),'operation':'apparatus'})
        reports={}; root=work/'apparatus'
        # Real independent instrument sources, excluded from all scientific sample counts.
        for kind in g.KINDS:
            p=g.Rig(kind,1016001); records=g.teaching(p,0)
            save(root,kind+'-parent',p)
            hashes={}
            for mode in ('plain','observed','restored','paused'):
                c=g.Rig.restore(p.save())
                if mode=='restored': c=g.Rig.restore(c.save())
                if mode=='paused':
                    before=m.digest(c.save()); time.sleep(.03)
                    if m.digest(c.save())!=before:raise RuntimeError('wall time changes state')
                g.probe(c,'X',frequent=mode=='observed',restore_mid=mode=='restored',pause_mid=mode=='paused')
                save(root,kind+'-'+mode,c); hashes[mode]=m.digest(c.save())
            reports[kind]={'whole_hashes':hashes,'passed':len(set(hashes.values()))==1,
                'selection':g.rnn_selection(p,records) if kind=='fixed-rnn-reader' else None}
        p,q=g.Rig('threemind',1016002),g.Rig('threemind',1016002)
        g.teaching(p,0);g.teaching(q,1);g.settle(p);g.settle(q)
        save(root,'transplant-recipient',p);save(root,'transplant-donor',q)
        grafts={}
        for mode in ('bundle','persistent','fast'):
            c,receipt=g.transfer(p,q,mode=mode)
            save(root,'transplant-'+mode,c)
            grafts[mode]=receipt
            g.probe(c,'X');save(root,'transplant-'+mode+'-final',c)
        sham,_=g.transfer(p,p);grafted,_=g.transfer(p,q);back,_=g.transfer(grafted,p)
        reports['exchange']={'passed':sham.save()==p.save()==back.save(),'packages':grafts,
                              'matching':g.matching(p)}
        result={'schema':'goal-closure-apparatus/1','passed':all(v['passed'] for v in reports.values()),'checks':reports,
                'scientific_origins':0}
        m.original(work/'apparatus.json',result)
        if not result['passed']:raise RuntimeError('apparatus failed; preserve marker')
        (work/'apparatus-in-flight.json').unlink()
        print(m.encoded(result).decode(),flush=True)


def run(work):
    import psutil
    with m.worker_lock(m.DEFAULT_WORK),m.worker_lock(work),m.connection() as client:
        m.frozen_check(work)
        if any((work/x).exists() for x in ('STOP','in-flight.json','apparatus-in-flight.json')):
            raise RuntimeError('unresolved marker; do not restart')
        if not m.read(work/'apparatus.json')['passed']:raise RuntimeError('apparatus not passed')
        if (work/'status.json').exists() and m.read(work/'status.json')['state']=='awaiting-analysis':
            raise RuntimeError('scientific execution complete')
        r=m.recorder(work,client)
        m.atomic_json(work/'host.json',{'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
        units=[(f'X1-o{o}',x1,(o,)) for o in range(8)]
        units += [(f'X2-d{d}-o{o}',x2,(o,d)) for d in (1,30,60,300) for o in range(8)]
        units += [(f'X3-{k}-o{o}',x3,(o,k)) for k in g.KINDS for o in range(8)]
        completed=0
        with m.Guard(work) as guard:
            for name,fn,args in units:
                folder=work/'units'/name
                if (folder/'result.json').exists():completed+=1;continue
                if (work/'STOP').exists():break
                if not guard.thread.is_alive():raise RuntimeError('resource guard absent')
                if sum(p.stat().st_size for p in work.rglob('*') if p.is_file())>4*2**30:
                    m.original(work/'STOP',{'reason':'4GiB original cap'});break
                m.original(work/'in-flight.json',{'unit':name,'pid':os.getpid(),'epoch':time.time()})
                result=fn(folder,*args)
                m.original(folder/'result.json',result)
                (work/'in-flight.json').unlink()
                completed+=1
                m.atomic_json(work/'progress.json',{'completed':completed,'total':len(units),'last':name,'epoch':time.time()})
                r.append('result',name,{'unit':name,'package':result['package'],'valid':result['valid'],
                    'sha256':hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()},request_id=uuid5(NS,'result:'+name))
                r.synchronize()
                print(json.dumps({'completed':completed,'total':len(units),'unit':name,'pending':r.status['pending']}),flush=True)
        m.atomic_json(work/'status.json',{'state':'awaiting-analysis' if completed==len(units) else 'resource-paused',
                                        'completed':completed,'total':len(units)})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('register','apparatus','run','check','status'))
    p.add_argument('--work',type=Path,default=WORK);args=p.parse_args();w=args.work.resolve()
    if args.command=='check':print(json.dumps(m.resource_check(w)))
    elif args.command=='status':print(json.dumps({n:m.read(w/n) if (w/n).exists() else None for n in
        ('platform.json','host.json','progress.json','status.json','STOP','in-flight.json','resource-summary.json')}))
    else:{'register':register,'apparatus':apparatus,'run':run}[args.command](w)
