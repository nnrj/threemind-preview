"""Measure original files and complete assay subjects without loading kernels."""
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'lab/explorations/2026-11-09-retention-causality'))
from storage_inventory import sum_files

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/assay-v1')


def main():
    assert json.loads((WORK/'status.json').read_text('utf-8'))==dict(state='awaiting-analysis',sequences_completed=1920)
    assert not any((WORK/p).exists() for p in ('STOP','in-flight.json'))
    files=[p for p in WORK.rglob('*') if p.is_file()
        and not set(p.relative_to(WORK).parts)&{'.research-records','publication','readback'}
        and not p.name.startswith('originals-v1') and not p.name.endswith('.lock')]
    states=list((WORK/'subjects').rglob('whole.json.gz'))
    assert len(states)==3840
    largest=max(states,key=lambda p:p.stat().st_size)
    raw=gzip.decompress(largest.read_bytes());state=json.loads(raw)
    out=dict(measurement='Before publication. Windows FileStandardInfo allocated file streams, hard links counted once; directory/MFT/database overhead excluded.',
        study=sum_files(files),one_complete_individual=sum_files([largest]),
        largest_state=dict(path=largest.relative_to(WORK).as_posix(),compressed_bytes=largest.stat().st_size,
            decoded_json_bytes=len(raw),nodes=len(state['core']['nodes']),directed_connections=len(state['core']['edges']),
            contributions=sum(len(r['decay_contributions']) for r in state['core']['nodes']+state['core']['edges'])),
        personal_state='This first-layer assay has fixed adapters and a fixed temporal instrument; its complete state is self-contained, with no learned weights or optimizer dependencies.')
    with (WORK/'storage-inventory-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2)
    print(json.dumps(out))


if __name__=='__main__':main()
