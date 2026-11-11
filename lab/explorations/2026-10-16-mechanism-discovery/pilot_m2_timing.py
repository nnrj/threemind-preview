"""Bounded new-material timing test; existing frozen /5.1 hosts and API only."""
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
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-timing-v1')
NS = UUID('104a2942-870c-427e-a2e0-3c3f4616dd78')
CUES = {'none': None, 'X': None, 'Y': None, **{f'XY-{n}': n for n in (0, 1, 10, 25, 50, 100)}}
ARMS = ('normalized', 'summed')


def parents():
    return [dict(c, id=f't{o}-h{h}', origin=f'timing-o{o}', seed=927100+o,
                 study='m2-timing/1')
            for o in range(8) for h in (0, 1)
            for c in [dict(f.parents()[2*o+h])]]


def probe_events(channels, start, cue):
    if cue not in CUES:
        raise ValueError('unregistered cue')
    items = []
    if cue == 'X' or cue == 'Y':
        items = [(start, ((channels[cue], .5),))]
    elif cue.startswith('XY-'):
        lag = CUES[cue]*1000
        items = ([(start, ((channels['X'], .5), (channels['Y'], .5)))] if lag == 0 else
                 [(start, ((channels['X'], .5),)), (start+lag, ((channels['Y'], .5),))])
    return [{'kind': 'probe', 'stimulus': m.Stimulus(t, channel_values, 1.).to_dict()}
            for t, channel_values in items]


def fork(parent, cue, arm):
    before = parent.save()
    child, _ = f.fork(parent, 'none', arm)
    prefix = copy.deepcopy(child.events[:child.cursor])
    future = child.events[child.cursor:] + probe_events(child.channels, child.probe_start, cue)
    child.events = prefix + sorted(future, key=lambda e: (int(e['stimulus']['time_us']), e['kind'] == 'probe'))
    child.branch['cue'] = cue
    child.branch['study'] = 'm2-timing/1'
    after = child.save()
    if parent.save() != before or after['environment']['schedule'][:child.cursor] != prefix:
        raise RuntimeError('parent/past input mutation')
    return child, {'parent_sha256': m.digest(before), 'branch_initial_sha256': m.digest(after),
                   'changed_paths': f.differences(before, after), 'parent_time_us': parent.engine.time_us,
                   'new_independent_origin': False}


def decay_clipped(value, lag_s, tau, floor):
    result = value*math.exp(-lag_s/tau)
    return result if abs(result) >= floor else 0.


def forecast(graph, channels, cfg, cue, arm):
    mix = f.ARMS[arm][-1]
    first = lambda c: f.forecast(graph, channels, cfg, c, mix)['response_at_110ms']['receiver']
    if cue == 'none':
        a = b = 0.
    elif cue in ('X', 'Y'):
        a = b = first(cue)
    elif CUES[cue] == 0:
        a = b = first('XY-per')
    else:
        a = first('X')
        b = decay_clipped(a, CUES[cue]/1000, cfg['activation_tau'], cfg['activation_floor'])+first('Y')
    return {'source': 'pre-cue-graph-only', 'first_110ms': a, 'at_second_arrival': b,
            'second_arrival_ms': 110+(CUES[cue] or 0),
            'assumptions': 'isolated first arrivals; per-route gating; clipped output decay; no cue-to-cue recurrent recruitment or subsequent source emissions',
            'scope': '100ms lag is a declared boundary test coinciding with a possible second X emission; no post-result refitting'}


def endpoint(saved, prediction):
    value = f.endpoint(saved, prediction)
    start = (17+saved['case']['delay'])*1_000_000
    second = start+prediction['second_arrival_ms']*1000
    value['response_second_arrival'] = next(r['response'] for r in saved['recent_activity'] if r['time_us'] == second)
    return value


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work/'platform.json').exists():
            raise RuntimeError('already registered')
        name = '2026-10-16 机制发现 · M2 提示时序与预测边界'
        found = [p for p in client.call('projects.list', {}) if p['name'] == name]
        if len(found) > 1:
            raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': name})
        platform = {'project_id': project['id'], 'resource_id': 'mechanism-m2-timing-20261016'}
        m.original(work/'platform.json', platform)
        paths = [Path(__file__), Path(f.__file__), m.HERE/'pilot_m1.py', Path(m.__file__),
                 m.HERE/'pilot-m2-timing.zh.md', m.HERE/'pilot-m2-timing.en.md',
                 m.ROOT/'lab/tools/study_lock.py',
                 m.ROOT/'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py']
        manifest = {p.relative_to(m.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        m.original(work/'runner-manifest.json', manifest)
        m.original(work/'implementation.json', m.capture_implementation('native'))
        m.original(work/'parents.json', parents())
        for p in paths:
            m.original(work/'frozen'/p.name, {'utf8': p.read_text(encoding='utf-8')})
        r = m.ResearchRecorder(work, project['id'], client=client)
        r.register({'source_key': 'mechanism-discovery:M2:timing-v1:20261016', 'title': name,
                    'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                    'kernels': [m.KERNEL], 'protocol': (m.HERE/'pilot-m2-timing.zh.md').read_text(encoding='utf-8'),
                    'protocol_version': m.digest(manifest), 'required_roles': ['protocol','report','note'],
                    'metadata': {'work': str(work), 'new_independent_origins': 8, 'parents': 16,
                                 'causal_copies': 288, 'core_code_changed': False, 'E69_resumed': False}},
                   request_id=uuid5(NS, 'register'))
        r.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={
            'resource_id': platform['resource_id'], 'target_id': 'managed-research-experiments',
            'relative_path': '2026-10-16-mechanism-discovery/m2-timing-v1', 'registered_work_path': str(work),
            'writer_mode': 'cooperative', 'expected_revision': 0}, headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={
            'project_id': project['id'], 'resource_id': platform['resource_id']},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh','en'):
            r.text({'request_id': str(uuid5(NS, 'protocol:'+lang)), 'identity': str(uuid5(NS, 'doc:'+lang)),
                    'expected_revision': 0, 'kind': 'protocol', 'title': 'M2 timing pilot '+lang,
                    'markdown': (m.HERE/f'pilot-m2-timing.{lang}.md').read_text(encoding='utf-8')})
        r.synchronize(strict=True)
        print(m.encoded(platform | {'record': r.experiment, 'status': r.status}).decode(), flush=True)


def apparatus(work):
    with m.worker_lock(work), m.connection() as client:
        m.frozen_check(work)
        if (work/'apparatus.json').exists() or (work/'apparatus-in-flight.json').exists():
            raise RuntimeError('apparatus already exists or is incomplete')
        m.resource_check(work)
        m.original(work/'apparatus-in-flight.json', {'time': time.time(), 'pid': os.getpid()})
        case = dict(parents()[0], id='apparatus', origin='apparatus', seed=927002, delay=1)
        parent = f.Subject(case)
        parent.advance(parent.probe_start)
        m.original(work/'apparatus/parent.json.gz', parent.save(), compressed=True)
        hashes, identities = {}, {}
        for cue in ('XY-1','XY-10','XY-100'):
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
        report = {'schema':'threemind.m2-timing-apparatus/1', 'passed': all(identities.values()) and
                  all(len(set(v.values()))==1 for v in hashes.values()), 'whole_state_hashes':hashes,
                  'configuration_identities':identities, 'new_scientific_origin':False, 'seed':927002}
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
                        m.atomic_json(work/'progress.json',{'completed':completed,'total':288,'last':out.name,'pending':r.status['pending']})
                        print(m.encoded({'completed':completed,'last':out.name}).decode(),flush=True)
                    if (work/'STOP').exists():break
            m.atomic_json(work/'status.json',{'state':'awaiting-analysis' if completed==288 else 'resource-paused',
                                             'completed':completed,'total':288,'recorder':r.status})


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
