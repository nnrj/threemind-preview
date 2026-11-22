"""Read-only R63p provenance, intervention, trajectory and arithmetic audit."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_recovery as r
m=r.compact.x.measure
read=r.read


def curve(folder,seed,begin_us):
    points=read(folder/'trajectory.json.gz')['points'];ids=r.x.identities(seed)
    values={p['time_us']-begin_us:{f:[next((n.get(f,0.) for n in p['nodes'] if n['channel']==ids[k]),0.)
                    for k in 'AB'] for f in m.FIELDS} for p in points}
    assert sorted(values)==list(range(0,5600001,20000))
    return values


def audit_inputs(folder,parent,stage,work):
    p,st=r.runtime_spec(parent,stage)
    expected=r.x.inputs(p,st,work/'materials'/stage['family'])
    assert read(folder/'input.json')=={'frames':expected,'mappings':r.x.identities(parent['seed'])}
    delivered=read(folder/'delivered.json.gz');scheduled=read(folder/'scheduled.json.gz')
    assert len(expected)==len(delivered)==len(scheduled)
    by_event={}
    for item,receipt in zip(expected,scheduled):
        assert item['enqueue_us']==receipt['enqueue_us']
        assert item['source']==receipt['receipt']['source']
        assert int(item['stimulus']['time_us'])==int(receipt['receipt']['scheduled_time_us'])
        by_event[receipt['receipt']['core_event_id']]=receipt['enqueue_us']
    norm=lambda d:json.dumps(d,sort_keys=True,separators=(',',':'))
    assert Counter(norm({k:v[k] for k in ('source','stimulus','enqueue_us')}) for v in expected)==Counter(
        norm({'source':v['source'],'stimulus':v['stimulus'],'enqueue_us':by_event[v['core_event_id']]}) for v in delivered)
    assert all(not v.get('labels') and int(v['stimulus']['time_us'])==int(v['scheduled_time_us'])==int(v['delivered_time_us']) for v in delivered)
    if stage['kind']=='probe':
        ids=r.x.identities(parent['seed'])
        assert all(ch not in (ids['A'],ids['B']) for row in expected for ch,_ in row['stimulus']['channels'])
    return expected


def analyze(work):
    frozen=r.check(work)
    assert not (work/'in-flight.json').exists() and read(work/'summary.json')['stages']==752
    assert r.s.sha(work/'lineage.json')==frozen['lineage_sha256']
    counts=Counter();cut=[];waiting=[];comparisons=[];change_counts=Counter();error=0.
    def state(path):
        image=r.x.base.image(path);d=image.to_dict()
        assert d['dynamics']==r.KERNEL and d['life']=='active'
        c=d['config']
        assert c['signal_threshold']==.0004 and c['prune_weight']==.008 and c['stp_facilitation_tau_s']==0.
        assert c['depletion_enabled'] and c['context_enabled']
        assert all(n['id']==n['channel'] for n in d['nodes'])
        counts['states']+=1
        return image
    refs={p['key']:state(work/'references'/p['key']/'state.tmind') for p in r.spec.parents()}
    lineage={v['parent']['key']:v for v in read(work/'lineage.json')}
    for parent in r.spec.parents():
        recipient=refs[parent['key']]
        assert recipient.digest==lineage[parent['key']]['state_sha256']
        observer=read(work/'references'/parent['key']/'observer.json')
        assert r.s.sha(work/'references'/parent['key']/'observer.json')==lineage[parent['key']]['observer_sha256']
        donor=refs[f"{parent['seed']}/{parent['mode']}/learn{'11' if parent['learn']=='01' else '01'}"]
        changed={};held={};hold_observers={}
        for stage in r.spec.stages(parent):
            folder=work/'cases'/stage['key'];result=read(folder/'result.json')
            p,st=r.runtime_spec(parent,stage)
            assert result['parent']==p and result['stage']==st and result['status']=='complete'
            assert result['calibration_seed'] is None and result['no_reconfigure'] and result['mode']=='observed'
            initial,final=state(folder/'initial.tmind'),state(folder/'final.tmind')
            assert result['initial_sha256']==initial.digest and result['final_sha256']==final.digest
            assert int(initial.to_dict()['time_us'])==stage['begin_us'] and int(final.to_dict()['time_us'])==stage['end_us']
            if stage['family']=='cut':
                label=''.join(stage['groups']) or 'none'
                if label not in changed:
                    group=work/'cases/cut'/parent['key']/label
                    expected,receipt=r.intervention.exchange(recipient,donor,stage['groups'])
                    actual=state(group/'changed.tmind')
                    assert actual.digest==expected.digest and read(group/'exchange.json')==receipt
                    changed[label]=actual
                    change_counts.update(str(v['location'][0])+'.'+str(v['location'][-1]) for v in receipt['changes'])
                    counts['exchanges']+=1
                source=changed[label];reader=observer
            elif stage['kind']=='hold':
                source=recipient;reader=observer
                held[stage['delay_s']]=final;hold_observers[stage['delay_s']]=read(folder/'observer.json')
            else:
                source=held[stage['delay_s']];reader=hold_observers[stage['delay_s']]
            assert source.digest==initial.digest==result['parent_sha256']
            assert read(folder/'initial-observer.json')==reader
            assert initial.to_dict()['config']==final.to_dict()['config']
            if stage['kind']=='probe':
                same=state(folder/'intervened.tmind');receipt=read(folder/'intervention.json')
                assert same.digest==initial.digest
                assert receipt['method']=='none' and receipt['advanced_us']==0 and receipt['changes']==[]
                assert receipt['before_sha256']==receipt['after_sha256']==initial.digest
                assert receipt['projected_before']==receipt['projected_after']
            frames=audit_inputs(folder,parent,stage,work)
            assert result['inputs']==len(frames)
            counts['stages']+=1;counts['inputs']+=len(frames)
            if stage['kind']=='probe' and stage['physical']:
                blank_path=folder.with_name('physical0')
                # A physical1 record is deliberately ordered after its matched physical0 record.
                cued=curve(folder,parent['seed'],stage['begin_us'])
                blank=curve(blank_path,parent['seed'],stage['begin_us'])
                full,e=m.integrate(cued,blank,0,5600000);error=max(error,e)
                post,e=m.integrate(cued,blank,600000,5600000);error=max(error,e)
                zero={t:{f:[0.,0.] for f in m.FIELDS} for t in cued}
                raw,e=m.integrate(cued,zero,0,5600000);error=max(error,e)
                row={'seed':parent['seed'],'mode':parent['mode'],'learn':parent['learn'],'sign':stage['sign'],
                     'margin':stage['sign']*(full['activation']['integrals'][0]-full['activation']['integrals'][1]),
                     'post_margin':stage['sign']*(post['activation']['integrals'][0]-post['activation']['integrals'][1]),
                     'full':full,'post':post,'raw':raw,'terminal':cued[5600000]}
                if stage['family']=='cut':row['groups']=''.join(stage['groups']) or 'none';cut.append(row)
                else:row['delay_s']=stage['delay_s'];waiting.append(row)
            if stage['family']=='cut' and not stage['groups']:
                previous=work/'r63o-reference'/parent['key']/f"sign{stage['sign']}/physical{int(stage['physical'])}"
                old_frames=read(previous/'input.json')['frames']
                clean=lambda rows:[{k:v[k] for k in ('enqueue_us','source','stimulus')} for v in rows]
                assert clean(frames)==clean(old_frames)
                a=curve(previous,parent['seed'],20200000);b=curve(folder,parent['seed'],20200000)
                diff=max(abs(a[t][f][i]-b[t][f][i]) for t in a for f in m.FIELDS for i in (0,1))
                assert diff<1e-9
                comparisons.append({'key':stage['key'],'max_process_error':diff,
                    'same_final_hash':result['final_sha256']==read(previous/'result.json')['final_sha256']})
        print(parent['key'],flush=True)
    assert counts=={'states':2352,'exchanges':128,'stages':752,'inputs':17888},counts
    assert len(comparisons)==64
    scores=r.measure.summarize(cut,waiting)
    stop=scores['scientific_stop'] or scores['measurement_stop']
    files=[p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&{'.research-records','publication','readback'}]
    analysis={'schema':'threemind.r63p-body-recovery/1','scores':scores,'cut_rows':cut,'waiting_rows':waiting,
        'r51r_sham_comparisons':comparisons,'intervention_changed_fields':dict(change_counts),
        'scientific_stop':stop,'timing':read(work/'summary.json'),'resources':read(work/'resource-summary.json'),
        'storage':{'logical_bytes':sum(p.stat().st_size for p in files),
                   'allocated_bytes':sum(r.compact.x.disk_allocation(p)['allocated_bytes'] for p in files)}}
    audit={'passed':True,'created_engines':0,'counts':dict(counts),'max_integral_error':error,
           'integral_decimal_precision':45,'scientific_stop':stop,'measurement_stop':scores['measurement_stop']}
    r.s.base.original(work/'analysis.json',analysis);r.s.base.original(work/'audit.json',audit)
    print(json.dumps({'audit':audit,'primary_weight_effects':scores['primary_weight_effects'],
                      'waiting_passed_cells':scores['waiting_passed_cells']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    analyze(p.parse_args().work.resolve())
