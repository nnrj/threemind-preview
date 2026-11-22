"""Attach the full audit before invoking the existing verified delivery path."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid5
sys.path.insert(0,str(Path(__file__).parent))
import run_exchanges as x
s=x.s
sys.path.insert(0,str(s.ROOT/'lab/explorations/2026-11-13-kernel61'))
import deliver_science_v2 as publisher

def run(work):
    x.check(work)
    audit=s.read(work/'final-audit.json')
    assert audit['passed'] and audit['stages']==94 and audit['states']==188 and audit['processes']==68
    assert not (work/'in-flight.json').exists()
    if (work/'publication/completion.json').exists():
        print(json.dumps(s.read(work/'publication/completion.json')));return
    s.base.load_env();import httpx
    with s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,s.PROJECT,client=client);rec.resume_recording()
        rec.save_original('delivery-tools/engineering-summary.json',(s.HERE/'engineering-summary.json').read_bytes())
        for name in ('final-analysis.json','final-audit.json'):
            p=work/name
            rec.attach({'logical_id':'r51t7:'+name,'role':'analysis','label':'R51t7 complete 94-stage '+name,'format':'application/json',
                        'byte_count':p.stat().st_size,'sha256':s.sha(p),'locator':{'kind':'file','resource_id':publisher.RESOURCE,'member':work.name+'/'+name}},
                        request_id=uuid5(s.NS,'final-attach-'+name))
        rec.synchronize(strict=True);assert rec.status['pending']==0
    publisher.deliver(work,s.HERE,'r51t7-prefix-recovery62',raw_cap_mib=1024)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();run(a.work)
