"""E54 bounded pointing and compositional classroom. No Core edits."""
import argparse
from dataclasses import replace
import gzip
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from lab.tools.activity_controller import ActivityLayout,ActivityController
from lab.tools.shape_color_world import ShapeColorWorld,Pointer,SHAPES,COLORS,POSITIONS,VERSION
from lab.tools.imitation_world import ImitationWorld
from lab.tools.service_study import Study,StudyConfig,new_json,read_json,write_gzip,encoded
from threemind_core import StateImage
from threemind_runtime.host import create_engine
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.activity_stream import RawActivityStream
from threemind_runtime.sensory import TextSensor,TextSensorConfig

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/shape-color-20261006'
DT=50000
SEEDS=(223,279)
HELD={(i,i) for i in range(4)}
LABELS=(*SHAPES,*COLORS)


def study(prepare=False):
    return Study(StudyConfig('shape-color-pointing/1','E54 形状、颜色与指向',HERE,WORK,59,
        instance_limit=1200,wall_seconds=7200,storage_soft=3*2**30,storage_hard=8*2**30,
        usage_soft_delta=6,usage_hard_delta=8),prepare=prepare)


class Case:
    def __init__(self,s,key):
        self.s=s;self.path=WORK/'cases'/key
        if self.path.exists():raise RuntimeError('existing evidence preserved: '+key)
        s.guard(True);self.path.mkdir(parents=True)
        self.born=time.monotonic();s.active_case=SimpleNamespace(born_wall=self.born)

    def finish(self,result):
        elapsed=time.monotonic()-self.born
        new_json(self.path/'result.json',result|{'wall_seconds':elapsed,'runner_signature':self.s.runner_signature})
        self.s.completed_count+=1;self.s.completed_wall+=elapsed;self.s.active_case=None
        print(json.dumps({'case':self.path.name,'wall_seconds':round(elapsed,2),**result},ensure_ascii=False),flush=True)


class Classroom:
    def __init__(self,seed=223,plasticity=True,state=None,image=None):
        counter=WORK/'instances.json'
        count=read_json(counter)['created'] if counter.exists() else 0
        if count>=1200:raise RuntimeError('registered Core instance budget')
        counter.write_bytes(encoded({'created':count+1}))
        sensory_seed=state['world']['seed'] if state else 91+seed-223
        self.world=ShapeColorWorld(sensory_seed)
        self.engine=create_engine({'seed':seed,'plasticity':plasticity} if state is None else None,
                                  state=(image or StateImage(encoded(state['core']))) if state else None,
                                  kernel_id=state['core']['dynamics'] if state else None)
        self.records=[]
        self.reader=ReadoutSession(self.engine,record=self.records.append,config={
            'structural_readout':{'enabled':False},'temporal_readout':{'enabled':False},
            'activity_readout':{'enabled':False}},state=state['reader'] if state else None)
        self.sensor=TextSensor(sensory_seed,TextSensorConfig(frame_characters=1,frame_interval_us=DT))
        self.stream=RawActivityStream();self.current=None
        self.stream.subscribe('E54-raw-observer',self._receive)
        if state:
            cls=ImitationWorld if state['world']['schema']=='threemind.imitation-classroom/1' else ShapeColorWorld
            self.world=cls.restore(state['world'])

    def _receive(self,frame):self.current=frame

    def snapshot(self):
        return {'core':self.engine.capture_state().to_dict(),'reader':self.reader.capture(),'world':self.world.state()}

    def tick(self,frame=None,*,motor=False,guard=lambda:None):
        guard()
        observation=self.world.observe(motor_only=motor)
        stimulus=self.world.stimulus(observation)
        if frame:
            channels=dict(stimulus.channels)
            if channels.keys() & dict(frame['stimulus'].channels).keys():raise ValueError('port collision')
            channels.update(frame['stimulus'].channels)
            stimulus=replace(stimulus,channels=tuple(sorted(channels.items())))
        self.reader.schedule([{'stimulus':stimulus,'labels':{}}],source='classroom-physical-sampling',adapter_id=VERSION)
        self.reader.advance_to(self.engine.time_us+DT,guard=guard)
        if self.engine.life=='dead':raise RuntimeError('Core died; preserve case, no automatic revival')
        self.world.time_s=self.engine.time_us/1e6
        self.stream.sample(self.engine)
        self.records.clear()
        return {'observation':observation,'stimulus':stimulus.to_dict(),'activity':self.current}

    def language(self,text,*,guard=lambda:None,hold=10):
        frames=list(self.sensor.frames(text)) if text else []
        result=[self.tick(f,guard=guard) for f in frames]
        result.extend(self.tick(guard=guard) for _ in range(hold))
        return result


def window(layout,rows,count=4):
    selected=np.rint(np.linspace(0,len(rows)-1,count)).astype(int)
    return np.stack([layout.frame(rows[i]['activity']) for i in selected])


def motor(s):
    case=Case(s,'motor-teaching');c=Classroom();layout=ActivityLayout(c.world.channels[256:])
    rng=np.random.default_rng(41);xs=[];ys=[];log=[]
    for episode in range(32):
        c.world.pointer=Pointer(*rng.uniform(-.8,.8,2))
        c.world.marker=rng.uniform(-.8,.8,2).tolist();history=[]
        for step in range(30):
            row=c.tick(motor=True,guard=s.guard);history.append(row)
            action=c.world.pointer.teacher_action(c.world.marker)
            if len(history)>=4:
                xs.append(window(layout,history[-4:]));ys.append(action)
            row['demonstration_action']=action.tolist();row['episode']=episode;log.append(row)
            c.world.pointer.step(action)
    np.savez_compressed(case.path/'training.npz',x=xs,y=ys)
    write_gzip(case.path/'process.json.gz',log)
    write_gzip(case.path/'checkpoint.json.gz',c.snapshot())
    head=ActivityController(layout.width,2,regression=True).to(device())
    fit=head.fit(xs,ys,steps=800,check=s.guard);head.save(case.path/'controller',layout.channels)
    trainerr=float(np.mean((head.predict(xs)-ys)**2))
    case.finish({'kind':'motor-teaching','samples':len(xs),'fit':fit,'train_mse':trainerr})


def read_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.65)
        return 'cuda'
    return 'cpu'


def motor_test(s,mode):
    case=Case(s,'motor-test-'+mode)
    source=WORK/'cases/motor-teaching'
    state=read_gzip(source/'checkpoint.json.gz')
    image=StateImage(encoded(state['core']))
    head,layout=ActivityController.restore(source/'controller',device())
    train=np.load(source/'training.npz',allow_pickle=False)['x']
    rng=np.random.default_rng(991);rows=[]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as stream:
        for i in range(32):
            c=Classroom(state=state,image=image);c.world.pointer=Pointer(*rng.uniform(-.8,.8,2))
            c.world.marker=rng.uniform(-.8,.8,2).tolist();history=[];steps=[]
            initial=float(np.linalg.norm(np.array(c.world.marker)-[c.world.pointer.x,c.world.pointer.y]))
            # All controllers receive the same150ms observation before action.
            for _ in range(3):history.append(c.tick(motor=True,guard=s.guard))
            for j in range(40):
                row=c.tick(motor=True,guard=s.guard);history.append(row)
                x=window(layout,history[-4:])
                if mode=='zero':x=np.zeros_like(x)
                if mode=='shuffled':x=train[(i*47+j*13)%len(train)]
                action=head.predict([x])[0];row['action']=action.tolist();steps.append(row)
                c.world.pointer.step(action)
            err=float(np.linalg.norm(np.array(c.world.marker)-[c.world.pointer.x,c.world.pointer.y]))
            rows.append({'trial':i,'initial_error':initial,'error':err,'success':err<=.15})
            stream.write(encoded({'trial':rows[-1],'steps':steps}).decode()+'\n')
    case.finish({'kind':'motor-test','mode':mode,'n':32,'success':sum(r['success'] for r in rows),
                 'median_error':float(np.median([r['error'] for r in rows])),'trials':rows})


def scene(shape,color,variant,slot):
    # Every scene retains all four objects. Distractors can share either
    # attribute; the target has a unique conjunction. Target placement varies.
    candidates=[(s,c) for s in range(4) for c in range(4) if (s,c) not in HELD and (s,c)!=(shape,color)]
    same_color=next(p for p in candidates if p[1]==color)
    same_shape=next(p for p in candidates if p[0]==shape)
    other=next(p for p in candidates if p not in (same_color,same_shape))
    items=[(shape,color),same_color,same_shape,other]
    items=items[-slot:]+items[:-slot] if slot else items
    return items


def choice_scene(shape,color,variant,slot):
    # Balanced2x2: every colour and shape occurs twice; no majority-object
    # shortcut. All distractor combinations exclude the held-out diagonal.
    other_shape=next(s for s in range(4) if s!=shape and s!=color)
    other_color=next(c for c in range(4) if c not in (color,shape,other_shape))
    items=[(shape,color),(other_shape,color),(shape,other_color),(other_shape,other_color)]
    return items[-slot:]+items[:-slot] if slot else items


def foundation_schedule():
    lessons=[]
    for shape in range(4):
        for rep in range(10):lessons.append((shape,4,0,f'这是{SHAPES[shape]}。{SHAPES[shape]}是一种形状。',rep))
    for color in range(4):
        for rep in range(10):lessons.append((4,color,1,f'这是{COLORS[color]}。{COLORS[color]}是一种颜色。',rep))
    for shape in range(4):
        for color in range(4):
            if (shape,color) in HELD:continue
            for cat in range(2):
                answer=SHAPES[shape] if cat==0 else COLORS[color]
                for rep in range(10):lessons.append((shape,color,cat,
                    ('这是什么形状？' if cat==0 else '这是什么颜色？')+f'这是{answer}。',rep))
    rng=np.random.default_rng(37)
    for review in range(2):
        for shape,color,cat in rng.permutation([(s,c,k) for s in range(4) for c in range(4) if (s,c) not in HELD for k in range(2)]):
            answer=SHAPES[shape] if cat==0 else COLORS[color]
            lessons.append((int(shape),int(color),int(cat),f'这是{answer}。',10+review))
    return lessons


def teach(s,seed,frozen=False):
    key=f's{seed}'+('-frozen' if frozen else '')
    case=Case(s,key+'-teaching');c=Classroom(seed,not frozen)
    new_json(case.path/'protocol.json',{'world':VERSION,'text':c.sensor.config.__dict__,'kernel':c.engine.capture_state().to_dict()['config'],
                                       'held_out':sorted(HELD),'seed':seed,'frozen':frozen})
    lessons=foundation_schedule();new_json(case.path/'lessons.json',lessons)
    with gzip.open(case.path/'teaching.jsonl.gz','xt',encoding='utf-8') as stream:
        for i,(shape,color,cat,text,rep) in enumerate(lessons):
            slot=(i//10+i%3)%4
            items=scene(shape,color,rep%4,slot) if color!=4 and shape!=4 else [(j,4) for j in range(4)]
            if color==4:slot=shape
            if shape==4:items=[(4,j) for j in range(4)];slot=color
            c.world.set_scene(items,rep%4);c.world.marker=list(POSITIONS[slot])
            rows=c.language(text,guard=s.guard,hold=4 if rep<10 else 14+rep%2*10)
            stream.write(encoded({'lesson':i,'shape':shape,'color':color,'category':cat,'text':text,'slot':slot,'process':rows}).decode()+'\n')
            if i%40==0:print(json.dumps({'teaching':key,'lesson':i,'of':len(lessons),'sim_seconds':c.engine.time_us/1e6}),flush=True)
    write_gzip(case.path/'checkpoint.json.gz',c.snapshot())
    case.finish({'kind':'teaching','seed':seed,'frozen':frozen,'lessons':len(lessons),'sim_seconds':c.engine.time_us/1e6,
                 'nodes':len(c.engine.observation_nodes()),'edges':len(c.engine.capture_state().to_dict()['edges'])})


def questions(split):
    pairs=[(s,c) for s in range(4) for c in range(4) if ((s,c) in HELD)==(split=='combinations')]
    variants=(0,1,2,3) if split=='train' else (5,6)
    return [(s,c,cat,v,(s+2*c+v)%4) for s,c in pairs for cat in range(2) for v in variants]


def collect(s,seed,frozen=False,intervention='none'):
    key=f's{seed}'+('-frozen' if frozen else '')
    source=WORK/'cases'/(key+'-teaching')
    state=read_gzip(source/'checkpoint.json.gz')
    image=StateImage(encoded(state['core']))
    c0=Classroom(state=state,image=image)
    layout=ActivityLayout((*c0.world.channels,*(c0.sensor.identity(0x100000+i) for i in range(c0.sensor.config.channel_count))))
    for split in ('train','layouts','combinations'):
        if intervention!='none' and split=='train':continue
        case=Case(s,key+'-'+split+('-'+intervention if intervention!='none' else ''))
        examples=[];meta=[]
        with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as stream:
            for shape,color,cat,variant,slot in questions(split):
                c=Classroom(state=state,image=image)
                if intervention!='none':
                    edge_pairs=[(e['source'],e['target']) for e in state['core']['edges']]
                    c.engine.intervene(edges=edge_pairs,action='silence')
                    if intervention=='rescue':c.engine.intervene(edges=edge_pairs,action='unsilence')
                c.world.set_scene(scene(shape,color,variant,slot),variant);c.world.marker=list(POSITIONS[slot])
                text='这是什么形状？' if cat==0 else '这是什么颜色？'
                rows=c.language(text,guard=s.guard,hold=10)
                # Six actual output samples cover question delivery and its
                # response, with physical vision still present throughout.
                x=window(layout,rows,6);target=shape if cat==0 else 4+color
                examples.append(x);meta.append({'shape':shape,'color':color,'category':cat,'variant':variant,'slot':slot,
                    'target':target,'text':text,'start_us':rows[0]['activity']['time_us'],'end_us':rows[-1]['activity']['time_us']})
                stream.write(encoded({'trial':meta[-1],'process':rows}).decode()+'\n')
        np.savez_compressed(case.path/'features.npz',x=examples,y=[r['target'] for r in meta])
        new_json(case.path/'trials.json',meta);new_json(case.path/'layout.json',list(layout.channels))
        case.finish({'kind':'probe','seed':seed,'frozen':frozen,'split':split,'intervention':intervention,'n':len(meta)})


def fit_expression(s,seed,frozen=False):
    key=f's{seed}'+('-frozen' if frozen else '')
    case=Case(s,key+'-expression');parent=WORK/'cases'/(key+'-train')
    arr=np.load(parent/'features.npz',allow_pickle=False);x,y=arr['x'],arr['y']
    head=ActivityController(x.shape[-1],8,seed=seed).to(device())
    fit=head.fit(x,y,steps=1000,check=s.guard)
    head.save(case.path/'controller',read_json(parent/'layout.json'))
    result={'kind':'expression','seed':seed,'frozen':frozen,'fit':fit,'train_correct':int((head.predict(x).argmax(-1)==y).sum()),'train_n':len(y)}
    predictions=[]
    for split in ('layouts','combinations'):
        p=WORK/'cases'/(key+'-'+split);test=np.load(p/'features.npz',allow_pickle=False);features=test['x'];targets=test['y']
        output=head.predict(features);yp=output.argmax(-1);n=len(yp)
        permutation=np.random.default_rng(491).permutation(n)
        shifted=head.predict(features[permutation]).argmax(-1)
        zeros=head.predict(np.zeros_like(features)).argmax(-1)
        detail=read_json(p/'trials.json')
        for i in range(n):predictions.append(detail[i]|{'split':split,'answer':LABELS[yp[i]],'prediction':int(yp[i]),
            'scores':output[i].tolist(),'correct':bool(yp[i]==targets[i]),'shifted':int(shifted[i]),
            'shuffled_source_index':int(permutation[i]),'zero':int(zeros[i])})
        result[split]={'n':n,'correct':int((yp==targets).sum()),'shape_correct':int(((yp==targets)&(targets<4)).sum()),
                      'color_correct':int(((yp==targets)&(targets>=4)).sum()),'wrong_category':int(((yp<4)!=(targets<4)).sum()),
                      'shuffled_correct':int((shifted==targets).sum()),'zero_correct':int((zeros==targets).sum())}
    new_json(case.path/'predictions.json',predictions);case.finish(result)


def score_intervention(s,seed,intervention):
    case=Case(s,f's{seed}-score-'+intervention)
    head,_=ActivityController.restore(WORK/f'cases/s{seed}-expression/controller',device())
    result={'kind':'intervention-score','seed':seed,'intervention':intervention};details=[]
    for split in ('layouts','combinations'):
        p=WORK/f'cases/s{seed}-{split}-{intervention}'
        data=np.load(p/'features.npz',allow_pickle=False);pred=head.predict(data['x']).argmax(-1)
        for row,answer in zip(read_json(p/'trials.json'),pred):
            details.append(row|{'split':split,'prediction':int(answer),'correct':int(answer)==row['target']})
        result[split]={'n':len(pred),'correct':int((pred==data['y']).sum())}
    new_json(case.path/'predictions.json',details);case.finish(result)


def reference_test(s,seed,frozen=False,corrected=False):
    key=f's{seed}'+('-frozen' if frozen else '')
    case=Case(s,key+('-corrected-reference' if corrected else '-reference'))
    state=read_gzip(WORK/f'cases/{key}-teaching/checkpoint.json.gz')
    image=StateImage(encoded(state['core']))
    head_folder=WORK/'cases'/(key+'-'+('corrected' if corrected else 'expression'))/'controller'
    head,layout=ActivityController.restore(head_folder,device())
    trials=[];rng=np.random.default_rng(709 if corrected else 128)
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as stream:
        for scene_id in range(4):
            shapes=rng.permutation(4);colors=rng.permutation(4);items=list(zip(map(int,shapes),map(int,colors)))
            for slot in range(4):
                for cat in range(2):
                    c=Classroom(state=state,image=image);c.world.set_scene(items,5+scene_id%2);c.world.marker=list(POSITIONS[slot])
                    text='这是什么形状？' if cat==0 else '这是什么颜色？'
                    rows=c.language(text,guard=s.guard,hold=10);x=window(layout,rows,6)
                    pred=int(head.predict([x]).argmax(-1)[0]);target=items[slot][cat]+cat*4
                    trial={'scene':scene_id,'items':items,'slot':slot,'category':cat,'target':target,'prediction':pred,
                           'answer':LABELS[pred],'correct':pred==target}
                    trials.append(trial);stream.write(encoded({'trial':trial,'process':rows}).decode()+'\n')
    new_json(case.path/'trials.json',trials)
    differentiated=sum(len({r['prediction'] for r in trials if r['scene']==j and r['category']==k})>1 for j in range(4) for k in range(2))
    case.finish({'kind':'reference','seed':seed,'frozen':frozen,'corrected':corrected,'n':len(trials),'correct':sum(r['correct'] for r in trials),
                 'pointer_sensitive_scene_categories':differentiated,'scene_categories':8})


def correct_expression(s,seed,frozen=False):
    key=f's{seed}'+('-frozen' if frozen else '')
    case=Case(s,key+'-corrected');state=read_gzip(WORK/f'cases/{key}-teaching/checkpoint.json.gz')
    image=StateImage(encoded(state['core']))
    layout=ActivityLayout(read_json(WORK/f'cases/{key}-train/layout.json'))
    settings=[]
    for variant in (0,2):
        for target in range(4):
            order=np.roll(np.arange(4),variant//2);slot=list(order).index(target)
            settings.append(([(int(i),4) for i in order],slot,0,variant,target))
            settings.append(([(4,int(i)) for i in order],slot,1,variant,4+target))
    for shift in (1,2,3):
        for variant in (1,3):
            order=np.roll(np.arange(4),variant);items=[(int(i),int((i+shift)%4)) for i in order]
            for slot in range(4):
                for cat in range(2):settings.append((items,slot,cat,variant,items[slot][cat]+4*cat))
    xs=[];ys=[]
    with gzip.open(case.path/'calibration.jsonl.gz','xt',encoding='utf-8') as stream:
        for items,slot,cat,variant,target in settings:
            c=Classroom(state=state,image=image);c.world.set_scene(items,variant);c.world.marker=list(POSITIONS[slot])
            text='这是什么形状？' if cat==0 else '这是什么颜色？'
            rows=c.language(text,guard=s.guard,hold=10);xs.append(window(layout,rows,6));ys.append(target)
            stream.write(encoded({'items':items,'slot':slot,'category':cat,'target':target,'process':rows}).decode()+'\n')
    original=np.load(WORK/f'cases/{key}-train/features.npz',allow_pickle=False)
    x=np.concatenate([original['x'],np.asarray(xs)]);y=np.r_[original['y'],ys]
    np.savez_compressed(case.path/'training.npz',x=x,y=y)
    head=ActivityController(layout.width,8,seed=seed).to(device());fit=head.fit(x,y,steps=1500,check=s.guard)
    head.save(case.path/'controller',layout.channels)
    result={'kind':'correction','seed':seed,'frozen':frozen,'extra_training':len(xs),'train_n':len(y),
            'train_correct':int((head.predict(x).argmax(-1)==y).sum()),'fit':fit,
            'scope':'external reader calibration only; same previously taught Core snapshot; no held-out combinations as targets'}
    for split in ('layouts','combinations'):
        data=np.load(WORK/f'cases/{key}-{split}/features.npz',allow_pickle=False)
        pred=head.predict(data['x']).argmax(-1);targets=data['y']
        result[split]={'n':len(pred),'correct':int((pred==targets).sum()),'shape_correct':int(((pred==targets)&(targets<4)).sum()),
                       'color_correct':int(((pred==targets)&(targets>=4)).sum()),'predictions':pred.tolist(),
                       'status':'exploratory retest after seeing original failure, not independent confirmation'}
    case.finish(result)


def goal_train(s,seed):
    case=Case(s,f's{seed}-goal-teaching')
    c=Classroom(state=read_gzip(WORK/f'cases/s{seed}-teaching/checkpoint.json.gz'))
    layout=ActivityLayout((*c.world.channels,*(c.sensor.identity(0x100000+i) for i in range(192))))
    xs=[];ys=[];rng=np.random.default_rng(87)
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as stream:
        for shape,color in [(s,c) for s in range(4) for c in range(4) if (s,c) not in HELD]:
            slots=np.r_[rng.permutation(4),rng.permutation(4),rng.permutation(4)[:2]]
            views=np.r_[rng.permutation(4),rng.permutation(4),rng.permutation(4)[:2]]
            for rep in range(10):
                slot=int(slots[rep]);variant=int(views[rep]);c.world.set_scene(choice_scene(shape,color,variant,slot),variant)
                c.world.marker=None;c.world.pointer=Pointer(*rng.uniform(-.8,.8,2))
                text=f'请指出{COLORS[color]}的{SHAPES[shape]}。'
                history=c.language(text,guard=s.guard,hold=0)
                for j in range(40):
                    row=c.tick(guard=s.guard);history.append(row)
                    action=c.world.pointer.teacher_action(POSITIONS[slot])
                    if j%2==0:xs.append(window(layout,history[-4:]));ys.append(action)
                    row['demonstration_action']=action.tolist();c.world.pointer.step(action)
                stream.write(encoded({'shape':shape,'color':color,'slot':slot,'variant':variant,'repetition':rep,'text':text,'process':history}).decode()+'\n')
            print(json.dumps({'goal_teaching':seed,'pair':[shape,color],'samples':len(xs)}),flush=True)
    np.savez_compressed(case.path/'training.npz',x=xs,y=ys)
    write_gzip(case.path/'checkpoint.json.gz',c.snapshot())
    head=ActivityController(layout.width,2,regression=True,seed=seed).to(device())
    fit=head.fit(xs,ys,steps=1000,check=s.guard);head.save(case.path/'controller',layout.channels)
    case.finish({'kind':'goal-teaching','seed':seed,'episodes':120,'samples':len(xs),'fit':fit})


def goal_test(s,seed,mode):
    case=Case(s,f's{seed}-goal-test-'+mode)
    parent=WORK/f'cases/s{seed}-goal-teaching';state=read_gzip(parent/'checkpoint.json.gz')
    image=StateImage(encoded(state['core']))
    head,layout=ActivityController.restore(parent/'controller',device());rng=np.random.default_rng(473)
    trials=[]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as stream:
        for shape in range(4):
            for color in range(4):
                for variant in (5,6):
                    slot=(shape+2*color+variant)%4;c=Classroom(state=state,image=image)
                    c.world.set_scene(choice_scene(shape,color,variant,slot),variant);c.world.marker=None
                    c.world.pointer=Pointer(*rng.uniform(-.8,.8,2))
                    text=f'请指出{COLORS[color]}的{SHAPES[shape]}。'
                    requested_slot=slot
                    if mode=='wrong-request':
                        requested_slot=next(i for i,p in enumerate(c.world.items) if p[0]==shape and p[1]!=color)
                        requested_color=c.world.items[requested_slot][1]
                        text=f'请指出{COLORS[requested_color]}的{SHAPES[shape]}。'
                    if mode=='silence':c.engine.intervene(edges=[(e['source'],e['target']) for e in state['core']['edges']],action='silence')
                    history=c.language(text,guard=s.guard,hold=0)
                    for j in range(40):
                        row=c.tick(guard=s.guard);history.append(row);x=window(layout,history[-4:])
                        if mode=='zero':x=np.zeros_like(x)
                        action=head.predict([x])[0];row['action']=action.tolist();c.world.pointer.step(action)
                    distances=np.linalg.norm(np.asarray(POSITIONS)-[c.world.pointer.x,c.world.pointer.y],axis=1)
                    targeterror=float(distances[slot]);chosen=int(distances.argmin())
                    # Nearest choice and actual contact are reported separately.
                    trial={'shape':shape,'color':color,'slot':slot,'requested_slot':requested_slot,
                           'requested_choice_correct':chosen==requested_slot,'variant':variant,'held_out':(shape,color) in HELD,
                           'chosen':chosen,'choice_correct':chosen==slot,'reached':targeterror<=.15,'error':targeterror,
                           'text':text,'final_pointer':c.world.state()['pointer']}
                    trials.append(trial);stream.write(encoded({'trial':trial,'process':history}).decode()+'\n')
    new_json(case.path/'trials.json',trials)
    result={'kind':'goal-test','mode':mode,'seed':seed,'n':len(trials),'reached':sum(t['reached'] for t in trials),
            'requested_choice_correct':sum(t['requested_choice_correct'] for t in trials),
            'choice_correct':sum(t['choice_correct'] for t in trials),'median_error':float(np.median([t['error'] for t in trials]))}
    for held in (False,True):
        group=[t for t in trials if t['held_out']==held]
        result['held_out' if held else 'taught']={'n':len(group),'reached':sum(t['reached'] for t in group),
                                                'choice_correct':sum(t['choice_correct'] for t in group)}
    case.finish(result)


def imitate(s):
    """A sensory-to-motor transfer assay, not a claim of an imitation instinct."""
    case=Case(s,'imitation-retry');c=Classroom();c.world=ImitationWorld()
    layout=ActivityLayout(c.world.channels[256:272],excluded_channels=c.world.channels[:256]+c.world.channels[272:])
    full_layout=ActivityLayout(c.world.channels[256:])
    xs=[];full_xs=[];ys=[];directions=np.linspace(0,2*np.pi,12,endpoint=False)
    with gzip.open(case.path/'teaching.jsonl.gz','xt',encoding='utf-8') as stream:
        for angle in directions:
            for rep in range(10):
                c.world.pointer=Pointer();c.world.teacher=Pointer()
                target=.65*np.array([np.cos(angle),np.sin(angle)])
                rows=[]
                for j in range(20):
                    row=c.tick(motor=True,guard=s.guard);rows.append(row)
                    action=c.world.teacher.teacher_action(target)
                    if j>=3:
                        xs.append(window(layout,rows[-4:]));full_xs.append(window(full_layout,rows[-4:]));ys.append(action)
                    c.world.teacher.step(action);c.world.pointer.step(action)
                stream.write(encoded({'angle':float(angle),'repetition':rep,'process':rows}).decode()+'\n')
    state=c.snapshot();write_gzip(case.path/'checkpoint.json.gz',state)
    head=ActivityController(layout.width,2,regression=True,seed=113).to(device())
    fit=head.fit(xs,ys,steps=800,check=s.guard)
    head.save(case.path/'controller',layout.channels,excluded_channels=layout.excluded_channels)
    full_head=ActivityController(full_layout.width,2,regression=True,seed=113).to(device())
    full_fit=full_head.fit(full_xs,ys,steps=800,check=s.guard);full_head.save(case.path/'full-controller',full_layout.channels)
    teacher=set(c.world.channels[272:]);own=set(c.world.channels[256:272])
    node_channels={int(n['id']):int(n['channel']) for n in state['core']['nodes']}
    cross=[(e['source'],e['target']) for e in state['core']['edges'] if
           node_channels[int(e['source'])] in teacher and node_channels[int(e['target'])] in own]
    cross_set=set(cross)
    eligible=sorted([e for e in state['core']['edges'] if (e['source'],e['target']) not in cross_set],key=lambda e:e['weight'])
    selected=sorted([e for e in state['core']['edges'] if (e['source'],e['target']) in cross_set],key=lambda e:e['weight'])
    matched=[]
    for edge in selected:
        nearest=min(range(len(eligible)),key=lambda i:abs(eligible[i]['weight']-edge['weight']))
        candidate=eligible.pop(nearest);matched.append((candidate['source'],candidate['target']))
    new_json(case.path/'interventions.json',{'target_edges':cross,'matched_edges':matched,
         'matching':'same count, nearest available weight, no target edges; not exact topology equivalence'})
    result=[]
    with gzip.open(case.path/'tests.jsonl.gz','xt',encoding='utf-8') as stream:
        for mode in ('normal','cross-silenced','matched','rescue','teacher-hidden','full-normal','full-cross-silenced','full-hidden'):
            for angle in directions+.13:
                q=Classroom(state=state);q.world.pointer=Pointer();q.world.teacher=Pointer()
                if mode in ('cross-silenced','matched','rescue','full-cross-silenced'):
                    q.engine.intervene(edges=matched if mode=='matched' else cross,action='silence')
                    if mode=='rescue':q.engine.intervene(edges=cross,action='unsilence')
                target=.65*np.array([np.cos(angle),np.sin(angle)]);rows=[]
                for j in range(20):
                    if mode in ('teacher-hidden','full-hidden'):q.world.teacher=Pointer()
                    row=q.tick(motor=True,guard=s.guard);rows.append(row)
                    if j>=3:
                        decoder,projection=(full_head,full_layout) if mode.startswith('full-') else (head,layout)
                        action=decoder.predict([window(projection,rows[-4:])])[0];q.world.pointer.step(action)
                        row['action']=action.tolist()
                    if mode not in ('teacher-hidden','full-hidden'):q.world.teacher.step(q.world.teacher.teacher_action(target))
                p=np.array([q.world.pointer.x,q.world.pointer.y]);norm=float(np.linalg.norm(p))
                cosine=float(p@target/(norm*.65)) if norm>1e-9 else 0.
                trial={'mode':mode,'angle':float(angle),'cosine':cosine,'displacement':norm,'directional':cosine>.707 and norm>.05}
                result.append(trial);stream.write(encoded({'trial':trial,'process':rows}).decode()+'\n')
    new_json(case.path/'trials.json',result)
    case.finish({'kind':'imitation','fit':fit,'full_fit':full_fit,'cross_edges':len(cross),
        'groups':{mode:{'n':12,'directional':sum(r['directional'] for r in result if r['mode']==mode),
                       'mean_cosine':float(np.mean([r['cosine'] for r in result if r['mode']==mode]))}
                  for mode in ('normal','cross-silenced','matched','rescue','teacher-hidden','full-normal','full-cross-silenced','full-hidden')}})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('prepare','motor','motor-test','teach','collect','fit','score','goal-train','goal-test','imitate','reference','correct'))
    p.add_argument('--seed',type=int,default=223);p.add_argument('--frozen',action='store_true')
    p.add_argument('--corrected',action='store_true')
    p.add_argument('--mode',choices=('normal','zero','shuffled','wrong-request','silence'),default='normal')
    p.add_argument('--intervention',choices=('none','silence','rescue'),default='none')
    a=p.parse_args();s=study(a.command=='prepare')
    try:
        if a.command=='motor':motor(s)
        elif a.command=='motor-test':motor_test(s,a.mode)
        elif a.command=='teach':teach(s,a.seed,a.frozen)
        elif a.command=='collect':collect(s,a.seed,a.frozen,a.intervention)
        elif a.command=='fit':fit_expression(s,a.seed,a.frozen)
        elif a.command=='score':score_intervention(s,a.seed,a.intervention)
        elif a.command=='goal-train':goal_train(s,a.seed)
        elif a.command=='goal-test':goal_test(s,a.seed,a.mode)
        elif a.command=='imitate':imitate(s)
        elif a.command=='reference':reference_test(s,a.seed,a.frozen,a.corrected)
        elif a.command=='correct':correct_expression(s,a.seed,a.frozen)
        elif a.command=='prepare':
            new_json(WORK/'instances.json',{'created':0});print(s.project)
    finally:s.db.close()


if __name__=='__main__':main()
