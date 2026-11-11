"""Local pathway and persistent-experience controls on disposable engine copies.

No control writes to the source engine. Counterfactual sensory replay isolates
internal action generation; it is reported separately from free closed-loop food.
"""
import copy
import math

import numpy as np

from lab.tools.ocean import channel
from lab.tools.ocean_controls import naive_same_receptors
from threemind_core import StateImage, Stimulus
from threemind_runtime import create_engine
from threemind_runtime.inheritance import birth


def motor(engine, gain=.12):
    seed=engine.config.seed
    nodes=engine.activations()
    return [math.tanh(gain*math.fsum((1 if channel(seed,f'motor:{j}:{n}')&1 else -1)*a for n,a in nodes))
            for j in range(3)]


def select_pathways(image, recent_channels, maximum=12, *, include_internal=False):
    state=image.to_dict()
    nodes={n['id']:n for n in state['nodes']}
    targets={n['id'] for n in nodes.values() if n['channel'] not in recent_channels and n['activation']>.004}
    candidates=[e for e in state['edges'] if e['target'] in targets and (include_internal or e['source'] not in targets)]
    candidates.sort(key=lambda e:(-e['weight']*nodes[e['source']]['activation'],e['source'],e['target']))
    selected=candidates[:maximum]
    selected_pairs={(e['source'],e['target']) for e in selected}
    available=[e for e in state['edges'] if (e['source'],e['target']) not in selected_pairs and e['target'] not in targets]
    matched=[]
    errors=[]
    for edge in selected:
        if not available:break
        def distance(e):
            return abs(e['weight']-edge['weight'])+abs(e['stability']-edge['stability'])
        chosen=min(available,key=lambda e:(distance(e),e['source'],e['target']))
        matched.append(chosen); errors.append(distance(chosen)); available.remove(chosen)
    if len(matched)!=len(selected):
        return {'applicable':False,'reason':'insufficient matched edges','targets':sorted(targets)}
    return {'applicable':bool(selected),'reason':None if selected else 'no active unprompted target with inbound edges',
            'targets':sorted(targets),'target_edges':[[e['source'],e['target']] for e in selected],
            'matched_edges':[[e['source'],e['target']] for e in matched],'matching_errors':errors,
            'target_channels':[nodes[i]['channel'] for i in sorted(targets)],
            'eligible_edges':len(candidates),'selected_edges':len(selected),'include_internal':include_internal}


def replay(image, rows, operation='sham', *, edges=(), gain=.12, reset=False, initial_reserve=None):
    state=image.to_dict()
    origin=int(state['time_us']) if reset else 0
    if reset:
        image=naive_same_receptors(image) if operation=='naive' else birth(image)
    engine=create_engine(state=image,backend='native')
    if initial_reserve is not None:
        # Explicit apparatus provision for paired births, never a source-world change.
        reserve=engine.metrics()['energy']['reserve']
        if reserve>initial_reserve+1e-9:raise ValueError('cannot silently discard birth energy')
        if initial_reserve>reserve:
            engine.supply_energy(initial_reserve-reserve,time_us=engine.time_us,source='paired-birth-provision/1')
    before=engine.capture_state().to_dict()
    if operation in ('target','matched','all','restore','release'):
        chosen=edges if operation!='all' else [(e['source'],e['target']) for e in before['edges']]
        engine.intervene(edges=chosen,action='silence')
        if operation=='restore':engine.intervene(edges=chosen,action='unsilence')
        after=engine.capture_state().to_dict()
        assert all(before[k]==after[k] for k in before if k not in ('silenced_edges','sequence'))
    trace=[]
    released=False
    start=int(state['time_us'])-origin
    for row in rows:
        s=copy.deepcopy(row['stimulus'])
        when=int(s['time_us'])-origin
        if when<=engine.time_us:continue
        if engine.life=='dead':
            # Death is an outcome, not permission to revive a counterfactual copy.
            # Keep aligned observation rows without delivering further input/energy.
            trace.append({'time_us':int(row['stimulus']['time_us']),'action':motor(engine,gain),
                          'nodes':[[n['id'],n['activation']] for n in engine.observation_nodes()],
                          'life':'dead','input_delivered':False})
            continue
        if operation=='release' and not released and when-start>=2000000:
            engine.intervene(edges=edges,action='unsilence')
            released=True
        s['time_us']=str(when)
        # The reference world supplied this amount. Every replay gets that same amount.
        if row['food']>0:engine.supply_energy(row['food'],time_us=when,source='ocean-causal-replay/1')
        action=motor(engine,gain)
        engine.inject(Stimulus.from_dict(s))
        engine.advance_to(when)
        trace.append({'time_us':int(row['stimulus']['time_us']),'action':action,
                      'nodes':[[n['id'],n['activation']] for n in engine.observation_nodes()],
                      'life':engine.life})
    return trace,engine.capture_state()


def compare(reference, altered, targets=()):
    if len(reference)!=len(altered) or any(a['time_us']!=b['time_us'] for a,b in zip(reference,altered)):
        raise ValueError('counterfactual observation times differ')
    if not reference:return {'samples':0}
    differences=np.asarray([np.asarray(a['action'])-b['action'] for a,b in zip(reference,altered)])
    target=[]
    for a,b in zip(reference,altered):
        na,nb=dict(a['nodes']),dict(b['nodes'])
        target.append(sum(abs(na.get(k,0)-nb.get(k,0)) for k in targets))
    return {'samples':len(reference),'motor_mean_absolute':float(np.abs(differences).mean()),
            'motor_peak_absolute':float(np.abs(differences).max()),'target_activation_mean_absolute':float(np.mean(target)),
            'first_action_change_us':next((a['time_us'] for a,d in zip(reference,differences) if np.abs(d).max()>1e-8),None)}


def local_persistent_transplant(recipient, donor, pairs):
    """Restore selected learned edges into a blank birth with identical identities.

    This does not transfer current activation, energy or short-term edge resources.
    The operation is artificial and only valid for exactly channel-aligned copies.
    """
    a,b=recipient.to_dict(),donor.to_dict()
    if a['config']!=b['config'] or [(n['id'],n['channel']) for n in a['nodes']] != [(n['id'],n['channel']) for n in b['nodes']]:
        raise ValueError('transplant requires identical configuration and receptor identities')
    wanted={tuple(p) for p in pairs}
    old={(e['source'],e['target']):e for e in a['edges']}
    for edge in b['edges']:
        key=edge['source'],edge['target']
        if key in wanted:old[key]=copy.deepcopy(edge)
    a['edges']=[old[k] for k in sorted(old)]
    out=StateImage.from_dict(a)
    engine=create_engine(state=out,backend='native')
    return engine.capture_state()


def neutralize_persistent_strength(image):
    """Development control: zero persistent strength, retain topology and fast states.

    Not total memory erasure. In-flight signals, current activation/inhibition,
    fast edge traces/resources, energy, clocks and receptor/motor identities stay.
    """
    before=image.to_dict()
    state=copy.deepcopy(before)
    for node in state['nodes']:
        node.update(support=0.0,stability=0.0,touches=0,local_plasticity=1.0)
    for edge in state['edges']:
        edge.update(weight=0.0,stability=0.0,eligibility=0.0,touches=0)
    result=create_engine(state=StateImage.from_dict(state),backend='native').capture_state()
    after=result.to_dict()
    assert all(before[k]==after[k] for k in before if k not in ('nodes','edges'))
    for a,b in zip(before['nodes'],after['nodes']):
        assert all(a[k]==b[k] for k in a if k not in ('support','stability','touches','local_plasticity'))
    for a,b in zip(before['edges'],after['edges']):
        assert all(a[k]==b[k] for k in a if k not in ('weight','stability','eligibility','touches'))
    return result
