"""Read-only R46b storage, cost and complete-subject measurements."""
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'lab/explorations/2026-11-09-retention-causality'))
from storage_inventory import sum_files

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/stimulus-v1')


def main():
    load=lambda p:json.loads(p.read_text('utf-8'))
    assert load(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=960)
    assert load(WORK/'independent-audit-v1.json')['passed']
    assert not any((WORK/n).exists() for n in ('STOP','in-flight.json','storage-inventory-v1.json'))
    files=[p for p in WORK.rglob('*') if p.is_file()
        and not set(p.relative_to(WORK).parts)&{'.research-records','publication','readback'}
        and not p.name.startswith('originals-v1') and not p.name.endswith('.lock')]
    states=list((WORK/'subjects').rglob('whole.json.gz'));assert len(states)==1920
    largest=max(states,key=lambda p:p.stat().st_size);raw=gzip.decompress(largest.read_bytes());s=json.loads(raw)
    analysis=load(WORK/'analysis-v1.json');cost=[]
    for curve in ('exponential','inverse-logarithmic','power-law'):
        for relax in (True,False):
            rows=[r for r in analysis['rows'] if r['case']['curve']==curve and r['case']['relaxation']==relax]
            assert len(rows)==160
            cost.append(dict(curve=curve,relaxation=relax,sequences=160,
                operation_wall_seconds=sum(r['wall_seconds'] for r in rows),
                maximum_boundary_private_bytes=max(r['max_boundary_private_bytes'] for r in rows)))
    out=dict(measurement='Before publication; Windows allocated streams deduplicated by file identity, excluding directory/MFT/database overhead.',
        study=sum_files(files),one_complete_individual=sum_files([largest]),cost_by_setting=cost,
        largest_state=dict(path=largest.relative_to(WORK).as_posix(),compressed_bytes=largest.stat().st_size,decoded_json_bytes=len(raw),
            nodes=len(s['core']['nodes']),directed_connections=len(s['core']['edges']),
            contributions=sum(len(r['decay_contributions']) for r in s['core']['nodes']+s['core']['edges'])),
        state_scope='Complete local assay: Core, fixed adapter mapping, event history, background cursor, condition and temporal instrument; no trained head.')
    with (WORK/'storage-inventory-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps(out))


if __name__=='__main__':main()
