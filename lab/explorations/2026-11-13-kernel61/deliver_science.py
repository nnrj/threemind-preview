"""Publish one completed R51 science batch through the existing research API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import UUID,uuid5
import zipfile
import httpx

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import support as s
NS=UUID('d5230456-a96e-5700-89fb-ce397c466c18')
RESOURCE='kernel60-revalidation-20261113'


def verify(pack,manifest):
    with zipfile.ZipFile(pack) as z:
        assert set(z.namelist())=={r['path'] for r in manifest['members']}|{'manifest.json'}
        assert json.loads(z.read('manifest.json'))==manifest
        for r in manifest['members']:
            data=z.read(r['path']);assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']


def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):digest.update(block)
    return digest.hexdigest()


def deliver(work,folder,tag,raw_cap_mib=512):
    if (work/'publication/completion.json').exists():
        print((work/'publication/completion.json').read_text('utf-8'));return
    assert not (work/'in-flight.json').exists()
    audit=json.loads((work/'audit.json').read_bytes());assert audit['passed']
    registration=json.loads((work/'registration.json').read_bytes())
    project=registration['project'];ident=lambda name:uuid5(NS,tag+':'+name)
    s.base.resource_check(work);s.base.load_env()
    with s.base.worker_lock(work),s.base.OperationsClient(url='http://127.0.0.1:8877',username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),reuse_session=False,require_auth=True,source='ai') as client:
        rec=s.base.ResearchRecorder(work,project,client=client);rec.resume_recording()
        for p in folder.iterdir():
            if p.suffix in ('.py','.md'):rec.save_original('delivery-tools/'+p.name,p.read_bytes())
        rec.save_original('delivery-tools/deliver_science.py',Path(__file__).read_bytes())
        for lang in ('zh','en'):
            rec.text({'identity':str(ident('report-document-'+lang)),'request_id':str(ident('report-'+lang)),
                      'kind':'report','expected_revision':0,'title':tag+' report '+lang,'markdown':(folder/f'report.{lang}.md').read_text('utf-8')})
        rec.text({'identity':str(ident('note-document')),'request_id':str(ident('note')),'kind':'note','expected_revision':0,
                  'title':tag+' evidence and provenance','markdown':'Explicit 6.1 replication. Historical originals and identities are retained. '
                  'Causal copies are nested within their source; the complete batch is audited before closure. '
                  'Read-only analysis by the assistant is not external reproduction. Scientific outcomes and stopping decisions are stated in both reports.'})
        excluded={'.research-records','publication','readback'}
        files=sorted(p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&excluded
                     and p.name not in ('originals.zip','manifest.json') and not p.name.endswith('.lock'))
        assert not any(p.name.endswith('.partial') for p in files)
        manifest={'members':[{'path':p.relative_to(work).as_posix(),'bytes':p.stat().st_size,'sha256':s.sha(p)} for p in files]}
        total=sum(x['bytes'] for x in manifest['members'])
        assert raw_cap_mib>0 and total<raw_cap_mib*2**20 and shutil.disk_usage(work).free>25*2**30+2*total+64*2**20
        rec.save_original('manifest.json',json.dumps(manifest,sort_keys=True).encode())
        pack=work/'originals.zip'
        if not pack.exists():
            part=pack.with_suffix('.zip.partial')
            with zipfile.ZipFile(part,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                for p in files+[work/'manifest.json']:z.write(p,p.relative_to(work).as_posix())
            verify(part,manifest);part.rename(pack)
        verify(pack,manifest)
        for name,role,fmt in (('originals.zip','original','application/zip'),('manifest.json','manifest','application/json'),('analysis.json','analysis','application/json')):
            p=work/name
            rec.attach({'logical_id':tag+':'+name,'role':role,'label':tag+' '+name,'format':fmt,'byte_count':p.stat().st_size,'sha256':file_sha(p),
                        'locator':{'kind':'file','resource_id':RESOURCE,'member':work.name+'/'+name}},request_id=ident('attach-'+name))
        rec.synchronize(strict=True)
        args={'path':{'project':project,'experiment':rec.experiment},'query':{'hashes':True}}
        check=client.call('records.verify',args);assert check['coverage']=='verified' and not check['problems']
        row=next(x for x in check['evidence'] if x['logical_id']==tag+':originals.zip')
        out=work/'readback/originals.zip';out.parent.mkdir(exist_ok=True)
        if not out.exists():client.call('records.download',{'path':{'project':project,'evidence':row['id']}},output=out,maximum=pack.stat().st_size)
        assert file_sha(out)==file_sha(pack);verify(out,manifest)
        for lang in ('zh','en'):
            doc=client.request('GET',f'/api/v2/projects/{project}/research-documents/{ident("report-document-"+lang)}')
            assert doc['spec']['blocks'][0]['markdown']==(folder/f'report.{lang}.md').read_text('utf-8')
        rec.finalize(request_id=ident('finalize'));rec.synchronize(strict=True)
        check=client.call('records.verify',args);assert check['coverage']=='verified' and not check['problems'] and rec.status['pending']==0
        result={'project':project,'record':rec.experiment,'coverage':'verified','pending':0,'members':len(manifest['members']),
                'archive_bytes':pack.stat().st_size,'archive_sha256':file_sha(pack),'scientific_stop':audit.get('scientific_stop',False)}
        s.base.original(work/'publication/completion.json',result);print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--tools',type=Path,required=True);p.add_argument('--tag',required=True)
    p.add_argument('--raw-cap-mib',type=int,default=512,help='Explicit cap from this batch\'s preregistered originals budget')
    a=p.parse_args();deliver(a.work.resolve(),a.tools.resolve(),a.tag,a.raw_cap_mib)
