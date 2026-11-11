"""Report tables from completed originals; all extra decompositions are descriptive."""
import argparse
import json
import numpy as np
import experiment as e


def tally(rows):
    out={}
    def rate(name,values):out[name]=dict(correct=sum(values),n=len(values),rate=sum(values)/len(values) if values else None)
    for kind in ('old','clear','ambiguous'):
        subset=[r for r in rows if r['case']['kind']==kind]
        for phase in ('first','second'):
            for head in ('sound','vision','action'):
                eligible=subset if phase=='second' or kind!='ambiguous' or head=='action' else []
                rate(f'{kind}.{phase}.{head}',[r[phase]['predictions'][head]==r['case']['expected' if phase=='first' else 'actual'] for r in eligible])
            eligible=subset if phase=='second' or kind!='ambiguous' else []
            rate(f'{kind}.{phase}.joint',[all(r[phase]['predictions'][h]==r['case']['expected' if phase=='first' else 'actual'] for h in ('sound','vision','action')) for r in eligible])
        rate(f'{kind}.view',[r['first']['predictions']['action']==2 for r in subset])
    conflicts=[r for r in rows if r['case'].get('conflict')]
    rate('conflict.second.joint',[all(r['second']['predictions'][h]==r['case']['actual'] for h in ('sound','vision','action')) for r in conflicts])
    rate('conflict.first.joint_actual',[all(r['first']['predictions'][h]==r['case']['actual'] for h in ('sound','vision','action')) for r in conflicts])
    return out


def main(work):
    a=e.load(work/'analysis-v1.json');audit=e.load(work/'integrity-audit-v1.json')
    rows={arm:[] for arm in e.ARMS};source=[]
    for i in range(e.N):
        item={}
        for arm in e.ARMS:
            r=[e.load(work/f'origins/o{i}/h{h}/{arm}/trial-{j:03d}/result.json.gz') for h in (0,1) for j in range(24)]
            rows[arm]+=r;item[arm]=tally(r)
        source.append(dict(origin=i,conditions=item))
    aggregates={arm:tally(r) for arm,r in rows.items()}
    rng=np.random.default_rng(20261109);indices=rng.integers(0,e.N,size=(20000,e.N))
    contrasts={}
    for name,arm,metric in [('view_benefit','view-blocked','ambiguous.second.action'),
                            ('target_loss','target','clear.first.joint'),('matched_loss','matched','clear.first.joint')]:
        v=np.array([s['conditions']['intact'][metric]['rate']-s['conditions'][arm][metric]['rate'] for s in source])
        interval=np.quantile(v[indices].mean(axis=1),[.025,.975]).tolist()
        contrasts[name]=dict(by_independent_origin=v.tolist(),mean=float(v.mean()),descriptive_percentile95=interval)
    files=[p for p in work.rglob('*') if p.is_file() and '.research-records' not in p.parts]
    largest=max((work/'origins').rglob('whole.json.gz'),key=lambda p:p.stat().st_size)
    state=e.load(largest)
    unique_adapter_files={work/ref['path']/name for ref in state['adapter_refs'].values() for name in ref['files']}
    out=dict(schema='threemind.context-report-tables/1',independent_n=e.N,aggregates=aggregates,by_source=source,
        primary_verdict=a['verdict'],primary_successes=a['successes'],primary_intervals=a['intervals'],
        descriptive_contrasts=contrasts,extra_analysis='per-head decomposition and bootstrap are descriptive; they do not change registered goals',
        resources=e.load(work/'resource-summary.json'),storage=dict(files_before_publication=len(files),logical_bytes_before_publication=sum(p.stat().st_size for p in files),
            largest_compressed_whole_state_bytes=largest.stat().st_size,adapter_dependency_bytes=sum(p.stat().st_size for p in unique_adapter_files)),
        validation=dict(complete_boundaries=audit['complete_boundaries'],continuous_groups=audit['continuous_groups'],
            checked_trials=a['checked_trials'],total_computed_internal_seconds=audit['total_computed_internal_seconds']))
    e.save(work/'summary-v1.json',out)
    print(json.dumps({k:v for k,v in out.items() if k not in ('by_source','aggregates')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=e.Path,default=e.WORK);a=p.parse_args();main(a.work.resolve())
