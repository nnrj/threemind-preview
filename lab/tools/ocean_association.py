"""Optional physical proximity and sharing of newly ingested nutrient energy.

External apparatus only: no steering, attraction, fusion, kin preference or Core
reward. Fraction zero preserves the material environment's dynamics.
"""
from __future__ import annotations
import copy
import math
from pathlib import Path
import numpy as np
from pydantic import Field, model_validator
from lab.tools.ocean import difference
from lab.tools.ocean_contact import capsule, segment_distance
from lab.tools.ocean_material import MaterialOcean, MaterialProtocol
from lab.tools.ocean_cli import read_json
from threemind_runtime.codec import ArtifactCodec

SCHEMA='threemind.ocean-association-state/1'


class AssociationProtocol(MaterialProtocol):
    schema_id: str=Field(default='threemind.ocean-association/1',alias='schema')
    intake_share_fraction: float=Field(default=0.,ge=0,le=1,allow_inf_nan=False)
    association_gap_m: float=Field(default=.001,ge=0,le=.02,allow_inf_nan=False)
    association_dwell_us: int=Field(default=1_000_000,ge=20000)

    @model_validator(mode='after')
    def boundaries(self):
        if self.schema_id!='threemind.ocean-association/1':raise ValueError('association /1 required')
        values={k:v for k,v in self.model_dump(by_alias=True).items()
                if k=='schema' or k in MaterialProtocol.model_fields}
        values['schema']='threemind.ocean-enclosure/2'
        MaterialProtocol.model_validate(values)
        if self.association_dwell_us%self.period_us:
            raise ValueError('association dwell must contain complete samples')
        return self


class AssociationOcean(MaterialOcean):
    protocol_model=AssociationProtocol

    def __init__(self,protocol,*,state=None,images=None,**kwargs):
        self.associations={};self.intake={};self.association_max_us=0
        if state is not None:
            if state.get('schema')!=SCHEMA:raise ValueError('association snapshot required')
            self.associations={(a,b):t for a,b,t in state['associations']}
            self.intake={int(k):v for k,v in state['intake'].items()}
            self.association_max_us=state['association_max_us']
            state=state['material']
        super().__init__(protocol,state=state,images=images,**kwargs)

    def _ingest(self,active):
        offset=len(self.events)
        super()._ingest(active)
        for e in self.events[offset:]:
            if e['kind']=='nutrient_contact':
                i=e['individual'];self.intake[i]=self.intake.get(i,0.)+e['energy']

    def _near_pairs(self,active):
        if len(active)<2:return set()
        bodies=[self.bodies[i] for i in active]
        positions=np.array([b.position for b in bodies])
        delta=difference(positions[:,None,:],positions[None,:,:],self.p.side_m)
        # Capsule bounding circles cheaply reject distant pairs.
        shapes=[capsule(b,origin=[0.,0.]) for b in bodies]
        bound=np.array([np.linalg.norm(a)+r for a,_,r in shapes])
        near=np.sum(delta*delta,axis=-1)<=(bound[:,None]+bound[None,:]+self.p.association_gap_m)**2
        result=set()
        for k,j in zip(*np.nonzero(np.triu(near,1))):
            a,b,ar=shapes[k];c,d,br=shapes[j]
            offset=difference(positions[j],positions[k],self.p.side_m)
            gap=segment_distance(a,b,c+offset,d+offset)-ar-br
            # Near surfaces, not a body already deeply inside another body.
            if abs(gap)<=self.p.association_gap_m:
                result.add(tuple(sorted((active[k],active[j]))))
        return result

    def _update_associations(self,active):
        near=self._near_pairs(active);now=self.time_us
        for pair in sorted(set(self.associations)-near):
            duration=now-self.associations.pop(pair)
            self.association_max_us=max(self.association_max_us,duration)
            self.events.append({'kind':'association_ended','time_us':now,'individuals':list(pair),
                                'duration_us':duration})
        for pair in sorted(near):
            if pair not in self.associations:
                self.associations[pair]=now
                self.events.append({'kind':'association_started','time_us':now,'individuals':list(pair)})
            self.association_max_us=max(self.association_max_us,now-self.associations[pair])

    def _share_intake(self):
        p=self.p;requests=[]
        for donor,amount in sorted(self.intake.items()):
            if not self.bodies[donor].physical:continue
            receivers=sorted(b if a==donor else a for (a,b),start in self.associations.items()
                             if donor in (a,b) and self.time_us-start>=p.association_dwell_us
                             and self.bodies[a].physical and self.bodies[b].physical)
            if not receivers or not amount or not p.intake_share_fraction:continue
            sent=min(amount*p.intake_share_fraction,self.bodies[donor].storage)
            requests.extend((donor,r,sent/len(receivers)) for r in receivers)
        incoming={r:math.fsum(v*p.sharing_efficiency for _,j,v in requests if j==r)
                  for _,r,_ in requests}
        delta={}
        for donor,receiver,wanted in requests:
            a,b=self.bodies[donor],self.bodies[receiver]
            scale=min(1.,max(0.,p.storage_capacity-b.storage)/incoming[receiver]) if incoming[receiver] else 0.
            sent=wanted*scale;got=sent*p.sharing_efficiency
            if not sent:continue
            delta[donor]=delta.get(donor,0.)-sent;delta[receiver]=delta.get(receiver,0.)+got
            a.share_sent+=sent;b.share_received+=got
            self.totals['sharing_heat']+=sent-got;self.totals['sharing_contacts']+=1
            self.events.append({'kind':'intake_resource_exchange','time_us':self.time_us,
                'donor':donor,'receiver':receiver,'sent':sent,'received':got,
                'fraction':p.intake_share_fraction,'intake_basis':self.intake[donor]})
        for i,v in delta.items():self.bodies[i].storage+=v
        self.intake={}

    def _predation(self,active):
        self._update_associations(active)
        super()._predation(active)
        self._share_intake()

    def _consume_body_energy(self,hunter,prey):
        result=super()._consume_body_energy(hunter,prey)
        self.intake[hunter.id]=self.intake.get(hunter.id,0.)+result['transferred']
        return result

    def metrics(self):
        value=super().metrics()
        value['association_pairs']=len(self.associations)
        value['mature_association_pairs']=sum(self.time_us-t>=self.p.association_dwell_us for t in self.associations.values())
        value['association_max_us']=self.association_max_us
        return value

    def capture(self):
        return {'schema':SCHEMA,'material':super().capture(),
                'associations':[[a,b,t] for (a,b),t in sorted(self.associations.items())],
                'intake':copy.deepcopy(self.intake),'association_max_us':self.association_max_us}


def load(folder):
    folder=Path(folder);state=read_json(folder/'manifest.json')['context']
    if state.get('schema')!=SCHEMA:raise ValueError('association snapshot required')
    base=state['material']['enclosure']['group']['community']['world']
    images={int(i):ArtifactCodec.decode((folder/f'{i}.tmind').read_bytes()) for i in base['core_hashes']}
    return AssociationOcean(base['protocol'],state=state,images=images)
