"""Preregistered alternative: raw process predicts posture, physical servo executes.

No target, words, object inventory or task labels are passed at inference.
This is explicitly a different external motor architecture, not a Core change.
"""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('e61',HERE/'experiment.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
e.TAG='gain01-';e.ACTIVITY_GAIN=.1
from lab.tools.service_study import read_json,new_json,write_gzip,encoded
from lab.tools.continuous_motor import ContinuousMotor


def labels(key):
    poses=[]
    with gzip.open(e.WORK/'cases'/key/'process.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            rec=json.loads(line)
            if rec['kind']!='teacher':continue
            for i in range(1,len(rec['process'])):
                if i<10 or i%2==0:
                    poses.append(rec['scoring_only_eye_targets'][i]+rec['scoring_only_hand_targets'][i])
    return np.array(poses,dtype=np.float32)/[.35,.35,1,1]


def fit(s,source,group):
    def execute(p):
        train=f'B-gain01-{source}-{group}';val=f'V-gain01-{source}-{group}'
        x=np.load(e.WORK/'cases'/train/'features.npz')['activity'];vx=np.load(e.WORK/'cases'/val/'features.npz')['activity']
        y=labels(train);vy=labels(val)
        if len(x)!=len(y) or len(vx)!=len(vy):raise ValueError('pose labels must align with original prior-state demonstration windows')
        head=ContinuousMotor(read_json(e.WORK/'cases'/train/'layout.json'),readout_version=2).to(e.e60.device())
        result=head.fit(x,y,validation=(vx,vy),steps=1600,check=s.guard)
        head.save(p/'controller');manifest=p/'controller/manifest.json';m=read_json(manifest)
        # Keep this model distinguishable from a force model. Dedicated loader only.
        m['schema']='threemind.posture-motor/1';m['outputs']=['eye_yaw_fraction','eye_pitch_fraction','hand_x_m','hand_y_m']
        m['physical_scales']=[.35,.35,1,1];manifest.write_bytes(encoded(m))
        return {'source':source,'group':group,'fit':result,'architecture':'posture plus physical servo'}
    return e.run(s,f'P-fit-{source}-{group}',execute)


class Servo:
    def __init__(self,path,world):
        from safetensors.torch import load_file
        m=read_json(path/'manifest.json')
        if m['schema']!='threemind.posture-motor/1':raise ValueError('posture protocol required')
        self.head=ContinuousMotor(m['channels'],seed=m['seed'],readout_version=2).to(e.e60.device())
        self.head.load_state_dict(load_file(str(path/'model.safetensors')),strict=True);self.head.eval()
        self.world=world;self.scales=np.array(m['physical_scales'])

    def action(self,raw):
        if not np.any(raw):return np.zeros(4)
        target=self.head.action(raw)*self.scales
        # Reuse the calibrated body PD equation. Despite its historical name,
        # teacher_action reads only body state and this predicted target; no
        # teacher or scoring target is available to the inference path.
        return np.r_[self.world.eye_servo(target[:2]),self.world.pointer.teacher_action(target[2:])]


def evaluate(s,source,group,mode='normal'):
    if mode not in ('normal','silence','rescue','empty'):raise ValueError('registered connection/command control')
    key=f'P-test-{source}-{group}'+('' if mode=='normal' else '-'+mode)
    def execute(p):
        saved=e.e60.read_gzip(e.WORK/'cases'/f'B-gain01-{source}-{group}'/'checkpoint.json.gz');results=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for i in range(12):
                c=e.instance(s,state=saved);e.classroom(c);head=Servo(e.WORK/'cases'/f'P-fit-{source}-{group}'/'controller',c.world)
                if mode in ('silence','rescue'):
                    pairs=[(edge['source'],edge['target']) for edge in saved['core']['edges']]
                    c.engine.intervene(edges=pairs,action='silence')
                    if mode=='rescue':c.engine.intervene(edges=pairs,action='unsilence')
                rec,_=e.e60.lesson(s,c,e.e60.task(i,'test',e.e60.MODES[i%4]),assist=False,head=head,seconds=6,retarget=True,intervention=mode)
                rec['action_source']='原始活动→姿态外设→物理伺服；非直接力主对照；'+mode
                for row in rec['process']:row['action_source']=rec['action_source']
                results.append(e.phase_metrics(rec));out.write(encoded(rec).decode()+'\n')
                if i==0:write_gzip(p/'first-end-state.json.gz',c.snapshot())
        new_json(p/'trials.json',results)
        eye=[p for r in results if r['mode'] in ('look','both') for p in r['phases']]
        hand=[p for r in results if r['mode'] in ('point','both') for p in r['phases']]
        return {'source':source,'group':group,'mode':mode,'n':12,**e.e60.summarize(results),
            'eye_enter_and_finish':sum(p['eye_entered'] and p['eye_ended_aligned'] for p in eye),
            'hand_enter_and_finish':sum(p['hand_entered'] and p['hand_ended_arrived'] for p in hand),
            'scope':'registered architecture diagnostic on the same prototype questions, not a new blind benchmark'}
    return e.run(s,key,execute)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=int,choices=[0,1],default=0);p.add_argument('--group',choices=e.GROUPS,default='explore');p.add_argument('--mode',choices=['normal','silence','rescue','empty'],default='normal');a=p.parse_args()
    s=e.study()
    try:s.allow_extension();fit(s,a.source,a.group);evaluate(s,a.source,a.group,a.mode)
    finally:s.db.close()


if __name__=='__main__':main()
