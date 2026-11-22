"""Append an identity correction to the completed R51t record, preserving its report."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid5
import httpx

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import investigate as h
s=h.s

def publish(work):
    receipt=work/'historical-record-correction.json'
    if receipt.exists():
        print(receipt.read_text('utf8'));return
    prior=work.parent/'memory-timescales61-v1'
    done=h.read(prior/'publication/completion.json')
    assert done['coverage']=='verified' and done['pending']==0
    source_report=HERE.parent/'memory_timescales/report.zh.md'
    source_hash=s.sha(source_report)
    original_manifest=s.sha(prior/'manifest.json')
    s.base.load_env()
    with s.base.worker_lock(prior),s.base.OperationsClient(url='http://127.0.0.1:8877',
        username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),
        require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(prior,h.e.base.PROJECT,client=client);rec.resume_recording()
        for lang in ('zh','en'):
            content=(HERE.parent/f'memory_timescales/errata-20261114.{lang}.md').read_text('utf8')
            ident=uuid5(h.NS,'historical-correction-document-'+lang)
            rec.text({'identity':str(ident),'request_id':str(uuid5(h.NS,'historical-correction-'+lang)),
                'expected_revision':0,'kind':'note','title':'R51t historical kernel identity correction '+lang,
                'markdown':content})
        rec.append('correction','r51t:historical-kernel-identity',{'correct_kernel':'threemind.continuous-memory/1',
            'superseded_label':'threemind.continuous-memory/2','historical_results':592,
            'scientific_results_unchanged':True,'original_manifest_sha256':original_manifest,
            'proof_record':h.read(work/'registration.json')['record'],
            'proof_sha256':s.sha(work/'historical-identity-proof.json')},
            request_id=uuid5(h.NS,'historical-correction-event'))
        rec.synchronize(strict=True)
        verified=client.call('records.verify',{'path':{'project':done['project'],'experiment':rec.experiment},'query':{'hashes':True}})
        assert verified['coverage']=='verified' and not verified['problems'] and rec.status['pending']==0
        for lang in ('zh','en'):
            ident=uuid5(h.NS,'historical-correction-document-'+lang)
            doc=client.request('GET',f'/api/v2/projects/{done["project"]}/notes/{ident}')
            body=doc['body']
            content=body['text'] if body['format']=='markdown' else body['content']['content'][0]['content'][0]['text']
            assert content==(HERE.parent/f'memory_timescales/errata-20261114.{lang}.md').read_text('utf8')
        assert s.sha(source_report)==source_hash and s.sha(prior/'manifest.json')==original_manifest
        result={'record':rec.experiment,'pending':0,'coverage':'verified','original_manifest_sha256':original_manifest,
            'original_report_sha256':source_hash,'correct_kernel':'threemind.continuous-memory/1'}
        s.base.original(receipt,result)
        print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();publish(a.work)
