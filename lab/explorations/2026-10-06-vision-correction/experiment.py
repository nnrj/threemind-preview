"""E56 staged optical resolution and corrective teaching; unchanged Core."""
import argparse
from dataclasses import replace
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import time
import weakref
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from threemind_core import StateImage
from threemind_runtime.host import create_engine
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.activity_stream import RawActivityStream
from threemind_runtime.sensory import TextSensor,TextSensorConfig
from lab.tools.classroom_eye import DetailedClassroom,VERSION
from lab.tools.shape_color_world import POSITIONS,SHAPES,COLORS,Pointer
from lab.tools.activity_controller import ActivityLayout,ActivityController
from lab.tools.service_study import Study,StudyConfig,new_json,read_json,write_gzip,encoded

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/vision-correction-20261006'
spec=importlib.util.spec_from_file_location('e55_reference',HERE.parent/'2026-10-06-grounded-reviews/experiment.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
# Reuse tested scheduling/observation and case wrappers in the NEW study only.
previous.WORK=WORK;previous.VERSION=VERSION
Case=previous.Case;read_gzip=previous.read_gzip;device=previous.device
DT=50000


class ExperimentStudy(Study):
    def __init__(self,*args,**kwargs):
        self.stopped_wall=sum(read_json(p)['wall_seconds'] for p in (WORK/'cases').glob('*/stopped.json'))
        super().__init__(*args,**kwargs)

    def guard(self,force=False):
        super().guard(force)
        active=time.monotonic()-self.active_case.born_wall if self.active_case else 0
        if self.completed_wall+self.stopped_wall+active>self.settings.wall_seconds:
            raise RuntimeError('aggregate budget including deliberately stopped cases')


def study(prepare=False):
    return ExperimentStudy(StudyConfig('vision-correction/1','E56 视觉分辨率与纠错指向',HERE,WORK,68,
           instance_limit=600,wall_seconds=9000,storage_soft=6*2**30,storage_hard=8*2**30,
           usage_soft_delta=5,usage_hard_delta=8),prepare=prepare)


class Classroom(previous.Classroom):
    def __init__(self,resolution=4,state=None,image=None,*,plasticity=True):
        counter=WORK/'instances.json';n=read_json(counter)['created']
        if n>=600:raise RuntimeError('creation limit')
        counter.write_bytes(encoded({'created':n+1}))
        self.world=DetailedClassroom.restore(state['world']) if state else DetailedClassroom(91,resolution=resolution)
        self.engine=create_engine(None if state else {'seed':223,'plasticity':plasticity},state=(image or StateImage(encoded(state['core']))) if state else None,
              kernel_id=state['core']['dynamics'] if state else 'threemind.continuous-memory/2')
        self.reader=ReadoutSession(self.engine,record=lambda row:None,config={
              'structural_readout':{'enabled':False},'temporal_readout':{'enabled':False},'activity_readout':{'enabled':False}},
              state=state['reader'] if state else None)
        self.sensor=TextSensor(91,TextSensorConfig(frame_characters=1,frame_interval_us=DT))
        self.stream=RawActivityStream();self.current=None
        owner=weakref.ref(self)
        def receive(frame):
            current=owner()
            if current is not None:current.current=frame
        self.stream.subscribe('E56-raw-observer',receive)


def request(c,text,guard):
    frames=list(c.sensor.frames(text))
    if len(frames)>30:raise ValueError('complete sentence requires longer reservation')
    return [c.tick(f,guard=guard) for f in frames]+[c.tick(guard=guard) for _ in range(max(0,20-len(frames)))]


def features(c,rows): return previous.window(c.layout(),rows,count=8)


def set_task(c,task):
    c.world.set_scene(task['items'],task['variant']);c.world.marker=None
    c.world.pointer=Pointer(*task['start']);c.world.acceleration=[0.,0.];c.world.motor_power=0.


def tasks(split):
    # Every scene receives all four requests; scene identity cannot predict slot.
    count=4 if split=='calibration' else 1 if split=='practice' else 2
    offset={'calibration':0,'practice':100,'test':200}[split]
    rows=[]
    for category in ('color','shape','pair'):
        for scene in range(count):
            rng=np.random.default_rng(7201+offset+scene*29+('color','shape','pair').index(category)*211)
            order=rng.permutation(4).tolist()
            if category=='color':items=[(2,c) for c in order]
            elif category=='shape':items=[(s,4) for s in order]
            else:
                s=scene%4;col=(scene+1)%4
                source=[(s,col),(s,(col+1)%4),((s+1)%4,col),((s+1)%4,(col+1)%4)]
                items=[source[i] for i in order]
            variant=scene if split=='calibration' else 4 if split=='practice' else 5+scene
            start=rng.uniform(-.85,.85,2).tolist()
            for slot,(shape,color) in enumerate(items):
                noun=COLORS[color]+'的物体' if category=='color' else SHAPES[shape] if category=='shape' else COLORS[color]+'的'+SHAPES[shape]
                rows.append({'category':category,'scene':scene,'slot':slot,'items':items,'variant':variant,
                     'start':start,'text':f'请指出{noun}。','statement':f'这是{noun}。','split':split})
    return rows


def teach(s,n,*,source='teach',plasticity=True):
    case=Case(s,f'r{n}-{source}');c=Classroom(n,plasticity=plasticity);schedule=[]
    for item in range(8):
        for rep in range(10):schedule.append((item,rep,0))
    for review in range(3):
        for item in range(8):schedule.append((item,10+review,review+1))
    rowspec=[]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
        for index,(item,rep,review) in enumerate(schedule):
            # Per-concept review gaps expand via actual bodily/environmental time.
            if index in (80,88,96):
                for _ in range((0,6,18)[review-1]*20):
                    c.world.marker=None;out.write(encoded({'kind':'interval','process':[c.tick(guard=s.guard)]}).decode()+'\n')
            cat=int(item>=4);value=item%4
            order=np.roll(np.arange(4),(rep+value)%4).tolist()
            items=[(2,v) if cat else (v,4) for v in order];slot=order.index(value)
            c.world.set_scene(items,rep%4);c.world.marker=list(POSITIONS[slot])
            noun=COLORS[value]+'的物体' if cat else SHAPES[value]
            task={'category':'color' if cat else 'shape','items':items,'slot':slot,'variant':rep%4,
                    'text':f'这是{noun}。','item':item,'rep':rep,'review':review}
            frames=list(c.sensor.frames(task['text']));rows=[c.tick(f,guard=s.guard) for f in frames]
            rows.extend(c.tick(guard=s.guard) for _ in range(30-len(rows)))
            rowspec.append(task)
            out.write(encoded({'kind':'lesson','lesson':task,'process':rows}).decode()+'\n')
            if index%16==0:print(json.dumps({'stage':case.path.name,'lesson':index,'of':104,'sim_s':c.engine.time_us/1e6}),flush=True)
    write_gzip(case.path/'checkpoint.json.gz',c.snapshot());new_json(case.path/'schedule.json',rowspec)
    new_json(case.path/'protocol.json',{'world':c.world.state(),'kernel_config':c.engine.config.to_dict(),'text':c.sensor.config.__dict__})
    case.finish({'resolution':n,'lessons':104,'sim_seconds':c.engine.time_us/1e6,'nodes':len(c.engine.observation_nodes()),
                 'edges':len(c.snapshot()['core']['edges'])})


def collect(s,n,split,parent='teach'):
    case=Case(s,f'r{n}-{parent}-{split}');state=read_gzip(WORK/f'cases/r{n}-{parent}/checkpoint.json.gz')
    image=StateImage(encoded(state['core']));xs=[];ys=[]
    settings=tasks(split)
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
        for i,task in enumerate(settings):
            c=Classroom(state=state,image=image);set_task(c,task)
            rows=request(c,task['text'],s.guard);xs.append(features(c,rows));ys.append(task['slot'])
            out.write(encoded({'trial':task,'process':rows}).decode()+'\n')
            if i%12==0:print(json.dumps({'stage':case.path.name,'trial':i,'of':len(settings)}),flush=True)
    np.savez_compressed(case.path/'features.npz',x=xs,y=ys);new_json(case.path/'trials.json',settings)
    new_json(case.path/'layout.json',list(c.layout().channels))
    case.finish({'resolution':n,'split':split,'trials':len(xs)})


def fit(s,n,parent='teach'):
    case=Case(s,f'r{n}-{parent}-fit')
    data=np.load(WORK/f'cases/r{n}-teach-calibration/features.npz');x,y=data['x'],data['y']
    if parent!='teach':
        extra=np.load(WORK/f'cases/r{n}-{parent}-practice/features.npz')
        x=np.concatenate([x,extra['x']]);y=np.concatenate([y,extra['y']])
    head=ActivityController(x.shape[-1],4,seed=223).to(device())
    result=head.fit(x,y,steps=1200,check=s.guard)
    head.save(case.path/'controller',read_json(WORK/f'cases/r{n}-teach-calibration/layout.json'))
    case.finish({'resolution':n,'source':parent,'fit':result,'samples':len(y),'training_correct':int((head.predict(x).argmax(-1)==y).sum())})


def evaluate(s,n,parent='teach',split='test',mode='normal'):
    case=Case(s,f'r{n}-{parent}-{split}-{mode}')
    head,layout=ActivityController.restore(WORK/f'cases/r{n}-{parent}-fit/controller',device())
    state=read_gzip(WORK/f'cases/r{n}-{parent}/checkpoint.json.gz');image=StateImage(encoded(state['core']))
    scores=[];xs=[]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
        for i,task in enumerate(tasks(split)):
            c=Classroom(state=state,image=image);set_task(c,task)
            if mode=='silence':c.engine.intervene(edges=[(e['source'],e['target']) for e in state['core']['edges']],action='silence')
            rows=request(c,task['text'],s.guard);x=features(c,rows);xs.append(x)
            selected=int(head.predict((np.zeros_like(x) if mode=='zero' else x)[None]).argmax(-1)[0])
            # This executor knows the selected physical endpoint, NEVER the target.
            for j in range(40):rows.append(c.tick(guard=s.guard,action=lambda row:c.world.pointer.teacher_action(POSITIONS[selected])))
            pos=np.array([c.world.pointer.x,c.world.pointer.y]);dist=np.linalg.norm(pos-np.array(POSITIONS),axis=1)
            result=task|{'selected':selected,'correct':selected==task['slot'],'final':pos.tolist(),
                        'selected_endpoint_reached':bool(dist[selected]<=.15),'requested_target_reached':bool(dist[task['slot']]<=.15),
                        'target_error_m':float(dist[task['slot']]),'control':'servo executes decoded slot only; no target/marker input'}
            scores.append(result);out.write(encoded({'trial':result,'process':rows}).decode()+'\n')
            if i%8==0:print(json.dumps({'stage':case.path.name,'trial':i,'of':len(tasks(split))}),flush=True)
    new_json(case.path/'predictions.json',scores);np.savez_compressed(case.path/'features.npz',x=xs,y=[r['slot'] for r in scores])
    grouped={cat:{'n':sum(r['category']==cat for r in scores),
                 'correct':sum(r['category']==cat and r['correct'] for r in scores),
                 'reached':sum(r['category']==cat and r['requested_target_reached'] for r in scores)} for cat in ('color','shape','pair')}
    case.finish({'resolution':n,'source':parent,'mode':mode,'split':split,'groups':grouped,
                 'selected_endpoint_reached':sum(r['selected_endpoint_reached'] for r in scores),'n':len(scores)})


def correct(s,n,enabled,*,base='teach'):
    name=('' if base=='teach' else base+'-')+('corrected' if enabled else 'exposure');case=Case(s,f'r{n}-{name}')
    state=read_gzip(WORK/f'cases/r{n}-{base}/checkpoint.json.gz');c=Classroom(state=state)
    practice=read_json(WORK/f'cases/r{n}-teach-practice-normal/predictions.json')
    errors=[r for r in practice if not r['requested_target_reached']]
    start=c.engine.time_us;lessons=[]
    # Exact same practice choices, scene order, time, and background in both branches.
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
        for repeat,gap in enumerate((0,0,0,6,18)):
            c.world.marker=None
            for _ in range(gap*20):out.write(encoded({'kind':'interval','process':[c.tick(guard=s.guard)]}).decode()+'\n')
            for task in errors:
                set_task(c,task);c.world.marker=list(POSITIONS[task['slot']]) if enabled else None
                text=task['statement'] if enabled else task['text']
                rows=request(c,text,s.guard)
                for j in range(40):
                    rows.append(c.tick(guard=s.guard,action=(lambda row:c.world.pointer.teacher_action(POSITIONS[task['slot']])) if enabled else (lambda row:(0.,0.))))
                lesson=task|{'repeat':repeat,'teacher_enabled':enabled}
                lessons.append(lesson);out.write(encoded({'kind':'correction' if enabled else 'matched-exposure','lesson':lesson,'process':rows}).decode()+'\n')
            print(json.dumps({'stage':case.path.name,'round':repeat,'error_items':len(errors),'sim_s':c.engine.time_us/1e6}),flush=True)
    write_gzip(case.path/'checkpoint.json.gz',c.snapshot());new_json(case.path/'lessons.json',lessons)
    case.finish({'resolution':n,'errors':len(errors),'lessons':len(lessons),'teacher_enabled':enabled,'sim_seconds':(c.engine.time_us-start)/1e6})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('prepare','teach','collect','fit','evaluate','correct','foundation','suite'))
    p.add_argument('--resolution',type=int,choices=(4,6),default=4);p.add_argument('--source',choices=('teach','corrected','exposure'),default='teach')
    p.add_argument('--split',choices=('calibration','practice','test'),default='test');p.add_argument('--mode',choices=('normal','zero','silence'),default='normal')
    a=p.parse_args();s=study(a.command=='prepare');n=a.resolution
    try:
        if a.command=='prepare':new_json(WORK/'instances.json',{'created':0});new_json(WORK/'usage.json',{'used_percent':68});print(s.project)
        elif a.command=='teach':teach(s,n)
        elif a.command=='collect':collect(s,n,a.split,a.source)
        elif a.command=='fit':fit(s,n,a.source)
        elif a.command=='evaluate':evaluate(s,n,a.source,a.split,a.mode)
        elif a.command=='correct':correct(s,n,a.source=='corrected')
        else:
            steps=[(f'r{n}-teach',lambda:teach(s,n)),(f'r{n}-teach-calibration',lambda:collect(s,n,'calibration')),
                   (f'r{n}-teach-fit',lambda:fit(s,n)),(f'r{n}-teach-test-normal',lambda:evaluate(s,n)),
                   (f'r{n}-teach-practice-normal',lambda:evaluate(s,n,split='practice'))]
            if a.command=='foundation':steps=steps[:4]
            for branch in (() if a.command=='foundation' else ('exposure','corrected')):
                steps.extend([(f'r{n}-{branch}',lambda b=branch:correct(s,n,b=='corrected')),
                         (f'r{n}-{branch}-practice',lambda b=branch:collect(s,n,'practice',b)),
                         (f'r{n}-{branch}-fit',lambda b=branch:fit(s,n,b)),
                         (f'r{n}-{branch}-test-normal',lambda b=branch:evaluate(s,n,b))])
            for key,run in steps:
                if not (WORK/'cases'/key/'result.json').exists():run()
    finally:s.db.close()

if __name__=='__main__':main()
