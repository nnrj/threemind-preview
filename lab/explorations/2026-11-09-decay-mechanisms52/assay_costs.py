"""Report operational cost by implementation; never pool unlike timing paths."""
from pathlib import Path
import hashlib
import json
import statistics

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')

def read(path):return json.loads(path.read_text('utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def summarize(work,analysis):
    grouped={};records=[]
    for row in analysis['rows']:
        c=row['case'];folder=work/'subjects'/c['key']
        receipts=[read(folder/phase/'complete.json') for phase in ('teaching','probe')]
        implementations={r.get('implementation','original-frozen') for r in receipts}
        assert len(implementations)==1,'explicitly account for a sequence spanning implementations'
        implementation=implementations.pop()
        assert implementation in ('original-frozen','exact-acceleration-v2')
        elapsed=sum(r['wall_seconds'] for r in receipts)
        assert elapsed==row['wall_seconds']
        record=dict(key=c['key'],origin=c['origin'],curve=c['curve'],relaxation=c['relaxation'],
            implementation=implementation,wall_seconds=elapsed,
            boundary_private_bytes=max(r['private_bytes'] for r in receipts))
        records.append(record)
        grouped.setdefault((c['curve'],c['relaxation'],implementation),[]).append(record)
    summaries=[]
    for (curve,relaxation,implementation),rows in grouped.items():
        values=[r['wall_seconds'] for r in rows]
        summaries.append(dict(curve=curve,relaxation=relaxation,implementation=implementation,
            sequences=len(rows),origins=sorted({r['origin'] for r in rows}),
            mean_wall_seconds=statistics.mean(values),median_wall_seconds=statistics.median(values),
            total_operation_seconds=sum(values),maximum_operation_seconds=max(values),
            max_boundary_private_bytes=max(r['boundary_private_bytes'] for r in rows)))
    assert sum(r['implementation']=='original-frozen' for r in records)==175
    assert sum(r['implementation']=='exact-acceleration-v2' for r in records)==1745
    return dict(schema='threemind.decay-assay-operational-cost/1',sequences=1920,
        interpretation='Observed strata are not randomized implementation comparisons. No pooled timing ranking.',
        conditions=summaries,records=records)

def main():
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=1920)
    assert not any((WORK/x).exists() for x in ('STOP','in-flight.json'))
    analysis=read(WORK/'analysis-v1.json');audit=read(WORK/'independent-audit-v1.json')
    assert analysis['sequences']==1920 and audit['passed']
    out=summarize(WORK,analysis)
    out['source_sha256']=sha(Path(__file__))
    out['analysis_sha256']=sha(WORK/'analysis-v1.json')
    out['acceleration_proof']=read(WORK/'resumptions/exact-acceleration-v2/r46-exact-acceleration-v3/verified.json')
    with (WORK/'operational-cost-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps(dict(cost_strata=out['conditions'],sequences=1920)))

if __name__=='__main__':main()
