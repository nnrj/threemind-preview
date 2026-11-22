"""Read-only descriptions of saved task connections and activity time courses.

These descriptions explain registered outcomes; they do not change the scores.
No Core is created or advanced.
"""
import argparse
import json
import lzma
from pathlib import Path

TOKENS={2932:'A',4786:'B',6969:'C',2064:'D',1925:'E'}

def unpack(path):return json.loads(lzma.decompress(path.read_bytes()))

def describe(work):
    cases=sum((json.loads((work/name).read_bytes()) for name in ('cases.json','supplement-cases.json','novelty-cases.json')),[])
    rows=[]
    for case in cases:
        folder=work/'cases'/case['key']
        assert json.loads((folder/'result.json').read_bytes())['status']=='complete'
        graph=unpack(folder/'projections.json.xz')['end']['graph']
        ids={n['id']:TOKENS[n['channel']] for n in graph['nodes'] if n.get('channel') in TOKENS}
        nodes={ids[n['id']]:{f:n.get(f) for f in ('activation','inhibition','support','trace','sleeping','half_life')}
               for n in graph['nodes'] if n['id'] in ids}
        outside_edges=[e for e in graph['edges'] if (e['source'] in ids)!=(e['target'] in ids)]
        edges=[{'source':ids[e['source']],'target':ids[e['target']],
                **{k:e.get(k) for k in ('weight','half_life','decay_age','sleeping','fast','short_term','stability')}}
               for e in graph['edges'] if e['source'] in ids and e['target'] in ids]
        trajectory=unpack(folder/'trajectory.json.xz')['points']
        activity=[{'seconds':(p['time_us']-case['begin_us'])/1e6,
                   **{f:max((n.get(f,0.) for n in p['nodes'] if n['channel'] in TOKENS),default=0.)
                      for f in ('activation','inhibition','direct','associative')}} for p in trajectory]
        first=activity[0];last_positive=max((p['seconds'] for p in activity if p['activation']>0),default=None)
        curve=activity if case['kind']=='readout_wait' or '/sustain/' in case['key'] and case['key'].endswith('/unchanged') else []
        rows.append({'key':case['key'],'kind':case['kind'],'variant':case['variant'],
                     'nodes':nodes,'edges':edges,'outside_incident_edges':len(outside_edges),'last_positive_seconds':last_positive,
                     'first':first,'end':activity[-1],'activity':curve})
    result={'description':'Retrospective description of frozen trajectories; registered scores are unchanged.',
            'stages':len(rows),'rows':rows}
    target=work/'profiles.json'
    text=json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf8')
    if target.exists():assert target.read_bytes()==text
    else:
        with target.open('xb') as stream:stream.write(text)
    print(json.dumps({'stages':len(rows),'bytes':len(text)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);a=p.parse_args();describe(a.work)
