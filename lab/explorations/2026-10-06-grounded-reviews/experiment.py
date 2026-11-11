"""E55: grounded expanding reviews and balanced reference tests. Core unchanged."""
import argparse
from dataclasses import replace
import gzip
import itertools
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]; sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from lab.tools.grounded_classroom import GroundedClassroom,VERSION
from lab.tools.classroom_reviews import classroom_reviews
from lab.tools.shape_color_world import SHAPES,COLORS,POSITIONS
from lab.tools.activity_controller import ActivityLayout,ActivityController
from lab.tools.service_study import Study,StudyConfig,new_json,read_json,write_gzip,encoded
from threemind_core import StateImage
from threemind_runtime.host import create_engine
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.activity_stream import RawActivityStream
from threemind_runtime.sensory import TextSensor,TextSensorConfig

HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/grounded-reviews-20261006'
DT=50000
LABELS=(*SHAPES,*COLORS)


def study(prepare=False):
    return Study(StudyConfig('grounded-reviews/1','E55 身体背景与间隔复习',HERE,WORK,62,
        instance_limit=900,wall_seconds=7200,storage_soft=6*2**30,storage_hard=8*2**30,
        usage_soft_delta=5,usage_hard_delta=8),prepare=prepare)


class Case:
    def __init__(self,s,key):
        self.s=s; self.path=WORK/'cases'/key
        if self.path.exists():raise RuntimeError('preserve existing case: '+key)
        s.guard(True); self.path.mkdir(parents=True); self.born=time.monotonic()
        s.active_case=SimpleNamespace(born_wall=self.born)
        new_json(self.path/'started.json',{'epoch':time.time(),'runner_signature':s.runner_signature})

    def finish(self,result):
        elapsed=time.monotonic()-self.born
        new_json(self.path/'result.json',result|{'wall_seconds':elapsed,'runner_signature':self.s.runner_signature})
        self.s.completed_count+=1; self.s.completed_wall+=elapsed; self.s.active_case=None
        print(json.dumps({'case':self.path.name,'wall_seconds':round(elapsed,2),**result},ensure_ascii=False),flush=True)


class Classroom:
    def __init__(self,seed=223,plasticity=True,state=None,image=None):
        p=WORK/'instances.json'; n=read_json(p)['created'] if p.exists() else 0
        if n>=900:raise RuntimeError('registered instance limit')
        p.write_bytes(encoded({'created':n+1}))
        sensory_seed=state['world']['seed'] if state else 91+seed-223
        self.world=GroundedClassroom.restore(state['world']) if state else GroundedClassroom(sensory_seed)
        self.engine=create_engine(None if state else {'seed':seed,'plasticity':plasticity},
                state=(image or StateImage(encoded(state['core']))) if state else None,
                kernel_id=state['core']['dynamics'] if state else 'threemind.continuous-memory/2')
        self.reader=ReadoutSession(self.engine,record=lambda row:None,config={
            'structural_readout':{'enabled':False},'temporal_readout':{'enabled':False},
            'activity_readout':{'enabled':False}},state=state['reader'] if state else None)
        self.sensor=TextSensor(sensory_seed,TextSensorConfig(frame_characters=1,frame_interval_us=DT))
        self.stream=RawActivityStream(); self.current=None
        self.stream.subscribe('E55-raw-observer',self._receive)

    def _receive(self,frame): self.current=frame

    def snapshot(self):
        return {'core':self.engine.capture_state().to_dict(),'reader':self.reader.capture(),'world':self.world.state()}

    def layout(self):
        return ActivityLayout((*self.world.channels,*(self.sensor.identity(0x100000+i) for i in range(self.sensor.config.channel_count))))

    def tick(self,frame=None,*,guard=lambda:None,action=None):
        guard(); observation=self.world.observe(); stimulus=self.world.stimulus(observation)
        if frame:
            channels=dict(stimulus.channels)
            if channels.keys() & dict(frame['stimulus'].channels).keys():raise ValueError('sensory port collision')
            channels.update(frame['stimulus'].channels)
            stimulus=replace(stimulus,channels=tuple(sorted(channels.items())))
        self.reader.schedule([{'stimulus':stimulus,'labels':{}}],source='grounded-classroom-sampling',adapter_id=VERSION)
        self.reader.advance_to(self.engine.time_us+DT,guard=guard)
        if self.engine.life=='dead':raise RuntimeError('Core died; no automatic revival')
        if action is not None:
            # Observe the actual output bus before selecting the next physical
            # force. The force only affects the next sensory sample, not Core.
            self.stream.sample(self.engine)
            row={'observation':observation,'stimulus':stimulus.to_dict(),'activity':self.current}
            force=action(row)
            self.world.advance_physics(force);self.world.time_s=self.engine.time_us/1e6
            row['action']=list(map(float,force));row['pointer_after']=self.world.state()['pointer']
            return row
        self.world.advance_physics(); self.world.time_s=self.engine.time_us/1e6
        self.stream.sample(self.engine)
        return {'observation':observation,'stimulus':stimulus.to_dict(),'activity':self.current}

    def language(self,text,*,hold=10,guard=lambda:None):
        frames=list(self.sensor.frames(text))
        return [self.tick(f,guard=guard) for f in frames]+[self.tick(guard=guard) for _ in range(hold)]


def window(layout,rows,count=6):
    ids=np.rint(np.linspace(0,len(rows)-1,count)).astype(int)
    return np.stack([layout.frame(rows[i]['activity']) for i in ids])


def read_gzip(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:return json.load(stream)


def device():
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(.65);return 'cuda'
    return 'cpu'


def lesson(row):
    item,rep=row['item'],row['presentation'];cat=int(item>=4);value=item%4
    rng=np.random.default_rng(2100+rep*31+item)
    order=rng.permutation(4).tolist();view=(rep-1)%4
    if row['phase']=='initial':
        items=[(v,4) if cat==0 else (4,v) for v in order]
    else:
        shift=1+(rep-13)%3
        items=[(v,(v+shift)%4) for v in order]
    slot=next(i for i,p in enumerate(items) if p[cat]==value)
    text=('这是什么形状？' if cat==0 else '这是什么颜色？')+f'这是{LABELS[item]}。'
    return {'items':items,'variant':view,'slot':slot,'category':cat,'target':item,'text':text}


def teach(s,seed,condition):
    key=f's{seed}-{condition}';case=Case(s,key+'-teaching')
    c=Classroom(seed,plasticity=condition!='frozen')
    schedule=classroom_reviews(mode='uniform' if condition=='uniform' else 'spaced')
    schedule=[row|lesson(row) for row in schedule]
    new_json(case.path/'schedule.json',schedule)
    new_json(case.path/'protocol.json',{'world':VERSION,'kernel':c.engine.capture_state().to_dict()['config'],
          'condition':condition,'text':c.sensor.config.__dict__,'background':'continuous simulated physical measurements',
          'per_lesson_us':1500000,'planned_end_us':516000000})
    with gzip.open(case.path/'teaching.jsonl.gz','xt',encoding='utf-8') as out:
        for index,task in enumerate(schedule):
            c.world.set_scene([(i,4) for i in range(4)]);c.world.marker=None
            while c.engine.time_us<task['time_us']:
                out.write(encoded({'kind':'interval','process':c.tick(guard=s.guard)}).decode()+'\n')
            if c.engine.time_us!=task['time_us']:raise RuntimeError('lesson is off the declared simulation schedule')
            c.world.set_scene(task['items'],task['variant']);c.world.marker=list(POSITIONS[task['slot']])
            frames=list(c.sensor.frames(task['text']))
            if len(frames)>30:raise RuntimeError('whole sentence exceeds reserved teaching duration')
            rows=[c.tick(f,guard=s.guard) for f in frames]
            rows.extend(c.tick(guard=s.guard) for _ in range(30-len(frames)))
            out.write(encoded({'kind':'lesson','index':index,'lesson':task,'process':rows}).decode()+'\n')
            if index%24==0:print(json.dumps({'teaching':key,'lesson':index,'of':168,'sim_seconds':c.engine.time_us/1e6}),flush=True)
    snapshot=c.snapshot();write_gzip(case.path/'checkpoint.json.gz',snapshot)
    edges=snapshot['core']['edges'];nodes=c.engine.observation_nodes()
    case.finish({'kind':'teaching','seed':seed,'condition':condition,'lessons':len(schedule),
        'sim_seconds':c.engine.time_us/1e6,'nodes':len(nodes),'edges':len(edges),
        'weight_sum':sum(e['weight'] for e in edges),'weight_max':max((e['weight'] for e in edges),default=0.)})


def probes(split):
    settings=[]
    views=(0,1,2,3) if split=='train' else (0,2) if split=='permutations' else (5,6)
    shifts=(0,) if split=='held' else (1,2,3)
    scene_id=0
    for shift in shifts:
        for view in views:
            order=np.random.default_rng(910+view*11+shift).permutation(4).tolist()
            if split=='permutations':
                old={tuple(np.random.default_rng(910+v*11+shift).permutation(4).tolist()) for v in range(4)}
                options=[q for q in itertools.permutations(range(4)) if q not in old]
                order=list(options[(shift*7+view)%len(options)])
            items=[(v,(v+shift)%4) for v in order]
            for slot in range(4):
                for cat in range(2):
                    settings.append({'scene':scene_id,'items':items,'variant':view,'slot':slot,'category':cat,
                        'target':items[slot][cat]+4*cat,'text':'这是什么形状？' if cat==0 else '这是什么颜色？'})
            scene_id+=1
    return settings


def collect(s,seed,condition,split,mode='normal'):
    key=f's{seed}-{condition}';case=Case(s,key+'-'+split+('-'+mode if mode!='normal' else ''))
    state=read_gzip(WORK/f'cases/{key}-teaching/checkpoint.json.gz');image=StateImage(encoded(state['core']))
    c0=Classroom(state=state,image=image);layout=c0.layout();xs=[];ys=[];meta=[]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
        settings=probes(split)[:8] if mode=='rescue' else probes(split)
        for index,task in enumerate(settings):
            c=Classroom(state=state,image=image)
            if mode in ('silence','rescue'):
                pairs=[(e['source'],e['target']) for e in state['core']['edges']]
                c.engine.intervene(edges=pairs,action='silence')
                if mode=='rescue':c.engine.intervene(edges=pairs,action='unsilence')
            c.world.set_scene(task['items'],task['variant']);c.world.marker=list(POSITIONS[task['slot']])
            rows=c.language(task['text'],guard=s.guard)
            x=window(layout,rows);xs.append(x);ys.append(task['target']);meta.append(task)
            out.write(encoded({'trial':task,'process':rows}).decode()+'\n')
            if index%24==0:print(json.dumps({'collect':case.path.name,'trial':index,'of':len(settings)}),flush=True)
    np.savez_compressed(case.path/'features.npz',x=xs,y=ys)
    new_json(case.path/'trials.json',meta);new_json(case.path/'layout.json',list(layout.channels))
    case.finish({'kind':'observations','seed':seed,'condition':condition,'split':split,'mode':mode,'n':len(xs)})


def score(head,path):
    arr=np.load(path/'features.npz',allow_pickle=False);x,y=arr['x'],arr['y']
    predictions=head.predict(x).argmax(-1)
    permutation=np.random.default_rng(903).permutation(len(y))
    shuffled=head.predict(x[permutation]).argmax(-1);zero=head.predict(np.zeros_like(x)).argmax(-1)
    trials=[r|{'prediction':int(p),'answer':LABELS[p],'correct':int(p)==r['target'],
               'shuffled':int(q),'zero':int(z),'shuffled_source_index':int(j)}
            for r,p,q,z,j in zip(read_json(path/'trials.json'),predictions,shuffled,zero,permutation)]
    groups=sorted({(r['scene'],r['category']) for r in trials})
    sensitive=0;perfect=0
    for scene,cat in groups:
        group=[r for r in trials if (r['scene'],r['category'])==(scene,cat)]
        sensitive+=len({r['prediction'] for r in group})>1;perfect+=all(r['correct'] for r in group)
    return {'n':len(y),'correct':int((predictions==y).sum()),'shape_correct':int(((predictions==y)&(y<4)).sum()),
        'color_correct':int(((predictions==y)&(y>=4)).sum()),'wrong_category':int(((predictions<4)!=(y<4)).sum()),
        'pointer_sensitive_groups':sensitive,'all_four_correct_groups':perfect,'groups':len(groups),
        'shuffled_correct':int((shuffled==y).sum()),'zero_correct':int((zero==y).sum())},trials


def fit(s,seed,condition):
    key=f's{seed}-{condition}';case=Case(s,key+'-expression');parent=WORK/f'cases/{key}-train'
    data=np.load(parent/'features.npz',allow_pickle=False);x,y=data['x'],data['y']
    head=ActivityController(x.shape[-1],8,seed=seed).to(device())
    fitted=head.fit(x,y,steps=1500,check=s.guard)
    head.save(case.path/'controller',read_json(parent/'layout.json'))
    result={'kind':'expression','seed':seed,'condition':condition,'fit':fitted,
        'train_n':len(y),'train_correct':int((head.predict(x).argmax(-1)==y).sum())}
    predictions=[]
    for split in ('familiar','held'):
        result[split],rows=score(head,WORK/f'cases/{key}-{split}')
        predictions.extend(r|{'split':split} for r in rows)
    new_json(case.path/'predictions.json',predictions);case.finish(result)


def score_extra(s,seed,condition,split,mode):
    key=f's{seed}-{condition}';suffix=split+('-'+mode if mode!='normal' else '')
    case=Case(s,key+'-'+suffix+'-score')
    head,_=ActivityController.restore(WORK/f'cases/{key}-expression/controller',device())
    path=WORK/f'cases/{key}-{suffix}';result,trials=score(head,path)
    if mode=='rescue':
        original=np.load(WORK/f'cases/{key}-{split}/features.npz',allow_pickle=False)['x'][:8]
        restored=np.load(path/'features.npz',allow_pickle=False)['x']
        result['max_raw_difference_from_original']=float(np.max(np.abs(original-restored)))
    new_json(case.path/'predictions.json',trials)
    case.finish({'kind':'extra-score','seed':seed,'condition':condition,'split':split,'mode':mode,**result})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('prepare','teach','collect','fit','suite','extra'))
    p.add_argument('--seed',type=int,default=223)
    p.add_argument('--condition',choices=('spaced','frozen','uniform'),default='spaced')
    p.add_argument('--split',choices=('train','familiar','held','permutations'),default='train')
    p.add_argument('--mode',choices=('normal','silence','rescue'),default='normal')
    a=p.parse_args();s=study(a.command=='prepare')
    try:
        if a.command=='prepare':
            new_json(WORK/'instances.json',{'created':0});new_json(WORK/'usage.json',{'used_percent':62})
            for name in ('grounded_classroom.py','classroom_reviews.py','shape_color_world.py','activity_controller.py'):
                dest=WORK/'delivered-tools/lab/tools'/name;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/'lab/tools'/name,dest)
            print(s.project)
        elif a.command=='teach':teach(s,a.seed,a.condition)
        elif a.command=='collect':collect(s,a.seed,a.condition,a.split,a.mode)
        elif a.command=='fit':fit(s,a.seed,a.condition)
        elif a.command=='extra':
            if a.split=='train':raise ValueError('extra is for registered tests, not reader training')
            prefix=f's{a.seed}-{a.condition}-{a.split}'+('-'+a.mode if a.mode!='normal' else '')
            if not (WORK/f'cases/{prefix}/result.json').exists():collect(s,a.seed,a.condition,a.split,a.mode)
            score_extra(s,a.seed,a.condition,a.split,a.mode)
        elif a.command=='suite':
            prefix=f's{a.seed}-{a.condition}'
            if not (WORK/f'cases/{prefix}-teaching/result.json').exists():teach(s,a.seed,a.condition)
            for split in ('train','familiar','held'):
                if not (WORK/f'cases/{prefix}-{split}/result.json').exists():collect(s,a.seed,a.condition,split)
            if not (WORK/f'cases/{prefix}-expression/result.json').exists():fit(s,a.seed,a.condition)
    finally:s.db.close()


if __name__=='__main__':main()
