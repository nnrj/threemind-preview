"""Prospective phase-boundary test after a preserved timing-model failure."""
from __future__ import annotations

import argparse
import copy
import hashlib
import math
import os
import sys
import time
from pathlib import Path
from uuid import UUID, uuid5

import pilot_m2_fusion_v2 as f

m = f.m
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-phase-v1')
NS = UUID('db445fd3-5d36-4949-a94c-75e7c8565e72')
OFFSETS = (7, 43, 87, 99)
LAGS = (0, 1, 2, 20, 80)
CUES = {'none': None, **{f'p{p}-d{d}': (p, d) for p in OFFSETS for d in LAGS}}
ARMS = ('normalized', 'summed')


def parents():
    return [dict(c, id=f'p{o}-h{h}', origin=f'phase-o{o}', seed=937100+o,
                 delay=23, teaching_intensity=(.30,.38,.46,.54)[o//2], study='m2-phase/1')
            for o in range(8) for h in (0, 1)
            for c in [dict(f.parents()[2*o+h])]]


def probe_events(channels, start, cue):
    if cue not in CUES:
        raise ValueError('unregistered cue')
    if cue == 'none':
        return []
    phase, lag = CUES[cue]
    x, y = start+phase*1000, start+(phase+lag)*1000
    items = ([(x, ((channels['X'], .5), (channels['Y'], .5)))] if lag == 0 else
             [(x, ((channels['X'], .5),)), (y, ((channels['Y'], .5),))])
    return [{'kind': 'probe', 'stimulus': m.Stimulus(t, values, 1.).to_dict()}
            for t, values in items]


def fork(parent, cue, arm):
    before = parent.save()
    child, _ = f.fork(parent, 'none', arm)
    prefix = copy.deepcopy(child.events[:child.cursor])
    future = child.events[child.cursor:] + probe_events(child.channels, child.probe_start, cue)
    child.events = prefix + sorted(future, key=lambda e: (int(e['stimulus']['time_us']), e['kind'] == 'probe'))
    child.branch['cue'] = cue
    child.branch['study'] = 'm2-phase/1'
    after = child.save()
    if parent.save() != before or after['environment']['schedule'][:child.cursor] != prefix:
        raise RuntimeError('parent/past input mutation')
    return child, {'parent_sha256': m.digest(before), 'branch_initial_sha256': m.digest(after),
                   'changed_paths': f.differences(before, after), 'parent_time_us': parent.engine.time_us,
                   'new_independent_origin': False}


def forecast(graph, channels, cfg, cue, arm):
    """Frozen first-cycle approximation; neither outcomes nor history labels used."""
    nodes = {n['channel']: n['id'] for n in graph['nodes']}
    edges = {(e['source'],e['target']):e['weight'] for e in graph['edges']}
    tau, floor = cfg['activation_tau'], cfg['activation_floor']
    if (cfg['propagation_interval_us'] != 100000 or cfg['delay_us'] != 10000
            or cfg['propagation_phase'] != 'aligned'):
        raise ValueError('this forecast only declares the fixed 100ms/10ms schedule')
    phase_lag = CUES[cue]
    times = {} if phase_lag is None else {'X':phase_lag[0], 'Y':sum(phase_lag)}
    scale = cfg['direct_gain']*cfg['propagation_rate']*.1*cfg['stp_utilization']*.5
    forecasts = {}
    for model in ('phase-aware','all-same-cycle'):
        outputs=[]
        for output in 'AB':
            arrivals=[]
            for source, input_ms in times.items():
                if model == 'phase-aware' and input_ms > 100:
                    continue
                # Comparator ignores crossing, but retains within-cycle source decay.
                wait_ms = max(0,100-input_ms)
                value=scale*math.exp(-wait_ms/1000/tau)*edges.get((nodes.get(channels[source]),nodes.get(channels[output])),0.)
                if value >= floor:
                    arrivals.append(value)
            value=sum(arrivals)
            if arm == 'normalized' and arrivals:
                value/=len(arrivals)
            outputs.append(value if value >= floor else 0.)
        forecasts[model]=outputs[0]-outputs[1]
    return {'source':'pre-cue-graph-only','response_at_110ms':forecasts,
            'input_ms':times,'first_cycle_sources':[s for s,v in times.items() if v<=100],
            'endpoint_ms':110,'absolute_phase_origin':'parent time is an exact 100ms boundary',
            'assumptions':'aligned emission, external input precedes same-time emission; first cycle only; long-rest STP recovery; negligible weight change before first pulse; no fitted parameters'}


def endpoint(saved, prediction):
    return f.endpoint(saved,prediction)


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered')
        name = '2026-10-16 机制发现 · M2 发放相位跨界预测'
        found = [p for p in client.call('projects.list', {}) if p['name'] == name]
        if len(found) > 1:
            raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': name})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-m2-phase-20261016'}
        m.original(work/'platform.json', platform)
        paths = [Path(__file__), Path(f.__file__), m.HERE/'pilot_m1.py', Path(m.__file__),
                 m.HERE/'pilot-m2-phase.zh.md', m.HERE/'pilot-m2-phase.en.md',
                 m.ROOT/'lab/tools/study_lock.py',
                 m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        m.original(work/'parents.json', parents())
        for p in paths:
            m.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:M2:phase-v1:20261016', 'title': name,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (m.HERE/'pilot-m2-phase.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol','report','note'],
                    'metadata': {'work': str(work), 'new_independent_origins': 8, 'parents': 16,
                                 'causal_copies': 672, 'core_code_changed': False, 'E69_resumed': False}},
                   request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={
            'resource_id': platform['resource_id'], 'target_id': 'managed-research-experiments',
            'relative_path': '2026-10-16-mechanism-discovery/m2-phase-v1', 'registered_work_path': str(work),
            'writer_mode': 'cooperative', 'expected_revision': 0}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={
            'project_id': project['id'], 'resource_id': platform['resource_id']},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh','en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M2 phase pilot '+lang,
                    'markdown': (m.HERE/f'pilot-m2-phase.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(m.encoded(platform | {'record': r.experiment, 'status': r.status}).decode(), flush=True)


def apparatus(work):
    with m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if (work/'apparatus.json').exists() or (work/'apparatus-in-flight.json').exists():
            raise RuntimeError('apparatus already exists or is incomplete')
        m.resource_check(work)
        m.original(work/'apparatus-in-flight.json', {'time': time.time(), 'pid': os.getpid()})
        case = dict(parents()[0], id='apparatus', origin='apparatus', seed=937002, delay=1)
        parent = f.Subject(case)
        parent.advance(parent.probe_start)
        m.original(work/'apparatus/parent.json.gz', parent.save(), compressed=True)
        hashes, identities = {}, {}
        for cue in ('p7-d80','p99-d1','p99-d2'):
            initial = {}
            for arm in ARMS:
                for mode in ('plain','observed','restored','paused'):
                    child, _ = fork(parent, cue, arm)
                    initial[arm] = copy.deepcopy(child.save()); initial[arm].pop('branch')
                    child.advance_probe(child.probe_start+1_000_000, frequent=mode=='observed')
                    mid = child.save()
                    m.original(work/'apparatus'/f'{cue}-{arm}-{mode}-mid.json.gz', mid, compressed=True)
                    if mode == 'restored':
                        child = f.Subject(case, f.load(work/'apparatus'/f'{cue}-{arm}-{mode}-mid.json.gz'))
                    if mode == 'paused':
                        time.sleep(.05)
                        if m.digest(child.save()) != m.digest(mid):
                            raise RuntimeError('wall time changed state')
                    child.advance_probe(child.probe_start+2_000_000, frequent=mode=='observed')
                    final = child.save()
                    m.original(work/'apparatus'/f'{cue}-{arm}-{mode}-final.json.gz', final, compressed=True)
                    hashes.setdefault(cue+'-'+arm,{})[mode] = m.digest(final)
            identities[cue] = f.intervention_identity_valid(initial['normalized'],initial['summed'])
        report = {'schema':'threemind.m2-phase-apparatus/1', 'passed': all(identities.values()) and
                  all(len(set(v.values()))==1 for v in hashes.values()), 'whole_state_hashes':hashes,
                  'configuration_identities':identities, 'new_scientific_origin':False, 'seed':937002}
        m.original(work/'apparatus.json',report)
        r=m.recorder(work,client); r.append('result','apparatus',report,request_id=uuid5(NS,'apparatus')); r.synchronize()
        if not report['passed']:
            raise RuntimeError('apparatus failed; preserve marker')
        (work/'apparatus-in-flight.json').unlink()
        print(m.encoded(report).decode(),flush=True)


def run(work):
    import psutil
    with m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if not m.read(work/'apparatus.json')['passed'] or any((work/n).exists() for n in ('STOP','in-flight.json','apparatus-in-flight.json')):
            raise RuntimeError('unresolved stop/apparatus')
        if (work/'status.json').exists() and m.read(work/'status.json').get('state') == 'awaiting-analysis':
            raise RuntimeError('already complete; no scientific rerun')
        r=m.recorder(work,client)
        m.atomic_json(work/'host.json', {'pid':os.getpid(),'created_at':psutil.Process().create_time(),'command':sys.argv})
        completed=0
        with m.Guard(work) as guard:
            for case in m.read(work/'parents.json'):
                folder=work/'parents'/case['id']
                if (work/'STOP').exists():break
                if (folder/'current.json').exists():
                    c=m.read(folder/'current.json'); p=folder/c['path']
                    if hashlib.sha256(p.read_bytes()).hexdigest()!=c['sha256']:raise RuntimeError('current hash differs')
                    parent,index=f.Subject(case,f.load(p)),c['index']+1
                else:
                    m.original(work/'in-flight.json',{'case':case,'operation':'birth'})
                    parent,index=f.Subject(case),0
                    m.commit_subject(folder,parent,index); (work/'in-flight.json').unlink(); index+=1
                while parent.engine.time_us<parent.probe_start:
                    if (work/'STOP').exists():break
                    if not guard.thread.is_alive():raise RuntimeError('guard died')
                    target=min(parent.probe_start,parent.engine.time_us+10_000_000)
                    m.original(work/'in-flight.json',{'case':case,'operation':'continuous-parent','from_us':parent.engine.time_us,'to_us':target})
                    parent.advance(target)
                    if parent.engine.life=='dead':raise RuntimeError('new parent death')
                    m.commit_subject(folder,parent,index); (work/'in-flight.json').unlink(); index+=1
                if parent.engine.time_us!=parent.probe_start:break
                graph,cfg=parent.engine.graph(),parent.engine.config.to_dict()
                m.original(folder/'pre-cue-graph.json.gz',graph,compressed=True)
                predictions={cue:{arm:forecast(graph,parent.channels,cfg,cue,arm) for arm in ARMS} for cue in CUES}
                m.original(folder/'forecasts.json',predictions)
                for cue in CUES:
                    for arm in ARMS:
                        out=work/'cases'/f'{case["id"]}-{cue}-{arm}'
                        request=uuid5(NS,'result:'+out.name)
                        if (out/'result.json').exists():
                            if not (r.control/'receipts'/f'{request}.json').exists():
                                r.append('result',out.name,m.read(out/'result.json'),request_id=request)
                            completed+=1; continue
                        if (work/'STOP').exists():break
                        if not guard.thread.is_alive():raise RuntimeError('guard died')
                        m.original(work/'in-flight.json',{'case':case,'cue':cue,'arm':arm,'operation':'registered-causal-copy','parent_sha256':m.digest(parent.save())})
                        child,lineage=fork(parent,cue,arm)
                        m.original(out/'lineage.json',lineage)
                        m.original(out/'initial-whole.json.gz',child.save(),compressed=True)
                        child.advance_probe(child.probe_start+2_000_000)
                        final=child.save()
                        m.original(out/'final-whole.json.gz',final,compressed=True)
                        result=endpoint(final,predictions[cue][arm]); m.original(out/'result.json',result)
                        r.append('result',out.name,result,request_id=request); r.synchronize()
                        (work/'in-flight.json').unlink(); completed+=1
                        m.atomic_json(work/'progress.json',{'completed':completed,'total':672,'last':out.name,'pending':r.status['pending']})
                        print(m.encoded({'completed':completed,'last':out.name}).decode(),flush=True)
                    if (work/'STOP').exists():break
            m.atomic_json(work/'status.json',{'state':'awaiting-analysis' if completed==672 else 'resource-paused',
                                             'completed':completed,'total':672,'recorder':r.status})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('register','apparatus','run','status','check'))
    parser.add_argument('--work',type=Path,default=WORK)
    args=parser.parse_args(); work=args.work.resolve()
    if args.command=='status':
        print(m.encoded({n:m.read(work/n) if (work/n).exists() else None for n in
                         ('progress.json','status.json','host.json','STOP','in-flight.json','apparatus.json')}).decode())
    elif args.command=='check':print(m.encoded(m.resource_check(work)).decode())
    else:globals()[args.command](work)
