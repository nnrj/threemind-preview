"""A declared exploratory shared-field reader, plus disjoint confirmation."""
import argparse
import gzip
import json
import numpy as np
from experiment import (ROOT,HERE,WORK,study,Case,read_json,new_json,read_gzip,device,
    Classroom,StateImage,encoded,DetailedClassroom,tasks,set_task,request,features,POSITIONS,COLORS,SHAPES)
from lab.tools.spatial_choice import SpatialChoice


def confirmation():
    output=[]
    for ci,category in enumerate(('color','shape','pair')):
        blocked={tuple(map(tuple,t['items'])) for split in ('calibration','practice','test') for t in tasks(split) if t['category']==category}
        for scene in range(2):
            rng=np.random.default_rng(8191+ci*100+scene)
            if category=='color':base=[(2,c) for c in range(4)]
            elif category=='shape':base=[(s,4) for s in range(4)]
            else:
                s=scene%4;c=(scene+1)%4;base=[(s,c),(s,(c+1)%4),((s+1)%4,c),((s+1)%4,(c+1)%4)]
            while True:
                items=[base[i] for i in rng.permutation(4)]
                if tuple(items) not in blocked:break
            blocked.add(tuple(items));start=rng.uniform(-.85,.85,2).tolist()
            for slot,(shape,color) in enumerate(items):
                noun=COLORS[color]+'的物体' if category=='color' else SHAPES[shape] if category=='shape' else COLORS[color]+'的'+SHAPES[shape]
                output.append({'category':category,'scene':scene,'slot':slot,'items':items,'variant':5+scene,
                               'start':start,'text':f'请指出{noun}。','split':'confirmation'})
    return output


def fit(s,n,parent):
    case=Case(s,f'r{n}-{parent}-shared-fit')
    base='nolearning' if parent.startswith('nolearning') else 'teach'
    data=np.load(WORK/f'cases/r{n}-{base}-calibration/features.npz');x,y=data['x'],data['y']
    if parent!=base:
        extra=np.load(WORK/f'cases/r{n}-{parent}-practice/features.npz')
        x=np.concatenate([x,extra['x']]);y=np.concatenate([y,extra['y']])
    w=DetailedClassroom.restore(read_json(WORK/f'cases/r{n}-{base}/protocol.json')['world'])
    layout=read_json(WORK/f'cases/r{n}-{base}-calibration/layout.json')
    head=SpatialChoice(layout,w.channels[:w.vision_width]).to(device())
    fitted=head.fit(x,y,steps=1200,check=s.guard);head.save(case.path/'controller')
    if parent.startswith('nolearning'):
        case.finish({'fit':fitted,'training_correct':int((head.predict(x).argmax(-1)==y).sum()),'training_n':len(y),
                     'status':'matched no-structural-learning control; no development selection'});return
    test=np.load(WORK/f'cases/r{n}-{parent}-test-normal/features.npz');meta=read_json(WORK/f'cases/r{n}-{parent}-test-normal/predictions.json')
    pred=head.predict(test['x']).argmax(-1);zero=head.predict(np.zeros_like(test['x'])).argmax(-1)
    rows=[r|{'shared_selected':int(p),'shared_correct':int(p)==r['slot'],'shared_zero_selected':int(z)} for r,p,z in zip(meta,pred,zero)]
    new_json(case.path/'predictions.json',rows)
    result={'fit':fitted,'training_correct':int((head.predict(x).argmax(-1)==y).sum()),'training_n':len(y),
           'status':'post-hoc development score; requires confirmation',
           'groups':{cat:{'n':sum(r['category']==cat for r in rows),'correct':sum(r['category']==cat and r['shared_correct'] for r in rows)} for cat in ('color','shape','pair')},
           'zero_correct':sum(r['slot']==int(z) for r,z in zip(meta,zero))}
    case.finish(result)


def test(s,n,parent,mode,reader_parent=None,world_parent=None):
    reader_parent=reader_parent or parent;world_parent=world_parent or parent
    suffix=('' if reader_parent==parent else '-reader-'+reader_parent)+('' if world_parent==parent else '-world-'+world_parent)
    case=Case(s,f'r{n}-{parent}-shared-confirmation-{mode}'+suffix)
    head,layout=SpatialChoice.restore(WORK/f'cases/r{n}-{reader_parent}-shared-fit/controller',device())
    state=read_gzip(WORK/f'cases/r{n}-{parent}/checkpoint.json.gz')
    if world_parent!=parent:
        state['world']=read_gzip(WORK/f'cases/r{n}-{world_parent}/checkpoint.json.gz')['world']
        if abs(state['world']['time_s']-int(state['core']['time_us'])/1e6)>1e-8:
            raise ValueError('common-world comparison requires matching simulation time')
    image=StateImage(encoded(state['core']))
    settings=read_json(HERE/'confirmation-tasks.json')
    scores=[];xs=[]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
        for index,task in enumerate(settings):
            c=Classroom(state=state,image=image);set_task(c,task)
            if mode in ('silence','rescue'):
                edges=[(e['source'],e['target']) for e in state['core']['edges']]
                c.engine.intervene(edges=edges,action='silence')
                if mode=='rescue':c.engine.intervene(edges=edges,action='unsilence')
            rows=request(c,task['text'],s.guard);x=features(c,rows);xs.append(x)
            selected=int(head.predict(x[None]).argmax(-1)[0])
            for _ in range(40):rows.append(c.tick(guard=s.guard,action=lambda row:c.world.pointer.teacher_action(POSITIONS[selected])))
            pos=np.array([c.world.pointer.x,c.world.pointer.y]);dist=np.linalg.norm(pos-np.array(POSITIONS),axis=1)
            result=task|{'selected':selected,'correct':selected==task['slot'],'final':pos.tolist(),
                    'selected_endpoint_reached':bool(dist[selected]<=.15),'requested_target_reached':bool(dist[task['slot']]<=.15),
                    'target_error_m':float(dist[task['slot']]),'control':'shared-field selection, servo executes only selected endpoint'}
            scores.append(result);out.write(encoded({'trial':result,'process':rows}).decode()+'\n')
            if index%8==0:print(json.dumps({'stage':case.path.name,'trial':index,'of':len(settings)}),flush=True)
    np.savez_compressed(case.path/'features.npz',x=xs,y=[r['slot'] for r in scores]);new_json(case.path/'predictions.json',scores)
    zero=head.predict(np.zeros_like(xs)).argmax(-1)
    shuffled=head.predict(np.asarray(xs)[np.random.default_rng(9401).permutation(len(xs))]).argmax(-1)
    case.finish({'source':parent,'reader_source':reader_parent,'world_source':world_parent,'resolution':n,'mode':mode,'groups':{cat:{'n':sum(r['category']==cat for r in scores),
       'correct':sum(r['category']==cat and r['correct'] for r in scores),'reached':sum(r['category']==cat and r['requested_target_reached'] for r in scores)} for cat in ('color','shape','pair')},
       'zero_correct':sum(r['slot']==int(p) for r,p in zip(scores,zero)),
       'shuffled_correct':sum(r['slot']==int(p) for r,p in zip(scores,shuffled)),
       'selected_endpoint_reached':sum(r['selected_endpoint_reached'] for r in scores),'n':len(scores)})


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('register','fit','test'))
    p.add_argument('--resolution',type=int,choices=(4,6),default=4);p.add_argument('--source',choices=('teach','exposure','corrected','nolearning-exposure'),default='teach')
    p.add_argument('--mode',choices=('normal','silence','rescue'),default='normal')
    p.add_argument('--reader-source',choices=('teach','exposure','corrected'))
    p.add_argument('--world-source',choices=('teach','exposure','corrected'));a=p.parse_args()
    if a.command=='register':new_json(HERE/'confirmation-tasks.json',confirmation());print('24 disjoint-layout confirmation tasks registered');return
    s=study()
    try:
        s.allow_extension()
        if a.command=='fit':fit(s,a.resolution,a.source)
        else:test(s,a.resolution,a.source,a.mode,a.reader_source,a.world_source)
    finally:s.db.close()

if __name__=='__main__':main()
