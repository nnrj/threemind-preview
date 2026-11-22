"""Inject a wall-budget crossing on calibration codes, preserving completion."""
import argparse
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile

spec=importlib.util.spec_from_file_location('r51t10_budget_recorder',Path(__file__).with_name('recording_v2.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
s=r.s


def run(work):
    stage=next(q for q in s.s.read(work/'plan.json') if q['key']=='prefix/p0-f0/0/train')
    case=deepcopy(stage['case']);case['end_us']=8000000
    rows=[v for v in s.load_inputs(work,stage,True) if int(v['source_policy']['resolved_at_us'])<case['end_us']]
    s.TARGETS={c^0x20000000 for c in s.TARGETS}
    checks=[]
    with tempfile.TemporaryDirectory(dir=s.ROOT/'.work',prefix='r51t10-budget-') as temp:
        for backend in ('reference','native'):
            outputs=[]
            for forced in (False,True):
                out=Path(temp)/backend/str(forced);out.mkdir(parents=True);r.ACTIVE_WORK=out
                e=s.engine({'seed':9291199}|case['initial_config']|s.FLAGS['p1-f1'],backend=backend)
                real=r.time.monotonic;clock=iter([0])
                if forced:r.time.monotonic=lambda:next(clock,301.)
                try:e,_,count=r.drive(e,case,rows,out,backend=backend)
                finally:r.time.monotonic=real
                assert e.time_us==8000000 and count==len(rows)
                assert (out/'STOP').exists()==forced
                with gzip.open(out/'course.jsonl.gz','rb') as f:outputs.append((e.capture_state().digest,f.read()))
            assert outputs[0]==outputs[1]
            checks.append({'backend':backend,'boundary_reached':True,'complete_state_and_records_equal':True})
    s.s.write(work/'recording-budget-verification.json',{'passed':True,'checks':checks})
    print(json.dumps(checks))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);run(p.parse_args().work)
