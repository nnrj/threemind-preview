"""Require both audited scientific components before standard API delivery."""
import argparse
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from deliver_science import deliver

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',required=True,type=Path);a=p.parse_args()
    audits=[json.loads((a.work/n).read_bytes()) for n in ('audit.json','audit-novelty.json')]
    assert all(x['passed'] for x in audits) and sum(x['stages'] for x in audits)==476
    assert json.loads((a.work/'historical-record-correction.json').read_bytes())['pending']==0
    assert json.loads((a.work/'report-statistics.json').read_bytes())['stages']==476
    deliver(a.work.resolve(),HERE,'r51t1',raw_cap_mib=2048)
