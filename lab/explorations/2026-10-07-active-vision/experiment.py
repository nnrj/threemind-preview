"""E59 bounded active-vision study. Stages are resumable; evidence is append-only."""
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
import psutil
import torch
from lab.tools.active_eye import ActiveEyeClassroom,EyeConfig,scan_angle
from lab.tools.whole_scene_classroom import WholeSceneClassroom
from lab.tools.classroom_eye import DetailedClassroom
from lab.tools.sensorimotor_session import SensorimotorSession,activity_totals,growth_summary
from lab.tools.service_study import Study,StudyConfig,new_json,read_json,write_gzip,encoded
from lab.tools.shape_color_world import POSITIONS,SHAPES,COLORS,Pointer
from lab.tools.choice_attribution import raw_window
from lab.tools.foveal_choice import FovealChoice
from lab.tools.foveal_sequence import FovealSequence

HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/active-vision-20261007'


def read_gzip(p):
    with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)


class BoundedStudy(Study):
    def guard(self,force=False):
        super().guard(force)
        if force:self.failed_wall=sum(read_json(p)['wall_seconds'] for p in (self.work/'cases').glob('*/stopped.json'))
        active=time.monotonic()-self.active_case.born_wall if self.active_case else 0
        if self.completed_wall+getattr(self,'failed_wall',0)+active>self.settings.wall_seconds:
            raise RuntimeError('total compute budget including failed attempts')


def study(prepare=False):
    return BoundedStudy(StudyConfig('active-vision/1','E59 视觉焦点、扫视与眼手配合',HERE,WORK,80,
        instance_limit=512,wall_seconds=10800,storage_soft=6*2**30,storage_hard=8*2**30,
        usage_soft_delta=5,usage_hard_delta=8),prepare=prepare)


def instance(s,**kwargs):
    p=WORK/'instances.json';n=read_json(p)['created']
    if n>=s.settings.instance_limit:raise RuntimeError('created-instance budget')
    p.write_bytes(encoded({'created':n+1}))
    return SensorimotorSession(**kwargs)


def run(s,key,fn):
    p=WORK/'cases'/key
    if (p/'result.json').exists():return read_json(p/'result.json')
    if p.exists():raise RuntimeError('preserve incomplete case '+key+'; register a new attempt')
    s.guard(True);p.mkdir(parents=True);start=time.monotonic()
    s.active_case=SimpleNamespace(born_wall=start)
    new_json(p/'started.json',{'epoch':time.time(),'runner_signature':s.runner_signature})
    try:
        result=fn(p);result|={'wall_seconds':time.monotonic()-start,'runner_signature':s.runner_signature}
        new_json(p/'result.json',result);s.active_case=None;s.completed_count+=1;s.completed_wall+=result['wall_seconds']
        print(json.dumps({'case':key,**result},ensure_ascii=False),flush=True);return result
    except Exception as error:
        new_json(p/'stopped.json',{'error':str(error),'wall_seconds':time.monotonic()-start});raise


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():torch.cuda.set_per_process_memory_fraction(.60);return 'cuda'
    return 'cpu'


def optics(s):
    for kind in ('old-fields','whole','fixed','scan','scan-low-gain'):
        def execute(p):
            w=(DetailedClassroom(resolution=4) if kind=='old-fields' else WholeSceneClassroom() if kind=='whole' else
               ActiveEyeClassroom(config=EyeConfig(visual_gain=.0075) if kind=='scan-low-gain' else None))
            w.set_scene([(0,0),(1,1),(2,2),(3,3)])
            c=instance(s,world=w);metrics=[];ports=set();inputs=[];peak=0;start=time.monotonic()
            with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
                for i in range(200):
                    eye=w.eye_servo(scan_angle(w.time_s)) if kind.startswith('scan') else (0.,0.)
                    row=c.tick(eye=eye,guard=s.guard);out.write(encoded(row).decode()+'\n')
                    ports.update(int(k) for k,_ in row['stimulus']['channels'])
                    inputs.append(sum(float(v) for _,v in row['stimulus']['channels']))
                    peak=max(peak,psutil.Process().memory_info().rss)
                    if i in (39,199):
                        state=c.snapshot();metric=growth_summary(state)|{'elapsed_wall':time.monotonic()-start,
                            'eye_angle_rad':getattr(w,'eye_angle',np.zeros(2)).tolist()}
                        metrics.append(metric);print(json.dumps({'optics':kind,**metric}),flush=True)
            write_gzip(p/'checkpoint.json.gz',state)
            return {'kind':kind,'metrics':metrics,'active_input_channels':len(ports),'input_mean':float(np.mean(inputs)),
                    'declared_visual_ports':w.vision_width,'peak_rss_bytes':peak,'gains':w.observe().get('visual_gain_per_channel')}
        run(s,'A-'+kind,execute)


def teach(s,policy):
    def execute(p):
        c=instance(s);w=c.world;schedule=[(i,j) for i in range(8) for j in range(10)]
        schedule += [(i,10+j) for j in range(3) for i in range(8)]
        def tick(f=None):
            eye=w.eye_servo(scan_angle(w.time_s)) if policy=='scan' else (0.,0.)
            return c.tick(f,eye=eye,guard=s.guard)
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for index,(item,repeat) in enumerate(schedule):
                if index in (80,88,96):
                    w.marker=None
                    for _ in range((0,6,18)[(index-80)//8]*20):out.write(encoded({'kind':'interval','process':[tick()]}).decode()+'\n')
                cat=int(item>=4);value=item%4;order=np.roll(np.arange(4),(repeat+value)%4).tolist()
                items=[(2,v) if cat else (v,4) for v in order];slot=order.index(value)
                w.set_scene(items);w.marker=list(POSITIONS[slot])
                text='这是'+(COLORS[value]+'的物体' if cat else SHAPES[value])+'。'
                frames=list(c.sensor.frames(text));rows=[tick(frames[i] if i<len(frames) else None) for i in range(30)]
                out.write(encoded({'kind':'lesson','item':item,'repeat':repeat,'text':text,'process':rows}).decode()+'\n')
                if index%8==0:print(json.dumps({'case':'teach-'+policy,'lesson':index,'sim_s':c.engine.time_us/1e6}),flush=True)
        state=c.snapshot();write_gzip(p/'checkpoint.json.gz',state);new_json(p/'layout.json',list(c.layout.channels))
        return {'policy':policy,'lessons':104,**growth_summary(state)}
    return run(s,'B-teach-'+policy,execute)


def tasks(split):
    result=[];scenes={'train':6,'validation':2,'test':2,'holdout':2}[split];offset={'train':0,'validation':7000,'test':14000,'holdout':21000}[split]
    for category in ('color','shape','pair'):
        for scene in range(scenes):
            rng=np.random.default_rng(10713+offset+scene*31+('color','shape','pair').index(category)*521)
            order=rng.permutation(4).tolist()
            if category=='color':items=[(2,x) for x in order]
            elif category=='shape':items=[(x,4) for x in order]
            else:
                a,b=scene%4,(scene+1)%4;source=[(a,b),(a,(b+1)%4),((a+1)%4,b),((a+1)%4,(b+1)%4)]
                items=[source[i] for i in order]
            positions=(np.array(POSITIONS)+rng.uniform(-.07,.07,(4,2))).tolist()
            for slot,(shape,color) in enumerate(items):
                noun=COLORS[color]+'的物体' if category=='color' else SHAPES[shape] if category=='shape' else COLORS[color]+'的'+SHAPES[shape]
                result.append({'category':category,'scene':scene,'items':items,'positions':positions,'slot':slot,
                               'text':f'请指出{noun}。','split':split})
    rng=np.random.default_rng(80521+offset)
    return [result[i] for i in rng.permutation(len(result))]


def collect(s,policy,split):
    def execute(p):
        saved=read_gzip(WORK/f'cases/B-teach-{policy}/checkpoint.json.gz');c=instance(s,state=saved);w=c.world
        data={'activity':[],'incoming':[],'y':[]};examples=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            for ti,task in enumerate(tasks(split)):
                w.set_scene(task['items'],positions=task['positions']);w.marker=None
                w.pointer=Pointer(0.,-.85);w.acceleration=[0.,0.];w.motor_power=0.
                frames=list(c.sensor.frames(task['text']));rows=[]
                for i in range(60):
                    eye=w.eye_servo(scan_angle(w.time_s)) if policy=='scan' else (0.,0.)
                    rows.append(c.tick(frames[i] if i<len(frames) else None,eye=eye,guard=s.guard))
                    if i in (19,39,59):
                        # Sample just-observed geometry, not the post-action eye.
                        last=rows[-1]['observation'];angle=w.eye_angle.copy();w.eye_angle=np.array(last['eye_angle_rad']);w._refresh_directions()
                        y=w.receptor_for_point(task['positions'][task['slot']]);points=[w.ground_point(j).tolist() for j in range(len(w.cells))]
                        w.eye_angle=angle;w._refresh_directions()
                        for kind in ('activity','incoming'):data[kind].append(raw_window(c.layout,rows,kind=kind,count=16))
                        data['y'].append(y);examples.append(task|{'question_index':ti,'sample_index':i,'eye_angle_rad':last['eye_angle_rad'],
                            'world':w.state(),'receptor_ground_points':points})
                out.write(encoded({'task':task,'process':rows}).decode()+'\n')
                if ti%8==0:print(json.dumps({'collect':policy+'-'+split,'question':ti,'of':len(tasks(split))}),flush=True)
        np.savez_compressed(p/'features.npz',**data);new_json(p/'examples.json',examples)
        write_gzip(p/'checkpoint.json.gz',c.snapshot())
        return {'policy':policy,'split':split,'questions':len(tasks(split)),'samples':len(examples)}
    return run(s,f'B-{policy}-{split}',execute)


def fit(s,policy,kind,role='hand'):
    def execute(p):
        train=np.load(WORK/f'cases/B-{policy}-train/features.npz');validation=np.load(WORK/f'cases/B-{policy}-validation/features.npz')
        w=ActiveEyeClassroom();channels=read_json(WORK/f'cases/B-teach-{policy}/layout.json')
        head=FovealChoice(channels,w.channels[:w.vision_width],w.retinal_centers,w.retinal_widths,
                         seed=223 if role=='hand' else 501).to(device())
        fit_result=head.fit(train[kind],train['y'],steps=1200,validation=(validation[kind],validation['y']),check=s.guard,batch_size=4)
        head.save(p/'controller')
        output={'policy':policy,'kind':kind,'role':role,'fit':fit_result}
        for split,ds in (('train',train),('validation',validation),('test',np.load(WORK/f'cases/B-{policy}-test/features.npz'))):
            preds=np.concatenate([head.predict(ds[kind][i:i+4]).argmax(-1) for i in range(0,len(ds['y']),4)])
            examples=read_json(WORK/f'cases/B-{policy}-{split}/examples.json');rows=[]
            for pixel,e in zip(preds,examples):
                world=ActiveEyeClassroom.restore(e['world']);endpoint=np.asarray(e['receptor_ground_points'][int(pixel)])
                for _ in range(40):world.advance_physics(world.pointer.teacher_action(endpoint))
                actual=np.array([world.pointer.x,world.pointer.y]);distances=np.linalg.norm(np.array(e['positions'])-actual,axis=1)
                chosen=int(np.argmin(distances));rows.append({k:v for k,v in e.items() if k not in ('world','receptor_ground_points')}|
                    {'receptor':int(pixel),'target_receptor':int(ds['y'][len(rows)]),'endpoint':endpoint.tolist(),'actual':actual.tolist(),
                     'chosen':chosen,'correct':chosen==e['slot'],'target_distance':float(distances[e['slot']])})
            new_json(p/f'{split}-predictions.json',rows)
            final=[r for r in rows if r['sample_index']==59]
            output[split]={'n':len(final),'correct':sum(r['correct'] for r in final),'arrived':sum(r['target_distance']<=.20 for r in final),
                'by_category':{cat:sum(r['correct'] for r in final if r['category']==cat) for cat in ('color','shape','pair')},
                'exact_training_target_rate':float(np.mean(preds==ds['y'])),
                'at_1_2_3_seconds':{str(sec):sum(r['correct'] for r in rows if r['sample_index']==sec*20-1) for sec in (1,2,3)}}
        return output
    return run(s,f'B-fit-{policy}-{kind}'+('' if role=='hand' else '-eye'),execute)


def closed(s,policy,mode='normal',kind='activity',reader='original',split='test',limit=0):
    def execute(p):
        saved=read_gzip(WORK/'cases/B-teach-scan/checkpoint.json.gz')
        head_class=FovealChoice if reader=='original' else FovealSequence
        prefix=f'B-fit-scan-{kind}' if reader=='original' else f'S-fit-scan-{kind}-{reader}'
        hand,_=head_class.restore(WORK/f'cases/{prefix}/controller',device())
        eye,_=head_class.restore(WORK/f'cases/{prefix}-eye/controller',device()) if policy=='learned' else (None,None)
        pairs=[(e['source'],e['target']) for e in saved['core']['edges']]
        results=[];totals=[]
        with gzip.open(p/'process.jsonl.gz','xt',encoding='utf-8') as out:
            questions=tasks(split)
            if limit:
                chosen=[];counts={k:0 for k in ('color','shape','pair')}
                for task in questions:
                    cat=task['category']
                    if counts[cat]<limit//3:chosen.append(task);counts[cat]+=1
                questions=chosen
            for ti,task in enumerate(questions):
                c=instance(s,state=saved);w=c.world
                w.set_scene(task['items'],positions=task['positions']);w.marker=None
                w.pointer=Pointer(0.,-.85);w.acceleration=[0.,0.];w.motor_power=0.;w.contact_force=[0.,0.]
                if mode in ('silence','rescue'):
                    c.engine.intervene(edges=pairs,action='silence')
                    if mode=='rescue':c.engine.intervene(edges=pairs,action='unsilence')
                frames=list(c.sensor.frames(task['text']));rows=[];commands=[]
                for i in range(60):
                    if rows and mode!='empty':
                        values=raw_window(c.layout,rows,kind=kind,count=None if reader=='full' else 16)
                        hi=hand.select(values);ei=eye.select(values) if eye else None
                        ha=w.execute_hand_selection(hi,rows[-1]['observation'])
                        ea=w.execute_eye_selection(ei,rows[-1]['observation']) if eye else (w.eye_servo(scan_angle(w.time_s)) if policy=='scan' else np.zeros(2))
                    else:hi=ei=None;ha=np.zeros(2);ea=np.zeros(2)
                    row=c.tick(frames[i] if i<len(frames) else None,hand=ha,eye=ea,guard=s.guard)
                    rows.append(row);commands.append({'hand_receptor':hi,'eye_receptor':ei})
                actual=np.array([w.pointer.x,w.pointer.y]);distances=np.linalg.norm(np.array(task['positions'])-actual,axis=1)
                chosen=int(np.argmin(distances));activity=[activity_totals(r) for r in rows]
                result=task|{'chosen':chosen,'correct':chosen==task['slot'],'actual':actual.tolist(),
                             'target_distance':float(distances[task['slot']]),'eye_angle_rad':w.eye_angle.tolist(),
                             'associative_integral':sum(a['associative'] for a in activity)*.05,
                             'direct_integral':sum(a['direct'] for a in activity)*.05}
                results.append(result);out.write(encoded({'task':task,'process':rows,'commands':commands,'result':result}).decode()+'\n')
                totals.append(activity)
                if ti%4==0:print(json.dumps({'closed':policy+'-'+kind+'-'+mode,'trial':ti,'correct_so_far':sum(r['correct'] for r in results)}),flush=True)
        new_json(p/'predictions.json',results);new_json(p/'activity-totals.json',totals)
        return {'policy':policy,'kind':kind,'mode':mode,'reader':reader,'split':split,'n':len(results),'correct':sum(r['correct'] for r in results),
            'arrived':sum(r['target_distance']<=.2 for r in results),
            'by_category':{cat:sum(r['correct'] for r in results if r['category']==cat) for cat in ('color','shape','pair')},
            'associative_integral':sum(r['associative_integral'] for r in results),
            'source':'independent restored Core per question; actual closed-loop eye/hand physics; two independent supervised readers'}
    suffix='' if reader=='original' and split=='test' and not limit else f'-{reader}-{split}'+(f'-pilot{limit}' if limit else '')
    return run(s,f'C-{policy}-{kind}-{mode}'+suffix,execute)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','optics','teach','collect','fit','closed'])
    p.add_argument('--policy',choices=['fixed','scan','learned'],default='scan');p.add_argument('--split',choices=['train','validation','test','holdout'])
    p.add_argument('--kind',choices=['activity','incoming'],default='activity');p.add_argument('--role',choices=['hand','eye'],default='hand')
    p.add_argument('--reader',choices=['original','full','sparse'],default='original');p.add_argument('--limit',type=int,default=0)
    p.add_argument('--mode',choices=['normal','empty','silence','rescue'],default='normal');args=p.parse_args()
    if args.policy=='learned' and args.stage!='closed':p.error('learned gaze is a closed-loop condition')
    if not 0<=args.limit<=24 or args.limit%3:p.error('pilot limit is zero or a multiple of three through 24')
    if args.stage=='closed' and args.split in ('train','validation'):p.error('closed evaluation uses test or holdout')
    if args.stage=='prepare':
        s=study(True);new_json(WORK/'instances.json',{'created':0});new_json(WORK/'usage.json',{'used_percent':80})
        print(json.dumps({'project':s.project,'work':str(WORK)}));s.db.close();return
    s=study()
    try:
        if args.stage=='optics':optics(s)
        elif args.stage=='teach':teach(s,args.policy)
        elif args.stage=='collect':collect(s,args.policy,args.split or 'train')
        elif args.stage=='fit':fit(s,args.policy,args.kind,args.role)
        else:closed(s,args.policy,args.mode,args.kind,args.reader,args.split or 'test',args.limit)
    finally:s.db.close()


if __name__=='__main__':main()
