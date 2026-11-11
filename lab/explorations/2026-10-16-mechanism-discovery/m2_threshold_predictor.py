"""Pre-cue first-hop transmission predictor; file arithmetic only, never loads Core.

Scope is the registered legacy-stability anonymous rig, inactive X/A/B at an
aligned boundary, zero fast traces, no energy/spatial attenuation. Its binary
prediction is tested against the unchanged native engine, not fitted to it.
"""
import math


def recovered_fraction(st, now, config):
    if st is None:
        return config['stp_utilization']
    dt=(now-int(st['time_us']))/1e6
    assert dt>=0 and config['stp_facilitation_tau_s']==0
    ta=config['stp_active_tau_s'];tr=config['stp_recovery_tau_s']
    assert ta!=tr
    active=st['active']*math.exp(-dt/ta)
    inactive=max(0.,1-st['available']-st['active'])*math.exp(-dt/tr)
    inactive+=st['active']*tr/(tr-ta)*(math.exp(-dt/tr)-math.exp(-dt/ta))
    available=min(1.,max(0.,1-active-inactive))
    return config['stp_utilization']*available


def predict(whole,dose):
    model=whole['model'];c=model['config'];start=int(model['time_us'])
    assert whole['mode']=='S' and c['consolidation_mode']=='legacy-stability'
    assert not c['energy_simulation_enabled'] and not c['spatial_embedding']
    assert c['propagation_phase']=='aligned' and start%c['propagation_interval_us']==0
    assert c['stp_enabled'] and not model['silenced_edges'] and not model['silenced_nodes']
    assert not c['strong_fatigue_enabled'] or all(n['fatigue']==0 for n in model['nodes'])
    nodes={n['channel']:n for n in model['nodes']};channels=whole['mappings']
    n=nodes[channels['X']]
    assert n['activation']==0 and n['pending_inhibition']==0 and not n['sleeping']
    interval=c['propagation_interval_us'];emission=start+interval
    dt=interval/1e6
    soft=lambda value:c['inhibition_saturation']*math.tanh(max(0.,value)/c['inhibition_saturation'])
    decay=lambda value,elapsed,enabled,tau:value*math.exp(-elapsed/tau) if enabled else value
    i0=decay(n['inhibition'],(start-int(n['state_us']))/1e6,c['inhibition_decay_enabled'],c['inhibition_tau'])
    response=lambda inh:1/(1+c['inhibition_response_gain']*soft(inh)) if c['inhibition'] else 1.
    activation=min(1.,dose*response(i0))
    activation=decay(activation,dt,c['activation_decay_enabled'],c['activation_tau'])
    if activation<c['activation_floor']:activation=0.
    inhibition=soft(decay(i0,dt,c['inhibition_decay_enabled'],c['inhibition_tau'])) if c['inhibition'] else i0
    flux=activation*response(inhibition)*c['propagation_rate']*dt
    edges={(e['source'],e['target']):e for e in model['edges']}
    targets={}
    for label in ('A','B'):
        target=nodes.get(channels[label])
        if target is None:
            targets[label]={'message':0.,'pre_stp':0.,'release_fraction':0.,'passes':False}
            continue
        assert target['activation']==0 and not target['sleeping']
        edge=edges.get((n['id'],target['id']))
        if edge is None:
            targets[label]={'message':0.,'pre_stp':0.,'release_fraction':0.,'passes':False}
            continue
        assert not edge['sleeping'] and edge['fast'] is None
        before=flux*edge['weight'];fraction=recovered_fraction(edge['short_term'],emission,c)
        message=before*fraction
        passes=activation>=c['propagation_activation_min'] and before>=c['activation_floor'] and message>=c['activation_floor'] and message>0
        targets[label]={'message':message,'pre_stp':before,'release_fraction':fraction,'passes':passes,
                        'edge':[n['id'],target['id']],'weight':edge['weight']}
    direction=int(targets['A']['passes'])-int(targets['B']['passes'])
    assert not(targets['A']['passes'] and targets['B']['passes'])
    return {'direction':direction,'first_arrival_us':emission+c['delay_us'],'targets':targets,
            'source_activation_at_emission':activation,'flux':flux,'floor':c['activation_floor'],
            'inputs':'complete pre-cue state and declared cue dose; no measured post-cue activity'}
