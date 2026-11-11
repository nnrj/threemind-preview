"""Pure-data connection masks for explicit copied-state research interventions."""
import numpy as np


def cross_domain_masks(image,left,right):
    left,right=set(left),set(right)
    if left & right:
        raise ValueError('comparison domains must not overlap')
    nodes={int(node['id']):int(node['channel']) for node in image['nodes']}
    def target(edge):
        a,b=nodes[int(edge['source'])],nodes[int(edge['target'])]
        return (a in left and b in right) or (a in right and b in left)
    selected=[edge for edge in image['edges'] if target(edge)]
    rest=[edge for edge in image['edges'] if not target(edge)]
    if not selected or len(rest)<len(selected):return None
    control=[];errors=[]
    for edge in sorted(selected,key=lambda row:-row['weight']):
        index=min(range(len(rest)),key=lambda j:abs(rest[j]['weight']-edge['weight']))
        other=rest.pop(index);control.append(other);errors.append(abs(other['weight']-edge['weight']))
    return {'schema':'threemind.connection-control/1',
        'target':[(int(e['source']),int(e['target'])) for e in selected],
        'matched':[(int(e['source']),int(e['target'])) for e in control],
        'mean_weight_error':float(np.mean(errors)),'max_weight_error':max(errors),
        'target_weight_sum':sum(e['weight'] for e in selected),'matched_weight_sum':sum(e['weight'] for e in control),
        'method':'descending_target_nearest_available','topology_matched':False,
        'interpretation':'count matched, weight approximated; not an equal-function or exact-topology control'}
