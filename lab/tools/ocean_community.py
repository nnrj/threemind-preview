"""Whole-habitat research copies, observation and focal-only controls.

No new physics, sensory rules or Core dynamics. Experimental state wrappers are
explicit so a generic Ocean/3 loader cannot silently discard a focal controller.
"""
from __future__ import annotations
from dataclasses import asdict
import copy
import gzip
import json
from pathlib import Path
import time
import numpy as np
from lab.tools.ocean import difference
from lab.tools.ocean_contact import ContactOcean
from lab.tools.ocean_contact_cli import save
from lab.tools.ocean_cli import read_json,write_json
from lab.tools.ocean_behavior import persistent_image,select_region
from lab.tools.ocean_encounter import ActivityHistory,measurement
from threemind_core import StateImage
from threemind_runtime import create_engine
from threemind_runtime.codec import ArtifactCodec

SCHEMA='threemind.ocean-community-state/1'
SPENT=('consumed_direct','consumed_associative','consumed_inhibition','consumed_maintenance','discarded_total')


class CommunityOcean(ContactOcean):
    def __init__(self,protocol,*,state=None,images=None,**kwargs):
        self.controls={};self.research={}
        if state is not None:
            if state.get('schema')!=SCHEMA:raise ValueError('community research state required')
            self.controls={int(k):v for k,v in state['controls'].items()}
            self.research=copy.deepcopy(state['research']);state=state['world']
        super().__init__(protocol,state=state,images=images,**kwargs)

    def action(self,i):
        if i not in self.controls:return super().action(i)
        control=self.controls[i]
        if control['kind']!='random':raise ValueError('unknown focal controller')
        rng=np.random.default_rng(np.random.SeedSequence([control['seed'],i,self.time_us//self.p.random_interval_us]))
        return (rng.uniform(-1,1,3)*self.p.random_amplitude).tolist()

    def _protected_pair(self,predator,victim,now):
        mode=self.research.get('parent_protection','legacy-one-way')
        if mode=='legacy-one-way':return super()._protected_pair(predator,victim,now)
        if mode!='bilateral-until-maturity/1':raise ValueError('unknown parental protection rule')
        a,b=self.bodies[predator],self.bodies[victim]
        return ((a.parent==victim and now-a.birth_us<self.p.maturity_us) or
                (b.parent==predator and now-b.birth_us<self.p.maturity_us))

    def capture(self):
        return {'schema':SCHEMA,'world':super().capture(),'controls':copy.deepcopy(self.controls),
                'research':copy.deepcopy(self.research)}


def load(folder):
    folder=Path(folder);c=read_json(folder/'manifest.json')['context']
    if c.get('schema')!=SCHEMA:raise ValueError('community state required')
    images={int(i):ArtifactCodec.decode((folder/f'{i}.tmind').read_bytes()) for i in c['world']['core_hashes']}
    return CommunityOcean(c['world']['protocol'],state=c,images=images)


def place_birth_clock(image,offset_us):
    """Translate an empty-activity birth origin, not an existing running state."""
    s=copy.deepcopy(image.to_dict())
    if int(s['time_us'])!=0 or s['life']!='waiting' or s['queue'] or s['traversed']:
        raise ValueError('only newly initialized waiting births can be translated')
    if offset_us<0:raise ValueError('negative time origin')
    for n in s['nodes']:
        if n['activation'] or n['inhibition']:raise ValueError('birth must have no live activation/inhibition')
    for k in ('time_us','state_time_us','next_step_us','next_propagation_us'):
        s[k]=str(int(s[k])+offset_us)
    for k in ('since_us','last_settlement_us'):
        s['energy'][k]=str(int(s['energy'][k])+offset_us)
    for row in s['nodes']+s['edges']:
        for k in ('birth_us','last_touch_us'):row[k]=str(int(row[k])+offset_us)
    return StateImage.from_dict(s)


def focal_intervention(w,i,operation,plan):
    """Only the focal engine/controller changes; physical community is intact."""
    old=w.engines[i];before=old.metrics()['energy'];source=old.capture_state()
    receipt={'individual':i,'operation':operation,'world_time_us':w.time_us,
             'scope':'one focal engine/controller; complete physical habitat retained'}
    if operation in ('target','matched'):
        pairs=plan[operation+'_edges'];old.intervene(edges=pairs,action='silence');receipt['edges']=pairs
    elif operation=='random':
        w.controls[i]={'kind':'random','seed':w.p.environment_seed+700000}
    elif operation in ('experienced','blank','graft','graft-matched'):
        image=place_birth_clock(persistent_image(source,operation,plan),old.time_us)
        # A paired research birth inherits the body's CURRENT finite reserve,
        # not the protocol's larger founder endowment. This is initialization,
        # not an energy input, injury or artificial spend during observation.
        value=image.to_dict()
        value['energy'].update(reserve=before['reserve'],initial_total=before['reserve'],discarded_total=0.0)
        new=create_engine(state=StateImage.from_dict(value),backend=w.backend)
        after=new.metrics()['energy']
        # Historical expense counters reset at birth. Correct their accounting
        # origin, not any body's actual reserve or environmental energy supply.
        correction=(after['reserve']+sum(after[k] for k in SPENT))-(before['reserve']+sum(before[k] for k in SPENT))
        w.totals['initial_core']+=correction;w.engines[i]=new
        receipt.update(core_clock_origin_us=old.time_us,reserve=after['reserve'],historical_ledger_offset=correction,
                       reset='immediate activity and queue; persistent state by named arm; body age unchanged')
    elif operation!='intact':raise ValueError(operation)
    w.research['intervention']=receipt
    return receipt


def nearest_objects(w,i):
    b=w.bodies[i];targets={}
    if len(w.food):targets['food']=w.food_ids[int(np.argmin(np.linalg.norm(difference(w.food,b.position,w.p.side_m),axis=1)))]
    strength=lambda x:x.thrust*(.25+x.grip)*x.radius**2
    for task in ('hunt','escape'):
        candidates=[j for j,c in w.bodies.items() if j!=i and c.physical and
            (strength(b)>strength(c) if task=='hunt' else strength(b)<strength(c))]
        if candidates:targets[task]=min(candidates,key=lambda j:(float(np.linalg.norm(difference(w.bodies[j].position,b.position,w.p.side_m))),j))
    return targets


def run(w,folder,seconds,*,guard=None,select_at_s=None,focal=None,wall_seconds=7200):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    write_json(folder/'protocol.json',w.p.model_dump(by_alias=True));save(w,folder/'initial')
    start=w.time_us;end=start+round(seconds*1e6);born=time.monotonic();history=ActivityHistory()
    selection=None;events=[];status='observing';error=None;living=0.;last_guard=last_progress=0.
    initial_metrics=w.metrics();last_actions={};action_delta=action_power=action_n=0
    try:
        with gzip.open(folder/'inputs.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as inputs, \
             gzip.open(folder/'trajectory.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as frames, \
             gzip.open(folder/'activity.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as activities, \
             gzip.open(folder/'focal.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as focal_stream:
            def record(row):
                nonlocal action_delta,action_power,action_n
                inputs.write(json.dumps(row,separators=(',',':'))+'\n');events.extend(row['events'])
                for item in row['inputs']:
                    j=item['individual'];a=np.asarray(item['action']);previous=last_actions.get(j,a)
                    action_delta+=float(np.mean(np.abs(a-previous)));action_power+=float(a@a);action_n+=1;last_actions[j]=a
            while w.time_us<end:
                now=time.monotonic()
                if now-last_guard>10:
                    if guard:guard()
                    if now-born>wall_seconds:raise RuntimeError('community case wall budget')
                    if (folder.parent/'STOP').exists():raise RuntimeError('requested study stop')
                    last_guard=now
                select_us=None if select_at_s is None else start+round(select_at_s*1e6)
                if select_us is not None and select_us-3000000<=w.time_us<=select_us:
                    history.sample(w,start)
                elif focal is not None:
                    history.sample(w,start,(focal,))
                if select_us is not None and w.time_us==select_us:
                    save(w,folder/'selection-source')
                    considered=[]
                    for i,b in sorted(w.bodies.items()):
                        if not b.physical or w.engines[i].life=='dead' or w.time_us-b.birth_us<20000000:continue
                        rows=list(history.activity.get(i,[]));plan=select_region(w.engines[i].capture_state(),rows)
                        considered.append({'individual':i,'applicable':plan['applicable']})
                        if plan['applicable']:
                            focal=i;selection={'individual':i,'time_us':w.time_us,'plan':plan,'considered':considered}
                            with gzip.open(folder/'selection-activity.json.gz','wt',encoding='utf-8') as f:json.dump(rows,f,separators=(',',':'))
                            break
                    if selection is None:selection={'individual':None,'time_us':w.time_us,'considered':considered,'reason':'no eligible matched region'}
                    write_json(folder/'selection.json',selection)
                if (w.time_us-start)%100000==0:
                    m=w.metrics();m['food_positions']=w.food.tolist();m['food_ids']=w.food_ids[:]
                    frames.write(json.dumps(m,separators=(',',':'))+'\n')
                    if focal is not None:
                        b=w.bodies[focal];row={'time_us':w.time_us,'individual':focal,'body':asdict(b),
                            'action':w.action(focal) if b.physical else [0.,0.,0.],
                            'objects':{task:{'target':target,**measurement(w,focal,task,target)} for task,target in nearest_objects(w,focal).items()} if b.physical else {}}
                        focal_stream.write(json.dumps(row,separators=(',',':'))+'\n')
                        rows=history.activity.get(focal,[])
                        if rows and rows[-1]['t']==(w.time_us-start)/1e6:
                            activities.write(json.dumps({'time_us':w.time_us,**rows[-1]},separators=(',',':'))+'\n')
                if (w.time_us-start)%1000000==0:
                    err=w.metrics()['energy_balance_error']
                    if abs(err)>max(1e-4,w.totals['environment_food']*1e-8):raise RuntimeError('community energy accounting mismatch')
                w.step(record);living+=sum(b.physical for b in w.bodies.values())*w.p.period_us/1e6
                if now-last_progress>30:
                    progress={'time_us':w.time_us,'wall_seconds':time.monotonic()-born,'alive':sum(b.physical for b in w.bodies.values()),
                        'food':sum(b.grains for b in w.bodies.values()),'nutrients':len(w.food),'captures':w.totals['predations'],'focal':focal}
                    tmp=folder/'progress.tmp';tmp.write_text(json.dumps(progress),encoding='utf-8');tmp.replace(folder/'progress.json')
                    print(json.dumps({'case':folder.name,**progress}),flush=True);last_progress=now
                if not any(b.physical for b in w.bodies.values()):status='physical_extinction';break
            else:status='horizon_paused'
    except (Exception,KeyboardInterrupt) as exc:status='paused_error';error=f'{type(exc).__name__}: {exc}'
    save(w,folder/'final');write_json(folder/'events.json',events)
    result=w.metrics()|{'status':status,'error':error,'wall_seconds':time.monotonic()-born,
        'observed_us':w.time_us-start,'living_body_s':living,'initial_metrics':initial_metrics,'focal':focal,
        'mean_command_change':action_delta/max(action_n,1),'mean_action_square':action_power/max(action_n,1)}
    write_json(folder/'result.json',result)
    if status=='paused_error':raise RuntimeError(error)
    return result
