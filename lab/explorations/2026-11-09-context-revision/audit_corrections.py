"""Observe committed development records only; flag unhandled correction cases."""
import argparse
import gzip
import json
from pathlib import Path
import time


def audit(work):
    rows=[];missed=[]
    for p in sorted(work.glob('origins/o*/h*/teaching-*/result.json.gz')):
        if not (p.parent/'complete.json').exists():continue
        d=json.loads(gzip.decompress(p.read_bytes()))
        stage=int(p.parent.name.rsplit('-',1)[1]);cases=[]
        for r in d['development']:
            c=r['case'];a=r['first']['predictions'];b=r['second']['predictions']
            heads=('action',) if c['expected']==2 else ('sound','vision','action')
            first=all(a[k]==c['expected'] for k in heads)
            later=all(b[k]==c['actual'] for k in ('sound','vision','action'))
            if c['kind']!='old' and first and not later:cases.append(c['id'])
        row=dict(path=p.relative_to(work).as_posix(),second_only_errors=cases,correction_follows=stage<2 and not d['ready'])
        rows.append(row)
        if cases and row['correction_follows']:missed.append(row)
    return dict(checked_stages=len(rows),unhandled_cases=missed,rows=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--watch',action='store_true')
    a=p.parse_args()
    while True:
        result=audit(a.work)
        if result['unhandled_cases']:
            if a.watch:
                try:
                    with (a.work/'STOP').open('x',encoding='utf-8') as f:
                        json.dump(dict(reason='development error omitted by correction selector; inspect before continuation',audit=result),f)
                except FileExistsError:pass
            print(json.dumps(result));raise SystemExit(2)
        if not a.watch or json.loads((a.work/'status.json').read_bytes())['state']!='running' or (a.work/'STOP').exists():
            print(json.dumps(result));break
        time.sleep(1)
