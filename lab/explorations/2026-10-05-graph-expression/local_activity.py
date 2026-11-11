"""Anonymous local activity windows, not the complete stored network.

Selection is entirely observational. Raw evidence is kept by the caller. No
amplitude normalization, baseline subtraction, semantic targets or top-k gate.
"""
import numpy as np
from threemind_runtime.graph_observation import VERSION,EDGE_FIELDS,graph_frame,NODE_FIELDS

FIELDS=('activation','inhibition','direct','associative','generated_inhibition','pending_inhibition')
POLICY={'schema':'threemind.local-activity-policy/1','samples':17,
        'selection':'nonzero activity/flow or an observed rise in inhibition; retain that node for the window',
        'top_k':None,'amplitude_floor':0,'normalize':False,'baseline_subtraction':False,
        'omitted':'quiet structural state and monotonically decaying inhibition without participation'}


def local_process(process,*,edges=False,samples=17):
    if not 2<=samples<=64:raise ValueError('bounded sample count')
    frames=process['trajectory'];selected=set();previous={}
    if not frames:raise ValueError('empty trajectory')
    for frame in frames:
        for node in frame['nodes']:
            channel=int(node['channel'])
            if any(float(node[k])!=0 for k in FIELDS if k!='inhibition') or (
                channel in previous and float(node['inhibition'])>previous[channel]):selected.add(channel)
            previous[channel]=float(node['inhibition'])
    if edges:
        recorded=[graph_frame(s) for s in process['states']]
        indices=[NODE_FIELDS.index(k) for k in FIELDS]
        for frame in recorded:
            frame['nodes']=[dict(n,values=[n['values'][i] for i in indices]) for n in frame['nodes'] if n['channel'] in selected]
            ids={n['id'] for n in frame['nodes']}
            frame['edges']=[e for e in frame['edges'] if e['source'] in ids and e['target'] in ids]
    else:
        positions=np.unique(np.rint(np.linspace(0,len(frames)-1,min(samples,len(frames)))).astype(int))
        recorded=[]
        for index in positions:
            frame=frames[index]
            recorded.append({'time_us':frame['time_us'],'nodes':[
                {'id':str(n['id']),'channel':int(n['channel']),'values':[float(n[k]) for k in FIELDS]}
                for n in frame['nodes'] if int(n['channel']) in selected],'edges':[]})
    return {'schema':VERSION,'node_fields':list(FIELDS),'edge_fields':list(EDGE_FIELDS),
            'start_us':process['start_us'],'end_us':process['end_us'],'frames':recorded}
