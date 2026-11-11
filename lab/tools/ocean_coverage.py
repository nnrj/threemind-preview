"""Separate /3 environment for configurable coverage-based consumption.

Capsule intersection uses a declared inscribed polygon resolution. Old complete
enclosure /1 and material /2 remain unchanged. All rules act outside Core.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
from typing import Literal
import numpy as np
from pydantic import Field, model_validator
from lab.tools.ocean import difference
from lab.tools.ocean_contact import capsule
from lab.tools.ocean_material import MaterialOcean,MaterialProtocol
from lab.tools.ocean_cli import read_json
from threemind_runtime.codec import ArtifactCodec

SCHEMA='threemind.ocean-enclosure-state/3'


def cross(a,b):
    return a[...,0]*b[...,1]-a[...,1]*b[...,0]


def polygon_area(points):
    return abs(float(np.sum(cross(points,np.roll(points,-1,axis=0)))))/2 if len(points)>=3 else 0.


def capsule_polygon(body,segments=96,origin=None):
    a,b,r=capsule(body,origin=origin)
    # Two semicircles, including the endpoints of the two straight sides.
    angles=body.angle+np.linspace(-math.pi/2,math.pi/2,segments//2+1)
    right=b+r*np.stack((np.cos(angles),np.sin(angles)),axis=-1)
    angles=body.angle+np.linspace(math.pi/2,3*math.pi/2,segments//2+1)
    left=a+r*np.stack((np.cos(angles),np.sin(angles)),axis=-1)
    return np.concatenate((right,left))


def intersection_area(subject,clip):
    """Convex polygon clipping in local coordinates (counterclockwise)."""
    result=subject
    for a,b in zip(clip,np.roll(clip,-1,axis=0)):
        if len(result)<3:return 0.
        edge=b-a
        if float(edge@edge)<1e-28:continue
        signed=cross(edge,result-a);inside=signed>=-1e-15
        if inside.all():continue
        if not inside.any():return 0.
        prior=np.roll(result,1,axis=0);before=np.roll(signed,1)
        changed=inside!=np.roll(inside,1)
        # Emit an intersection before each entering/leaving endpoint.
        out=np.empty((len(result)*2,2));keep=np.zeros(len(result)*2,dtype=bool)
        denominator=before-signed
        t=np.divide(before,denominator,out=np.zeros_like(before),where=changed)
        out[0::2]=prior+(result-prior)*t[:,None];keep[0::2]=changed
        out[1::2]=result;keep[1::2]=inside
        result=out[keep]
    return polygon_area(result)


def coverage_fractions(a,b,side,segments=96,*,common_center=False):
    delta=np.zeros(2) if common_center else difference(b.position,a.position,side)
    pa=capsule_polygon(a,segments,origin=np.zeros(2))
    pb=capsule_polygon(b,segments,origin=delta)
    shared=intersection_area(pa,pb)
    return min(1.,shared/polygon_area(pb)),min(1.,shared/polygon_area(pa))


class CoverageProtocol(MaterialProtocol):
    schema_id:str=Field(default='threemind.ocean-enclosure/3',alias='schema')
    enclosure_fraction:float=Field(default=.5,ge=.5,le=1,allow_inf_nan=False)
    coverage_segments:int=Field(default=96,ge=32,le=256,multiple_of=4)
    coverage_contest:Literal['body','larger']='body'

    @model_validator(mode='after')
    def boundaries(self):
        if self.schema_id!='threemind.ocean-enclosure/3':raise ValueError('coverage environment /3 required')
        values={k:v for k,v in self.model_dump(by_alias=True).items()
                if k=='schema' or k in MaterialProtocol.model_fields}
        values['schema']='threemind.ocean-enclosure/2'
        MaterialProtocol.model_validate(values)
        return self


class CoverageOcean(MaterialOcean):
    protocol_model=CoverageProtocol

    def __init__(self,protocol,*,state=None,images=None,**kwargs):
        self.contests={};self._deciding_contests=False
        if state is not None:
            if state.get('schema')!=SCHEMA:raise ValueError('coverage /3 snapshot required')
            self.contests={(a,b):winner for a,b,winner in state['contests']}
            state=state['material']
        super().__init__(protocol,state=state,images=images,**kwargs)
        if any(a>=b or winner not in (a,b) or a not in self.bodies or b not in self.bodies
               for (a,b),winner in self.contests.items()):raise ValueError('invalid stored body contest')

    def geometry(self,i,j):
        gap,full,delta=super().geometry(i,j)
        if self.p.enclosure_fraction==1 or not self.p.predation:return gap,full,delta
        if gap>=0:return gap,False,delta
        a,b=self.bodies[i],self.bodies[j]
        ab,ba=coverage_fractions(a,b,self.p.side_m,self.p.coverage_segments)
        qa,qb=ab>=self.p.enclosure_fraction,ba>=self.p.enclosure_fraction
        qa=qa and not self._protected_pair(i,j,self.time_us)
        qb=qb and not self._protected_pair(j,i,self.time_us)
        if self.p.coverage_contest=='larger':
            qa=qa and a.radius>b.radius;qb=qb and b.radius>a.radius
        pair=tuple(sorted((i,j)))
        # Once simultaneous eligibility has decided a contact, a later change
        # in overlap cannot reverse that encounter's roles before separation.
        if pair in self.contests:return gap,qa and self.contests[pair]==i,delta
        if not qa or not qb:return gap,qa,delta
        winner=self.contests.get(pair)
        if winner is None:
            sa=a.thrust*(.25+a.grip)*a.radius**2
            sb=b.thrust*(.25+b.grip)*b.radius**2
            if sa!=sb:winner=i if sa>sb else j
            else:
                # Exchangeable, repeatable tie-breaking; do not privilege the
                # smaller ID or consume the mutation/environment RNG stream.
                token=f'{self.p.environment_seed}:{pair[0]}:{pair[1]}:{self.time_us}'.encode()
                winner=pair[hashlib.blake2b(token,digest_size=8).digest()[0]&1]
            if self._deciding_contests:self.contests[pair]=winner
        return gap,winner==i,delta

    def _separate_overlap(self,a,b,gap,normal):
        if self.p.enclosure_fraction==1:return super()._separate_overlap(a,b,gap,normal)
        allowed=False
        if self.p.predation:
            ab,ba=coverage_fractions(a,b,self.p.side_m,self.p.coverage_segments,common_center=True)
            for hunter,prey,amount in ((a,b,ab),(b,a,ba)):
                if (amount>=self.p.enclosure_fraction and not self._protected_pair(hunter.id,prey.id,self.time_us)
                    and (self.p.coverage_contest!='larger' or hunter.radius>prey.radius)):
                    allowed=True;break
        if not allowed:
            # The original hard collision, without /1's full-containment test.
            from lab.tools.ocean_contact import ContactOcean
            ContactOcean._separate_overlap(self,a,b,gap,normal)

    def _predation(self,active):
        self.contests={pair:winner for pair,winner in self.contests.items()
            if all(self.bodies[i].physical for i in pair)
            and super(CoverageOcean,self).geometry(*pair)[0]<=self.p.contact_skin_m}
        offset=len(self.events);self._deciding_contests=True
        try:super()._predation(active)
        finally:self._deciding_contests=False
        if self.p.enclosure_fraction<1:
            for event in self.events[offset:]:
                if event['kind'] not in ('capture_started','body_engulfed'):continue
                event['method']='area-coverage'
                event['coverage_required']=self.p.enclosure_fraction
                event['coverage_measured']=coverage_fractions(
                    self.bodies[event['predator']],self.bodies[event['individual']],
                    self.p.side_m,self.p.coverage_segments)[0]
                if event['kind']=='body_engulfed':event['kind']='body_consumed_by_coverage'
        self.contests={pair:winner for pair,winner in self.contests.items()
                       if all(self.bodies[i].physical for i in pair)}

    def capture(self):
        return {'schema':SCHEMA,'material':super().capture(),
                'contests':[[a,b,winner] for (a,b),winner in sorted(self.contests.items())]}


def load(folder):
    folder=Path(folder);state=read_json(folder/'manifest.json')['context']
    if state.get('schema')!=SCHEMA:raise ValueError('coverage snapshot required')
    base=state['material']['enclosure']['group']['community']['world']
    images={int(i):ArtifactCodec.decode((folder/f'{i}.tmind').read_bytes()) for i in base['core_hashes']}
    return CoverageOcean(base['protocol'],state=state,images=images)
