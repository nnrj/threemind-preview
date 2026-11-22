"""6.3 first-arrival arithmetic for a quiescent connected component.

This is a measurement predictor, not a Core implementation. It neither creates
nor advances a subject. Preconditions deliberately exclude unmodelled earlier
arrivals; formal tests must record an invalid apparatus rather than bypass them.
"""
import math


def decay(value, seconds, enabled, tau):
    assert seconds >= 0
    return value*math.exp(-seconds/tau) if enabled else value


def recovered_fraction(state, emission_us, config):
    if not config['stp_enabled']:
        return 1.
    assert config['stp_facilitation_tau_s'] == 0
    if not config['depletion_enabled'] or state is None:
        return config['stp_utilization']
    dt = (emission_us-int(state['time_us']))/1e6
    assert dt >= 0
    ta, tr = config['stp_active_tau_s'], config['stp_recovery_tau_s']
    assert ta != tr
    active = state['active']*math.exp(-dt/ta)
    inactive = max(0., 1-state['available']-state['active'])*math.exp(-dt/tr)
    inactive += state['active']*tr/(tr-ta)*(math.exp(-dt/tr)-math.exp(-dt/ta))
    return config['stp_utilization']*min(1., max(0., 1-active-inactive))


def predict(whole, cue='X', dose=.8):
    assert cue in ('X','Y','Z','W') and math.isfinite(dose) and 0 <= dose <= 1
    model, mapping = whole['model'], whole['mappings']
    c, now = model['config'], int(model['time_us'])
    assert model['dynamics'] == 'threemind.continuous-memory/6.3'
    assert c['consolidation_mode'] == 'adaptive-half-life' and c['decay_curve'] == 'inverse-logarithmic'
    assert not c['retention_growth_enabled'] and not c['retention_relaxation_enabled']
    assert not c['energy_simulation_enabled'] and not c['spatial_embedding']
    assert c['propagation_phase'] == 'aligned' and now % c['propagation_interval_us'] == 0
    assert int(model['completed_emission_us']) == now
    assert not model['silenced_nodes'] and not model['silenced_edges']
    assert c['activation_decay_enabled'] and c['inhibition_distribution'] == 'per-connection'
    assert not c['resource_precheck_enabled'] and not c['separate_inhibition_resources']
    nodes = {n['id']:n for n in model['nodes']}
    source = nodes[mapping[cue]]
    edges = {(e['source'],e['target']):e for e in model['edges']}
    component = {source['id']}
    while True:
        expanded = component | {x for pair in edges for x in pair if any(n in component for n in pair)}
        if expanded == component:
            break
        component = expanded
    soft = lambda value:c['inhibition_saturation']*math.tanh(max(0.,value)/c['inhibition_saturation'])
    response = lambda inhibition:1/(1+c['inhibition_response_gain']*soft(inhibition)) if c['inhibition'] else 1.
    for ident in component:
        node = nodes[ident]
        elapsed = (now-int(node['state_us']))/1e6
        activity = decay(node['activation'],elapsed,c['activation_decay_enabled'],c['activation_tau'])
        assert activity < c['activation_floor'] or activity == 0
        inhibition = decay(node['inhibition'],elapsed,c['inhibition_decay_enabled'],c['inhibition_tau'])
        assert inhibition < c['inhibition_send_threshold']
        assert node['pending_inhibition'] == node['generated_inhibition'] == node['fatigue'] == 0
        assert not node['sleeping']
    # This bounded predictor requires no pending events at all. Background
    # timers outside the task component may continue but cannot reach it.
    assert model['queue'] == []
    assert not any(int(row[0]) == 0 and int(row[1]) in component for row in model['timers'])
    interval = c['propagation_interval_us']
    emission, arrival = now+interval, now+interval+c['delay_us']
    assert interval+c['delay_us'] == 110_000
    assert not any(int(row[0]) in (2,3,4,5,7) and int(row[1]) in component
                   and int(row[3]) <= arrival for row in model['timers'])
    i0 = decay(source['inhibition'],(now-int(source['state_us']))/1e6,
               c['inhibition_decay_enabled'],c['inhibition_tau'])
    start_activation = min(1.,dose*c['direct_gain']*response(i0))
    activation = start_activation*math.exp(-(interval/1e6)/c['activation_tau'])
    if activation < c['activation_floor']:
        activation = 0.
    inhibition = decay(i0,interval/1e6,c['inhibition_decay_enabled'],c['inhibition_tau'])
    if c['inhibition']:
        inhibition = soft(inhibition)
    flux = activation*response(inhibition)*c['propagation_rate']*interval/1e6
    if activation < max(c['propagation_activation_min'],c['activation_send_threshold']):
        flux = 0.
    threshold = c['activation_signal_threshold']
    threshold = c['signal_threshold'] if threshold is None else threshold
    targets, answer = {}, 0.
    for label,sign in (('A',1),('B',-1)):
        target = nodes.get(mapping[label])
        edge = edges.get((source['id'],mapping[label]))
        if target is None or edge is None:
            targets[label] = {'message':0.,'activation':0.,'edge_exists':False}
            continue
        assert not edge['sleeping'] and not target['sleeping']
        assert target['activation'] == 0. and target['pending_inhibition'] == 0. and target['fatigue'] == 0.
        age = edge['decay_age']
        later = age+(emission-int(edge['state_us']))/(1e6*edge['half_life'])
        weight = edge['weight']*(1+math.log1p(math.expm1(1.)*age))/(1+math.log1p(math.expm1(1.)*later))
        fast = edge['fast']
        gain = 0. if fast is None or not c['fast_enabled'] else fast['value']*math.exp(-(emission-int(fast['time_us']))/(1e6*c['fast_tau_s']))
        effective = min(1.,weight+c['fast_gain']*gain) if c['fast_enabled'] else weight
        fraction = recovered_fraction(edge['short_term'],emission,c)
        offered = flux*effective*fraction
        passes = offered > 0 and (not c['signal_threshold_enabled'] or offered >= threshold)
        passes = passes and (not c['weight_gate_enabled'] or weight >= c['weight_gate'])
        message = offered if passes else 0.
        target_inhibition = decay(target['inhibition'],(arrival-int(target['state_us']))/1e6,
                                  c['inhibition_decay_enabled'],c['inhibition_tau'])
        value = min(1.,message*response(target_inhibition))
        targets[label] = {'edge_exists':True,'persistent_weight':weight,'effective_weight':effective,
                          'release_fraction':fraction,'offered':offered,'message':message,'activation':value}
        answer += sign*value
    return {'schema':'threemind.r63-first-arrival-development/1','cue':cue,'dose':dose,
            'direction':int(answer>1e-4)-int(answer < -1e-4),'endpoint':answer,
            'first_arrival_us':arrival,'source_activation':activation,'flux':flux,'targets':targets,
            'inputs':'complete pre-cue state and declared cue; no post-cue observations'}
