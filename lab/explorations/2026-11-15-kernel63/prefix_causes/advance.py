"""Continue after a harmless ordering mismatch in the immutable historical audit.

The frozen historical verifier lists changed fields by set iteration. The first
audit remains intact. Verify identical content with that list sorted, then
register exactly the previously declared B plan. No subject or score changes.
"""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
t=module('r51t15_advance_study',HERE/'study.py')
h=module('r51t15_advance_history',HERE/'historical.py')
def normalized(d):
    d=deepcopy(d)
    for row in d['rows']:row['different_state_fields'].sort()
    return d
def advance(work):
    t.check(work)
    assert not any((work/n).exists() for n in ('STOP','in-flight.json','phase-B.json'))
    original=t.s.read(work/'historical-comparison.json')
    assert normalized(original)==normalized(h.verify(work))
    assert t.s.read(work/'phase-A-summary.json')['stages']==18
    scores=t.scores(work)
    assert scores['legacy-positive']['passed'] and scores['bypass-l0-g0']['passed']
    cases=t.s.read(work/'materials.json')
    plan=[q for name in t.GROUPS if name!='bypass-l0-g0' for q in t.stages(cases,'B','S',name)]
    assert len(plan)==66
    src=Path(__file__).read_bytes()
    out=work/'analysis-tools/advance.py';out.parent.mkdir(exist_ok=True)
    if out.exists():assert out.read_bytes()==src
    else:out.write_bytes(src)
    t.freeze(work,'B',plan,{'positive_controls':scores,'factorial_remaining':66,
        'historical_content_verified':True,'format_issue':'unordered list of changed field names; original preserved',
        'continuation_source_sha256':hashlib.sha256(src).hexdigest()})
    print('B registered: 66 stages; historical audit preserved and content verified.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);advance(p.parse_args().work)
