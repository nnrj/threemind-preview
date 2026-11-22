"""Append mechanism-description corrections without altering verified originals."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID,uuid5
import httpx
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import components_study as h
NS=UUID('65cf0b85-266b-5566-be9e-1d1a6ae86af9')

def publish(root):
    for work_name,folder_name,topic in (
      ('closed-body61-v1','body_report','threshold applies to excitation and inhibition after connection transmission; sender thresholds unchanged'),
      ('prefix-cross61-v1','prefix_cross_report','legacy and adaptive configurations share base-weight strengthening formulas; legacy changes forgetting and its stability/use dependence')):
        work=root/work_name;folder=HERE.parent/'dynamics_function'/folder_name
        receipt=work/'publication/mechanism-description-r2.json'
        if receipt.exists():continue
        old=h.read(work/'publication/completion.json');assert old['coverage']=='verified' and old['pending']==0
        manifest=h.s.sha(work/'manifest.json');original={lang:h.s.sha(folder/f'report.{lang}.md') for lang in ('zh','en')}
        h.s.base.load_env()
        with h.s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),require_auth=True,source='ai') as client:
            rec=h.s.base.ResearchRecorder(work,old['project'],client=client);rec.resume_recording();ident=lambda x:uuid5(NS,work_name+':'+x)
            for lang in ('zh','en'):
                md=(folder/f'report-r2.{lang}.md').read_text('utf8')
                rec.save_original('publication/mechanism-description-r2.'+lang+'.md',md.encode())
                rec.text({'identity':str(ident('report-'+lang)),'request_id':str(ident('request-'+lang)),
                    'expected_revision':0,'kind':'report','title':work_name+' mechanism description revision '+lang,'markdown':md})
            rec.append('correction','mechanism-description-20261114',{'topic':topic,'scientific_scores_unchanged':True,
                'manifest_sha256':manifest,'original_reports':original},request_id=ident('event'))
            rec.synchronize(strict=True)
            for lang in ('zh','en'):
                doc=client.request('GET',f'/api/v2/projects/{old["project"]}/research-documents/{ident("report-"+lang)}')
                assert doc['spec']['blocks'][0]['markdown']==(folder/f'report-r2.{lang}.md').read_text('utf8')
            rec.finalize(request_id=ident('finalize'));rec.synchronize(strict=True)
            check=client.call('records.verify',{'path':{'project':old['project'],'experiment':rec.experiment},'query':{'hashes':True}})
            assert check['coverage']=='verified' and not check['problems'] and rec.status['pending']==0
            assert h.s.sha(work/'manifest.json')==manifest
            assert all(h.s.sha(folder/f'report.{lang}.md')==original[lang] for lang in original)
            result={'coverage':'verified','pending':0,'topic':topic,'record':rec.experiment,'original_manifest_unchanged':True,'original_reports_unchanged':True,'scientific_scores_unchanged':True}
            h.s.base.original(receipt,result);print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();publish(a.root)
