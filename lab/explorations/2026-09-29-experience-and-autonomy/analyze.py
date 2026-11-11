"""Prespecified time-weighted contrasts and complete checkpoint audit."""
import argparse
import gzip
import json
import math
import statistics
from collections import Counter

from common import WORK, Study, encoded, read_json
from experiment import PARENTS, SEEDS, LOCAL, PROTOCOLS, name, symbols, gzread
from threemind_core import StateImage

EPS=.0001

def result(key): return read_json(WORK/'cases'/key/'result.json')
def rows(key): return gzread(WORK/'cases'/key/'behavior.json.gz')['rows']

def area(series,fn,lo=0,hi=1_000_000):
    return math.fsum(max(0,min(b['relative_us'],hi)-max(a['relative_us'],lo))/1e6*fn(a)
                     for a,b in zip(series,series[1:]))

def value(row, channel): return math.fsum(n['activation'] for n in row['nodes'] if n['channel']==channel)

def net(key,none,seed,lo=0,hi=1_000_000):
    a,b=rows(key),rows(none)
    assert [r['relative_us'] for r in a]==[r['relative_us'] for r in b]
    values={'motor':area(a,lambda r:r['control'],lo,hi)-area(b,lambda r:r['control'],lo,hi)}
    for k,ch in symbols(seed).items():
        values[k]=area(a,lambda r:value(r,ch),lo,hi)-area(b,lambda r:value(r,ch),lo,hi)
    return values

def subtract(a,b): return {k:a[k]-b[k] for k in a}

def save(filename,value):
    (WORK/filename).write_bytes(encoded(value))
    return value

def local():
    output=[];sham=0;restored=0
    for seed,arm in PARENTS:
        for condition in LOCAL:
            prefix=f'local/{name(seed,arm)}'
            p=net(f'{prefix}/P/{condition}/A',f'{prefix}/P/{condition}/none',seed)
            q=net(f'{prefix}/Q/{condition}/A',f'{prefix}/Q/{condition}/none',seed)
            r={'parent':name(seed,arm),'condition':condition,'P':p,'Q':q,
               'history_motor':p['motor']-q['motor'],'history_association':p['B']-p['D']-q['B']+q['D']}
            output.append(r)
        for history in ('P','Q'):
            for cue in ('A','none'):
                base=f'{prefix}/{history}'
                assert rows(f'{base}/normal/{cue}')==rows(f'{base}/sham/{cue}')
                assert result(f'{base}/normal/{cue}')['state_sha256']==result(f'{base}/sham/{cue}')['state_sha256']
                assert rows(f'{base}/normal/{cue}')==rows(f'{base}/restore/{cue}')
                sham+=1;restored+=1
    return save('local-analysis.json',{'rows':output,'exact_shams':sham,'exact_restored_trajectories':restored})

def memory():
    output=[]
    for seed in SEEDS:
        for protocol in PROTOCOLS:
            for age in (1,30,300):
                conditions=[('live','normal')]+([('birth',k) for k in ('normal','returns','off')] if age==300 else [])
                for mode,condition in conditions:
                    prefix=f'memory-probe/s{seed}/{protocol}/age{age}/{mode}/{condition}'
                    base=f'memory-probe/s{seed}/none/age{age}/{mode}/{condition}'
                    a=net(prefix+'/A',prefix+'/none',seed)
                    b=net(base+'/A',base+'/none',seed)
                    delta=subtract(a,b)
                    output.append({'seed':seed,'protocol':protocol,'age_s':age,'mode':mode,'condition':condition,
                        'net':a,'no_training_net':b,'training_effect':delta,'D_minus_B_effect':delta['D']-delta['B']})
    return save('memory-analysis.json',output)

def sequence():
    output=[]
    for seed,arm in PARENTS:
        for history in ('P','Q'):
            values={}
            for condition in ('normal','off'):
                prefix=f'sequence/{name(seed,arm)}/{history}/{condition}'
                trials={k:rows(prefix+'/'+k) for k in ('00','01','10','11')}
                vals={k:area(v,lambda r:r['control'],500_000,1_500_000) for k,v in trials.items()}
                values[condition]={'cells':vals,'interaction':vals['11']-vals['10']-vals['01']+vals['00']}
            output.append({'parent':name(seed,arm),'history':history,**values,
                'communication_effect':values['normal']['interaction']-values['off']['interaction']})
    return save('sequence-analysis.json',output)

def environment():
    output=[];identical_first=0
    for seed,arm in PARENTS:
        prefix=f'environment-probe/{name(seed,arm)}'
        for changed,constant in (('PQP','PPP'),('QPQ','QQQ')):
            for phase in (1,2,3):
                for mode in (('live','birth') if phase==2 else ('live',)):
                    a=f'{prefix}/{changed}/stage{phase}/{mode}'
                    b=f'{prefix}/{constant}/stage{phase}/{mode}'
                    av=net(a+'/A',a+'/none',seed);bv=net(b+'/A',b+'/none',seed)
                    if phase==1:
                        assert rows(a+'/A')==rows(b+'/A') and rows(a+'/none')==rows(b+'/none')
                        identical_first+=1
                    output.append({'parent':name(seed,arm),'changed':changed,'constant':constant,'phase':phase,
                                   'mode':mode,'changed_net':av,'constant_net':bv,'history_effect':subtract(av,bv)})
    return save('environment-analysis.json',{'rows':output,'exact_first_stage_pairs':identical_first})

def novelty():
    output=[];variability=[]
    for seed in SEEDS:
        for condition in ('intact','erase','matched_erase','novelty_off'):
            net_fixed=[]
            for index in range(4):
                prefix=f'novelty-probe/s{seed}/{condition}/round{index}'
                fixed=net(prefix+'/fixed',prefix+'/none',seed)
                current=net(prefix+'/current',prefix+'/none',seed)
                base=f'novelty/s{seed}/{condition}/round{index}'
                before=gzread(WORK/'cases'/base/'before-training.json.gz')
                after=gzread(WORK/'cases'/base/'before-erasure.json.gz')
                old={(e['source'],e['target']):e for e in before['edges']}
                added=[e for e in after['edges'] if (e['source'],e['target']) not in old]
                removed=[e for e in old if e not in {(v['source'],v['target']) for v in after['edges']}]
                first=gzread(WORK/'cases'/base/'first-response.json.gz')['rows']
                net_fixed.append(fixed['motor'])
                output.append({'seed':seed,'condition':condition,'round':index,'changed_features':(0,1,2,4)[index],
                    'fixed_net':fixed,'current_net':current,'generalization_motor_difference':current['motor']-fixed['motor'],
                    'first_motor_auc':area(first,lambda r:r['control'],0,990_000),
                    'new_edge_count':len(added),'lost_edge_count':len(removed),
                    'new_mean_weight':statistics.mean(e['weight'] for e in added) if added else 0,
                    'new_mean_stability':statistics.mean(e['stability'] for e in added) if added else 0,
                    'erased_count':len(result(base)['extra']['edges_selected']) if condition in ('erase','matched_erase') else 0})
            variability.append({'seed':seed,'condition':condition,'fixed_motor_series':net_fixed,
                                'range':max(net_fixed)-min(net_fixed),'sd':statistics.pstdev(net_fixed)})
    return save('novelty-analysis.json',{'rows':output,'variability':variability})

def decisions(local_data, seq_data, env_data):
    criteria=[]
    passed1=[];passed2=[];passed3=[];passed4=[]
    details=[]
    for seed,arm in PARENTS:
        parent=name(seed,arm)
        loc={r['condition']:r for r in local_data['rows'] if r['parent']==parent}
        p1=abs(loc['normal']['history_motor'])>EPS and abs(loc['normal']['history_association'])>EPS
        p2=abs(loc['normal']['history_motor']-loc['off']['history_motor'])>EPS
        seq=[r for r in seq_data if r['parent']==parent]
        seq_effect=statistics.mean(abs(r['communication_effect']) for r in seq)
        env=[r for r in env_data['rows'] if r['parent']==parent and r['phase']==2 and r['mode']=='live']
        env_effect=statistics.mean(abs(r['history_effect']['motor']) for r in env)
        p3=seq_effect>EPS;p4=env_effect>EPS
        for flag,bucket in ((p1,passed1),(p2,passed2),(p3,passed3),(p4,passed4)):
            if flag: bucket.append(parent)
        details.append({'parent':parent,'criteria':[p1,p2,p3,p4],'history_motor':loc['normal']['history_motor'],
                        'sequence_effect':seq_effect,'environment_effect':env_effect})
    for i,bucket in enumerate((passed1,passed2,passed3,passed4),1):
        ok=len(bucket)>=3 and all(any(str(seed) in p for p in bucket) for seed in SEEDS)
        criteria.append({'criterion':i,'pass':ok,'passing_parents':bucket})
    return save('criteria-decision.json',{'version':'autonomy-criteria/1','threshold':EPS,'criteria':criteria,
        'meets_all':all(r['pass'] for r in criteria),'parent_results':details,
        'meaning':'Project operational conclusion; not a measurement of subjective experience'})

def audit(study):
    counts=Counter();classifications=Counter();wall=0;failures=[];config_checks=0
    for path in sorted((WORK/'cases').rglob('result.json')):
        r=read_json(path);counts[r['extra'].get('stage','unknown')]+=1;wall+=r['wall_seconds']
        image=StateImage(gzip.decompress((path.parent/'parent-state.json.gz').read_bytes()))
        assert image.digest==r['state_sha256']
        _,dbimage=study.db.load_checkpoint(study.project,r['id'])
        assert dbimage.digest==image.digest and dbimage.to_dict()==image.to_dict()
        assert not r['extra'].get('budget_stop'),r['key']
        assert image.to_dict()['energy']['unserved_total']==0
        c=image.to_dict()['config']
        for key in ('inhibition','plasticity','activation_decay_enabled','stability_decay_enabled','eligibility_decay_enabled',
                    'support_decay_enabled','depletion_enabled','stp_enabled','energy_simulation_enabled'):
            assert c[key],(r['key'],key)
        assert c['forgetting_rate']>0 and c['propagation_interval_us']==100000
        config_checks+=1
        windows=[]
        for line in gzip.decompress((path.parent/'events.jsonl.gz').read_bytes()).splitlines():
            event=json.loads(line)
            if event['kind']=='temporal_readout':
                w=event['payload'];classifications[w['classification']]+=1
                w['end_activation_ranking']=sorted(w['nodes'],key=lambda n:(-n['last_activation'],n['node_id']))
                windows.append(w)
        out=path.parent/'temporal-end-ranking.json.gz'
        if windows and not out.exists():
            with gzip.open(out,'xb') as f:f.write(encoded(windows))
    expected=722+(read_json(WORK/'retention-extension-registration.json')['additional_instances']
                  if (WORK/'retention-extension-registration.json').exists() else 0)
    assert sum(counts.values())==expected,counts
    return save('analysis.json',{'cases':sum(counts.values()),'counts':dict(counts),'compute_seconds':wall,
        'kernel_unchanged':True,'full_database_state_verified':sum(counts.values()),'preserved_mechanism_checks':config_checks,
        'temporal_classifications':dict(classifications),'failures':failures})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('local','memory','sequence','environment','novelty','all','audit'))
    command=parser.parse_args().command
    if command=='audit':
        study=Study()
        try: print(json.dumps(audit(study)),flush=True)
        finally: study.db.close()
    elif command=='all':
        a=local();memory();b=sequence();c=environment();novelty()
        print(json.dumps(decisions(a,b,c)),flush=True)
    else:
        v=globals()[command]()
        print(json.dumps(v),flush=True)

if __name__=='__main__':main()
