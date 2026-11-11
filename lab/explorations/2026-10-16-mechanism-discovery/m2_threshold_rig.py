"""Preregistered resource-state interventions on independent complete research copies."""
import copy
import time
import closure_rig as g
from m2_relearning_cal_driver import lesson,save
from m2_threshold_predictor import predict
import pilot_m2 as m

N=8
SEEDS=tuple(range(1118100,1118108))
APPARATUS_SEED=1118002
TEST_SEED=1118004
DELAYS=(0,2)
ARMS=('intact','target-empty','target-full','matched-empty','matched-full','restored')
CAUSAL_DOSES=(0.,.55,.8)
NOVEL_DOSES=(.47,.57,.63,.73)


def cases():
    return [{'origin':i,'seed':s,'mode':'S','lessons':16,'lesson_dose':.4,'delays':list(DELAYS),
             'causal_doses':list(CAUSAL_DOSES),'novel_doses':list(NOVEL_DOSES)} for i,s in enumerate(SEEDS)]


def select(whole):
    model=whole['model'];nodes={n['channel']:n for n in model['nodes']};n=nodes[whole['mappings']['X']]
    byid={x['id']:x for x in model['nodes']};edges=model['edges']
    targets=[e for e in edges if e['source']==n['id']]
    matched=[e for e in edges if n['id'] not in (e['source'],e['target'])]
    assert len(targets)==len(matched)==2
    # All candidate edges are retained; pairing minimizes the two possible nuisance residuals.
    def features(e):
        return [e['weight'],sum(x['source']==e['source'] for x in edges),sum(x['target']==e['source'] for x in edges),
                sum(x['source']==e['target'] for x in edges),sum(x['target']==e['target'] for x in edges),
                byid[e['source']]['activation'],byid[e['target']]['activation']]
    choices=[]
    for ordered in (matched,matched[::-1]):
        pairs=[{'target':[a['source'],a['target']],'matched':[b['source'],b['target']],
                'residual':[abs(x-y) for x,y in zip(features(a),features(b))]} for a,b in zip(targets,ordered)]
        choices.append((max(x['residual'][0] for x in pairs),pairs))
    pairs=min(choices,key=lambda x:x[0])[1]
    assert all(x['residual'][0]<=.01 and all(v==0 for v in x['residual'][1:]) for x in pairs)
    return {'pairs':pairs,'calipers':{'weight':.01,'each_degree':0,'each_activation':0},
            'selection':'all two outgoing X edges; nonincident two-edge matched set, no test results used'}


def arm(parent,name,label,selection):
    child=parent.fork(label);reference=child.save();modified=copy.deepcopy(reference)
    keys={tuple(x['matched' if name.startswith('matched') else 'target']) for x in selection['pairs']}
    changed=[]
    if name!='intact':
        full=name.endswith('full')
        for e in modified['model']['edges']:
            if (e['source'],e['target']) in keys:
                before=copy.deepcopy(e['short_term'])
                e['short_term']={'available':1. if full else 0.,'active':0.,
                                'utilization':modified['model']['config']['stp_utilization'],
                                'time_us':str(parent.time)}
                changed.append({'edge':[e['source'],e['target']],'before':before,'after':copy.deepcopy(e['short_term'])})
        assert len(changed)==2
        child=g.Rig.restore(modified)
    receipt={'arm':name,'parent_sha256':m.digest(parent.save()),'reference_sha256':m.digest(reference),
             'modified_sha256':m.digest(child.save()),'changed_short_term_bundles':changed,
             'persistent_weights_changed':False,'Core_config_changed':False}
    if name=='restored':
        child=g.Rig.restore(reference);receipt['restored_exact']=child.save()==reference
        assert receipt['restored_exact']
    return child,receipt


def probe(child,dose,*,frequent=False,restore_mid=False,pause_mid=False):
    start=child.time;initial=len(child.rows)
    child.tick(start,{'X':dose} if dose else {})
    for dt in range(1000,150001,1000):
        child.tick(start+dt,frequent=frequent)
        child.rows.append({'time_us':child.time,'response':child.actuator,'body':copy.deepcopy(child.body)})
        if dt==50000:
            if restore_mid:
                restored=g.Rig.restore(child.save());child.__dict__.update(restored.__dict__)
            if pause_mid:
                before=child.save();time.sleep(.03);assert child.save()==before
    rows=child.rows[initial:];first=next(x['response'] for x in rows if x['time_us']==start+110000)
    return {'start_us':start,'end_us':child.time,'first':first,'direction':int(first>1e-4)-int(first<-1e-4),
            'trace_count':len(rows),'final_sha256':m.digest(child.save())}


def cultivated(seed,folder,history):
    p=g.Rig('threemind',seed,'S');save(folder,'birth',p)
    g.teaching(p,0,delay=30,trained=False);save(folder,'age47',p)
    baseline=g.probe(p,'X',.4);save(folder,'baseline',p)
    rows=[]
    for j in range(1,17):
        rows.append({'lesson':j,**lesson(p,history,.4),'checkpoint':save(folder,f'lesson{j:02d}',p)})
    assert p.time==104500000
    return p,{'baseline':baseline,'lessons':rows}


def unit(folder,origin):
    case=cases()[origin]
    # Histories share the declared birth origin; all later copies are nested observations.
    root=g.Rig('threemind',case['seed'],'S');save(folder,'birth',root)
    g.teaching(root,0,delay=30,trained=False);save(folder,'age47',root)
    baseline=g.probe(root,'X',.4);save(folder,'baseline',root)
    histories=[]
    for history in (0,1):
        parent=root.fork('h'+str(history));save(folder,f'h{history}-initial',parent);lessons=[]
        for j in range(1,17):
            lessons.append({'lesson':j,**lesson(parent,history,.4),'checkpoint':save(folder,f'h{history}-lesson{j:02d}',parent)})
        assert parent.time==104500000
        tests=[];delay_states=[]
        for delay in DELAYS:
            cohort=parent.fork(f'h{history}-delay{delay}');begin=cohort.time
            cohort.advance(begin+delay*1000000,{begin+t:{'K':.2} for t in range(500000,delay*1000000+1,500000)})
            checkpoint=save(folder,f'h{history}-delay{delay}',cohort);selection=select(cohort.save())
            delay_states.append({'delay':delay,'checkpoint':checkpoint,'selection':selection})
            for name in ARMS:
                doses=CAUSAL_DOSES+NOVEL_DOSES if name=='intact' else CAUSAL_DOSES
                for dose in doses:
                    label=f'h{history}-d{delay}-{name}-q{dose:.2f}'
                    child,receipt=arm(cohort,name,label,selection)
                    initial=save(folder,label+'-initial',child)
                    prediction=predict(child.save(),dose)
                    # This exclusive original exists before any diagnostic input is injected.
                    m.original(folder/(label+'-prediction.json'),prediction)
                    measured=probe(child,dose);final=save(folder,label+'-final',child)
                    tests.append({'history':history,'delay':delay,'arm':name,'dose':dose,'novel':dose in NOVEL_DOSES,
                                  'initial':initial,'checkpoint':final,'prediction':prediction,'probe':measured,'intervention':receipt})
            assert checkpoint['sha256']==save(folder,f'h{history}-delay{delay}',cohort)['sha256']
        histories.append({'history':history,'lessons':lessons,'delays':delay_states,'tests':tests})
    return {'origin':origin,'case':case,'baseline':baseline,'histories':histories,'valid':True,'scientific_origins':1}


def instrument(folder,seed=APPARATUS_SEED):
    parent,_=cultivated(seed,folder/'cultivation',0);selection=select(parent.save());hashes={};checks=[]
    for mode in ('plain','observed','restored','paused'):
        child=g.Rig.restore(parent.save());probe(child,.8,frequent=mode=='observed',restore_mid=mode=='restored',pause_mid=mode=='paused')
        save(folder,mode,child);hashes[mode]=m.digest(child.save())
    for name in ARMS:
        child,r=arm(parent,name,'instrument-'+name,selection);save(folder,name+'-initial',child)
        p=predict(child.save(),.8);result=probe(child,.8);save(folder,name+'-final',child)
        checks.append({'arm':name,'intervention':r,'prediction':p,'probe':result})
    return {'passed':len(set(hashes.values()))==1 and all(x['prediction']['direction']==x['probe']['direction'] for x in checks),
            'whole_hashes':hashes,'selection':selection,'checks':checks,'scientific_origins':0,'seed':seed,
            'unseen_scientific_doses_used':False}
