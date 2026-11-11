"""Explicit copied-state connection transfer, extracted from the E50 control.

No original state is modified; this is research intervention, not Core learning.
Node history, clock, energy and pending signals remain the recipient's.
"""
import copy


def transfer_edges(recipient, donor, selected):
    result=copy.deepcopy(recipient)
    rc={int(n['id']):int(n['channel']) for n in recipient['nodes']}
    target={int(n['channel']):int(n['id']) for n in recipient['nodes']}
    dc={int(n['id']):int(n['channel']) for n in donor['nodes']}
    selected={tuple(map(int,e)) for e in selected}
    pairs={(rc[a],rc[b]) for a,b in selected}
    inserted={};removed={}
    for field in ('edges','short_term','fast'):
        receiver=result['edges'] if field=='edges' else result['operator_state'][field]
        original=donor['edges'] if field=='edges' else donor['operator_state'][field]
        keep=[r for r in receiver if (int(r['source']),int(r['target'])) not in selected]
        removed[field]=len(receiver)-len(keep); added=0
        for row in original:
            a,b=dc[int(row['source'])],dc[int(row['target'])]
            if (a,b) not in pairs:continue
            clone=copy.deepcopy(row);clone['source']=target[a];clone['target']=target[b]
            keep.append(clone);added+=1
        keep.sort(key=lambda r:(int(r['source']),int(r['target'])))
        if field=='edges':result['edges']=keep
        else:result['operator_state'][field]=keep
        inserted[field]=added
    return result,{'selected':len(selected),'removed':removed,'inserted':inserted,
          'retained':'recipient nodes, activity, energy, clock, novelty state and pending transmissions'}
