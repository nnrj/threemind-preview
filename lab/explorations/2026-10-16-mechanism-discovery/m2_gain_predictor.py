"""Gain-aware first-arrival formula; pure pre-cue arithmetic, no Core loading."""
import math
from m2_threshold_predictor import predict as first_version


def predict(whole,dose):
    c=whole['model']['config']
    forecast=first_version(whole,dose*c['direct_gain'])
    nodes={n['channel']:n for n in whole['model']['nodes']};value=0.;received={}
    for label,sign in [('A',1),('B',-1)]:
        p=forecast['targets'][label]
        amount=0.
        if p['passes']:
            n=nodes[whole['mappings'][label]]
            assert n['fatigue']==0 and n['pending_inhibition']==0
            dt=(forecast['first_arrival_us']-int(n['state_us']))/1e6
            inh=n['inhibition']*(math.exp(-dt/c['inhibition_tau']) if c['inhibition_decay_enabled'] else 1.)
            soft=c['inhibition_saturation']*math.tanh(max(0.,inh)/c['inhibition_saturation'])
            amount=p['message']/(1+c['inhibition_response_gain']*soft) if c['inhibition'] else p['message']
        received[label]=amount;value+=sign*amount
    return {'schema':'threemind.first-arrival-gain-prediction/1','direction':int(value>1e-4)-int(value<-1e-4),
            'endpoint':value,'dose':dose,'direct_gain':c['direct_gain'],'received':received,'sender':forecast,
            'first_arrival_us':forecast['first_arrival_us'],'inputs':'complete pre-cue state and declared cue; no post-cue activity'}
