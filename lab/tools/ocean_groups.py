"""Declared group controls and cross-cohort capture, outside consciousness Core.

Stopped cores remain recoverable frozen artifacts. Their energy is not transferred
to bodies, and no artificial neural death or replacement food reward is invented.
"""
from __future__ import annotations
import copy
from pathlib import Path
import numpy as np
from pydantic import Field,model_validator
from lab.tools.ocean import rotation
from lab.tools.ocean_contact import ContactProtocol
from lab.tools.ocean_community import CommunityOcean,SCHEMA as COMMUNITY_SCHEMA
from lab.tools.ocean_cli import read_json
from threemind_runtime.codec import ArtifactCodec

SCHEMA='threemind.ocean-groups-state/1'
CONTROLLERS=('core','random-shadow','random-stopped')


class GroupProtocol(ContactProtocol):
    schema_id:str=Field(default='threemind.ocean-groups/1',alias='schema')
    founders:int=Field(default=106,ge=1,le=254)
    population_limit:int=Field(default=194,ge=1,le=254)
    nutrient_capacity:int=Field(default=8192,ge=0,le=16384)

    @model_validator(mode='after')
    def boundaries(self):
        if self.schema_id!='threemind.ocean-groups/1':raise ValueError('group protocol required')
        if self.founders>self.population_limit or self.nutrient_initial>self.nutrient_capacity:
            raise ValueError('initial population/food exceeds capacity')
        # This apparatus expands storage/count ceilings only. Validate every
        # physical and temporal parameter through the established Ocean/3 model.
        check=self.model_dump(by_alias=True)
        check.update(schema='threemind.ocean/3',founders=min(127,self.founders),
            population_limit=min(127,self.population_limit),nutrient_capacity=min(4096,self.nutrient_capacity))
        ContactProtocol.model_validate(check)
        return self


class GroupOcean(CommunityOcean):
    protocol_model=GroupProtocol

    def __init__(self,protocol,*,state=None,images=None,**kwargs):
        self.cohorts={};self.group_controls={};self.cross_only=False
        if state is not None:
            if state.get('schema')!=SCHEMA:raise ValueError('explicit group state required')
            self.cohorts={int(i):v for i,v in state['cohorts'].items()}
            self.group_controls=dict(state['group_controls']);self.cross_only=state['cross_only']
            state=state['community']
        super().__init__(protocol,state=state,images=images,**kwargs)

    def configure(self,cohorts,controls,*,cross_only=False):
        if set(cohorts)!=set(self.bodies) or set(cohorts.values())!=set(controls):
            raise ValueError('every current body must have one declared cohort')
        if any(v not in CONTROLLERS for v in controls.values()):raise ValueError('unsupported group controller')
        for i,b in self.bodies.items():
            if (self.controller(i)=='random-stopped' and controls[cohorts[i]]!='random-stopped'
                and self.engines[i].life!='dead' and self.engines[i].time_us!=self.time_us-b.birth_us):
                raise ValueError('frozen Core clock cannot silently resume at a later body time; declare a new restart experiment')
        self.cohorts=copy.deepcopy(cohorts);self.group_controls=dict(controls);self.cross_only=bool(cross_only)
        self.controls.clear()
        self.research['parent_protection']='bilateral-until-maturity/1'

    def controller(self,i):
        return self.group_controls.get(self.cohorts.get(i),'core')

    def action(self,i):
        if self.controller(i)=='core':return super().action(i)
        # The two random variants use identical commands for a shared identity/time.
        rng=np.random.default_rng(np.random.SeedSequence([self.p.environment_seed,i,self.time_us//self.p.random_interval_us]))
        return (rng.uniform(-1,1,3)*self.p.random_amplitude).tolist()

    def _protected_pair(self,predator,victim,now):
        if self.cross_only and self.cohorts[predator]==self.cohorts[victim]:return True
        return super()._protected_pair(predator,victim,now)

    def _advance_body_input(self,i,b,actions,initial_v):
        if self.controller(i)!='random-stopped':return super()._advance_body_input(i,b,actions,initial_v)
        if not b.physical:return None
        acceleration=rotation(b.angle).T@((np.asarray(b.velocity)-initial_v[i])/(self.p.period_us/1e6))
        b.acceleration_x,b.acceleration_y=map(float,acceleration)
        _,physical=self.senses(i)
        # Observe physical measurements without injecting, supplying or advancing Core.
        return {'individual':i,'stimulus':None,'delivered':False,'core_stopped':True,
                'food':0.0,'raw':physical,'action':actions[i]}

    def _reproduction_ready(self,i):
        if self.controller(i)=='random-stopped':return self.engines[i].life!='dead'
        return super()._reproduction_ready(i)

    def _reproduce(self):
        old=set(self.bodies);super()._reproduce()
        for i in self.bodies.keys()-old:
            self.cohorts[i]=self.cohorts[self.bodies[i].parent]

    def metrics(self):
        out=super().metrics();groups={}
        for row in out['members']:
            i=row['id'];cohort=self.cohorts.get(i,'unassigned');control=self.controller(i)
            row.update(cohort=cohort,controller=control,core_running=control!='random-stopped')
            if control=='random-stopped':row['life']='suspended'
            g=groups.setdefault(cohort,{'controller':control,'physical':0,'powered_bodies':0,'food':0,'captures':0,'births':0,
                'body_energy':0.0,'core_energy':0.0,'body_unserved':0.0})
            g['physical']+=int(row['physical']);g['powered_bodies']+=int(row['physical'] and row['storage']>0)
            g['food']+=row['grains'];g['captures']+=row['captured'];g['births']+=int(row['parent'] is not None)
            g['body_energy']+=row['storage'];g['core_energy']+=row['core_energy']['reserve'];g['body_unserved']+=row['body_unserved']
        out['groups']=groups
        return out

    def capture(self):
        return {'schema':SCHEMA,'community':super().capture(),'cohorts':copy.deepcopy(self.cohorts),
            'group_controls':dict(self.group_controls),'cross_only':self.cross_only}


def load(folder):
    folder=Path(folder);state=read_json(folder/'manifest.json')['context']
    if state.get('schema')!=SCHEMA:raise ValueError('group state required')
    base=state['community']['world']
    images={int(i):ArtifactCodec.decode((folder/f'{i}.tmind').read_bytes()) for i in base['core_hashes']}
    return GroupOcean(base['protocol'],state=state,images=images)


def copy_community(world):
    state={'schema':SCHEMA,'community':world.capture(),'cohorts':{},'group_controls':{},'cross_only':False}
    if state['community']['schema']!=COMMUNITY_SCHEMA:raise ValueError('community source required')
    protocol=world.p.model_dump(by_alias=True);protocol['schema']='threemind.ocean-groups/1'
    state['community']['world']['protocol']=protocol
    return GroupOcean(protocol,state=state,
        images={i:e.capture_state() for i,e in world.engines.items()},backend=world.backend)
