"""E58 bounded optical, feedback, history-content and adapter comparisons."""
import argparse
import copy
from dataclasses import replace
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import time
import weakref
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from threemind_core import StateImage
from threemind_runtime.host import create_engine
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.activity_stream import RawActivityStream
from threemind_runtime.sensory import TextSensor,TextSensorConfig
from lab.tools.whole_scene_classroom import WholeSceneClassroom,sensory_replay
from lab.tools.classroom_eye import DetailedClassroom
from lab.tools.shape_color_world import POSITIONS,Pointer,SHAPES,COLORS
from lab.tools.activity_controller import ActivityLayout
from lab.tools.spatial_choice import SpatialChoice
from lab.tools.retinal_choice import RetinalChoice
from lab.tools.choice_attribution import raw_window,paired_scores
from lab.tools.choice_interventions import transfer_edges
from lab.tools.service_study import Study,StudyConfig,new_json,read_json,write_gzip,encoded

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/embodied-memory-20261007'
OLD=ROOT/'.work/choice-attribution-20261006'
DT=50000
MAPS=((0,1,2,3),(1,2,3,0),(2,3,0,1))
NAMES=('甲','乙','丁','戊')


def read_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.60)
        return 'cuda'
    return 'cpu'


class BoundedStudy(Study):
    def guard(self,force=False):
        super().guard(force)
        stopped=sum(read_json(p)['wall_seconds'] for p in (self.work/'cases').glob('*/stopped.json')) if force else getattr(self,'stopped_wall',0.)
        self.stopped_wall=stopped
        active=time.monotonic()-self.active_case.born_wall if self.active_case else 0.
        if self.completed_wall+stopped+active>self.settings.wall_seconds:raise RuntimeError('compute budget including failed cases')


def study(prepare=False):
    s=BoundedStudy(StudyConfig('embodied-memory/1','E58 完整视野、反馈与记忆内容',HERE,WORK,76,
        instance_limit=800,wall_seconds=7200,storage_soft=6*2**30,storage_hard=8*2**30,
        usage_soft_delta=4,usage_hard_delta=6),prepare=prepare)
    amendment=WORK/'compute-budget-amendment.json'
    if amendment.exists():
        record=read_json(amendment)
        if (record.get('schema'),record.get('original_seconds'),record.get('revised_seconds')) != ('E58-budget-amendment/1',7200,8400):
            raise ValueError('unrecognized E58 budget amendment')
        # Preserve platform.json and the original registration. This explicit
        # resource-only amendment adds no cases or changes to study conditions.
        s.settings=replace(s.settings,wall_seconds=8400)
    return s


class Case:
    def __init__(self,s,key):
        self.s=s;self.key=key;self.path=WORK/'cases'/key
        if self.path.exists():raise RuntimeError('preserve case '+key)
        s.guard(True);self.path.mkdir(parents=True);self.born=time.monotonic()
        s.active_case=SimpleNamespace(born_wall=self.born)
        new_json(self.path/'started.json',{'epoch':time.time(),'runner_signature':s.runner_signature})

    def finish(self,result):
        elapsed=time.monotonic()-self.born
        new_json(self.path/'result.json',result|{'wall_seconds':elapsed,'runner_signature':self.s.runner_signature})
        self.s.completed_count+=1;self.s.completed_wall+=elapsed;self.s.active_case=None
        print(json.dumps({'case':self.key,**result,'wall_seconds':round(elapsed,2)},ensure_ascii=False),flush=True)
        return result


def run(s,key,fn):
    if (WORK/'cases'/key/'result.json').exists():return read_json(WORK/'cases'/key/'result.json')
    c=Case(s,key)
    try:return c.finish(fn(c))
    except Exception as error:
        elapsed=time.monotonic()-c.born
        new_json(c.path/'stopped.json',{'error':str(error),'wall_seconds':elapsed})
        raise


class Classroom:
    def __init__(self, *, state=None, whole=True, plasticity=True, seed=223, image=None):
        counter=WORK/'instances.json';n=read_json(counter)['created']
        if n>=800:raise RuntimeError('instance cap')
        counter.write_bytes(encoded({'created':n+1}))
        if state:
            kind=WholeSceneClassroom if state['world']['schema'].endswith('/3') else DetailedClassroom
            self.world=kind.restore(state['world'])
        else:self.world=WholeSceneClassroom(91,47+seed-223) if whole else DetailedClassroom(91,47+seed-223,resolution=4)
        self.engine=create_engine(None if state else {'seed':seed,'plasticity':plasticity},
            state=(image or StateImage(encoded(state['core']))) if state else None,
            kernel_id=state['core']['dynamics'] if state else 'threemind.continuous-memory/2')
        self.reader=ReadoutSession(self.engine,record=lambda row:None,config={
            'structural_readout':{'enabled':False},'temporal_readout':{'enabled':False},'activity_readout':{'enabled':False}},
            state=state['reader'] if state else None)
        self.sensor=TextSensor(91,TextSensorConfig(frame_characters=1,frame_interval_us=DT))
        self.stream=RawActivityStream();self.current=None
        owner=weakref.ref(self)
        def receive(frame):
            obj=owner()
            if obj is not None:obj.current=frame
        self.stream.subscribe('E58-raw',receive)

    def receive(self,frame):self.current=frame

    def layout(self):
        return ActivityLayout((*self.world.channels,*(self.sensor.identity(0x100000+i) for i in range(self.sensor.config.channel_count))))

    def snapshot(self):
        return {'core':self.engine.capture_state().to_dict(),'reader':self.reader.capture(),'world':self.world.state()}

    def tick(self,frame=None,*,guard=lambda:None,force=(0.,0.),observation=None):
        guard()
        observed=self.world.observe() if observation is None else observation
        stim=self.world.stimulus(observed)
        if frame:
            channels=dict(stim.channels);extra=dict(frame['stimulus'].channels)
            if channels.keys()&extra.keys():raise ValueError('input port collision')
            channels.update(extra);stim=replace(stim,channels=tuple(sorted(channels.items())))
        self.reader.schedule([{'stimulus':stim,'labels':{}}],source='E58-sampling',adapter_id=observed['schema'])
        self.reader.advance_to(self.engine.time_us+DT,guard=guard)
        if self.engine.life=='dead':raise RuntimeError('Core died; no revival')
        self.stream.sample(self.engine)
        self.world.advance_physics(force)
        return {'observation':observed,'stimulus':stim.to_dict(),'activity':self.current,'force':list(force),
                'pointer_after':self.world.state()['pointer']}

    def request(self,text,guard):
        frames=list(self.sensor.frames(text))
        return [self.tick(f,guard=guard) for f in frames]+[self.tick(guard=guard) for _ in range(max(0,20-len(frames)))]


def optics(s):
    def execute(case):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        w=WholeSceneClassroom();w.set_scene([(0,0),(1,1),(2,2),(3,3)])
        images=[]
        for p in ((-.35,-.1),(.4,.15)):
            w.pointer=Pointer(*p);row=w.observe();images.append(np.asarray(row['values'][:w.vision_width]).reshape(16,16,4))
        fig,axes=plt.subplots(1,2,figsize=(9,4))
        for ax,img,label in zip(axes,images,('Self at left','Self at right')):
            ax.imshow(img[:,:,1:]);ax.set_title(label);ax.set_xlabel('one physical retina / 16 x 16')
        fig.tight_layout();fig.savefig(case.path/'retina.png',dpi=150);plt.close(fig)
        new_json(case.path/'world.json',w.state())
        w.visible_self=False;signatures=[]
        for shape in range(4):
            w.set_scene([(shape,4)]*4)
            signatures.append(np.array(w.vision()['values']))
        distances=[[float(np.linalg.norm(a-b)) for b in signatures] for a in signatures]
        # Only a two-second apparatus/performance sample, not a learning result.
        c=Classroom();start=time.monotonic()
        with gzip.open(case.path/'warmup.jsonl.gz','xt',encoding='utf-8') as out:
            for _ in range(40):out.write(encoded(c.tick(guard=s.guard)).decode()+'\n')
        state=c.snapshot();write_gzip(case.path/'warmup.json.gz',state)
        return {'camera_count':1,'resolution':16,'self_movement_changes_pixels':int(np.any(images[0]!=images[1],axis=-1).sum()),
            'shape_raw_distances':distances,'two_sim_seconds_wall':time.monotonic()-start,
            'nodes':len(state['core']['nodes']),'edges':len(state['core']['edges'])}
    return run(s,'A-optics',execute)


def taskset(split):
    # Every complete scene receives every object request; positions are physical
    # jitter, never passed to the reader, and kept out of the new test scenes.
    tasks=[];count=4 if split=='train' else 2
    for cat in ('color','shape','pair'):
        for scene in range(count):
            rng=np.random.default_rng(8051+(0 if split=='train' else 1000)+scene*37+('color','shape','pair').index(cat)*131)
            order=rng.permutation(4).tolist()
            if cat=='color':items=[(2,c) for c in order]
            elif cat=='shape':items=[(v,4) for v in order]
            else:
                # All four confusable color/shape combinations, no unique shortcut.
                a,b=scene%4,(scene+1)%4
                source=[(a,b),(a,(b+1)%4),((a+1)%4,b),((a+1)%4,(b+1)%4)]
                items=[source[i] for i in order]
            positions=(np.array(POSITIONS)+rng.uniform(-.08,.08,(4,2))).tolist()
            for slot,(shape,color) in enumerate(items):
                noun=COLORS[color]+'的物体' if cat=='color' else SHAPES[shape] if cat=='shape' else COLORS[color]+'的'+SHAPES[shape]
                tasks.append({'category':cat,'scene':scene,'items':items,'positions':positions,'slot':slot,
                    'text':f'请指出{noun}。','split':split})
    return tasks


def eye_teach(s):
    def execute(case):
        c=Classroom();schedule=[(item,rep) for item in range(8) for rep in range(10)]
        schedule += [(item,10+review) for review in range(3) for item in range(8)]
        with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for index,(item,rep) in enumerate(schedule):
                if index in (80,88,96):
                    c.world.marker=None
                    for _ in range((0,6,18)[(index-80)//8]*20):out.write(encoded({'kind':'interval','process':[c.tick(guard=s.guard)]}).decode()+'\n')
                cat=int(item>=4);value=item%4;order=np.roll(np.arange(4),(rep+value)%4).tolist()
                items=[(2,v) if cat else (v,4) for v in order];slot=order.index(value)
                c.world.set_scene(items);c.world.marker=list(POSITIONS[slot])
                text='这是'+(COLORS[value]+'的物体' if cat else SHAPES[value])+'。'
                rows=c.request(text,s.guard)+[c.tick(guard=s.guard) for _ in range(10)]
                out.write(encoded({'kind':'lesson','item':item,'rep':rep,'text':text,'process':rows}).decode()+'\n')
                if index%8==0:print(json.dumps({'case':case.key,'lesson':index,'of':104,'sim_s':c.engine.time_us/1e6}),flush=True)
        state=c.snapshot();write_gzip(case.path/'checkpoint.json.gz',state);new_json(case.path/'layout.json',list(c.layout().channels))
        return {'lessons':104,'sim_seconds':c.engine.time_us/1e6,'nodes':len(state['core']['nodes']),'edges':len(state['core']['edges'])}
    return run(s,'A-teach',execute)


def eye_collect(s,split,mode='normal'):
    def execute(case):
        state=read_gzip(WORK/'cases/A-teach/checkpoint.json.gz');xs=[];incoming=[];ys=[];tasks=taskset(split)
        # One continuous question episode per split, separately branched from
        # the taught state. Random order prevents question index being a label.
        rng=np.random.default_rng(8121 if split=='train' else 9147)
        tasks=[tasks[i] for i in rng.permutation(len(tasks))]
        c=Classroom(state=state)
        if mode in ('silence','rescue'):
            pairs=[(r['source'],r['target']) for r in state['core']['edges']]
            c.engine.intervene(edges=pairs,action='silence')
            if mode=='rescue':c.engine.intervene(edges=pairs,action='unsilence')
        with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for index,task in enumerate(tasks):
                c.world.set_scene(task['items'],positions=task['positions']);c.world.marker=None
                c.world.pointer=Pointer(0.,-.85);c.world.acceleration=[0.,0.];c.world.motor_power=0.
                rows=c.request(task['text'],s.guard);layout=c.layout()
                xs.append(raw_window(layout,rows));incoming.append(raw_window(layout,rows,kind='incoming'))
                pixel=np.clip(np.rint(c.world.project(task['positions'][task['slot']])),0,15).astype(int)
                ys.append(int(pixel[1]*16+pixel[0]));out.write(encoded({'trial':task,'process':rows}).decode()+'\n')
                if index%8==0:print(json.dumps({'case':case.key,'trial':index,'of':len(tasks)}),flush=True)
        np.savez_compressed(case.path/'features.npz',activity=xs,incoming=incoming,y=ys)
        new_json(case.path/'tasks.json',tasks)
        write_gzip(case.path/'checkpoint.json.gz',c.snapshot())
        return {'split':split,'mode':mode,'n':len(tasks),'trial_process':'continuous within split; independent split start; randomized question order'}
    return run(s,f'A-{split}-{mode}',execute)


def eye_fit(s,kind):
    def execute(case):
        train=np.load(WORK/'cases/A-train-normal/features.npz');test=np.load(WORK/'cases/A-test-normal/features.npz')
        layout=read_json(WORK/'cases/A-teach/layout.json');w=WholeSceneClassroom()
        head=RetinalChoice(layout,w.channels[:w.vision_width],16).to(device())
        fit=head.fit(train[kind],train['y'],steps=600,check=s.guard,batch_size=4)
        head.save(case.path/'controller');prediction=head.predict(test[kind]).argmax(-1)
        tasks=read_json(WORK/'cases/A-test-normal/tasks.json');rows=[]
        # Executor follows the predicted pixel, never the scoring target.
        for pixel,task in zip(prediction,tasks):
            w.set_scene(task['items'],positions=task['positions']);w.pointer=Pointer(0.,-.85)
            endpoint=w.ground_point(int(pixel)%16,int(pixel)//16)
            for _ in range(40):w.advance_physics(w.pointer.teacher_action(endpoint))
            actual=np.array([w.pointer.x,w.pointer.y]);distances=np.linalg.norm(np.array(task['positions'])-actual,axis=1)
            chosen=int(np.argmin(distances));rows.append(task|{'pixel':int(pixel),'endpoint':endpoint.tolist(),
                'actual':actual.tolist(),'chosen':chosen,'correct':chosen==task['slot'],'target_distance':float(distances[task['slot']])})
        new_json(case.path/'predictions.json',rows)
        return {'kind':kind,'fit':fit,'n':len(rows),'correct':sum(r['correct'] for r in rows),
            'arrived':sum(r['target_distance']<=.20 for r in rows),
            'categories':{cat:sum(r['correct'] for r in rows if r['category']==cat) for cat in ('color','shape','pair')},
            'train_exact_pixels':int((head.predict(train[kind]).argmax(-1)==train['y']).sum())}
    return run(s,'A-fit-'+kind,execute)


def feedback(s):
    def execute(case):
        source=read_gzip(WORK/'cases/A-optics/warmup.json.gz')
        moving=WholeSceneClassroom.restore(source['world']);still=WholeSceneClassroom.restore(source['world'])
        # Same actual physical weather, parked reference coordinates. Parking is
        # an explicit external experimental constraint, not a natural behavior.
        tape=[]
        for i in range(120):
            angle=i*.05*1.4;force=[.8*np.cos(angle),.8*np.sin(angle)]
            tape.append({'moving':moving.observe(),'reference':still.observe(),'force':list(force)})
            moving.advance_physics(force);still.advance_physics()
            still.pointer=Pointer();still.acceleration=[0.,0.];still.motor_power=0.;still.contact_force=[0.,0.]
        write_gzip(case.path/'physical-tape.json.gz',tape)
        arrays={};summary={};image=StateImage(encoded(source['core']))
        for v,b in ((True,True),(False,True),(True,False),(False,False)):
            tag=f'v{int(v)}b{int(b)}';c=Classroom(state=source,image=image);features=[]
            with gzip.open(case.path/f'{tag}.jsonl.gz','xt',encoding='utf-8') as out:
                for row in tape:
                    observed=sensory_replay(row['moving'],row['reference'],vision=v,body=b)
                    result=c.tick(guard=s.guard,observation=observed)
                    features.append(c.layout().frame(result['activity']))
                    out.write(encoded(result).decode()+'\n')
            arrays[tag]=np.asarray(features)
            shaped=arrays[tag].reshape(120,-1,4)
            summary[tag]={'activation_integral':float(shaped[:,:,0].sum()*.05),
                          'associative_integral':float(shaped[:,:,3].sum()*.05)}
        base=arrays['v0b0'];np.savez_compressed(case.path/'activity.npz',**arrays)
        for tag,array in arrays.items():summary[tag]['raw_process_L1_vs_reference']=float(np.abs(array-base).sum())
        # Repeat no-feedback tape with no relation to the hidden moving body.
        c=Classroom(state=source,image=image);same=[]
        for row in tape:same.append(c.layout().frame(c.tick(guard=s.guard,observation=row['reference'])['activity']))
        return {'samples':120,'sim_seconds':6,'conditions':summary,
                'fully_replaced_equals_reference':bool(np.array_equal(same,base)),
                'interpretation':'sensory causation only; no claim of subjective agency or decision control'}
    return run(s,'B-feedback',execute)


def legacy_module():
    spec=importlib.util.spec_from_file_location('e57_readonly',HERE.parent/'2026-10-06-choice-attribution/experiment.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def old_source(seed,history,plasticity=True):
    return OLD/f'cases/B-s{seed}-p{int(plasticity)}-h{history}-teach/checkpoint.json.gz'


def balanced(s,seed,history,plasticity,delay):
    key=f'C-s{seed}-p{int(plasticity)}-h{history}-d{delay}'
    def execute(case):
        state=read_gzip(old_source(seed,history,plasticity));common=read_gzip(old_source(seed,0,plasticity))
        state['world']=copy.deepcopy(common['world']);c=Classroom(state=state)
        with gzip.open(case.path/'tail.jsonl.gz','xt',encoding='utf-8') as out:
            # All four physical positions, equal duration, no names/answers.
            c.world.set_scene([(i,4) for i in range(4)],0)
            for target in POSITIONS:
                c.world.marker=list(target)
                for _ in range(10):out.write(encoded(c.tick(guard=s.guard)).decode()+'\n')
            c.world.marker=None
            for _ in range(delay*20):out.write(encoded(c.tick(guard=s.guard)).decode()+'\n')
        snap=c.snapshot();write_gzip(case.path/'checkpoint.json.gz',snap)
        new_json(case.path/'layout.json',list(c.layout().channels))
        return {'seed':seed,'history':history,'plasticity':plasticity,'common_tail_s':2,'delay_s':delay,
                'nodes':len(snap['core']['nodes']),'edges':len(snap['core']['edges'])}
    run(s,key,execute);return key


def history_probe(s,key,history,split,mode='normal',donor_key=None):
    def execute(case):
        state=read_gzip(WORK/'cases'/key/'checkpoint.json.gz');original=copy.deepcopy(state['core']);receipt={}
        legacy=legacy_module();tasks=legacy.history_tasks(split);xs=[];raw=[];ys=[]
        if mode=='teacher-swap':
            donor=read_gzip(WORK/'cases'/donor_key/'checkpoint.json.gz')['core']
            world=DetailedClassroom.restore(state['world'])
            ids=set(world.channels[world.vision_width+8:world.vision_width+14]);bychannel={int(n['channel']):n for n in donor['nodes']}
            change=0.
            for n in state['core']['nodes']:
                if int(n['channel']) in ids and int(n['channel']) in bychannel:
                    value=bychannel[int(n['channel'])]['activation'];change+=abs(value-n['activation']);n['activation']=value
            receipt={'activation_absolute_change':change,'fields':'activation of teacher receptor channels only'}
        elif mode=='connections-swap':
            donor=read_gzip(WORK/'cases'/donor_key/'checkpoint.json.gz')['core']
            selected=[(e['source'],e['target']) for e in state['core']['edges']]
            state['core'],receipt=transfer_edges(state['core'],donor,selected)
        image=StateImage(encoded(state['core']))
        with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for task in tasks:
                c=Classroom(state=state,image=image);c.world.set_scene(task['items'],task['variant']);c.world.marker=None
                c.world.pointer=Pointer(*task['start']);c.world.acceleration=[0.,0.];c.world.motor_power=0.
                if mode in ('silence','rescue'):
                    pairs=[(e['source'],e['target']) for e in original['edges']]
                    c.engine.intervene(edges=pairs,action='silence')
                    if mode=='rescue':c.engine.intervene(edges=pairs,action='unsilence')
                rows=c.request(task['text'],s.guard);layout=c.layout()
                xs.append(raw_window(layout,rows));raw.append(raw_window(layout,rows,kind='incoming'))
                y=next(i for i,(shape,color) in enumerate(task['items']) if shape==MAPS[history][task['name']]);ys.append(y)
                out.write(encoded({'trial':task|{'history':history,'target':y},'process':rows}).decode()+'\n')
        np.savez_compressed(case.path/'features.npz',activity=xs,incoming=raw,y=ys)
        new_json(case.path/'tasks.json',tasks)
        return {'source':key,'history':history,'n':len(ys),'mode':mode,'receipt':receipt}
    result_key=key+'-'+split+'-'+mode;run(s,result_key,execute);return result_key


def evaluate(head,paths,kind='activity'):
    data=[np.load(WORK/'cases'/p/'features.npz') for p in paths]
    preds=[head.predict(d[kind]).argmax(-1).tolist() for d in data]
    targets=[d['y'].tolist() for d in data]
    identical=bool(np.array_equal(data[0]['incoming'],data[1]['incoming']))
    if not identical:raise RuntimeError('history leaked into current input')
    return paired_scores(preds,targets)|{'predictions':preds,'targets':targets,'identical_current_input':identical}


def memory(s,seed=223,plasticity=True,delays=(0,6,30)):
    model_kind='learned' if plasticity else 'unlearned'
    oldhead,_=SpatialChoice.restore(OLD/f'cases/B-s{seed}-{model_kind}-fit/controller',device())
    for delay in delays:
        keys=[balanced(s,seed,h,plasticity,delay) for h in (0,1)]
        tests=[history_probe(s,k,h,'test') for h,k in enumerate(keys)]
        run(s,f'C-s{seed}-p{int(plasticity)}-d{delay}-frozen',lambda case:evaluate(oldhead,tests))
        if delay!=6:continue
        trains=[history_probe(s,k,h,'train') for h,k in enumerate(keys)]
        def fit(case):
            layout=read_json(WORK/'cases'/keys[0]/'layout.json')
            world=DetailedClassroom.restore(read_gzip(WORK/'cases'/keys[0]/'checkpoint.json.gz')['world'])
            visual=world.channels[:world.vision_width]
            data=[np.load(WORK/'cases'/p/'features.npz') for p in trains]
            x=np.concatenate([d['activity'] for d in data]);y=np.concatenate([d['y'] for d in data])
            head=SpatialChoice(layout,visual,seed=223).to(device());fitted=head.fit(x,y,steps=1200,check=s.guard)
            head.save(case.path/'controller');result=evaluate(head,tests)
            new_json(case.path/'predictions.json',result)
            return {'fit':fitted,'train_correct':int((head.predict(x).argmax(-1)==y).sum()),**result}
        key=f'C-s{seed}-p{int(plasticity)}-d6-refit-saved-layout';score=run(s,key,fit)
        # Interventions at >=24/32 were preregistered before this batch.
        if plasticity and score['correct']>=24:
            head,_=SpatialChoice.restore(WORK/'cases'/key/'controller',device())
            for mode in ('silence','rescue','teacher-swap','connections-swap'):
                paths=[history_probe(s,k,h,'test',mode,keys[1-h]) for h,k in enumerate(keys)]
                run(s,f'C-s{seed}-d6-{mode}-score',lambda case,p=paths:evaluate(head,p))


def new_mapping(s):
    key='D-h2-teach'
    def teach(case):
        # Same experienced starting individual as E57; only ordinary teaching.
        c=Classroom(state=read_gzip(old_source(223,0)));schedule=[(n,r) for n in range(4) for r in range(10)]
        schedule += [(n,10+r) for r in range(3) for n in range(4)]
        lessons=[]
        with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for i,(name,rep) in enumerate(schedule):
                if i in (40,44,48):
                    c.world.marker=None
                    for _ in range((0,6,18)[(i-40)//4]*20):out.write(encoded({'kind':'interval','process':[c.tick(guard=s.guard)]}).decode()+'\n')
                order=np.roll(np.arange(4),(rep+name)%4).tolist();target=MAPS[2][name];slot=order.index(target)
                c.world.set_scene([(v,4) for v in order],rep%4);c.world.marker=list(POSITIONS[slot]);text=f'这是{NAMES[name]}。'
                rows=c.request(text,s.guard)+[c.tick(guard=s.guard) for _ in range(10)]
                lesson={'name':name,'object':target,'slot':slot,'text':text,'rep':rep};lessons.append(lesson)
                out.write(encoded({'kind':'lesson','lesson':lesson,'process':rows}).decode()+'\n')
            # Match C's terminal experience before expression calibration.
            c.world.set_scene([(v,4) for v in range(4)])
            for target in POSITIONS:
                c.world.marker=list(target)
                for _ in range(10):out.write(encoded({'kind':'common_tail','process':[c.tick(guard=s.guard)]}).decode()+'\n')
            c.world.marker=None
            for _ in range(120):out.write(encoded({'kind':'wait','process':[c.tick(guard=s.guard)]}).decode()+'\n')
        write_gzip(case.path/'checkpoint.json.gz',c.snapshot());new_json(case.path/'lessons.json',lessons)
        new_json(case.path/'layout.json',list(c.layout().channels))
        return {'history':2,'lessons':52,'unseen_pairs':all(MAPS[2][n] not in (MAPS[0][n],MAPS[1][n]) for n in range(4))}
    run(s,key,teach)
    return [history_probe(s,key,2,split) for split in ('train','test')]


def plastic(s):
    trains,test=new_mapping(s)
    newtrain=np.load(WORK/'cases'/trains/'features.npz');newtest=np.load(WORK/'cases'/test/'features.npz')
    # Four feedback examples (one per name) per scene, with old-example replay.
    for kind in ('activity','incoming'):
        def execute(case):
            source='learned' if kind=='activity' else 'incoming'
            head,layout=SpatialChoice.restore(OLD/f'cases/B-s223-{source}-fit/controller',device())
            before=head.predict(newtest[kind]).argmax(-1)
            oldtrain=[np.load(OLD/f'cases/B-s223-p1-h{h}-teach-train-normal/features.npz') for h in (0,1)]
            oldtest=[np.load(OLD/f'cases/B-s223-p1-h{h}-teach-test-normal/features.npz') for h in (0,1)]
            results=[]
            old_before=[head.predict(a[kind]).argmax(-1).tolist() for a in oldtest]
            for count in (4,16):
                # Restore the SAME frozen baseline for each dose, not cumulative.
                head,_=SpatialChoice.restore(OLD/f'cases/B-s223-{source}-fit/controller',device())
                x=np.concatenate([newtrain[kind][:count],*(a[kind][:4] for a in oldtrain)])
                y=np.concatenate([newtrain['y'][:count],*(a['y'][:4] for a in oldtrain)])
                fit=head.fit(x,y,steps=600,check=s.guard)
                head.save(case.path/f'feedback-{count}')
                prediction=head.predict(newtest[kind]).argmax(-1)
                oldpred=[head.predict(a[kind]).argmax(-1) for a in oldtest]
                results.append({'feedback_examples':count,'old_rehearsal_examples':8,'fit':fit,
                    'new_correct':int((prediction==newtest['y']).sum()),'new_n':len(prediction),
                    'new_predictions':prediction.tolist(),
                    'old_correct':sum(int((p==a['y']).sum()) for p,a in zip(oldpred,oldtest)),
                    'old_n':sum(len(a['y']) for a in oldtest)})
            return {'kind':kind,'frozen_new_correct':int((before==newtest['y']).sum()),'new_n':len(before),
                'frozen_old_correct':sum(int((np.array(p)==a['y']).sum()) for p,a in zip(old_before,oldtest)),
                'conditions':results,'teacher_labels':'external supervised feedback, never held-out inference'}
        run(s,'D-'+kind,execute)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','optics','eye-teach','eye-collect','eye-fit','feedback','memory','plastic'))
    parser.add_argument('--seed',type=int,choices=(223,279),default=223)
    parser.add_argument('--unlearned',action='store_true');parser.add_argument('--delay',type=int,choices=(0,6,30))
    parser.add_argument('--split',choices=('train','test'),default='train')
    parser.add_argument('--kind',choices=('activity','incoming'),default='activity')
    args=parser.parse_args()
    if args.command=='prepare':
        new_json(WORK/'usage.json',{'used_percent':76});new_json(WORK/'instances.json',{'created':0})
    s=study(args.command=='prepare')
    try:
        if args.command=='prepare':print(s.project)
        elif args.command=='optics':optics(s)
        elif args.command=='eye-teach':eye_teach(s)
        elif args.command=='eye-collect':eye_collect(s,args.split)
        elif args.command=='eye-fit':eye_fit(s,args.kind)
        elif args.command=='feedback':feedback(s)
        elif args.command=='memory':memory(s,args.seed,not args.unlearned,(args.delay,) if args.delay is not None else (0,6,30))
        elif args.command=='plastic':plastic(s)
    finally:s.db.close()


if __name__=='__main__':main()
