"""Read-only /2 cross-sensory matching at the actual saved instant.

No engine is constructed, no state is modified, and no outcome is consulted.
This selector is preparation for a separately registered historical factorial.
"""
import math
import numpy as np
from scipy.optimize import linear_sum_assignment

KERNEL='threemind.continuous-memory/2'
CALIPERS=np.asarray([.05,.05,2.,2.,2.,2.,.1,.1])
FEATURES=('slow_weight','effective_weight','source_out','source_in','target_out','target_in','source_activation','target_activation')


def edge_features(state):
    if state['definition']['kernel_id']!=KERNEL:
        raise ValueError('historical /2 state required; never substitute a newer kernel')
    now=int(state['time_us']);config=state['config']
    nodes={n['id']:n for n in state['nodes']}
    degree={i:[0,0] for i in nodes}
    for e in state['edges']:
        degree[e['source']][0]+=1;degree[e['target']][1]+=1
    fast={(r['source'],r['target']):r['state'] for r in state['operator_state']['fast']}
    out=[]
    for edge in sorted(state['edges'],key=lambda e:(e['source'],e['target'])):
        key=(edge['source'],edge['target']);effective=edge['weight']
        if config['fast_enabled']:
            trace=fast.get(key,{'value':0.,'time_us':edge['birth_us']})
            age=(now-int(trace['time_us']))/1e6
            if age<0:raise ValueError('future fast-state timestamp')
            effective=min(1.,edge['weight']+config['fast_gain']*trace['value']*math.exp(-age/config['fast_tau_s']))
        values=[edge['weight'],effective,*degree[key[0]],*degree[key[1]],nodes[key[0]]['activation'],nodes[key[1]]['activation']]
        if not np.isfinite(values).all():raise ValueError('nonfinite matching input')
        out.append({'key':list(key),'features':dict(zip(FEATURES,map(float,values)))})
    return out


def match_edges(table,hearing_nodes,count=16):
    if type(count) is not int or count<1:raise ValueError('positive edge count required')
    hearing=set(hearing_nodes)
    target=sorted((e for e in table if (e['key'][0] in hearing)!=(e['key'][1] in hearing)),key=lambda e:tuple(e['key']))
    control=sorted((e for e in table if not set(e['key'])&hearing),key=lambda e:tuple(e['key']))
    base={'required_pairs':count,'cross_edges':len(target),'control_edges':len(control),'calipers':dict(zip(FEATURES,CALIPERS.tolist())),
          'selection_uses_only_parent':True,'matching':'maximum cardinality then minimum sum of normalized residuals; retain lowest-cost declared count; sorted endpoint tie order'}
    if not target or not control:return base|{'valid':False,'available_pairs':0,'pairs':[]}
    x=np.asarray([[e['features'][f] for f in FEATURES] for e in target])
    y=np.asarray([[e['features'][f] for f in FEATURES] for e in control])
    residual=np.abs((x[:,None,:]-y[None,:,:])/CALIPERS)
    allowed=(residual<=1.).all(axis=2)
    # One forbidden assignment costs more than all possible valid assignments.
    forbidden=8.*(min(len(x),len(y))+1)+1.
    cost=np.where(allowed,residual.sum(axis=2),forbidden)
    rr,cc=linear_sum_assignment(cost)
    found=[]
    for i,j in zip(rr,cc):
        if not allowed[i,j]:continue
        diffs=np.abs(x[i]-y[j])
        found.append({'target':target[i],'matched':control[j],'residual':dict(zip(FEATURES,diffs.tolist())),
                      'normalized_cost':float(cost[i,j])})
    found.sort(key=lambda p:(p['normalized_cost'],tuple(p['target']['key']),tuple(p['matched']['key'])))
    valid=len(found)>=count
    return base|{'valid':valid,'available_pairs':len(found),'pairs':found[:count] if valid else [],
                 'maximum_normalized_residual':max((max(p['residual'][f]/c for f,c in zip(FEATURES,CALIPERS)) for p in found[:count]),default=None)}


def select(state,hearing_channels,count=16):
    h={n['id'] for n in state['nodes'] if n['channel'] in set(hearing_channels)}
    return match_edges(edge_features(state),h,count)
