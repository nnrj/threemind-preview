"""Read saved M1 parents only. No Core construction, restoration or advancement."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_parent(folder):
    current=json.loads((folder/'current.json').read_bytes())
    path=folder/current['path']
    if sha(path)!=current['sha256']:
        raise ValueError('parent witness hash mismatch')
    wrapper=json.loads(gzip.decompress(path.read_bytes()))
    if set(wrapper)!={'schema','subject','observation'}:
        raise ValueError('unexpected M1 complete witness wrapper')
    whole=wrapper['subject']
    if int(whole['core']['time_us'])!=current['time_us']:
        raise ValueError('parent time mismatch')
    return whole, {'path':str(path.resolve()),'sha256':sha(path)}


def topology(whole):
    # Correspondence uses declared anonymous interfaces, never outcome search.
    channels={n['id']:n['channel'] for n in whole['core']['nodes']}
    return {(channels[e['source']],channels[e['target']]) for e in whole['core']['edges']}


def audit(work):
    rows=[]
    for origin in range(8):
        a,wa=read_parent(work/'parents'/f'o{origin}-h0')
        b,wb=read_parent(work/'parents'/f'o{origin}-h1')
        ca,cb=a['core'],b['core']; ta,tb=topology(a),topology(b)
        rows.append({'origin':origin,'parent_witnesses':[wa,wb],
                     'schema':ca['schema'],'kernel':ca['dynamics'],
                     'same_current_time':ca['time_us']==cb['time_us'],
                     'time_us':ca['time_us'],'same_declared_mappings':a['mappings']==b['mappings'],
                     'same_configuration':ca['config']==cb['config'],
                     'edge_counts':[len(ta),len(tb)],'shared_edges':len(ta&tb),
                     'only_h0':len(ta-tb),'only_h1':len(tb-ta),
                     'queue_lengths':[len(ca['queue']),len(cb['queue'])],
                     'timer_rows':sorted(ca['timers']),
                     'edge_fields':sorted({k for c in (ca,cb) for e in c['edges'] for k in e}),
                     'legacy_schema_compatible':ca['schema']=='threemind.continuous-memory-state/2',
                     'legacy_topology_compatible':ta==tb})
    old=Path(__file__).resolve().parents[2]/'tools/state_exchange.py'
    return {'schema':'threemind.exchange-readiness/1','classification':'read-only tooling readiness, not transplantation',
            'sources':8,'parent_count':16,'legacy_tool':str(old.resolve()),'legacy_tool_sha256':sha(old),
            'all_parent_witnesses_verified':True,
            'legacy_eligible_pairs':sum(r['legacy_schema_compatible'] and r['legacy_topology_compatible'] for r in rows),
            'rows':rows,'decision':'Do not apply the state/2 exchange tool to these /5.1 parents. Specify structural/state-field mapping and scheduler closure in a separate /5.1 research-copy protocol; preserve parents and verify sham/roundtrip before any graft. No graft or Core change performed.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); result=audit(args.work)
    with args.out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
