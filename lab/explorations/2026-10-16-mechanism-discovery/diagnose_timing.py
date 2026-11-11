"""Post-result clock-phase diagnostic; does not change frozen forecasts or scores."""
import argparse
import hashlib
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import pilot_m2_timing as t


def aligned_first(graph, channels, cfg, cue, arm):
    lag=t.CUES[cue]/1000
    nodes={n['channel']:n['id'] for n in graph['nodes']}
    edges={(e['source'],e['target']):e['weight'] for e in graph['edges']}
    coefficient=cfg['direct_gain']*math.exp(-.1/cfg['activation_tau'])*cfg['propagation_rate']*.1*cfg['stp_utilization']
    out=[]
    for target in 'AB':
        arrivals=[coefficient*.5*edges.get((nodes.get(channels[s]),nodes.get(channels[target])),0.)*
                  (math.exp(lag/cfg['activation_tau']) if s=='Y' else 1.) for s in 'XY']
        valid=[a for a in arrivals if a>=cfg['activation_floor']]
        value=sum(valid) if arm=='summed' else (statistics.mean(valid) if valid else 0.)
        out.append(value if value>=cfg['activation_floor'] else 0.)
    return out[0]-out[1]


def main(work):
    a=t.m.read(work/'analysis-v1.json')
    rows,errors=[],defaultdict(list)
    for case in t.m.read(work/'parents.json'):
        folder=work/'parents'/case['id']; current=t.m.read(folder/'current.json')
        parent=t.f.load(folder/current['path']); graph=t.f.load(folder/'pre-cue-graph.json.gz')
        for cue in [c for c in t.CUES if c.startswith('XY-')]:
            for arm in t.ARMS:
                final=t.f.load(work/'cases'/f'{case["id"]}-{cue}-{arm}'/'final-whole.json.gz')
                probe=[r for r in final['recent_activity'] if r['time_us']>32_000_000]
                first=next((r['time_us']-32_000_000 for r in probe if abs(r['response'])>1e-9),None)
                actual=next(r['response'] for r in probe if r['time_us']==32_110_000)
                pred=aligned_first(graph,parent['mappings'],parent['core']['config'],cue,arm)
                errors[case['origin']].append(abs(actual-pred))
                rows.append({'origin':case['origin'],'history':case['history'],'cue':cue,'arm':arm,
                             'first_nonzero_grid_us':first,'actual_110ms':actual,'posthoc_aligned_110ms':pred})
    source=t.m.ROOT/'crates/threemind-core/src/local_shared.rs'
    result={'schema':'threemind.m2-timing-posthoc-diagnostic/1','classification':'post-result interpretation, not prospective validation',
            'original_analysis_sha256':hashlib.sha256((work/'analysis-v1.json').read_bytes()).hexdigest(),
            'source_path':source.relative_to(t.m.ROOT).as_posix(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_mechanism':'pulse: aligned ceiling period plus completed_emission guard; external input can precede same-time emission',
            'original_primary_gain':a['summary']['primary_1ms_gain'],'original_prediction_status':'failed and unchanged',
            'first_nonzero_grid_us_counts':dict(Counter(str(r['first_nonzero_grid_us']) for r in rows)),
            'first_arrival_mae_by_origin':{o:statistics.mean(v) for o,v in errors.items()},
            'first_arrival_mae_mean':statistics.mean(statistics.mean(v) for v in errors.values()),
            'limitations':'Posthoc first-arrival approximation; not a validated forecast of later pulses or arbitrary phase/spacing. Nominal 110+lag endpoint was not necessarily a second physical arrival.',
            'rows':rows}
    t.m.original(work/'timing-diagnostic-v1.json',result)
    print(t.m.encoded({k:v for k,v in result.items() if k!='rows'}).decode())


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,default=t.WORK)
    main(p.parse_args().work)
