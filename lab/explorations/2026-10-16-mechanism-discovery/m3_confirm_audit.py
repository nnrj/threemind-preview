"""Independent saved-trajectory and arithmetic verification; zero Core engines loaded."""
import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

from closure_audit import probe_check,replay_rnn
from pilot_m1 import differences
import m3_confirm_spec as spec
import pilot_m2 as m


def load(path):return json.loads(gzip.decompress(path.read_bytes()))


def check_probe(parent,whole,result,cue,second=None):
    probe_check(whole,result)
    assert whole['time_us']==parent['time_us']+1_500_000
    assert result['start_us']==parent['time_us']
    assert whole['rows'][:len(parent['rows'])]==parent['rows']
    for key in ('kind','seed','mode','mappings','rng','reader','optimizer'):
        assert whole[key]==parent[key]
    new=[];start=parent['time_us']
    if cue:new.append({'time_us':start,'values':{cue:.8}})
    for dt in (500_000,1_000_000,1_500_000):
        values={'K':.2}
        if second and dt==500_000:values[second]=.8
        new.append({'time_us':start+dt,'values':values})
    assert whole['inputs']==parent['inputs']+new
    return result['early_integral'],result['late_integral']


def check_world(start,end,report,replay=None):
    assert end['time_us']==start['time_us']+30_000_000
    assert report['start_us']==start['time_us'] and report['end_us']==end['time_us']
    assert report['model_sha256']==m.digest(end['model'])
    assert end['rows'][:len(start['rows'])]==start['rows']
    rows=end['rows'][len(start['rows']):];assert len(rows)==600
    body=copy.deepcopy(start['body']);events=[];inputs=[]
    replay=None if replay is None else {e['relative_us']:e['values'] for e in replay}
    for i,row in enumerate(rows,1):
        dt=i*50_000;assert row['time_us']==start['time_us']+dt
        if replay is not None:values=replay.get(dt,{})
        else:
            values={}
            if i%10==0:values['K']=.2
            if i%20==1:
                left=body['x']<.5
                group=('XYA' if left else 'ZWB') if report['environment']=='P' else ('XYB' if left else 'ZWA')
                values.update(dict.fromkeys(group,.8))
            if i%5==0:values['N']=.05+.1*abs(body['v'])
        if values:
            events.append({'relative_us':dt,'values':dict(values)})
            inputs.append({'time_us':start['time_us']+dt,'values':dict(values)})
        body['v']=.9*body['v']+.1*report['sign']*math.tanh(row['response'])
        body['x']=(body['x']+.05*body['v'])%1.
        assert body==row['body']
    assert events==report['input_frames'] and end['inputs']==start['inputs']+inputs
    assert end['body']==body and end['actuator']==rows[-1]['response']
    assert report['path_displacement']==abs(rows[-1]['body']['x']-rows[0]['body']['x'])


def criteria(result):
    h=result['histories']
    def delta(cells,arm):return cells[arm+'-X']['early_integral']-cells[arm+'-none']['early_integral']
    history=(delta(h[0]['cells'],'intact')-delta(h[1]['cells'],'intact'))/2
    selective=[];temporal=[]
    for row in h:
        cells=row['cells'];base=delta(cells,'intact')
        target=abs(base-delta(cells,'target'));matched=abs(base-delta(cells,'matched'))
        sham=abs(base-delta(cells,'sham'));restored=abs(base-delta(cells,'restored'))
        selective.append(target>1e-4 and target>10*sham and matched<=.25*target and restored<=1e-9)
        t=row['temporal'];interactions=[]
        for arm in ('intact','all'):
            interactions.append(t[arm+'-XY']['late_integral']-t[arm+'-X0']['late_integral']-
                                t[arm+'-0Y']['late_integral']+t[arm+'-00']['late_integral'])
        temporal.append(abs(interactions[0]-interactions[1])>1e-4)
    def d(seq):
        diag=result['worlds'][seq][1]['diagnostics']
        return diag['X']['early_integral']-diag['none']['early_integral']
    history_change=max(abs(d('PQP')-d('PPP')),abs(d('QPQ')-d('QQQ')))>1e-4
    loops=[result['worlds'][s][1]['world']['loop_audit'] for s in spec.SEQUENCES]
    feedback=any(a['closed_reversal_inputs_differ'] and a['closed_reversal_model_differs'] for a in loops)
    replay_ok=all(a['replay_model_equal'] and a['reversed_replay_model_equal'] for a in loops)
    return [abs(history)>1e-4,all(selective),any(temporal),history_change and feedback and replay_ok]


def exact_p(plus,minus):
    n=plus+minus
    return 1. if not n else min(1.,2*sum(math.comb(n,j) for j in range(min(plus,minus)+1))/2**n)


def audit(work):
    m.frozen_check(work);assert m.read(work/'cases.json')==spec.cases()
    analysis=m.read(work/'analysis-v1.json');assert len(analysis['units'])==spec.N
    counts={'origins':0,'systems':0,'probes':0,'whole_snapshots':0,'loop_pairs':0,'rnn_teaching_replays':0,'intervention_receipts':0}
    hashes=[];matrix={k:[] for k in spec.KINDS};residuals=[]
    for case in spec.cases():
        folder=work/'units'/f'o{case["origin"]}';result=m.read(folder/'result.json')
        assert result['case']==case and result['origin']==case['origin']
        a=next(u for u in analysis['units'] if u['origin']==case['origin'])
        for kind in spec.KINDS:
            sub=folder/kind;r=result['systems'][kind]
            assert r['origin']==case['rig_origin'] and r['kind']==kind
            for p in sorted(sub.glob('*.json.gz')):
                raw=p.read_bytes();whole=json.loads(gzip.decompress(raw))
                assert whole['schema']=='threemind.goal-closure-whole/1'
                assert whole['kind']==kind and whole['seed']==case['seed']
                if kind=='threemind':assert int(whole['model']['time_us'])==whole['time_us']
                hashes.append({'path':p.relative_to(work).as_posix(),'sha256':hashlib.sha256(raw).hexdigest()})
                counts['whole_snapshots']+=1
            for h in r['histories']:
                prefix=f'h{h["history"]}';parent=load(sub/(prefix+'-parent.json.gz'))
                selected=m.read(sub/(prefix+'-selection.json'))
                if kind=='fixed-rnn-reader':
                    assert replay_rnn(parent)==h['selection']==selected and selected['passed']
                    residuals.extend(selected['standardized_residual']);counts['rnn_teaching_replays']+=1
                for arm in spec.ARMS:
                    initial=load(sub/f'{prefix}-{arm}-initial.json.gz')
                    receipt=m.read(sub/f'{prefix}-{arm}-intervention.json')
                    if arm in ('intact','sham','restored'):
                        left=copy.deepcopy(parent);right=copy.deepcopy(initial)
                        left['branch']=right['branch']=None;assert left==right
                    else:
                        field={'reactive':None,'finite-state':'model.memory','hebbian':'model.W',
                               'fixed-rnn-reader':'model.R' if arm=='all' else 'model.h','threemind':'model.silenced_edges'}[kind]
                        changes=differences(parent,initial)
                        assert changes==receipt['changed_paths'] and set(changes)<={'branch',field}
                    for cue in ('X','none'):
                        whole=load(sub/f'{prefix}-{arm}-{cue}-final.json.gz')
                        assert whole['branch']['parent_sha256']==m.digest(initial)
                        check_probe(initial,whole,h['cells'][arm+'-'+cue],'' if cue=='none' else cue)
                        counts['probes']+=1
                    counts['intervention_receipts']+=1
                for name,p in h['temporal'].items():
                    arm,sequence=name.split('-');initial=load(sub/f'{prefix}-{arm}-initial.json.gz')
                    check_probe(initial,load(sub/f'{prefix}-temporal-{name}.json.gz'),p,
                                '' if sequence[0]=='0' else sequence[0],None if sequence[1]=='0' else sequence[1])
                    counts['probes']+=1
            for sequence,stages in r['worlds'].items():
                current=load(sub/f'{sequence}-birth.json.gz')
                for j,stage in enumerate(stages,1):
                    live=load(sub/f'{sequence}-stage{j}.json.gz');check_world(current,live,stage['world'])
                    for cue,p in stage['diagnostics'].items():
                        whole=load(sub/f'{sequence}-stage{j}-diagnostic-{cue}.json.gz')
                        assert whole['branch']['parent_sha256']==m.digest(live)
                        assert whole['body']=={'x':.3125,'v':0.,'gate':0}
                        check_probe(live,whole,p,'' if cue=='none' else cue);counts['probes']+=1
                    if j==2:
                        la=stage['world']['loop_audit']
                        replay=load(sub/f'{sequence}-stage2-replay.json.gz')
                        reverse=load(sub/f'{sequence}-stage2-replay-reversed.json.gz')
                        closed=load(sub/f'{sequence}-stage2-closed-reversed.json.gz')
                        frames=stage['world']['input_frames']
                        check_world(current,replay,la['replay'],frames)
                        check_world(current,reverse,la['reversed_replay'],frames)
                        check_world(current,closed,la['closed_reversed'])
                        assert la['replay_model_equal']==(replay['model']==live['model'])
                        assert la['reversed_replay_model_equal']==(replay['model']==reverse['model'])
                        assert la['closed_reversal_inputs_differ']==(la['closed_reversed']['input_frames']!=frames)
                        assert la['closed_reversal_model_differs']==(closed['model']!=live['model'])
                        counts['loop_pairs']+=1
                    current=live
            passes=criteria(r);assert passes==a['scores'][kind]['passes']
            matrix[kind].append(passes);counts['systems']+=1
        counts['origins']+=1
    assert counts=={'origins':spec.N,'systems':spec.N*5,'probes':spec.N*320,
                    'whole_snapshots':spec.N*530,'loop_pairs':spec.N*20,
                    'rnn_teaching_replays':spec.N*2,'intervention_receipts':spec.N*60}
    for kind,rows in matrix.items():
        assert [sum(r[j] for r in rows) for j in range(4)]==analysis['systems'][kind]['criterion_counts']
        assert sum(all(r) for r in rows)==analysis['systems'][kind]['joint_count']
    t=[all(r) for r in matrix['threemind']]
    for kind in spec.KINDS[:-1]:
        c=[all(r) for r in matrix[kind]];positive=sum(x and not y for x,y in zip(t,c));negative=sum(y and not x for x,y in zip(t,c))
        stats=analysis['paired_comparisons'][kind]
        assert (positive,negative)==(stats['positive'],stats['negative'])
        assert abs(exact_p(positive,negative)-stats['exact_two_sided_p'])<1e-14
    report={'schema':'threemind.m3-confirmation-audit/1','passed':True,'counts':counts,
            'maximum_rnn_matching_residual':max(residuals),'whole_manifest':hashes,'Core_engines_loaded':0,
            'baseline_replays':'Offline numerical instrument checks, not scientific sources or additional training.'}
    m.original(work/'audit-v1.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='whole_manifest'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);audit(p.parse_args().work)
