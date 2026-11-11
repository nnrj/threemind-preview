"""E57 attribution: bounded external baselines and fixed-reader history tests."""
import argparse
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import time
import weakref
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
import numpy as np
import torch
from threemind_core import StateImage
from threemind_runtime.host import create_engine
from threemind_runtime.readout_session import ReadoutSession
from threemind_runtime.activity_stream import RawActivityStream
from threemind_runtime.sensory import TextSensor, TextSensorConfig
from lab.tools.activity_controller import ActivityLayout
from lab.tools.spatial_choice import SpatialChoice
from lab.tools.choice_attribution import raw_window, paired_scores
from lab.tools.classroom_eye import DetailedClassroom
from lab.tools.shape_color_world import POSITIONS, Pointer
from lab.tools.service_study import Study, StudyConfig, new_json, read_json, write_gzip, encoded

HERE = Path(__file__).resolve().parent
WORK = ROOT/'.work/choice-attribution-20261006'
OLD = ROOT/'.work/vision-correction-20261006'
spec = importlib.util.spec_from_file_location('e56_attribution_reference', HERE.parent/'2026-10-06-vision-correction/experiment.py')
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
NAMES = ('甲', '乙', '丁', '戊')
MAPS = ((0,1,2,3), (1,2,3,0))
DT = 50000


def study(prepare=False):
    return Study(StudyConfig('choice-attribution/1', 'E57 指认答案的内核与外设归属', HERE, WORK, 74,
                 instance_limit=600, wall_seconds=5400, storage_soft=2*2**30, storage_hard=4*2**30,
                 usage_soft_delta=4, usage_hard_delta=6), prepare=prepare)


class Case:
    def __init__(self, s, key):
        self.s=s; self.path=WORK/'cases'/key
        if self.path.exists(): raise RuntimeError('preserve existing case: '+key)
        s.guard(True); self.path.mkdir(parents=True); self.born=time.monotonic()
        s.active_case=SimpleNamespace(born_wall=self.born)
        new_json(self.path/'started.json', {'epoch':time.time(), 'runner_signature':s.runner_signature})

    def finish(self, result):
        elapsed=time.monotonic()-self.born
        value=result|{'wall_seconds':elapsed, 'runner_signature':self.s.runner_signature}
        new_json(self.path/'result.json', value)
        self.s.completed_count+=1; self.s.completed_wall+=elapsed; self.s.active_case=None
        print(json.dumps({'case':self.path.name, **result, 'wall_seconds':round(elapsed,2)},ensure_ascii=False),flush=True)


class Classroom(old.Classroom):
    def __init__(self, seed=223, *, plasticity=True, state=None, image=None):
        path=WORK/'instances.json'; n=read_json(path)['created']
        if n>=600: raise RuntimeError('new instance budget')
        path.write_bytes(encoded({'created':n+1}))
        self.world=DetailedClassroom.restore(state['world']) if state else DetailedClassroom(91,weather_seed=47+seed-223,resolution=4)
        self.engine=create_engine(None if state else {'seed':seed,'plasticity':plasticity},
              state=(image or StateImage(encoded(state['core']))) if state else None,
              kernel_id=state['core']['dynamics'] if state else 'threemind.continuous-memory/2')
        self.reader=ReadoutSession(self.engine,record=lambda row:None,config={
            'structural_readout':{'enabled':False},'temporal_readout':{'enabled':False},'activity_readout':{'enabled':False}},
            state=state['reader'] if state else None)
        self.sensor=TextSensor(91,TextSensorConfig(frame_characters=1,frame_interval_us=DT))
        self.stream=RawActivityStream(); self.current=None; owner=weakref.ref(self)
        def receive(frame):
            c=owner()
            if c is not None: c.current=frame
        self.stream.subscribe('E57-raw-observer', receive)


def cached(key): return (WORK/'cases'/key/'result.json').exists()


def read_records(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f: yield json.loads(line)


def extract(s):
    case=Case(s,'A-recorded-inputs'); manifest={}
    for kind, base, parent in [('learned','teach','exposure'),('unlearned','nolearning','nolearning-exposure')]:
        layout=ActivityLayout(read_json(OLD/f'cases/r4-{base}-calibration/layout.json'))
        new_json(case.path/f'{kind}-layout.json',list(layout.channels))
        for split, names in [('train',[f'r4-{base}-calibration',f'r4-{parent}-practice']),
                             ('test',[f'r4-{parent}-shared-confirmation-normal'])]:
            activity=[]; incoming=[]; full=[]; labels=[]; meta=[]
            with gzip.open(case.path/f'{kind}-{split}.jsonl.gz','xt',encoding='utf-8') as dest:
                for name in names:
                    for entry in read_records(OLD/'cases'/name/'process.jsonl.gz'):
                        rows=entry['process'][:20]
                        if len(rows)!=20: raise ValueError('registered complete request length')
                        task=entry['trial']; labels.append(task['slot']); meta.append(task)
                        activity.append(raw_window(layout,rows))
                        incoming.append(raw_window(layout,rows,kind='incoming'))
                        full.append(raw_window(layout,rows,kind='incoming',count=None))
                        dest.write(encoded({'source_case':name,'trial':task,'process':rows}).decode()+'\n')
            np.savez_compressed(case.path/f'{kind}-{split}.npz',activity=activity,incoming=incoming,full=full,y=labels)
            new_json(case.path/f'{kind}-{split}-tasks.json',meta)
            manifest[f'{kind}-{split}']={'n':len(labels),'sources':names}
    case.finish(manifest)


def baseline(s, mode, seed):
    case=Case(s,f'A-{mode}-s{seed}'); src=WORK/'cases/A-recorded-inputs'
    origin='unlearned' if mode=='unlearned' else 'learned'
    key=mode if mode in ('incoming','full') else 'activity'
    train=np.load(src/f'{origin}-train.npz'); test=np.load(src/f'{origin}-test.npz')
    layout=read_json(src/f'{origin}-layout.json'); visual=DetailedClassroom(91,resolution=4).channels[:256]
    head=SpatialChoice(layout,visual,seed=seed).to(old.device())
    fit=head.fit(train[key],train['y'],steps=1200,check=s.guard)
    head.save(case.path/'controller')
    preds=head.predict(test[key]).argmax(-1); tasks=read_json(src/f'{origin}-test-tasks.json')
    rows=[t|{'prediction':int(p),'correct':int(p)==t['slot']} for p,t in zip(preds,tasks)]
    new_json(case.path/'predictions.json',rows)
    case.finish({'mode':mode,'seed':seed,'fit':fit,'train_correct':int((head.predict(train[key]).argmax(-1)==train['y']).sum()),
                 'train_n':len(train['y']),'correct':int((preds==test['y']).sum()),'n':len(preds),
                 'groups':{cat:int(sum(r['correct'] for r in rows if r['category']==cat)) for cat in ('color','shape','pair')},
                 'parameters':sum(p.numel() for p in head.parameters()),'time_samples':train[key].shape[1]})


def teaching(s, seed, history, *, plasticity=True, source=None, suffix=None):
    key=suffix or f'B-s{seed}-p{int(plasticity)}-h{history}-teach'
    case=Case(s,key); c=Classroom(seed,plasticity=plasticity,state=old.read_gzip(source) if source else None)
    start=c.engine.time_us; lessons=[]
    schedule=[(i,r,0) for i in range(4) for r in range(10)]
    schedule += [(i,10+rev,rev+1) for rev in range(3) for i in range(4)]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
        for index,(name,rep,review) in enumerate(schedule):
            if index in (40,44,48):
                c.world.marker=None; c.world.set_scene([(i,4) for i in range(4)])
                for _ in range((0,6,18)[review-1]*20):
                    out.write(encoded({'kind':'interval','process':[c.tick(guard=s.guard)]}).decode()+'\n')
            order=np.roll(np.arange(4),(rep+name)%4).tolist()
            target=MAPS[history][name]; slot=order.index(target)
            c.world.set_scene([(i,4) for i in order],rep%4); c.world.marker=list(POSITIONS[slot])
            text=f'这是{NAMES[name]}。'; frames=list(c.sensor.frames(text))
            rows=[c.tick(f,guard=s.guard) for f in frames]
            rows += [c.tick(guard=s.guard) for _ in range(30-len(rows))]
            lesson={'name':name,'object':target,'slot':slot,'text':text,'rep':rep,'history':history}
            lessons.append(lesson);out.write(encoded({'kind':'lesson','lesson':lesson,'process':rows}).decode()+'\n')
            if index%16==0: print(json.dumps({'case':key,'lesson':index,'of':52}),flush=True)
    snapshot=c.snapshot();write_gzip(case.path/'checkpoint.json.gz',snapshot);new_json(case.path/'lessons.json',lessons)
    new_json(case.path/'layout.json',list(c.layout().channels))
    case.finish({'seed':seed,'history':history,'plasticity':plasticity,'lessons':len(lessons),
                 'sim_seconds':(c.engine.time_us-start)/1e6,'edges':len(snapshot['core']['edges']),
                 'nodes':len(snapshot['core']['nodes'])})


def history_tasks(split):
    import itertools
    permutations=list(itertools.permutations(range(4)))
    chosen=(0,7,14,21) if split=='train' else (2,9,16,23)
    tasks=[]
    for scene,idx in enumerate(chosen):
        for name in range(4):
            tasks.append({'scene':scene,'name':name,'items':[(i,4) for i in permutations[idx]],
                'variant':scene if split=='train' else 5+scene%2,'start':[.1,-.15],
                'text':f'请指出{NAMES[name]}。','split':split})
    return tasks


def probe(s, source_key, history, split, *, common_key=None, mode='normal', masks=None, donor=None):
    key=f'{source_key}-{split}-{mode}';case=Case(s,key)
    state=old.read_gzip(WORK/'cases'/source_key/'checkpoint.json.gz')
    common=old.read_gzip(WORK/'cases'/(common_key or source_key)/'checkpoint.json.gz')
    if state['core']['time_us']!=common['core']['time_us']:raise ValueError('common external time required')
    state['world']=copy.deepcopy(common['world'])
    receipt=None
    if mode.startswith('transfer'):
        from lab.tools.choice_interventions import transfer_edges
        donor_state=old.read_gzip(WORK/'cases'/donor/'checkpoint.json.gz')
        state['core'],receipt=transfer_edges(state['core'],donor_state['core'],masks)
    image=StateImage(encoded(state['core'])); xs=[]; raw=[]; labels=[]; meta=[]
    with gzip.open(case.path/'process.jsonl.gz','xt',encoding='utf-8') as out:
        for i,task in enumerate(history_tasks(split)):
            c=Classroom(state=state,image=image);old.set_task(c,task)
            if mode.startswith('silence') or mode=='rescue':
                c.engine.intervene(edges=masks,action='silence')
                if mode=='rescue':c.engine.intervene(edges=masks,action='unsilence')
            rows=old.request(c,task['text'],s.guard)
            target=next(j for j,(shape,color) in enumerate(task['items']) if shape==MAPS[history][task['name']])
            xs.append(raw_window(c.layout(),rows));raw.append(raw_window(c.layout(),rows,kind='incoming'))
            labels.append(target);meta.append(task|{'target':target,'history':history})
            out.write(encoded({'trial':meta[-1],'process':rows}).decode()+'\n')
            if i%8==0:print(json.dumps({'case':key,'trial':i,'of':16}),flush=True)
    np.savez_compressed(case.path/'features.npz',activity=xs,incoming=raw,y=labels)
    new_json(case.path/'tasks.json',meta)
    case.finish({'n':len(labels),'source':source_key,'history':history,'mode':mode,'common_world':common_key or source_key,'transfer':receipt})


def history_fit(s, seed, mode):
    case=Case(s,f'B-s{seed}-{mode}-fit'); plasticity=int(mode!='unlearned')
    paths=[WORK/f'cases/B-s{seed}-p{plasticity}-h{h}-teach-train-normal/features.npz' for h in (0,1)]
    data=[np.load(p) for p in paths];kind='incoming' if mode=='incoming' else 'activity'
    x=np.concatenate([d[kind] for d in data]); y=np.concatenate([d['y'] for d in data])
    layout=read_json(WORK/f'cases/B-s{seed}-p{plasticity}-h0-teach/layout.json')
    model=SpatialChoice(layout,DetailedClassroom(91,resolution=4).channels[:256],seed=223).to(old.device())
    fit=model.fit(x,y,steps=1200,check=s.guard);model.save(case.path/'controller')
    test=[np.load(WORK/f'cases/B-s{seed}-p{plasticity}-h{h}-teach-test-normal/features.npz') for h in (0,1)]
    preds=[model.predict(d[kind]).argmax(-1).tolist() for d in test]; targets=[d['y'].tolist() for d in test]
    new_json(case.path/'predictions.json',{'predictions':preds,'targets':targets})
    # Small, task-relevant checks, not repeated large-file integrity sweeps.
    incoming_identical=bool(np.array_equal(test[0]['incoming'],test[1]['incoming']))
    if not incoming_identical:raise RuntimeError('history comparison leaked into current physical input')
    case.finish({'seed':seed,'mode':mode,'fit':fit,'train_correct':int((model.predict(x).argmax(-1)==y).sum()),
                 'train_n':len(y),'identical_current_input':incoming_identical,**paired_scores(preds,targets)})


def evaluate_frozen(s, seed, sources, key):
    case=Case(s,key);model,_=SpatialChoice.restore(WORK/f'cases/B-s{seed}-learned-fit/controller',old.device())
    arrays=[np.load(WORK/'cases'/p/'features.npz') for p in sources]
    if not np.array_equal(arrays[0]['incoming'],arrays[1]['incoming']): raise ValueError('unmatched current inputs')
    preds=[model.predict(a['activity']).argmax(-1).tolist() for a in arrays];ys=[a['y'].tolist() for a in arrays]
    new_json(case.path/'predictions.json',{'predictions':preds,'targets':ys,'sources':sources})
    case.finish({'seed':seed,'sources':sources,**paired_scores(preds,ys)})


def run_if(s,key,run):
    if not cached(key): run()


def history_suite(s, seed):
    s.allow_extension()
    for plasticity in (True,False):
        for history in (0,1):
            base=f'B-s{seed}-p{int(plasticity)}-h{history}-teach'
            run_if(s,base,lambda p=plasticity,h=history:teaching(s,seed,h,plasticity=p))
            for split in ('train','test'):
                key=f'{base}-{split}-normal'
                run_if(s,key,lambda b=base,h=history,t=split:probe(s,b,h,t,common_key=f'B-s{seed}-p1-h0-teach'))
    for mode in ('learned','unlearned','incoming'):
        run_if(s,f'B-s{seed}-{mode}-fit',lambda m=mode:history_fit(s,seed,m))
    # Teacher-only correction with fixed previously fitted reader, plus sham review.
    for h,condition in ((0,'continue'),(1,'reverse')):
        key=f'B-s{seed}-{condition}'
        run_if(s,key,lambda h=h,k=key:teaching(s,seed,h,source=WORK/f'cases/B-s{seed}-p1-h0-teach/checkpoint.json.gz',suffix=k))
        run_if(s,key+'-test-normal',lambda h=h,k=key:probe(s,k,h,'test',common_key=f'B-s{seed}-continue'))
    run_if(s,f'B-s{seed}-frozen-correction',lambda:evaluate_frozen(s,seed,
        [f'B-s{seed}-continue-test-normal',f'B-s{seed}-reverse-test-normal'],f'B-s{seed}-frozen-correction'))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('prepare','baselines','history'))
    parser.add_argument('--seed',type=int,choices=(223,279),default=223);args=parser.parse_args()
    if args.command=='prepare':
        new_json(WORK/'usage.json',{'used_percent':74});new_json(WORK/'instances.json',{'created':0})
    s=study(args.command=='prepare')
    try:
        if args.command=='prepare':print(s.project)
        elif args.command=='baselines':
            run_if(s,'A-recorded-inputs',lambda:extract(s))
            for seed in (223,279,337):
                for mode in ('learned','unlearned','incoming','full'):
                    run_if(s,f'A-{mode}-s{seed}',lambda m=mode,q=seed:baseline(s,m,q))
        else:history_suite(s,args.seed)
    finally:s.db.close()


if __name__=='__main__': main()
