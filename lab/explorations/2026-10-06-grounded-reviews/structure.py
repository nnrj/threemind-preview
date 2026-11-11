"""Read-only grouping by known external sensory ports; no Core brain regions."""
from collections import Counter,defaultdict
import gzip,json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from lab.tools.grounded_classroom import GroundedClassroom
WORK=ROOT/'.work/grounded-reviews-20261006'


def inspect(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:state=json.load(f)
    w=GroundedClassroom.restore(state['world'])
    ports={c:'vision' for c in w.channels[:256]}
    ports.update({c:'body' for c in w.channels[256:272]})
    ports.update({c:'background' for c in w.channels[272:]})
    groups={n['id']:ports.get(n['channel'],'text') for n in state['core']['nodes']}
    stats=defaultdict(lambda:defaultdict(float));edges=Counter();weights=Counter()
    for n in state['core']['nodes']:
        g=groups[n['id']];stats[g]['nodes']+=1
        stats[g]['active_nodes']+=n['activation']>0
        for field in ('activation','inhibition','direct','associative','stability','support'):
            stats[g][field+'_sum']+=n[field]
    for e in state['core']['edges']:
        key=groups[e['source']]+' -> '+groups[e['target']]
        edges[key]+=1;weights[key]+=e['weight']
    return {'groups':dict(stats),'edges':dict(edges),'weight_sums':dict(weights),
        'scope':'external observer groups by sensory provenance, never Core semantic areas',
        'time_us':state['core']['time_us']}


def main():
    results={}
    for p in sorted((WORK/'cases').glob('*-teaching/checkpoint.json.gz')):results[p.parent.name]=inspect(p)
    path=Path(__file__).parent/'structure.json'
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False))


if __name__=='__main__':main()
