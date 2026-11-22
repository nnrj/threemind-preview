"""Read-only E15 artifact, closed-loop feedback, and prespecified arithmetic audit."""
import argparse
from collections import Counter
import copy
from functools import lru_cache
import json
import math
from pathlib import Path
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_original as r
e=r.e;m=r.m;read=r.read
from threemind_core import StateImage
from threemind_kernels.local63_config import Local63Config


def apply_changes(state,changes,reverse=False):
    value=copy.deepcopy(state)
    for change in changes:
        keys=change['path'].split('.');target=value
        for key in keys[:-1]:target=target[key]
        old,new=(change['after'],change['before']) if reverse else (change['before'],change['after'])
        assert target.get(keys[-1])==old
        target[keys[-1]]=copy.deepcopy(new)
    return value


def verify_body(rows,final):
    if not rows:return 0.
    error=0.
    extended=rows+[{'relative_us':final[0],'body':final[1]}]
    for a,b in zip(extended,extended[1:]):
        seconds=(b['relative_us']-a['relative_us'])/1e6
        decay=math.exp(-.8*seconds);velocity=a['body']['v'];control=a['control']
        next_v=velocity*decay+.375*control*(1-decay)
        next_x=(a['body']['x']+velocity*(1-decay)/.8+.375*control*(seconds-(1-decay)/.8))%1
        # Positions are circular; compare the shortest numerical distance.
        dx=abs(next_x-b['body']['x']);error=max(error,min(dx,1-dx),abs(next_v-b['body']['v']))
    return error


def analyze(work):
    frozen=r.check(work)
    assert not (work/'in-flight.json').exists() and read(work/'summary.json')['stages']==826
    cases=read(work/'cases.json');counts=Counter();classes=Counter();checks=[];texture_structure=[]
    body_error=0.;projection_error=0.;supply_error=0.;costs=[]
    def inspect(image):
        value=image.to_dict();cfg=value['config']
        assert value['dynamics']==e.KERNEL and value['life'] in ('active','waiting')
        assert cfg['signal_threshold']==.0004 and cfg['prune_weight']==.008
        assert cfg['decay_curve']=='inverse-logarithmic' and not cfg['retention_growth_enabled']
        assert cfg['depletion_enabled'] and cfg['stp_facilitation_tau_s']==1. and cfg['energy_simulation_enabled']
        assert all(n['id']==n['channel'] for n in value['nodes'])
        counts['states']+=1
        return value
    for number,case in enumerate(cases,1):
        folder=work/'cases'/case['key'];result=read(folder/'result.json');ex=case['historical_details']
        assert result['key']==case['key'] and result['kernel']==e.KERNEL
        assert result['status']=='complete' and result['life']=='active' and not result['calibration'] and result['mode']=='observed'
        initial=e.base.image(folder/'initial.tmind');changed=e.base.image(folder/'intervened.tmind');final=e.base.image(folder/'final.tmind')
        a,b,z=(inspect(i) for i in (initial,changed,final))
        assert [i.digest for i in (initial,changed,final)]==[result[k] for k in ('initial_sha256','intervened_sha256','final_sha256')]
        assert int(a['time_us'])==int(b['time_us'])==case['begin_us'] and int(z['time_us'])==case['end_us']
        first=e.unpacked(folder/'initial-whole.json.xz');last=e.unpacked(folder/'whole.json.xz')
        if case['parent']:
            parent=e.base.image(work/'cases'/case['parent']/'final.tmind')
            old=parent.to_dict();previous=e.unpacked(work/'cases'/case['parent']/'whole.json.xz')
            assert parent.digest==result['parent_sha256'] and a['config']==old['config']
            if case['birth_intervention']:
                assert result['birth']=={'inheritance_rule':'threemind.birth/2','inheritance_decay_age':'preserve'}
                assert int(a['time_us'])==0 and not a['queue'] and not a['active']
                assert {n['id'] for n in a['nodes']}=={n['id'] for n in old['nodes']}
                assert {(x['source'],x['target']) for x in a['edges']}=={(x['source'],x['target']) for x in old['edges']}
                fast=('activation','inhibition','trace','direct','associative','fatigue','salience',
                      'pending_inhibition','generated_inhibition')
                assert all(not n[k] for n in a['nodes'] for k in fast)
                assert all(x['fast'] is None and x['short_term'] is None and x['eligibility']==0 for x in a['edges'])
                old_nodes={n['id']:n for n in old['nodes']};old_edges={(x['source'],x['target']):x for x in old['edges']}
                assert all(n['decay_age']>=old_nodes[n['id']]['decay_age'] for n in a['nodes'])
                assert all(x['decay_age']>=old_edges[x['source'],x['target']]['decay_age'] for x in a['edges'])
                counts['declared_births']+=1
            else:
                assert initial.digest==parent.digest
                assert first['observer']==previous['observer'] and first['supplier']==previous['supplier']
                if result['stage']=='environment' and ex['phase']>1:assert first['body']==previous['body']
                counts['complete_continuations_or_copies']+=1
        else:
            assert result['parent_sha256'] is None and not a['nodes'] and not a['edges']
            assert a['config']==Local63Config(seed=case['seed'],energy_simulation_enabled=True,
                depletion_enabled=True,stp_facilitation_tau_s=1.,edge_consolidation_enabled=True).to_dict()
            counts['blank_origins']+=1
        known={initial.digest:a,changed.digest:b,final.digest:z}
        with zipfile.ZipFile(folder/'milestones.zip') as archive:
            expected={'end'}|({'before-training','before-erasure'} if result['stage']=='novelty' else set())
            assert expected==set(result['milestones']) and set(archive.namelist())=={n+'.tmind' for n in expected}
            for label in expected:
                image=e.base.ArtifactCodec.decode(archive.read(label+'.tmind'));value=inspect(image)
                assert image.digest==result['milestones'][label]
                known[image.digest]=value
                if label=='end':assert image.digest==final.digest
        interventions=e.unpacked(folder/'interventions.json.xz');pending=list(interventions)
        while pending:
            progressed=False
            for receipt in list(pending):
                assert not receipt['patch'] or set(receipt['patch'])<=set(('propagation_rate','inhibition_diffusion_rate',
                    'edge_consolidation_enabled','local_novelty_gain'))
                assert receipt['action'] in (None,'silence','restore','disconnect_edges')
                for reverse in (False,True):
                    before,after=('after','before') if reverse else ('before','after')
                    if receipt[before] not in known:continue
                    value=apply_changes(known[receipt[before]],receipt['changes'],reverse)
                    assert StateImage.from_dict(value).digest==receipt[after]
                    assert value['time_us']==known[receipt[before]]['time_us']
                    known[receipt[after]]=value;pending.remove(receipt);progressed=True;break
            assert progressed,'intervention receipt disconnected from saved complete states'
        counts['interventions']+=len(interventions)
        expected=r.mat.normalize((work/'materials'/case['key']/'frames.jsonl').read_bytes(),case)
        if case['new_closed_loop']:expected=[v for v in expected if v['source']!='controlled-environment']
        inputs=e.unpacked(folder/'inputs.json.xz');assert inputs['replayed']==expected
        trajectory=e.unpacked(folder/'trajectory.json.xz');rows=trajectory['rows']
        if case['new_closed_loop']:
            dynamic=inputs['closed_loop'];assert len(dynamic)==30
            by_time={row['relative_us']+case['begin_us']:row for row in rows}
            for index,item in enumerate(dynamic):
                at=case['begin_us']+index*1000000;point=by_time[at]
                assert item['body']==point['body'] and item['environment']==ex['route'][ex['phase']-1]
                assert item['stimulus']==e.sensation(e.Body(**item['body']),case['seed'],at,item['environment']).to_dict()
                expected.append({'enqueue_us':at,'source':'controlled-environment','stimulus':item['stimulus']})
            counts['closed_loop_frames']+=len(dynamic)
        else:assert not inputs['closed_loop']
        scheduled=e.unpacked(folder/'scheduled.json.xz');delivered=e.unpacked(folder/'delivered.json.xz')
        assert len(expected)==len(scheduled)==len(delivered)==result['inputs']
        by_event={row['receipt']['core_event_id']:row['enqueue_us'] for row in scheduled}
        norm=lambda d:json.dumps(d,sort_keys=True,separators=(',',':'))
        assert Counter(norm({k:v[k] for k in ('stimulus','source','enqueue_us')}) for v in expected)==Counter(
            norm({'stimulus':v['stimulus'],'source':v['source'],'enqueue_us':by_event[v['core_event_id']]}) for v in delivered)
        assert all(not v.get('labels') and v['scheduled_time_us']==v['delivered_time_us']==v['stimulus']['time_us'] for v in delivered)
        assert not last['observer']['input_bus']['pending']
        counts['inputs']+=len(expected)
        if result['stage']=='probe':
            assert [p['relative_us'] for p in rows]==list(range(0,2000000,10000))+list(range(2000000,15000001,100000))
            assert first['body']=={'x':.3125,'v':0.,'phase':0.}
        elif result['stage'] in ('environment','ring_world'):
            assert [p['relative_us'] for p in rows]==list(range(0,case['end_us']-case['begin_us'],100000))
        else:assert not rows
        if rows:
            end=case['end_us']-case['begin_us']
            to_check=rows[:-1] if rows[-1]['relative_us']==end else rows
            body_error=max(body_error,verify_body(to_check,(end,last['body'])))
        for point in rows+trajectory['first']:
            projection_error=max(projection_error,abs(e.motor(case['seed'],point['nodes'])-point['control']))
        assert body_error<1e-12 and projection_error<1e-15
        energies=[v['payload'] for v in trajectory['events'] if v['kind']=='core_event' and v['payload']['kind']=='energy']
        duration=case['end_us']-case['begin_us'];assert len(energies)==duration//100000
        assert [int(v['time_us']) for v in energies]==list(range(case['begin_us']+100000,case['end_us']+1,100000))
        increment=last['supplier']['accepted_total']-first['supplier']['accepted_total']
        supply_error=max(supply_error,abs(math.fsum(v['payload']['accepted'] for v in energies)-increment))
        assert supply_error<1e-9 and z['energy']['unserved_total']<=1e-10
        assert last['supplier']['sequence']-first['supplier']['sequence']==len(energies)
        assert not last['supplier']['pending']
        counts['energy_deliveries']+=len(energies)
        if result['stage']=='novelty':
            before=known[result['milestones']['before-training']];after=known[result['milestones']['before-erasure']]
            old={(v['source'],v['target']):v for v in before['edges']};new={(v['source'],v['target']):v for v in after['edges']}
            texture_structure.append({'key':case['key'],'added_edges':len(new.keys()-old.keys()),
                'removed_during_teaching':len(old.keys()-new.keys()),
                'removed_by_intervention':len(new)-len(z['edges']),
                'first_motor_auc':m.area(trajectory['first'],lambda p:p['control'],0,990000)})
        classes.update(result['window_classifications']);counts['stages']+=1;counts[case['source']+'_stages']+=1
        cost=read(work/'costs'/f'{number:03d}.json');assert cost['unit']==case['key']
        actual=r.cost(folder,case)
        assert all(actual[k]==cost[k] for k in actual)
        costs.append(cost['comparable_bytes']/cost['historical_allocated_bytes'])
        if number%64==0:print('audited',number,'/826',flush=True)
    assert counts['states']==3368 and counts['inputs']==23552 and counts['closed_loop_frames']==1440
    assert counts['stages']==826 and counts['main_stages']==802 and len(texture_structure)==32
    @lru_cache(maxsize=4)
    def load_rows(key):return e.unpacked(work/'cases/main'/key/'trajectory.json.xz')['rows']
    result=m.measure(load_rows,e.symbols)
    assert result['exact_shams']==result['exact_restored_trajectories']==16 and result['exact_first_stage_pairs']==8
    assert result['maximum_decimal_motor_error']<1e-12
    analysis={'kernel':e.KERNEL,'wiring_blocks':2,'related_parents':4,'counts':dict(counts),**result,
        'texture_structure':texture_structure,'window_classifications':dict(classes),
        'maximum_body_error':body_error,'maximum_projection_error':projection_error,'maximum_supply_error':supply_error,
        'comparable_allocation_ratio':{'minimum':min(costs),'maximum':max(costs)}}
    r.s.base.original(work/'analysis.json',analysis)
    audit={'passed':True,'read_only':True,'created_engines':0,'counts':dict(counts),
           'scientific_stop':result['decision']['scientific_stop'],'maximum_decimal_error':result['maximum_decimal_motor_error'],
           'maximum_body_error':body_error,'maximum_supply_error':supply_error}
    r.s.base.original(work/'audit.json',audit);print(json.dumps(audit),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True)
    analyze(parser.parse_args().work.resolve())
