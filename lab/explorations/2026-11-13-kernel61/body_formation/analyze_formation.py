"""Read-only E21C input, intervention, complete-state and arithmetic audit."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study_formation as x


def read(p):
    raw=Path(p).read_bytes()
    return json.loads(gzip.decompress(raw) if str(p).endswith('.gz') else raw)


def curve(folder, seed):
    points=read(folder/'trajectory.json.gz')['points'];ids=x.x.identities(seed)
    result={p['time_us']-20200000:{f:[next((n.get(f,0.) for n in p['nodes'] if n['channel']==ids[k]),0.)
                                      for k in 'AB'] for f in x.measure.FIELDS} for p in points}
    assert sorted(result)==list(range(0,5600001,20000))
    return result


def analyze(work):
    x.check(work)
    assert not (work/'in-flight.json').exists() and read(work/'summary.json')['stages']==544
    counts=Counter();rows=[];max_error=0.;projection_error=0.;changes=Counter();references=[];prior_checks=[]
    def state(path):
        image=x.x.base.image(path);d=image.to_dict()
        assert d['dynamics']==x.spec.KERNEL
        assert d['config']['signal_threshold']==.0004 and d['config']['prune_weight']==.008
        assert d['config']['stp_facilitation_tau_s']==0.
        assert all(n['id']==n['channel'] for n in d['nodes'])
        birth=int(d['time_us'])==0 and not d['nodes'] and not d['edges']
        assert d['life']==('waiting' if birth else 'active')
        counts['states']+=1
        return image
    for parent in x.spec.parents():
        folder=work/'cases'/parent['key'];taught=None;observer=None
        for stage in x.spec.stages(parent):
            case=folder/stage['name'];r=read(case/'result.json')
            assert r['parent']==parent and r['stage']==stage and r['status']=='complete'
            assert r['calibration_seed'] is None and not r['prequeue_blank'] and not r['no_reconfigure']
            before,after=state(case/'initial.tmind'),state(case/'final.tmind')
            assert before.digest==r['initial_sha256'] and after.digest==r['final_sha256']
            bd,ad=before.to_dict(),after.to_dict()
            assert int(bd['time_us'])==stage['begin_us'] and int(ad['time_us'])==stage['end_us']
            if stage['kind']=='train':
                assert r['parent_sha256'] is None
                assert bd['config']==ad['config']
                assert bd['config']['depletion_enabled']==parent['teaching_depletion']
                assert bd['config']['context_enabled']==parent['teaching_competition']
                taught,observer=after.digest,read(case/'observer.json')
                teaching=state(case/'before-wait.tmind')
                assert int(teaching.to_dict()['time_us'])==19200000 and teaching.digest==r['snapshots']['before-wait']
                if parent['teaching_depletion'] and parent['teaching_competition']:
                    prior=work/'r51m-reference'/f"v61-{parent['seed']}-ordinary-{parent['mode']}"
                    prior_checks.append({'parent':parent['key'],'stage':'teaching',
                        'same_teaching_hash':teaching.digest==x.x.base.image(prior/'teaching/final.tmind').digest,
                        'same_wait_hash':after.digest==x.x.base.image(prior/'wait1/final.tmind').digest})
            else:
                assert before.digest==r['parent_sha256']==taught and read(case/'initial-observer.json')==observer
                intervention=read(case/'intervention.json');changed=state(case/'intervened.tmind');cd=changed.to_dict()
                assert intervention['method']=='public same-time reconfigure' and intervention['advanced_us']==0
                assert intervention['before_sha256']==before.digest and intervention['after_sha256']==changed.digest
                patch={'depletion_enabled':stage['test_depletion'],'context_enabled':stage['test_competition']}
                assert intervention['patch']==patch and cd['config']==ad['config']==(bd['config']|patch)
                assert intervention['changes']==x.x.differences(bd,cd)
                for field in ('time_us','queue','sequence','next_event','dynamics','life','silenced_nodes','silenced_edges'):
                    assert bd[field]==cd[field]
                assert [(e['source'],e['target']) for e in bd['edges']]==[(e['source'],e['target']) for e in cd['edges']]
                bp={n['id']:n for n in intervention['projected_before']};cp={n['id']:n for n in intervention['projected_after']}
                assert bp.keys()==cp.keys()
                for nid in bp:
                    projection_error=max(projection_error,*(abs(bp[nid][f]-cp[nid][f]) for f in x.measure.FIELDS))
                assert projection_error<1e-9
                changes.update(row['path'] for row in intervention['changes']);counts['interventions']+=1
            expected=x.x.inputs(parent,stage,work/'materials')
            assert read(case/'input.json')=={'frames':expected,'mappings':x.x.identities(parent['seed'])}
            delivered,scheduled=read(case/'delivered.json.gz'),read(case/'scheduled.json.gz')
            assert len(expected)==len(delivered)==len(scheduled)==r['inputs']
            by_event={}
            for target,receipt in zip(expected,scheduled):
                assert target['enqueue_us']==receipt['enqueue_us']
                assert target['source']==receipt['receipt']['source']
                assert int(target['stimulus']['time_us'])==int(receipt['receipt']['scheduled_time_us'])
                by_event[receipt['receipt']['core_event_id']]=receipt['enqueue_us']
            norm=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'))
            assert Counter(norm({k:r[k] for k in ('source','stimulus','enqueue_us')}) for r in expected)==Counter(
                norm({'source':r['source'],'stimulus':r['stimulus'],'enqueue_us':by_event[r['core_event_id']]}) for r in delivered)
            assert all(not r.get('labels') and int(r['stimulus']['time_us'])==int(r['scheduled_time_us'])==int(r['delivered_time_us']) for r in delivered)
            counts['inputs']+=len(delivered);counts['stages']+=1
        for stage in [st for st in x.spec.stages(parent)[1:] if st['physical']]:
            cued=curve(folder/stage['name'],parent['seed'])
            blank=curve(folder/(stage['name'].removesuffix('physical1')+'physical0'),parent['seed'])
            full,error=x.measure.integrate(cued,blank,0,5600000);max_error=max(error,max_error)
            post,error=x.measure.integrate(cued,blank,600000,5600000);max_error=max(error,max_error)
            zero={t:{f:[0.,0.] for f in x.measure.FIELDS} for t in cued}
            raw,error=x.measure.integrate(cued,zero,0,5600000);max_error=max(error,max_error)
            margin=(full['activation']['integrals'][0]-full['activation']['integrals'][1])*stage['sign']
            post_margin=(post['activation']['integrals'][0]-post['activation']['integrals'][1])*stage['sign']
            row={'seed':parent['seed'],'mode':parent['mode'],'learn_d':int(parent['teaching_depletion']),
                 'learn_c':int(parent['teaching_competition']),'test_d':int(stage['test_depletion']),
                 'test_c':int(stage['test_competition']),'sign':stage['sign'],'margin':margin,'post_margin':post_margin,
                 'full':full,'post':post,'raw':raw,'terminal':cued[5600000]}
            rows.append(row)
            if all(row[k] for k in ('learn_d','learn_c','test_d','test_c')):
                references.append(row)
                prior=work/'r51m-reference'/f"v61-{parent['seed']}-ordinary-{parent['mode']}"
                for which,old_name,current in (('cued',f"intact-{stage['sign']}",cued),('blank','intact-0',blank)):
                    previous=read(prior/old_name/'trajectory.json.gz')['points']
                    ids=x.x.identities(parent['seed']);error=0.
                    for point in previous:
                        t=point['time_us']-20200000
                        for f in x.measure.FIELDS:
                            for i,k in enumerate('AB'):
                                value=next((n.get(f,0.) for n in point['nodes'] if n['channel']==ids[k]),0.)
                                error=max(error,abs(current[t][f][i]-value))
                    prior_checks.append({'parent':parent['key'],'stage':stage['name'],'condition':which,
                        'common_sample_max_error':error})
        print(parent['key'],flush=True)
    assert counts=={'states':1632,'stages':544,'inputs':32544,'interventions':512},counts
    scores=x.measure.contrasts(rows)
    baseline=[]
    for mode in ('full','no_imu'):
        blocks=[]
        for seed in x.spec.SEEDS:
            selected=[r for r in references if r['seed']==seed and r['mode']==mode]
            assert len(selected)==2
            blocks.append({'seed':seed,'post_margins':[r['post_margin'] for r in selected],
                           'passed':all(r['post_margin']>1e-6 for r in selected)})
        baseline.append({'mode':mode,'blocks':blocks,'passed_blocks':sum(b['passed'] for b in blocks)})
    stop=not all(r['passed_blocks']>=3 for r in baseline) or scores['primary_effects_detected']==0
    files=[p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&{'.research-records','publication','readback'}]
    result={'schema':'threemind.r51r-body-formation/1','scores':scores,'rows':rows,'baseline':baseline,
            'scientific_stop':stop,'timing':read(work/'summary.json'),'resources':read(work/'resource-summary.json'),
            'intervention_changed_fields':dict(changes),'r51m_comparisons':prior_checks,
            'storage':{'logical_bytes':sum(p.stat().st_size for p in files),
                       'allocated_bytes':sum(x.disk_allocation(p)['allocated_bytes'] for p in files)}}
    audit={'passed':True,'created_engines':0,'counts':dict(counts),'max_integral_error':max_error,
           'same_time_projection_error':projection_error,'scientific_stop':stop,'integral_decimal_precision':45}
    x.s.base.original(work/'analysis.json',result);x.s.base.original(work/'audit.json',audit)
    print(json.dumps({'audit':audit,'primary_effects_detected':scores['primary_effects_detected'],'baseline':baseline}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    analyze(p.parse_args().work.resolve())
