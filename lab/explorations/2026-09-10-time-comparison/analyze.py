"""Read-only, channel-aligned analysis of the entire recorded activity."""
import gzip
import json
from pathlib import Path

import numpy as np
from run import HERE, WORK, save


def read(path):
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def vector(row):
    return {n[1]:n[2] for n in row['nodes']}


def difference(left,right):
    a,b=vector(left),vector(right)
    return max((abs(a.get(k,0)-b.get(k,0)) for k in a.keys() | b.keys()),default=0)


def analyze():
    cases=[]
    for path in sorted(WORK.glob('*-summary.json')):
        result=json.loads(path.read_bytes())
        key=path.name.removesuffix('-summary.json')
        start=result['trained']['time_us']
        branches={}
        for branch in ('no_input','cue'):
            rows=read(WORK/(key+'-'+branch+'.jsonl.gz'))
            late=[r for r in rows if r['time_us']>=start+11_000_000]
            bytime={r['time_us']:r for r in rows}
            phase_error=[difference(r,bytime[r['time_us']-100_000]) for r in late
                         if r['time_us']-100_000 in bytime]
            end=rows[-1]
            ranking=sorted(end['nodes'],key=lambda n:(-n[2],n[0]))
            top=ranking[0][2] if ranking else 0
            branches[branch]={**result['continuations'][branch],
                'last_second_max_100ms_vector_change':max(phase_error,default=None),
                'last_second_min_active':min((r['active'] for r in late),default=None),
                'top_tie_count':sum(abs(n[2]-top)<=1e-12 for n in ranking),
                'endpoint_ranking':ranking,
                'death_after_training_seconds':(end['time_us']-start)/1e6 if end['life']=='dead' else None}
            branches[branch].pop('last')
        quiet=read(WORK/(key+'-no_input.jsonl.gz')); cue=read(WORK/(key+'-cue.jsonl.gz'))
        quiet_bytime={r['time_us']:r for r in quiet}
        contrasts=[dict(after_training_seconds=(r['time_us']-start)/1e6,
                        max_abs_activation_difference=difference(r,quiet_bytime[r['time_us']]))
                   for r in cue if r['time_us'] in quiet_bytime and r['time_us']>=start+100_000]
        windows=[]
        reader_path=WORK/(key+'-temporal-readouts.json')
        if reader_path.exists():
            for record in json.loads(reader_path.read_bytes()):
                if record['kind']!='temporal_readout':continue
                w=record['payload']
                windows.append({k:w.get(k) for k in ('window_id','classification','reason','start_us','end_us',
                                                     'censored','coverage','configuration')})
                windows[-1]['endpoint_ranking']=sorted(w['nodes'],key=lambda n:(-n['last_activation'],n['node_id']))
        cases.append(dict(key=key,seed=result['seed'],group=result['group'],version=result['version'],
          training_count=result['training_count'],nodes=len(result['trained']['nodes']),edges=result['trained']['edges'],
          branches=branches,matched_cue_difference=contrasts,temporal_windows=windows,
          wall_seconds=result['wall_seconds'],peak_rss=result['peak_rss']))
    result=dict(cases=cases,completed_training_cases=len(cases),
                computational_seconds=sum(c['wall_seconds'] for c in cases),
                peak_rss=max(c['peak_rss'] for c in cases),
                scope='within-version comparisons are controlled; cross-version comparison is descriptive')
    save(HERE/'analysis.json',result)
    return result


if __name__=='__main__':
    result=analyze()
    for c in result['cases']:
        print(c['key'],c['nodes'],c['edges'])
        for branch,v in c['branches'].items():
            print(branch,{k:v[k] for k in ('late_mean_range','late_spread_range',
                 'last_second_max_100ms_vector_change','top_tie_count','death_after_training_seconds')})
        print('windows',[(w['classification'],w['reason']) for w in c['temporal_windows']])
