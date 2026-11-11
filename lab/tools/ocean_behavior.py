"""Copy-only, exterior behavior assays for Ocean/3. Normal Core output is untouched.

Scene coordinates and behavioral scores are observer data. Only the existing
physical sensors supply stimuli. No behavior score is fed back to any engine.
"""
from __future__ import annotations

import copy
import gzip
import json
import math
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from lab.tools.ocean import difference, rotation
from lab.tools.ocean_causality import local_persistent_transplant
from lab.tools.ocean_cli import write_json
from lab.tools.ocean_contact import ContactBody, ContactOcean, ContactProtocol
from lab.tools.ocean_contact_cli import save
from lab.tools.ocean_controls import naive_same_receptors
from threemind_runtime import create_engine
from threemind_runtime.inheritance import birth


class BehaviorOcean(ContactOcean):
    """Explicit controls attach only to selected experimental copies."""

    def __init__(self, *args, controls=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.controls = controls or {}
        self.control_origin = self.time_us

    def action(self, i):
        control = self.controls.get(i)
        if not control:
            return super().action(i)
        kind = control['kind']
        if kind == 'passive':
            return [0., 0., 0.]
        if kind == 'random':
            tick = (self.time_us-self.control_origin)//1000000
            rng = np.random.default_rng(np.random.SeedSequence([control['seed'], i, tick]))
            return rng.uniform(-1, 1, 3).tolist()
        if kind == 'replay':
            index = (self.time_us-self.control_origin)//self.p.period_us
            tape = control['actions']
            if index >= len(tape):
                raise ValueError('action replay exhausted; no invented continuation')
            return list(tape[index])
        raise ValueError(f'unknown exterior control: {kind}')


def persistent_image(source, operation, plan=None):
    if operation == 'experienced':
        return birth(source)
    blank = naive_same_receptors(source)
    if operation == 'blank':
        return blank
    if operation in ('graft', 'graft-matched'):
        key = 'target_edges' if operation == 'graft' else 'matched_edges'
        return local_persistent_transplant(blank, birth(source), plan[key])
    raise ValueError(operation)


def scene(protocol, source, body, *, task, bearing, seed, operation='intact', plan=None, actions=None):
    """Create a new controlled scene, retaining actual evolved focal body traits.

All scenes start at the same external water phase (200s). Awake variants retain
the donor's clock; structural births start their own clock at zero. New finite
body reserves and poses are experimental initial conditions, equal across arms.
"""
    p = copy.deepcopy(protocol)
    p.update(founders=1, nutrient_initial=180 if task == 'transfer' else 0,
             environment_seed=seed, mode='core')
    w = BehaviorOcean(p)
    w.time_us = w.control_origin = 200000000
    image = persistent_image(source, operation, plan) if operation in ('experienced','blank','graft','graft-matched') else source
    e = create_engine(state=image, backend='native')
    if operation in ('experienced','blank','graft','graft-matched'):
        reserve = e.metrics()['energy']['reserve']
        if reserve > p['initial_energy']+1e-8:
            raise ValueError('birth reserve exceeds declared finite endowment')
        if reserve < p['initial_energy']:
            e.supply_energy(p['initial_energy']-reserve, time_us=0, source='paired-behavior-birth/1')
            e.advance_to(0)
    b = ContactBody(id=0, parent=None, generation=body['generation'], birth_us=w.time_us-e.time_us,
        radius=body['radius'], thrust=body['thrust'], sensor_range=body['sensor_range'],
        position=[.4,.4], velocity=[0.,0.], angle=0., storage=p['initial_body_energy'],
        shell=body['shell'], reflectance=body['reflectance'], ligand=body['ligand'],
        neutral_allele=body['neutral_allele'], elongation=body['elongation'], grip=body['grip'],
        last_birth_us=w.time_us)
    w.engines = {0:e}; w.bodies = {0:b}; w.seeds = {0:e.config.seed}; w.projections = {}
    w.next_food_us = w.time_us+p['nutrient_interval_us']
    direction = np.array([math.cos(bearing), math.sin(bearing)])
    target_ids = []
    if task == 'food':
        center = np.asarray(b.position)+direction*.04
        tangent = np.array([-direction[1],direction[0]])
        w.food = np.asarray([center+tangent*k*.002 for k in (-1,0,1)])
        w.food_ids = [0,1,2]; w.next_food_id=3; target_ids=[0,1,2]
    elif task in ('hunt','escape'):
        other = copy.deepcopy(b)
        other.id=1; other.radius *= .67 if task == 'hunt' else 1.5
        other.position=(np.asarray(b.position)+direction*(2*(b.radius+other.radius)+.012)).tolist()
        other.angle=math.pi
        other.birth_us=w.time_us
        other_engine=create_engine(state=birth(source),backend='native')
        reserve=other_engine.metrics()['energy']['reserve']
        if reserve<p['initial_energy']:
            other_engine.supply_energy(p['initial_energy']-reserve,time_us=0,source='paired-neighbor-endowment/1')
            other_engine.advance_to(0)
        w.bodies[1]=other;w.engines[1]=other_engine;w.seeds[1]=other_engine.config.seed
        w.controls[1]={'kind':'random','seed':seed+10000}
    elif task != 'transfer':
        raise ValueError(task)
    if operation in ('target','matched','all','restore'):
        edges = ([(v['source'],v['target']) for v in image.to_dict()['edges']] if operation=='all'
                 else plan['matched_edges' if operation=='matched' else 'target_edges'])
        e.intervene(edges=edges,action='silence')
        if operation=='restore':e.intervene(edges=edges,action='unsilence')
    elif operation in ('random','passive'):
        w.controls[0]={'kind':operation,'seed':seed+20000}
    elif operation=='replay':
        if actions is None:raise ValueError('replay needs actual actions')
        w.controls[0]={'kind':'replay','actions':actions}
    elif operation not in ('intact','experienced','blank','graft','graft-matched'):
        raise ValueError(operation)
    # The snapshot includes historical energy counters. Rebase the experimental
    # ledger, not the reserve, so past expenditure is not charged a second time.
    w.totals = dict.fromkeys(w.totals,0.)
    spent_keys=('consumed_direct','consumed_associative','consumed_inhibition','consumed_maintenance','discarded_total')
    w.totals['initial_core']=sum(m['reserve']+sum(m[k] for k in spent_keys)
                                for m in (x.metrics()['energy'] for x in w.engines.values()))
    w.totals['initial_body']=sum(x.storage for x in w.bodies.values())
    w.totals['environment_food']=len(w.food)*w.p.nutrient_energy
    w.assay={'task':task,'bearing':bearing,'operation':operation,'seed':seed,'target_food_ids':target_ids}
    return w


def observation(w, origin, focal=0):
    b=w.bodies[focal];e=w.engines[focal]
    act=w.action(focal) if b.physical and e.life!='dead' else [0.,0.,0.]
    channels, raw=w.senses(focal)
    target=None; gap=None
    if w.assay['task']=='food':
        points=[p for p,i in zip(w.food,w.food_ids) if i in w.assay['target_food_ids']]
        if points:target=min(points,key=lambda p:float(np.linalg.norm(difference(p,b.position,w.p.side_m))))
    elif w.assay['task'] in ('hunt','escape') and w.bodies[1].physical:
        target=w.bodies[1].position;gap=w.geometry(0,1)[0]
    if target is not None:
        delta=difference(target,b.position,w.p.side_m);distance=float(np.linalg.norm(delta))
        direction=delta/max(distance,1e-12)
        world_action=rotation(b.angle) @ np.asarray(act[:2])
        flow,_=w.environment(b.position)
        velocity=np.asarray(b.velocity)-flow
        toward_action=float(world_action@direction)
        toward_velocity=float(velocity@direction)
        alignment=toward_action/max(float(np.linalg.norm(world_action)),1e-12)
        if gap is None:gap=distance-b.radius-w.p.nutrient_radius_m
    else:distance=toward_action=toward_velocity=alignment=None
    return {'t':(w.time_us-origin)/1e6,'world_time_us':w.time_us,'action':act,'physical':b.physical,'life':e.life,
            'position':list(b.position),'angle':b.angle,'velocity':list(b.velocity),'raw':raw,
            'direct_channels':[c for c,v in channels if v], 'distance':distance,'gap':gap,
            'toward_action':toward_action,'toward_velocity':toward_velocity,'alignment':alignment,
            'food':b.grains,'captured':b.captured,'consumed_by':b.consumed_by,
            'core_reserve':e.metrics()['energy']['reserve'],'body_reserve':b.storage}


def select_region(source, activity, maximum=128):
    """Select from discovery activity, never from later feeding/ablation scores."""
    s=source.to_dict();nodes={n['id']:n for n in s['nodes']}
    totals={n:0. for n in nodes};unprompted={n:0. for n in nodes}
    for row in activity:
        if row['t']<1.0:continue  # First second lacks a complete observed input history.
        recent=set(row['recent_channels'])
        for node in row['nodes']:
            n=node['id']
            if n not in nodes:continue
            totals[n]+=node['activation']
            if node['channel'] not in recent and node['activation']>.004:
                unprompted[n]+=node['activation']
    targets={n for n,v in unprompted.items() if v>0}
    edges=[x for x in s['edges'] if x['target'] in targets]
    edges.sort(key=lambda x:(-x['weight']*totals[x['source']]*unprompted[x['target']],x['source'],x['target']))
    picked=edges[:maximum];pairs={(e['source'],e['target']) for e in picked}
    others=[x for x in s['edges'] if (x['source'],x['target']) not in pairs and x['target'] not in targets]
    matched=[];errors=[]
    for e in picked:
        if not others:break
        cost=lambda x:abs(x['weight']-e['weight'])+abs(x['stability']-e['stability'])
        x=min(others,key=lambda x:(cost(x),x['source'],x['target']))
        errors.append(cost(x));matched.append(x);others.remove(x)
    return {'applicable':bool(picked) and len(matched)==len(picked),'targets':sorted(targets),
        'target_edges':[[x['source'],x['target']] for x in picked],
        'matched_edges':[[x['source'],x['target']] for x in matched],
        'matching_errors':errors,'eligible_edges':len(edges),'selected_edges':len(picked),
        'unprompted_activation':unprompted,'discovery_samples':len(activity),
        'selection':'pre-existing inbound weight x observed source activity x unprompted target activity; no performance selection'}


def observe(w, folder, seconds, *, guard=None, save_states=True):
    """Actual input, motion, activity and event recording; observation only."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    start=w.time_us;end=start+round(seconds*1e6);born=time.monotonic()
    if round(seconds*1e6)%w.p.period_us:raise ValueError('whole sensor periods required')
    write_json(folder/'assay.json',w.assay|{'protocol':w.p.model_dump(by_alias=True),'controls':w.controls})
    if save_states:save(w,folder/'initial')
    trace=[];activity=[];events=[];recent=[];status='observing';error=None
    try:
        with gzip.open(folder/'inputs.jsonl.gz','wt',encoding='utf-8',compresslevel=1) as raw:
            def record(row):
                raw.write(json.dumps(row,separators=(',',':'))+'\n');events.extend(row['events'])
            while w.time_us<end:
                if (w.time_us-start)%1000000==0:
                    if guard:guard()
                    if time.monotonic()-born>900:raise RuntimeError('single assay wall budget')
                    if abs(w.metrics()['energy_balance_error'])>1e-4:raise RuntimeError('assay energy ledger')
                row=observation(w,start)
                trace.append(row)
                recent.append((w.time_us,row['direct_channels']))
                recent=[r for r in recent if r[0]>=w.time_us-1000000]
                if (w.time_us-start)%100000==0:
                    activity.append({'t':row['t'],'nodes':w.engines[0].observation_nodes(),
                                     'recent_channels':sorted({c for _,cs in recent for c in cs})})
                    row['bodies']=[asdict(b) for b in w.bodies.values()]
                    row['food_positions']=w.food.tolist()
                    row['food_ids']=list(w.food_ids)
                w.step(record)
            status='horizon_paused'
    except (Exception,KeyboardInterrupt) as exc:
        status='paused_error';error=f'{type(exc).__name__}: {exc}'
    for name,value in (('trajectory',trace),('activity',activity)):
        with gzip.open(folder/f'{name}.json.gz','wt',encoding='utf-8',compresslevel=1) as stream:
            json.dump(value,stream,separators=(',',':'))
    write_json(folder/'events.json',events)
    if save_states:save(w,folder/'final')
    contact=next((r['t'] for r in trace if r['gap'] is not None and r['gap']<=w.p.contact_skin_m),None)
    windows={}
    for lo,hi in ((0,.5),(.5,2),(2,6),(6,20),(0,20)):
        values=[r for r in trace if lo<=r['t']<hi and r['physical'] and r['toward_action'] is not None]
        pre=[r for r in values if contact is None or r['t']<contact]
        windows[f'{lo}-{hi}']={'samples':len(values),'precontact_samples':len(pre),
            **{k:float(np.mean([r[k] for r in values])) if values else None for k in ('toward_action','toward_velocity','alignment')},
            'precontact_toward_velocity':float(np.mean([r['toward_velocity'] for r in pre])) if pre else None}
    b=w.bodies[0]
    answer={'status':status,'error':error,'wall_seconds':time.monotonic()-born,'observed_us':w.time_us-start,
        'assay':w.assay,'windows':windows,'first_contact_s':contact,
        'food':b.grains,'captured':b.captured,'physical':b.physical,'consumed_by':b.consumed_by,
        'motor_energy':b.motor_energy,'core_energy':w.engines[0].metrics()['energy'],
        'members':w.metrics()['members'],'energy_balance_error':w.metrics()['energy_balance_error']}
    write_json(folder/'result.json',answer)
    if status!='horizon_paused':raise RuntimeError(f'{folder.name}: {status}: {error}')
    return answer,trace,activity
