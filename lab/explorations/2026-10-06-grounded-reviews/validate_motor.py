"""Predeclared whole-demonstration validation; no test labels or Core execution."""
import argparse
import json
import hashlib
import shutil
import numpy as np
from experiment import ROOT,WORK,Case,study,read_json,new_json,ActivityController,device


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--test-if-qualified',action='store_true')
    p.add_argument('--exploratory-task-test',action='store_true',help='Registered one-off task test; does not change the failed validation gate')
    a=p.parse_args()
    s=study()
    try:
        if a.test_if_qualified or a.exploratory_task_test:
            from motor import test
            result=read_json(WORK/'cases/s223-motor-validation/result.json')
            s.allow_extension()
            expected=read_json(WORK/'cases/s223-motor-test-episode-normal/result.json')['wall_seconds']*1.2
            if (not result['passed_registered_gate'] and not a.exploratory_task_test) or s.completed_wall+expected>s.settings.wall_seconds:
                print(json.dumps({'new_motor_tests_started':False,'reason':'registered validation gate or remaining budget'}));return
            test(s,'episode','normal',validated=True);return
        case=Case(s,'s223-motor-validation');parent=WORK/'cases/s223-motor-teaching'
        rel='lab/tools/activity_controller.py';source=ROOT/rel;dest=case.path/'used-tools'/rel
        dest.parent.mkdir(parents=True);shutil.copy2(source,dest)
        new_json(case.path/'tool-sources.json',{rel:hashlib.sha256(source.read_bytes()).hexdigest()})
        data=np.load(parent/'episode.npz',allow_pickle=False);schedule=read_json(parent/'schedule.json')
        if len(data['x'])!=len(schedule)*10:raise ValueError('ten samples per complete demonstration')
        held=np.repeat([r['presentation']==15 for r in schedule],10)
        if held.sum()!=120:raise ValueError('registered twelve final demonstrations')
        x,y=data['x'],data['y'];baseline=float(np.mean((y[held]-y[~held].mean(axis=0))**2))
        head=ActivityController(x.shape[-1],2,regression=True,seed=223).to(device())
        fit=head.fit(x[~held],y[~held],validation=(x[held],y[held]),steps=1500,check=s.guard)
        head.save(case.path/'controller',read_json(parent/'layout.json'))
        accepted=fit['loss']<=.05 and fit['loss']<=.8*baseline
        case.finish({'kind':'motor-validation','fit':fit,'constant_action_validation_loss':baseline,
                     'passed_registered_gate':accepted,'held_lesson_indices':np.where(held[::10])[0].tolist()})
    finally:s.db.close()


if __name__=='__main__':main()
