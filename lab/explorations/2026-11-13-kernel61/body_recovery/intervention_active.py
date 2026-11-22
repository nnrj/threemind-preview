"""Prepared E22-style persistent exchange retaining recipient in-flight signals.

Pure StateImage transformation; no Core construction, advancement or mutation.
This is an explicit research intervention, not an observation operation.
"""
import copy
import importlib.util
from pathlib import Path

from threemind_core import StateImage
from threemind_kernels.decay61 import crossing_seconds
from threemind_kernels.local61_config import Local61Config

SOURCE=Path(__file__).resolve().parents[1]/'order_exchange/intervention.py'
spec=importlib.util.spec_from_file_location('r51o_persistent_fields',SOURCE)
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
GROUPS=('W','S','N')


def exchange(recipient,donor,groups=()):
    groups=tuple(groups)
    if len(set(groups))!=len(groups) or set(groups)-set(GROUPS):
        raise ValueError('only distinct persistent groups W, S, N are supported')
    original_a,original_b=recipient.to_dict(),donor.to_dict()
    a,b=copy.deepcopy(original_a),copy.deepcopy(original_b)
    if any(s['dynamics']!='threemind.continuous-memory/6.1' for s in (a,b)):
        raise ValueError('genuine 6.1 states required')
    shared=('schema','dynamics','config','definition','definition_hash','time_us','life','sources_open',
            'quiet_since_us','energy','pools','energy_rng','energy_serial','completed_emission_us')
    if any(a[k]!=b[k] for k in shared):raise ValueError('configuration, clock, lifecycle or energy differs')
    c=Local61Config(**a['config']);now=int(a['time_us'])
    if c.deletion_strategy!='local' or c.energy_simulation_enabled or c.dormant_traces_enabled:
        raise ValueError('requires current local deletion without global energy or dormancy')
    for state in (a,b):
        if state['silenced_nodes'] or state['silenced_edges']:raise ValueError('silenced source')
        if any(int(r['state_us'])!=now for r in state['nodes']+state['edges']):raise ValueError('values not settled')
        if any(n['id']!=n['channel'] for n in state['nodes']):raise ValueError('fixed addresses required')
        for e in state['edges']:
            if e['novelty_deadline_us'] is not None:raise ValueError('pending novelty not supported')
            for key in ('short_term','fast'):
                if e[key] is not None and int(e[key]['time_us'])!=now:raise ValueError('unsettled short-term state')
    an,bn=({n['id']:n for n in s['nodes']} for s in (a,b))
    ae,be=({(e['source'],e['target']):e for e in s['edges']} for s in (a,b))
    if an.keys()!=bn.keys() or ae.keys()!=be.keys():raise ValueError('fixed addresses or topology differ')
    changes=[]
    def assign(target,source,fields,location):
        for field in fields:
            if target[field]!=source[field]:
                changes.append({'location':location+[field],'before':copy.deepcopy(target[field]),'after':copy.deepcopy(source[field])})
                target[field]=copy.deepcopy(source[field])
    for nid,node in an.items():
        if 'N' in groups:assign(node,bn[nid],prior.NODE_HISTORY,['node',nid])
    for pair,edge in ae.items():
        if 'W' in groups:assign(edge,be[pair],('weight',),['edge',*pair])
        if 'S' in groups:assign(edge,be[pair],prior.EDGE_HISTORY,['edge',*pair])
    timers={(k,source,target):when for k,source,target,when in a['timers']}
    old_edges={(e['source'],e['target']):e for e in original_a['edges']}
    if 'W' in groups or 'S' in groups:
        for pair,edge in ae.items():
            if all(edge[k]==old_edges[pair][k] for k in ('weight','decay_age','half_life')):continue
            seconds=crossing_seconds(edge['weight'],edge['decay_age'],edge['half_life'],c.prune_weight,c) if c.plasticity else None
            due=prior.deadline(now,edge['state_us'],seconds,c.structure_check_interval_us);key=(2,*pair)
            if due is None:timers.pop(key,None)
            else:timers[key]=str(due)
    if 'N' in groups:
        old_nodes={n['id']:n for n in original_a['nodes']};incident={nid for pair in ae for nid in pair}
        for nid,node in an.items():
            if all(node[k]==old_nodes[nid][k] for k in ('support','decay_age','half_life')):continue
            key=(3,nid,0)
            if c.plasticity and not c.retain_nodes and node['activation']==0 and nid not in incident:
                seconds=(crossing_seconds(node['support'],node['decay_age'],node['half_life'],.006,c)
                         if c.support_decay_enabled else (0. if node['support']<.006 else None))
                due=prior.deadline(now,node['state_us'],seconds,c.structure_check_interval_us)
                if due is None:timers.pop(key,None)
                else:timers[key]=str(due)
            else:timers.pop(key,None)
    updated=[[k,source,target,when] for (k,source,target),when in timers.items()]
    updated.sort(key=lambda row:(int(row[3]),row[0],row[1],row[2]))
    if updated!=a['timers']:
        changes.append({'location':['timers'],'before':a['timers'],'after':updated});a['timers']=updated
    retained=[k for k in a if k not in ('nodes','edges','timers')]
    assert all(a[k]==original_a[k] for k in retained)
    assert [r for r in a['timers'] if r[0] in (0,1)]==[r for r in original_a['timers'] if r[0] in (0,1)]
    node_allowed=set(prior.NODE_HISTORY) if 'N' in groups else set()
    edge_allowed=({'weight'} if 'W' in groups else set()) | (set(prior.EDGE_HISTORY) if 'S' in groups else set())
    for changed,original in zip(a['nodes'],original_a['nodes']):assert all(changed[k]==original[k] for k in original.keys()-node_allowed)
    for changed,original in zip(a['edges'],original_a['edges']):assert all(changed[k]==original[k] for k in original.keys()-edge_allowed)
    image=StateImage.from_dict(a)
    if not groups:assert image.digest==recipient.digest
    assert recipient.to_dict()==original_a and donor.to_dict()==original_b
    return image,{'schema':'threemind.research-persistent-cut61/1','groups':[g for g in GROUPS if g in groups],
        'recipient_sha256':recipient.digest,'donor_sha256':donor.digest,'after_sha256':image.digest,
        'time_us':now,'retained_queue_events':len(a['queue']),'retained_transport':a['transport'],
        'unchanged_global_state':retained,'changes':changes,
        'derived_changes':'only deletion schedules required by changed persistent values',
        'alignment':'fixed anonymous addresses and directed address pairs; recipient signals retained',
        'artificial_intervention':True,'created_engines':0}
