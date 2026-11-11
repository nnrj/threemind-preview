"""E55 actual language-conditioned limb control, with readout-window comparison."""
import argparse
from dataclasses import asdict
import gzip
import json
import numpy as np
from experiment import (ROOT,WORK,Classroom,Case,study,read_gzip,read_json,new_json,
                        write_gzip,encoded,StateImage,ActivityController,device)
from lab.tools.classroom_motor import motor_reviews,choice_scene,raw_process_window
from lab.tools.shape_color_world import Pointer,SHAPES,COLORS,POSITIONS


def set_trial(c,task):
    c.world.set_scene(task['items'],task['variant']);c.world.marker=None
    c.world.pointer=Pointer(*task['start']);c.world.acceleration=[0.,0.];c.world.motor_power=0.


def request(c,text,guard):
    frames=list(c.sensor.frames(text))
    if len(frames)>20:raise ValueError('whole request exceeds one simulated second')
    rows=[c.tick(f,guard=guard) for f in frames]
    rows.extend(c.tick(guard=guard) for _ in range(20-len(frames)))
    return rows


def teaching_task(row):
    shape,color=row['pair'];rep=row['presentation']
    rng=np.random.default_rng(387+row['item']*131)
    slots=np.concatenate([rng.permutation(4) for _ in range(4)])
    views=np.concatenate([rng.permutation(4) for _ in range(4)])
    slot,variant=int(slots[rep-1]),int(views[rep-1])
    layout=rep+row['item']*23
    return row|{'slot':slot,'variant':variant,'items':choice_scene(shape,color,slot,layout),
       'start':np.random.default_rng(892+layout*43).uniform(-.8,.8,2).tolist(),
       'text':f'请指出{COLORS[color]}的{SHAPES[shape]}。'}


def teach(s):
    case=Case(s,'s223-motor-teaching')
    c=Classroom(state=read_gzip(WORK/'cases/s223-spaced-teaching/checkpoint.json.gz'))
    start=c.engine.time_us;layout=c.layout();schedule=[teaching_task(r) for r in motor_reviews()]
    new_json(case.path/'schedule.json',schedule)
    new_json(case.path/'protocol.json',{'parent':'s223-spaced-teaching','start_time_us':str(start),
        'request_frames':20,'action_frames':40,'teacher':'external PD forces during demonstration only',
        'testing_teacher_marker':False,'motor_fit_steps':1500,'sample_every_action_frames':4,
        'world':c.world.state()['schema'],'kernel':c.engine.config.to_dict()})
    xs={'recent':[],'episode':[]};ys=[];reached=0
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as stream:
        for index,task in enumerate(schedule):
            c.world.set_scene([(i,4) for i in range(4)]);c.world.marker=None
            while c.engine.time_us<start+task['time_us']:
                stream.write(encoded({'kind':'interval','process':[c.tick(guard=s.guard)]}).decode()+'\n')
            if c.engine.time_us!=start+task['time_us']:raise RuntimeError('motor lesson time mismatch')
            set_trial(c,task);history=request(c,task['text'],s.guard)
            for j in range(40):
                def demonstrate(row):
                    history.append(row)
                    force=c.world.pointer.teacher_action(POSITIONS[task['slot']])
                    if j%4==0:
                        for scope in xs:xs[scope].append(raw_process_window(layout,history,scope))
                        ys.append(force)
                    return force
                c.tick(guard=s.guard,action=demonstrate)
            error=float(np.linalg.norm(np.asarray(POSITIONS[task['slot']])-[c.world.pointer.x,c.world.pointer.y]))
            reached+=error<=.15
            stream.write(encoded({'kind':'lesson','index':index,'lesson':task,
                    'teacher_final_error':error,'process':history}).decode()+'\n')
            if index%12==0:print(json.dumps({'motor_teaching':index,'of':180,'sim_seconds':c.engine.time_us/1e6}),flush=True)
    write_gzip(case.path/'checkpoint.json.gz',c.snapshot())
    for scope,values in xs.items():np.savez_compressed(case.path/(scope+'.npz'),x=values,y=ys)
    new_json(case.path/'layout.json',list(layout.channels))
    case.finish({'kind':'motor-teaching','episodes':len(schedule),'samples':len(ys),
        'sim_seconds':(c.engine.time_us-start)/1e6,'teacher_reached':reached})


def fit(s,scope):
    case=Case(s,'s223-motor-fit-'+scope);parent=WORK/'cases/s223-motor-teaching'
    data=np.load(parent/(scope+'.npz'),allow_pickle=False)
    head=ActivityController(data['x'].shape[-1],2,regression=True,seed=223).to(device())
    fitted=head.fit(data['x'],data['y'],steps=1500,check=s.guard)
    head.save(case.path/'controller',read_json(parent/'layout.json'))
    case.finish({'kind':'motor-fit','scope':scope,'samples':len(data['y']),'fit':fitted})


def trials():
    rows=[]
    for shape in range(4):
        for color in range(4):
            for variant in (0,5):
                slot=(shape+2*color+variant)%4
                rows.append({'shape':shape,'color':color,'slot':slot,'variant':variant,
                    'held_out':shape==color,'items':choice_scene(shape,color,slot,200+shape*7+color*3+variant),
                    'text':f'请指出{COLORS[color]}的{SHAPES[shape]}。',
                    'start':np.random.default_rng(491+shape*31+color*3+variant).uniform(-.8,.8,2).tolist()})
    return rows


def test(s,scope,mode,*,validated=False):
    reader_name=scope+('-validated' if validated else '')
    case=Case(s,'s223-motor-test-'+reader_name+'-'+mode)
    source=WORK/'cases/s223-motor-teaching'
    state=read_gzip(source/'checkpoint.json.gz');image=StateImage(encoded(state['core']))
    controller=WORK/'cases/s223-motor-validation/controller' if validated else WORK/f'cases/s223-motor-fit-{scope}/controller'
    head,layout=ActivityController.restore(controller,device())
    pairs=[(e['source'],e['target']) for e in state['core']['edges']]
    results=[]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as stream:
        settings=trials()[:4] if mode=='rescue' else trials()
        for index,task in enumerate(settings):
            c=Classroom(state=state,image=image);set_trial(c,task);requested=task['slot'];text=task['text']
            if mode=='changed-request':
                requested=next(i for i,p in enumerate(task['items']) if p[0]==task['shape'] and p[1]!=task['color'])
                text=f'请指出{COLORS[task["items"][requested][1]]}的{SHAPES[task["shape"]]}。'
            if mode in ('silence','rescue'):
                c.engine.intervene(edges=pairs,action='silence')
                if mode=='rescue':c.engine.intervene(edges=pairs,action='unsilence')
            history=request(c,text,s.guard);errors=[]
            for j in range(40):
                def control(row):
                    history.append(row);x=raw_process_window(layout,history,scope)
                    if mode=='zero':x=np.zeros_like(x)
                    return head.predict([x])[0]
                c.tick(guard=s.guard,action=control)
                errors.append(float(np.linalg.norm(np.asarray(POSITIONS[requested])-[c.world.pointer.x,c.world.pointer.y])))
            distances=np.linalg.norm(np.asarray(POSITIONS)-[c.world.pointer.x,c.world.pointer.y],axis=1)
            chosen=int(distances.argmin())
            result=task|{'text':text,'requested_slot':requested,'chosen':chosen,
                'choice_correct':chosen==requested,'reached':errors[-1]<=.15,
                'entered_target':min(errors)<=.15,'error':errors[-1],
                'original_held_out':task['held_out'],
                'held_out':task['items'][requested][0]==task['items'][requested][1],
                'final_pointer':asdict(c.world.pointer),'action_source':scope,'mode':mode,'reader_name':reader_name}
            results.append(result);stream.write(encoded({'trial':result,'process':history}).decode()+'\n')
            if index%8==0:print(json.dumps({'motor_test':[scope,mode],'trial':index,'of':len(settings)}),flush=True)
    new_json(case.path/'trials.json',results)
    summary={'kind':'motor-test','scope':scope,'mode':mode,'reader_name':reader_name,'n':len(results),
        'choice_correct':sum(r['choice_correct'] for r in results),'reached':sum(r['reached'] for r in results),
        'entered_target':sum(r['entered_target'] for r in results),
        'median_error':float(np.median([r['error'] for r in results]))}
    for flag in (False,True):
        group=[r for r in results if r['held_out']==flag]
        summary['held_out' if flag else 'taught']={'n':len(group),'choice_correct':sum(r['choice_correct'] for r in group),
                                                  'reached':sum(r['reached'] for r in group)}
    if mode!='normal':
        baseline=read_json(WORK/f'cases/s223-motor-test-{reader_name}-normal/trials.json')[:len(results)]
        summary['choice_changed']=sum(a['chosen']!=b['chosen'] for a,b in zip(results,baseline))
        if mode=='changed-request':
            summary['both_requests_correct']=sum(a['choice_correct'] and b['choice_correct'] for a,b in zip(results,baseline))
        if mode=='rescue':
            summary['max_endpoint_difference']=max(abs(a['final_pointer'][key]-b['final_pointer'][key])
                for a,b in zip(results,baseline) for key in ('x','y','vx','vy'))
    case.finish(summary)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('teach','fit','test','suite'))
    p.add_argument('--scope',choices=('recent','episode'),default='episode')
    p.add_argument('--mode',choices=('normal','changed-request','silence','zero','rescue'),default='normal')
    a=p.parse_args();s=study()
    try:
        if a.command=='teach':teach(s)
        elif a.command=='fit':fit(s,a.scope)
        elif a.command=='test':test(s,a.scope,a.mode)
        else:
            if not (WORK/'cases/s223-motor-teaching/result.json').exists():teach(s)
            for scope in ('episode','recent'):
                if not (WORK/f'cases/s223-motor-fit-{scope}/result.json').exists():fit(s,scope)
                if not (WORK/f'cases/s223-motor-test-{scope}-normal/result.json').exists():test(s,scope,'normal')
            for mode in ('changed-request','silence','zero','rescue'):
                if not (WORK/f'cases/s223-motor-test-episode-{mode}/result.json').exists():test(s,'episode',mode)
    finally:s.db.close()


if __name__=='__main__':main()
