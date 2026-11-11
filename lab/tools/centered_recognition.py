"""A complete blank-born recognition system with a physically fixed whole eye.

Teacher labels train a personal peripheral; inference receives raw Core only.
This apparatus removes active search, not sensory/background information.
"""
import copy
import gzip
import json
from dataclasses import asdict
from pathlib import Path
import time
import numpy as np
import torch
from torch import nn
import mujoco
from lab.tools.developmental_world import DevelopmentalWorld, VERSION as DEV_WORLD
from lab.tools.active_eye import ActiveEyeClassroom
from lab.tools.sensorimotor_session import SensorimotorSession, WORLD_TYPES
from lab.tools.activity_controller import ActivityLayout, FIELDS
from lab.tools.continuous_motor import WINDOW, recent_window
from lab.tools.shape_color_world import Pointer, SHAPES, COLORS
from safetensors.torch import save_file, load_file

WORLD_VERSION='threemind.centered-observation/1'
VERSION='threemind.centered-system/1'
WORDS=(*SHAPES,*COLORS)


class CenteredWorld(DevelopmentalWorld):
    # Opt in only for this apparatus; historical classrooms still require objects.
    allow_empty_scene = True
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.pointer=Pointer(-.75,-.75)
        self.toys=False

    def set_scene(self,items,variant=0,positions=None):
        # Same physical renderer/receptors; no synthetic object crop.
        ActiveEyeClassroom.set_scene(self,items,variant,positions)
        n=len(items)
        self.anchors=np.array(self.positions).reshape(n,2)
        self.toy_velocity=np.zeros((n,2));self.resonance=np.zeros(n)
        self.contacting=np.zeros(n,bool);self.external_forces=np.zeros((n,2))
        self.external_sound=np.zeros(4);self.external_sound_position=np.array([0.,.5])
        self.object_ids=[mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_GEOM,'o'+str(i)) for i in range(n)]

    def present(self,shape,color,*,offset=(0.,0.)):
        # Intersection of the fixed optical axis with the objects' center plane.
        center=self.origin+( .16-self.origin[2])/self.forward[2]*self.forward
        self.set_scene([(int(shape),int(color))],positions=[(center[:2]+offset).tolist()])

    def advance_physics(self,action=(0.,0.),dt=.05,*,eye_action=(0.,0.),mouth=(0.,0.)):
        if any(np.any(v) for v in (action,eye_action,mouth)):
            raise ValueError('fixed diagnostic apparatus accepts no actuator commands')
        if not 0<dt<=.1:raise ValueError('bounded physical time')
        wx,wy,air,_=self.weather()
        # External rigid fixture reacts to the breeze. No invisible pose reset.
        self.contact_force=[-.15*wx,-.15*wy]
        self.acceleration=[0.,0.];self.motor_power=self.eye_power=0.
        self.body_temperature+=dt*.4*(air-self.body_temperature)/20
        self.time_s+=dt;self.resonance*=np.exp(-dt/.22)

    def observe(self,**kwargs):
        return super().observe(**kwargs)|{'schema':WORLD_VERSION,'apparatus':'fixed eye and hand; single centered object'}

    def stimulus(self,ob):
        if ob['schema']!=WORLD_VERSION:raise ValueError('centered world version')
        return super().stimulus(ob|{'schema':DEV_WORLD})

    def state(self):return super().state()|{'schema':WORLD_VERSION}

    @classmethod
    def restore(cls,state):
        if state['schema']!=WORLD_VERSION:raise ValueError('centered world version')
        return super().restore(state|{'schema':DEV_WORLD})


WORLD_TYPES[WORLD_VERSION]=CenteredWorld


class PersonalVocabulary(nn.Module):
    """Persistent eight-word peripheral with raw shared-cell temporal encoding."""
    def __init__(self,channels,retinal,identity,seed=631):
        super().__init__();self.identity=identity;self.seed=seed;self.layout=ActivityLayout(channels)
        self.retinal=tuple(map(int,retinal));self.steps=self.seen=0
        self.rng=np.random.default_rng(seed+1);self.retention_rng=np.random.default_rng(seed+2)
        self.readout_profile='recent-window'
        self.x=[];self.y=[];self.capacity=256
        self.register_buffer('vi',torch.tensor([4*self.layout.index[c]+f for c in self.retinal for f in range(4)],dtype=torch.long))
        self.register_buffer('oi',torch.tensor([4*self.layout.index[c]+f for c in self.layout.channels if c not in set(self.retinal) for f in range(4)],dtype=torch.long))
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.cell=nn.Sequential(nn.Linear(16,8),nn.Tanh())
            self.input=nn.Linear(len(self.retinal)//4*8+len(self.oi),48)
            self.position=nn.Parameter(torch.zeros(1,WINDOW,48))
            layer=nn.TransformerEncoderLayer(48,4,96,dropout=0,batch_first=True,norm_first=True)
            self.temporal=nn.TransformerEncoder(layer,1,enable_nested_tensor=False)
            self.output=nn.Sequential(nn.LayerNorm(48),nn.Linear(48,8))
        self.optimizer=torch.optim.AdamW(self.parameters(),lr=.001,weight_decay=.0001)

    def forward(self,x):
        if x.ndim!=3 or x.shape[1:]!=(WINDOW,self.layout.width):raise ValueError('raw complete window')
        b,t=x.shape[:2];shared=self.cell(x[...,self.vi].reshape(b,t,-1,16)).flatten(2)
        h=self.input(torch.cat((shared,x[...,self.oi]),-1))+self.position
        return self.output(self.temporal(h)[:,-1])

    def predict(self,x):
        x=np.asarray(x,dtype='float32')
        if x.shape!=(WINDOW,self.layout.width) or not np.isfinite(x).all():raise ValueError('raw finite activity')
        if not np.any(x):return None
        self.eval()
        with torch.no_grad():return self(torch.as_tensor(x[None],device=next(self.parameters()).device)).softmax(-1)[0].cpu().numpy()

    def teach(self,x,label,updates=2):
        x=np.asarray(x,dtype='float32')
        if x.shape!=(WINDOW,self.layout.width) or not np.isfinite(x).all() or not 0<=label<8 or not 0<=updates<=32:
            raise ValueError('bounded teacher supervision only')
        self.seen+=1
        if len(self.x)<self.capacity:self.x.append(x.copy());self.y.append(int(label))
        else:
            i=int(self.retention_rng.integers(self.seen))
            if i<self.capacity:self.x[i]=x.copy();self.y[i]=int(label)
        device=next(self.parameters()).device;self.train();loss=None
        for _ in range(updates):
            ids=self.rng.integers(len(self.x),size=min(16,len(self.x)))
            bx=torch.as_tensor(np.stack([self.x[i] for i in ids]),device=device)
            by=torch.tensor([self.y[i] for i in ids],device=device)
            self.optimizer.zero_grad(set_to_none=True)
            loss=nn.functional.cross_entropy(self(bx),by);loss.backward()
            nn.utils.clip_grad_norm_(self.parameters(),1.);self.optimizer.step();self.steps+=1
        self.eval();return None if loss is None else float(loss.detach())

    def calibrate(self,x,y,*,updates=1200,guard=lambda:None):
        """Continue this peripheral on an explicit, answer-free question corpus.

        No weight/optimizer reset, best-checkpoint rollback or Core mutation.
        Teacher labels are retained with the existing rehearsal policy.
        """
        x=np.asarray(x,dtype='float32');y=np.asarray(y,dtype='int64')
        if x.shape!=(len(y),WINDOW,self.layout.width) or not 1<=len(y)<=1024 or not np.isfinite(x).all():
            raise ValueError('finite bounded raw calibration corpus')
        if y.ndim!=1 or np.any((y<0)|(y>=8)) or not 1<=updates<=4000:raise ValueError('calibration labels or updates')
        for example,label in zip(x,y):self.teach(example,int(label),updates=0)
        device=next(self.parameters()).device;self.train()
        bx=torch.as_tensor(x,device=device);by=torch.as_tensor(y,device=device)
        for i in range(updates):
            if i%50==0:guard()
            ids=self.rng.integers(len(x),size=min(32,len(x)))
            self.optimizer.zero_grad(set_to_none=True)
            loss=nn.functional.cross_entropy(self(bx[ids]),by[ids]);loss.backward()
            nn.utils.clip_grad_norm_(self.parameters(),1.);self.optimizer.step();self.steps+=1
        self.eval()
        with torch.no_grad():correct=int((self(bx).argmax(-1)==by).sum())
        return dict(updates=updates,examples=len(y),training_correct=correct,
                    selection='last state; original weights, optimizer and learning RNG continued')

    def save(self,folder):
        p=Path(folder);p.mkdir(parents=True,exist_ok=False)
        save_file({k:v.detach().cpu().contiguous() for k,v in self.state_dict().items()},str(p/'weights.safetensors'))
        # Local optimizer-only tensor dictionary; restricted weights_only loading.
        torch.save(self.optimizer.state_dict(),p/'optimizer.pt')
        np.savez_compressed(p/'teaching.npz',x=np.asarray(self.x,dtype='float32'),y=np.asarray(self.y,dtype='int64'))
        meta=dict(schema='threemind.personal-vocabulary/1',identity=self.identity,seed=self.seed,
                  channels=self.layout.channels,retinal=self.retinal,steps=self.steps,seen=self.seen,
                  rng=self.rng.bit_generator.state,retention_rng=self.retention_rng.bit_generator.state,
                  words=WORDS,fields=FIELDS,retention='uniform reservoir 256',selection='latest state')
        if self.readout_profile!='recent-window':
            meta.update(schema='threemind.personal-vocabulary/2',readout_profile=self.readout_profile)
        (p/'manifest.json').write_text(json.dumps(meta),encoding='utf-8')

    @classmethod
    def restore(cls,folder,device='cpu',identity=None):
        p=Path(folder);m=json.loads((p/'manifest.json').read_text(encoding='utf-8'))
        if m['schema'] not in ('threemind.personal-vocabulary/1','threemind.personal-vocabulary/2') or m['words']!=list(WORDS) or m['fields']!=list(FIELDS):raise ValueError('vocabulary version')
        if identity is not None and identity!=m['identity']:raise ValueError('wrong individual')
        a=cls(m['channels'],m['retinal'],m['identity'],m['seed']).to(device)
        a.load_state_dict(load_file(str(p/'weights.safetensors')))
        a.optimizer.load_state_dict(torch.load(p/'optimizer.pt',map_location=device,weights_only=True))
        with np.load(p/'teaching.npz',allow_pickle=False) as d:a.x=list(d['x']);a.y=list(d['y'])
        a.steps=m['steps'];a.seen=m['seen'];a.rng.bit_generator.state=m['rng'];a.retention_rng.bit_generator.state=m['retention_rng']
        a.readout_profile=m.get('readout_profile','recent-window')
        if a.readout_profile not in ('recent-window','whole-question'):raise ValueError('readout profile')
        return a


class CenteredSystem:
    def __init__(self,seed=631,device='cpu'):
        self.identity=f'e63-centered-{seed}'
        w=CenteredWorld(seed=seed,toys=False);w.present(0,4)
        self.session=SensorimotorSession(w,seed=seed)
        self.words=PersonalVocabulary(self.session.layout.channels,w.channels[:w.vision_width],self.identity,seed).to(device)
        self.phase='birth';self.cursor=0

    def window(self):return recent_window(self.words.layout,self.session.history)

    def step(self,frame=None,*,label=None,guard=lambda:None):
        row=self.session.tick(frame,guard=guard)
        prediction=self.words.predict(self.window())
        row['expression']={'probabilities':None if prediction is None else prediction.tolist(),
                           'word':None if prediction is None else WORDS[int(prediction.argmax())],
                           'steps_before':self.words.steps,'identity':self.identity}
        if label is not None:row['expression']['teacher_loss']=self.words.teach(self.window(),label)
        return row

    def save(self,folder):
        p=Path(folder)
        if p.exists():raise FileExistsError(p)
        temp=p.with_name(p.name+'.partial');temp.mkdir(parents=True,exist_ok=False)
        s=self.session
        with gzip.open(temp/'system.json.gz','xt',encoding='utf-8') as f:
            json.dump(dict(schema=VERSION,identity=self.identity,phase=self.phase,cursor=self.cursor,
                           session=s.snapshot(),current=s.current,history=list(s.history),published=s.stream.published,
                           sensor=asdict(s.sensor.config),layout=s.layout.channels),f,ensure_ascii=False)
        self.words.save(temp/'words')
        (temp/'complete.json').write_text(json.dumps(dict(schema=VERSION,identity=self.identity,steps=self.words.steps,time_us=s.engine.time_us)),encoding='utf-8')
        for attempt in range(4):
            try:temp.rename(p);break
            except PermissionError:
                if attempt==3:raise
                time.sleep(.25*(attempt+1))

    @classmethod
    def restore(cls,folder,device='cpu',branch=None):
        p=Path(folder);m=json.loads((p/'complete.json').read_text(encoding='utf-8'))
        with gzip.open(p/'system.json.gz','rt',encoding='utf-8') as f:d=json.load(f)
        if m['schema']!=VERSION or d['schema']!=VERSION or m['identity']!=d['identity']:raise ValueError('complete centered system required')
        a=cls.__new__(cls);a.identity=d['identity'];a.phase=d['phase'];a.cursor=d['cursor']
        a.words=PersonalVocabulary.restore(p/'words',device,a.identity)
        s=a.session=SensorimotorSession(state=d['session'],dt_us=d['session']['dt_us'])
        s.current=d['current'];s.history.extend(d['history']);s.stream.published=d['published']
        if m['steps']!=a.words.steps or m['time_us']!=s.engine.time_us or list(s.layout.channels)!=d['layout'] or asdict(s.sensor.config)!=d['sensor']:
            raise ValueError('state, mapping or learning mismatch')
        if branch:a.identity+='/'+branch;a.words.identity=a.identity
        return a
