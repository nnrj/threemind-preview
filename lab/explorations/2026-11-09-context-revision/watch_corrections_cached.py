"""Check newly committed development records without rereading unchanged originals."""
import argparse
import json
import time
from pathlib import Path
from audit_corrections import audit


def main(work):
    checked=set();result=None
    while True:
        committed={p.relative_to(work).as_posix() for p in work.glob('origins/o*/h*/teaching-*/complete.json')}
        if committed!=checked:
            result=audit(work);checked=committed
            print(json.dumps(dict(checked_stages=result['checked_stages'],unhandled_cases=result['unhandled_cases'])),flush=True)
            if result['unhandled_cases']:
                try:
                    with (work/'STOP').open('x',encoding='utf-8') as f:
                        json.dump(dict(reason='development error omitted by correction selector; inspect before continuation',audit=result),f)
                except FileExistsError:pass
                return
        state=json.loads((work/'status.json').read_bytes())
        if state['state']!='running' or (work/'STOP').exists():
            print(json.dumps(dict(final_status=state,checked_stages=len(checked))),flush=True);return
        time.sleep(2)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();main(a.work.resolve())
