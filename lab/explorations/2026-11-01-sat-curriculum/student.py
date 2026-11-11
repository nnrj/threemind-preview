"""New continuous SAT students; no changes to the genuine /5.1 implementation."""
from __future__ import annotations
import copy, hashlib, json, random, sys, time
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'lab/explorations/2026-10-16-mechanism-discovery'))
sys.path.insert(0,str(ROOT/'lab/explorations/2026-11-01-sat-pilot'))
import pilot_m2 as base
import sat_problem as sat
from lab.tools.calibrated_activity import CalibratedActivity
FIELDS=('activation','inhibition','direct','associative')
FRAME_INDEX=np.rint(np.linspace(0,19,8)).astype(int).tolist()
LIMIT=96

def load(p):
    import gzip
    raw=Path(p).read_bytes()
    return json.loads(gzip.decompress(raw) if str(p).endswith('.gz') else raw)
def save(p,v):return base.original(Path(p),v,compressed=str(p).endswith('.gz'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tup(x):return tuple(tup(y) for y in x) if isinstance(x,list) else x

def tensor_hash(value):
    h=hashlib.sha256()
    def visit(x):
        if torch.is_tensor(x):
            z=x.detach().cpu().contiguous();h.update(str(z.dtype).encode());h.update(str(tuple(z.shape)).encode());h.update(z.numpy().tobytes())
        elif isinstance(x,dict):
            for k in sorted(x,key=str):h.update(str(k).encode());visit(x[k])
        elif isinstance(x,(list,tuple)):
            h.update(str(len(x)).encode())
            for y in x:visit(y)
        else:h.update(base.encoded(x))
    visit(value);return h.hexdigest()

class Student:
    def __init__(self,seed,identity):
        self.seed,self.identity=seed,identity
        self.rng=random.Random(seed)
        symbols=['C0','C1','C2','C3','P','N','K']
        self.mapping=dict(zip(symbols,self.rng.sample(range(1,2**32),len(symbols))))
        self.core=base.create_engine(base.Local51Config(seed=seed,energy_seed=seed ^ 0x1634AB),kernel_id=base.KERNEL,backend='native')
        self.reader=CalibratedActivity(list(self.mapping.values()),('prefer','avoid'),identity,seed=seed)
        self.next_background=0;self.recent=[];self.world=None;self.cursor={'stage':'birth'}
        self.input_digest=base.digest([]);self.input_count=0;self.lesson_times=[];self.sample_refs=[]
        self.reader_ref=None;self.learning_blocks=0
    def reader_digest(self):
        return tensor_hash([self.reader.state_dict(),self.reader.optimizer.state_dict(),self.reader.learning_rng,
                            self.reader.computed_updates,self.reader.committed_updates])
    def state(self):
        return dict(schema='threemind.sat-curriculum/1',seed=self.seed,identity=self.identity,
            core=self.core.capture_state().to_dict(),mapping=self.mapping,rng=json.loads(base.encoded(self.rng.getstate())),
            next_background=self.next_background,recent=self.recent,world=self.world,cursor=self.cursor,
            input_digest=self.input_digest,input_count=self.input_count,lesson_times=self.lesson_times,
            sample_refs=self.sample_refs,reader_ref=self.reader_ref,reader_digest=self.reader_digest(),
            learning_blocks=self.learning_blocks,torch_rng=torch.get_rng_state().tolist(),
            body={'type':'SAT-assignment','state':self.world},actuator={'type':'one-bit-flip','noise':.25},
            kernel=base.KERNEL)
    def checkpoint(self,folder,name):
        folder=Path(folder);rd=self.reader_digest()
        if self.reader_ref is None or self.reader_ref['digest']!=rd:
            rel=f'readers/{self.reader.committed_updates:06d}-{rd[:12]}'
            self.reader.save(folder/rel)
            self.reader_ref={'path':rel,'digest':rd,'files':{p.name:sha(p) for p in (folder/rel).iterdir()}}
        value=self.state();save(folder/name,value);return value
    @classmethod
    def restore(cls,folder,value):
        value=copy.deepcopy(value);obj=cls.__new__(cls)
        obj.seed=value['seed'];obj.identity=value['identity'];obj.mapping=value['mapping']
        obj.core=base.create_engine(state=base.StateImage.from_dict(value['core']),kernel_id=base.KERNEL,backend='native')
        obj.rng=random.Random();obj.rng.setstate(tup(value['rng']))
        for k in ('next_background','recent','world','cursor','input_digest','input_count','lesson_times','sample_refs','reader_ref','learning_blocks'):setattr(obj,k,value[k])
        for name,h in obj.reader_ref['files'].items():
            if sha(Path(folder)/obj.reader_ref['path']/name)!=h:raise RuntimeError('reader evidence changed')
        obj.reader=CalibratedActivity.restore(Path(folder)/obj.reader_ref['path'])
        torch.set_rng_state(torch.tensor(value['torch_rng'],dtype=torch.uint8))
        if base.digest(obj.state())!=base.digest(value):raise RuntimeError('whole-state restore mismatch')
        return obj
    def inject(self,t,values):
        event={'time_us':t,'channels':[[self.mapping[k],v] for k,v in values.items()],'intensity':1.}
        self.core.inject(base.Stimulus(t,tuple(tuple(x) for x in event['channels']),1.))
        self.input_digest=base.digest([self.input_digest,event]);self.input_count+=1
        return event
    def advance(self,end):
        if end<self.core.time_us:raise RuntimeError('time reversal')
        while self.next_background<=end:
            self.inject(self.next_background,{'K':.2});self.next_background+=500_000
        self.core.advance_to(end)
        if self.core.life=='dead':raise RuntimeError('new death: preserve in-flight')
    def question(self,category):
        if type(category) is not int or category not in range(4):raise ValueError('category')
        start=self.core.time_us;event=self.inject(start,{f'C{category}':.8});frames=[]
        for i in range(20):
            self.advance(start+(i+1)*50_000)
            frames.append(self.reader.layout.frame({'nodes':self.core.observation_nodes()}).tolist())
        x=[frames[i] for i in FRAME_INDEX]
        logits=self.reader.predict([x])[0].tolist();prediction=int(np.argmax(logits))
        row=dict(start_us=start,end_us=self.core.time_us,category=category,input=event,frames=frames,
                 frame_times_us=[start+(i+1)*50_000 for i in range(20)],selected_indices=FRAME_INDEX,
                 logits=logits,prediction=prediction,score=int(prediction==0))
        self.recent=(self.recent+[row])[-3:]
        return row
    def lesson(self,category,label,condition,stage):
        start=self.core.time_us;events=[]
        for i in range(5):
            t=start+i*250_000
            if t>self.core.time_us:self.advance(t)
            events.append(self.inject(t,{f'C{category}':.4,('P' if label==0 else 'N'):.4}))
        self.advance(start+1_500_000)
        row=dict(category=category,label=label,condition=condition,start_us=start,end_us=self.core.time_us,
                 events=events,stage=stage)
        self.lesson_times.append({k:v for k,v in row.items() if k!='events'});return row
    def curriculum(self,examples,history,stage,errors=None):
        # Initial 10 dense passes; review after added 2, 6 and 18 internal seconds.
        # Correction: two dense passes plus the same three increasingly spaced reviews.
        dense=10 if stage=='initial' else 2
        selected=[]
        if errors:
            selected=errors[:16]+[examples[c][1] | {'category':c} for c in range(4)]
        else:selected=[examples[c][0] | {'category':c} for c in range(4)]
        rows=[]
        for cycle in range(dense+3):
            gap=0 if cycle<dense else (2,6,18)[cycle-dense]
            self.advance(self.core.time_us+gap*1_000_000)
            current=copy.deepcopy(selected);self.rng.shuffle(current)
            labels=[int(e['category']!=0) for e in current]
            if history=='shuffled':self.rng.shuffle(labels)
            for e,label in zip(current,labels):
                rows.append(self.lesson(e['category'],label,e,stage))
        self.cursor={'stage':stage,'history':history}
        return dict(stage=stage,history=history,added_review_delays_s=[2,6,18],dense_passes=dense,lessons=rows)
    def sample(self,cases):
        rows=[]
        for e in cases:
            q=self.question(e['category'])
            rows.append({'condition':e,'question':q,'label':int(e['category']!=0)})
        return rows
    def fit(self,folder,rel,rows):
        save(Path(folder)/rel,rows);self.sample_refs.append(rel)
        records=[r for p in self.sample_refs for r in load(Path(folder)/p)]
        if len(records)>1024:raise RuntimeError('registered calibration sample limit')
        x=[[r['question']['frames'][i] for i in FRAME_INDEX] for r in records]
        y=[r['label'] for r in records];before=self.core.capture_state().to_dict()
        receipt=self.reader.continue_calibration(x,y,steps=1200)
        if before!=self.core.capture_state().to_dict():raise RuntimeError('calibration advanced/mutated Core')
        self.learning_blocks+=1
        return receipt | {'samples':len(records),'core_time_us':self.core.time_us,'reader_digest':self.reader_digest()}
    def solve(self,problem,limit=LIMIT):
        a,rng=sat.begin_problem(problem);initial=a[:];steps=[];start=self.core.time_us;wall=time.perf_counter()
        for step in range(limit):
            bad=sat.unsatisfied(problem['clauses'],a)
            if not bad:break
            ci=rng.choice(bad);candidates=[abs(v)-1 for v in problem['clauses'][ci]];rng.shuffle(candidates)
            breaks=[sat.break_count(problem['clauses'],a,v) for v in candidates]
            queries=[self.question(min(b,3)) for b in breaks]
            selected,noise=sat.choose([q['score'] for q in queries],rng,.25)
            a[candidates[selected]]=not a[candidates[selected]]
            steps.append(dict(step=step,clause=ci,candidates=candidates,breaks=breaks,queries=queries,
                              selected=selected,noise=noise,assignment=a[:]))
            self.world={'problem_id':problem['id'],'assignment':a[:],'step':step+1,
                        'environment_rng':json.loads(base.encoded(rng.getstate()))}
        solved=sat.verify_witness(problem['n'],problem['clauses'],a)
        self.world={'problem_id':problem['id'],'assignment':a[:],'step':len(steps),
                    'environment_rng':json.loads(base.encoded(rng.getstate()))}
        return dict(initial_assignment=initial,final_assignment=a,solved=solved,outcome='SAT' if solved else 'UNKNOWN',
                    flips=len(steps),steps=steps,start_us=start,end_us=self.core.time_us,wall_seconds=time.perf_counter()-wall)

def balanced_cases(examples,start,count,rng):
    cases=[examples[c][(start+i)%16] | {'category':c} for i in range(count) for c in range(4)]
    rng.shuffle(cases);return cases

def make_material(seed):
    m=sat.material(seed);dev=sat.material(seed+100000,per_size=2)
    m['development']=dev['training'];m['development_examples']=dev['examples'];m['dev_problems']=dev['tests'][:4]
    def canon(f):return tuple(sorted(tuple(sorted(c)) for c in f['clauses']))
    sets=[set(map(canon,x)) for x in (m['training'],m['development'],m['dev_problems'],m['tests'])]
    if any(sets[i]&sets[j] for i in range(4) for j in range(i)):raise RuntimeError('material overlap')
    return m
