"""New origins/materials for gain-aware prediction; old failed batch untouched."""
import copy
import m2_threshold_rig as prior
from m2_threshold_predictor import predict as old_predict
from m2_gain_predictor import predict
from m2_relearning_cal_driver import lesson,save
import closure_rig as g
import pilot_m2 as m

N=8
SEEDS=tuple(range(1120100,1120108))
APPARATUS_SEED=1120002
TEST_SEED=1120004
DELAYS=(.5,1.5)
DOSES=(0.,.51,.59,.65,.77)


def cases():
    return [{'origin':i,'seed':s,'mode':'S','lessons':16,'lesson_dose':.4,
             'delays':list(DELAYS),'doses':list(DOSES)} for i,s in enumerate(SEEDS)]


def unit(folder,origin):
    case=cases()[origin];root=g.Rig('threemind',case['seed'],'S');save(folder,'birth',root)
    g.teaching(root,0,delay=30,trained=False);save(folder,'age47',root)
    baseline=g.probe(root,'X',.4);save(folder,'baseline',root);histories=[]
    for history in (0,1):
        parent=root.fork('h'+str(history));save(folder,f'h{history}-initial',parent);lessons=[]
        for j in range(1,17):
            lessons.append({'lesson':j,**lesson(parent,history,.4),'checkpoint':save(folder,f'h{history}-lesson{j:02d}',parent)})
        tests=[];waits=[]
        for delay in DELAYS:
            child=parent.fork(f'h{history}-delay{delay}');begin=child.time;wait_us=int(delay*1e6)
            child.advance(begin+wait_us,{begin+t:{'K':.2} for t in range(500000,wait_us+1,500000)})
            waits.append({'delay':delay,'checkpoint':save(folder,f'h{history}-delay{delay}',child)})
            for dose in DOSES:
                label=f'h{history}-d{delay}-q{dose:.2f}';trial=child.fork(label)
                initial=save(folder,label+'-initial',trial)
                prediction=predict(trial.save(),dose);comparison=old_predict(trial.save(),dose)
                m.original(folder/(label+'-prediction.json'),{'gain_aware':prediction,'original':comparison})
                measured=prior.probe(trial,dose);final=save(folder,label+'-final',trial)
                tests.append({'history':history,'delay':delay,'dose':dose,'initial':initial,'checkpoint':final,
                              'prediction':prediction,'comparison':comparison,'probe':measured})
            assert waits[-1]['checkpoint']['sha256']==save(folder,f'h{history}-delay{delay}',child)['sha256']
        histories.append({'history':history,'lessons':lessons,'delays':waits,'tests':tests})
    return {'origin':origin,'case':case,'histories':histories,'baseline':baseline,'valid':True,'scientific_origins':1}


def instrument(folder,seed=APPARATUS_SEED):
    parent,_=prior.cultivated(seed,folder/'cultivation',0);hashes={};checks=[]
    for mode in ('plain','observed','restored','paused'):
        child=g.Rig.restore(parent.save());p=predict(child.save(),.8)
        result=prior.probe(child,.8,frequent=mode=='observed',restore_mid=mode=='restored',pause_mid=mode=='paused')
        save(folder,mode,child);hashes[mode]=m.digest(child.save())
        checks.append({'mode':mode,'direction_equal':p['direction']==result['direction'],
                       'absolute_error':abs(p['endpoint']-result['first'])})
    return {'passed':len(set(hashes.values()))==1 and all(r['direction_equal'] and r['absolute_error']<=1e-6 for r in checks),
            'whole_hashes':hashes,'checks':checks,'scientific_origins':0,'seed':seed,'unseen_conditions_used':False}
