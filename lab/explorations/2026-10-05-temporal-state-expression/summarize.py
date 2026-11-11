"""Summarize all registered outputs, including fitting failures and controls."""
from collections import Counter,defaultdict
from experiment import *


def decoder_summary(path):
    path=path.resolve()
    r=read_json(path);groups={}
    for group,conditions,seconds in (
        ('seen532',('continued','reversal'),532),('seen592',('continued','reversal'),592),
        ('unseen532',('cycle1','cycle2'),532),('unseen592',('cycle1','cycle2'),592)):
        rows=[x for x in r['rows'] if x['item']>=0 and x['condition'] in conditions and x['seconds']==seconds]
        groups[group]={'raw_correct':sum(x['output']==x['target'] for x in rows),
                       'cue_specific':sum(x['correct'] for x in rows),'count':len(rows)}
    return {'name':path.stem,'owner':r['owner'],'fit_correct':r['fit_correct'],'fit_count':r['fit_count'],
            'parameters':r['metadata']['parameters'],'device':r['metadata']['device'],'groups':groups,
            'evidence':str(path.relative_to(ROOT))}


def main():
    timing=read_json(HERE/'raw-timing.json')
    groups=defaultdict(list)
    keys=('regime','scope','fields','interval_us','seconds','modality')
    for row in timing['rows']:
        if row['item']>=0:groups[tuple(row[k] for k in keys)].append(row)
    timing_scores=[dict(zip(keys,key))|{'raw_correct':sum(x['output']==x['target'] for x in rows),
        'cue_specific':sum(x['correct'] for x in rows),'count':len(rows)} for key,rows in sorted(groups.items())]
    sources=[read_json(p) for p in (WORK/'cases').glob('*/result.json')]
    models=[decoder_summary(p) for folder in ('raw-models','graph-models') for p in sorted((WORK/folder).glob('*.json'))]
    result={'date':'2026-10-05','study':'E48','project':read_json(WORK/'platform.json')['project_id'],
        'core_changed':False,'sample_normalization':False,'counterfactual_subtraction':False,'dialogue_cache':False,
        'timing':timing_scores,'timing_legacy_summary':timing['summary'],'decoders':models,
        'timing_followup':read_json(HERE/'timing-followup-results.json') if (HERE/'timing-followup-results.json').exists() else None,
        'events':read_json(HERE/'events-results.json') if (HERE/'events-results.json').exists() else None,
        'cases':dict(Counter(r['kind'] for r in sources)),
        'recorded_compute_seconds':sum(r['wall_seconds'] for r in sources)+sum(read_json(p).get('wall_seconds',0) for p in (WORK/'timing').glob('*.json')),
        'work_bytes':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
        'account_start':45,'account_latest':read_json(WORK/'usage.json')['used_percent'],
        'stage_execution':{p.stem:read_json(p) for p in (WORK/'stage-execution').glob('*.json')}}
    new_json(HERE/'results.json',result)
    print(json.dumps({k:result[k] for k in ('cases','recorded_compute_seconds','work_bytes','decoders')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
