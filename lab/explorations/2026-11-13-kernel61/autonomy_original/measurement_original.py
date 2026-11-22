"""Prespecified E15 arithmetic; no Core creation or simulation advancement."""
from decimal import Decimal, localcontext
import math
import statistics

EPS=.0001
SEEDS=(9293201,9293202)
PARENTS=tuple((seed,arm) for seed in SEEDS for arm in ('region0','region1'))
LOCAL=('normal','sham','task_edges','matched_edges','returns','restore','off')
PROTOCOLS=('none','single_high','single_ordinary','massed_ordinary','spaced_ordinary',
           'massed_weak','spaced_weak','spaced_no_consolidation')


def name(seed,arm):return f's{seed}/{arm}'


def area(rows,field,lo=0,hi=1000000):
    return math.fsum(max(0,min(b['relative_us'],hi)-max(a['relative_us'],lo))/1e6*field(a)
                     for a,b in zip(rows,rows[1:]))


def decimal_area(rows,field,lo=0,hi=1000000):
    with localcontext() as ctx:
        ctx.prec=50
        result=sum(Decimal(max(0,min(b['relative_us'],hi)-max(a['relative_us'],lo)))*
            Decimal.from_float(float(field(a)))/Decimal(1000000) for a,b in zip(rows,rows[1:]))
    return float(result)


def response_values(rows,channels):
    values={'motor':area(rows,lambda r:r['control'])}
    for key,ch in channels.items():
        values[key]=area(rows,lambda r:math.fsum(n['activation'] for n in r['nodes'] if n['channel']==ch))
    return values


def subtract(a,b):return {k:a[k]-b[k] for k in a}


def decide(local_rows,sequence_rows,environment_rows,sham_error):
    threshold=max(EPS,10*sham_error)
    parents=[];buckets=[[] for _ in range(4)]
    for seed,arm in PARENTS:
        identity=name(seed,arm)
        loc={r['condition']:r for r in local_rows if r['parent']==identity}
        history=loc['normal']['history_motor'];association=loc['normal']['history_association']
        causal=history-loc['off']['history_motor']
        sequence=statistics.mean(abs(r['communication_effect']) for r in sequence_rows if r['parent']==identity)
        environment=statistics.mean(abs(r['history_effect']['motor']) for r in environment_rows
            if r['parent']==identity and r['phase']==2 and r['mode']=='live')
        passed=[abs(history)>threshold and abs(association)>threshold,abs(causal)>threshold,
                sequence>threshold,environment>threshold]
        for index,flag in enumerate(passed):
            if flag:buckets[index].append(identity)
        target_loss=abs(history-loc['task_edges']['history_motor'])
        matched_loss=abs(history-loc['matched_edges']['history_motor'])
        parents.append({'parent':identity,'criteria':passed,'history_motor':history,
            'history_association':association,'communication_causal_effect':causal,
            'sequence_effect':sequence,'environment_effect':environment,
            'target_loss':target_loss,'matched_loss':matched_loss,
            'selective_target_effect':target_loss>matched_loss+threshold,
            'target_residual_fraction':abs(loc['task_edges']['history_motor'])/abs(history) if history else None})
    criteria=[{'criterion':i+1,'pass':len(bucket)>=3 and all(any(str(seed) in p for p in bucket) for seed in SEEDS),
               'passing_parents':bucket} for i,bucket in enumerate(buckets)]
    return {'version':'autonomy-criteria/1','threshold':threshold,'sham_error':sham_error,
        'criteria':criteria,'parent_results':parents,'meets_all':all(r['pass'] for r in criteria),
        'scientific_stop':not all(r['pass'] for r in criteria)}


def measure(load_rows,channels_for):
    local_rows=[];seq_rows=[];env_rows=[];memory_rows=[];extensions=[];texture=[]
    exact_shams=0;exact_restored=0;sham_error=0.;first_equal=0;decimal_error=0.
    def net(prefix,seed,cue='A'):
        nonlocal decimal_error
        a,b=load_rows(prefix+'/'+cue),load_rows(prefix+'/none')
        assert [r['relative_us'] for r in a]==[r['relative_us'] for r in b]
        for rows in (a,b):
            decimal_error=max(decimal_error,abs(area(rows,lambda r:r['control'])-decimal_area(rows,lambda r:r['control'])))
        return subtract(response_values(a,channels_for(seed)),response_values(b,channels_for(seed)))
    for seed,arm in PARENTS:
        prefix='local/'+name(seed,arm)
        for condition in LOCAL:
            p=net(prefix+'/P/'+condition,seed);q=net(prefix+'/Q/'+condition,seed)
            local_rows.append({'parent':name(seed,arm),'condition':condition,'P':p,'Q':q,
                'history_motor':p['motor']-q['motor'],'history_association':p['B']-p['D']-q['B']+q['D']})
        for history in ('P','Q'):
            for cue in ('A','none'):
                plain=load_rows(f'{prefix}/{history}/normal/{cue}')
                sham=load_rows(f'{prefix}/{history}/sham/{cue}')
                restored=load_rows(f'{prefix}/{history}/restore/{cue}')
                exact_shams+=plain==sham;exact_restored+=plain==restored
                sham_error=max(sham_error,abs(area(plain,lambda r:r['control'])-area(sham,lambda r:r['control'])))
            values={}
            for condition in ('normal','off'):
                path=f'sequence/{name(seed,arm)}/{history}/{condition}'
                cells={k:area(load_rows(path+'/'+k),lambda r:r['control'],500000,1500000) for k in ('00','01','10','11')}
                values[condition]={'cells':cells,'interaction':cells['11']-cells['10']-cells['01']+cells['00']}
            seq_rows.append({'parent':name(seed,arm),'history':history,**values,
                'communication_effect':values['normal']['interaction']-values['off']['interaction']})
        for changed,constant in (('PQP','PPP'),('QPQ','QQQ')):
            for phase in (1,2,3):
                for mode in (('live','birth') if phase==2 else ('live',)):
                    prefix='environment-probe/'+name(seed,arm)
                    a=f'{prefix}/{changed}/stage{phase}/{mode}';b=f'{prefix}/{constant}/stage{phase}/{mode}'
                    av=net(a,seed);bv=net(b,seed)
                    if phase==1:
                        first_equal+=all(load_rows(a+'/'+cue)==load_rows(b+'/'+cue) for cue in ('A','none'))
                    env_rows.append({'parent':name(seed,arm),'changed':changed,'constant':constant,
                        'phase':phase,'mode':mode,'changed_net':av,'constant_net':bv,'history_effect':subtract(av,bv)})
    for seed in SEEDS:
        for protocol in PROTOCOLS:
            for age in (1,30,300):
                for mode,condition in [('live','normal')]+([('birth',c) for c in ('normal','returns','off')] if age==300 else []):
                    value=net(f'memory-probe/s{seed}/{protocol}/age{age}/{mode}/{condition}',seed)
                    reference=net(f'memory-probe/s{seed}/none/age{age}/{mode}/{condition}',seed)
                    delta=subtract(value,reference)
                    memory_rows.append({'seed':seed,'protocol':protocol,'age_s':age,'mode':mode,'condition':condition,
                        'net':value,'no_training_net':reference,'training_effect':delta,'D_minus_B_effect':delta['D']-delta['B']})
        for protocol in ('none','single_high','massed_ordinary','spaced_ordinary','spaced_no_consolidation'):
            for condition in ('normal','task_edges','matched_edges','off'):
                value=net(f'retention-extension/s{seed}/{protocol}/{condition}',seed)
                ref=net(f'retention-extension/s{seed}/none/{condition}',seed)
                extensions.append({'seed':seed,'protocol':protocol,'condition':condition,'net':value,
                    'no_training_net':ref,'training_effect':subtract(value,ref)})
        for condition in ('intact','erase','matched_erase','novelty_off'):
            for index in range(4):
                path=f'novelty-probe/s{seed}/{condition}/round{index}'
                fixed=net(path,seed,'fixed');current=net(path,seed,'current')
                texture.append({'seed':seed,'condition':condition,'round':index,'changed_features':(0,1,2,4)[index],
                    'fixed_net':fixed,'current_net':current,'generalization_motor_difference':current['motor']-fixed['motor']})
    assert len(local_rows)==28 and len(seq_rows)==8 and len(env_rows)==32
    assert len(memory_rows)==96 and len(extensions)==40 and len(texture)==32
    return {'local':local_rows,'sequence':seq_rows,'environment':env_rows,'memory':memory_rows,
        'retention_extension':extensions,'texture':texture,
        'exact_shams':exact_shams,'exact_restored_trajectories':exact_restored,
        'exact_first_stage_pairs':first_equal,'maximum_decimal_motor_error':decimal_error,
        'decision':decide(local_rows,seq_rows,env_rows,sham_error)}


def arithmetic_check():
    rows=[{'relative_us':i*100000,'value':i*.1} for i in range(11)]
    observed=area(rows,lambda r:r['value'],250000,850000)
    reference=decimal_area(rows,lambda r:r['value'],250000,850000)
    assert math.isclose(observed,.3,abs_tol=1e-15) and abs(observed-reference)<1e-15
    local=[];sequence=[];environment=[]
    for seed,arm in PARENTS:
        identity=name(seed,arm)
        for condition in LOCAL:
            local.append({'parent':identity,'condition':condition,'history_motor':0. if condition in ('off','task_edges') else .01,
                          'history_association':.02})
        for history in ('P','Q'):sequence.append({'parent':identity,'history':history,'communication_effect':.01})
        for route in ('PQP','QPQ'):
            environment.append({'parent':identity,'phase':2,'mode':'live','history_effect':{'motor':.01},'route':route})
    assert decide(local,sequence,environment,0.)['meets_all']
    assert decide(local,sequence,environment,.002)['scientific_stop']
    for axis in range(4):
        import copy
        l,q,e=copy.deepcopy((local,sequence,environment))
        if axis==0:
            for r in l:r['history_association']=0.
        elif axis==1:
            for r in l:
                if r['condition']=='off':r['history_motor']=.01
        elif axis==2:
            for r in q:r['communication_effect']=0.
        else:
            for r in e:r['history_effect']['motor']=0.
        decision=decide(l,q,e,0.)
        assert decision['scientific_stop'] and not decision['criteria'][axis]['pass']
    return {'passed':True,'negative_targets_checked':4,'noise_fixture_checked':True,'created_engines':0}
