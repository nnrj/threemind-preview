"""Publish completed engineering checks through the existing research API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import UUID, uuid5
import zipfile

import httpx
import foundation_v2 as f

NS=UUID('310a0666-c277-48f6-889d-d25526af9c43')
RESOURCE='kernel60-revalidation-20261113'


def ident(s):
    return uuid5(NS,s)


def read(p):
    return json.loads(p.read_bytes())


def connection():
    f.base.load_env()
    return f.base.OperationsClient(url='http://127.0.0.1:8877',
        username=os.environ.get('THREEMIND_API_USERNAME'),password=os.environ.get('THREEMIND_API_PASSWORD'),
        token=os.environ.get('THREEMIND_API_TOKEN'),transport=httpx.HTTPTransport(trust_env=False),
        reuse_session=False,require_auth=True,source='ai')


def verify(pack, manifest):
    with zipfile.ZipFile(pack) as z:
        assert set(z.namelist())=={r['path'] for r in manifest['members']}|{'manifest.json'}
        assert read_bytes(z.read('manifest.json'))==manifest
        for r in manifest['members']:
            data=z.read(r['path'])
            assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']


def read_bytes(data):
    return json.loads(data)


def publish(work):
    assert read(work/'audit-v2.json')['passed']
    assert read(work/'foundation-v2/summary.json')['state']=='paused-performance'
    assert not list(work.rglob('in-flight.json'))
    if (work/'publication/completion.json').exists():
        print((work/'publication/completion.json').read_text('utf-8'));return
    f.base.resource_check(work)
    with f.base.worker_lock(work), connection() as client:
        title='2026-11-13 ThreeMind · 6.0全面复验 R51'
        if (work/'platform.json').exists():
            project=read(work/'platform.json')['project']
        else:
            found=[p for p in client.call('projects.list',{}) if p['name']==title]
            assert len(found)<=1
            project=(found[0] if found else client.request('POST','/api/v2/projects',body={'name':title}))['id']
            f.base.original(work/'platform.json',{'project':project})
        recorder=f.base.ResearchRecorder(work,project,client=client)
        if (work/'.research-records/identity.json').exists():
            recorder.resume_recording()
        else:
            recorder.register({'source_key':'kernel60:revalidation:foundation:20261113:v2',
                'title':'R51a：6.0繁殖完成；全面复验因性能门限暂停', 'classification':'development',
                'execution_status':'running','executor':'ai','kernels':list(f.KERNELS)+['threemind.continuous-memory/5.3'],
                'protocol':(f.HERE/'foundation-protocol-v2.zh.md').read_text('utf-8'),
                'protocol_version':f.sha(f.HERE/'foundation-protocol-v2.zh.md'),
                'required_roles':['protocol','report','note'],
                'metadata':{'engineering_only':True,'scientific_origins':0,'campaign_status':'paused-performance',
                    'local_protocol_frozen_before_measurement':True,'api_registration_after_engineering':True,
                    'authorization':'Approved 6.0 revalidation v2 and reproduction-first instruction',
                    'work':str(work),'scientific_batches_started':False}},request_id=ident('register'))
        recorder.synchronize(strict=True)
        client.request('POST','/api/v2/storage/resources',body={'resource_id':RESOURCE,
            'target_id':'managed-research-experiments','relative_path':'2026-11-13-kernel60-revalidation',
            'registered_work_path':str(work),'writer_mode':'cooperative','expected_revision':0},
            headers={'X-ThreeMind-Request-ID':str(ident('resource'))})
        client.request('POST','/api/v2/storage/record-evidence-grants',body={'project_id':project,'resource_id':RESOURCE},
            headers={'X-ThreeMind-Request-ID':str(ident('grant'))})
        impl=read(work/'foundation-v2/implementation.json')
        for rel,h in impl['source_files'].items():
            assert f.sha(f.ROOT/rel)==h, 'source changed after benchmark: '+rel
            recorder.save_original('source/'+rel,(f.ROOT/rel).read_bytes())
        for p in f.HERE.iterdir():
            if p.suffix in ('.py','.md') and p.name!='HANDOFF.md':
                recorder.save_original('tools/'+p.name,p.read_bytes())
        for name in ('historical-birth-witness.json','pytest-final.xml','pytest-final.log','pytest-delivery.xml'):
            recorder.save_original('engineering/'+name,(f.ROOT/'.work/native60-birth'/name).read_bytes())
        binary=Path(impl['native_path'])
        assert f.sha(binary)==impl['native_binary_sha256']
        recorder.save_original('binaries/_threemind_native.pyd',binary.read_bytes())
        exe=f.ROOT/'.work/native60-birth/release/threemind-runtime.exe'
        recorder.save_original('binaries/threemind-runtime.exe',exe.read_bytes())
        for lang in ('zh','en'):
            for kind,filename in (('protocol',f'foundation-protocol-v2.{lang}.md'),('report',f'report.{lang}.md')):
                recorder.text({'request_id':str(ident(kind+lang)),'identity':str(ident('doc-'+kind+lang)),
                    'expected_revision':0,'kind':kind,'title':'R51a '+kind+' '+lang,
                    'markdown':(f.HERE/filename).read_text('utf-8')})
        recorder.text({'request_id':str(ident('note')),'identity':str(ident('note-doc')),'expected_revision':0,
            'kind':'note','title':'R51a scope, correction and arithmetic review',
            'markdown':'Engineering only. v1 identifier alignment failed and is preserved; v2 checks id=channel. '
                '32 engineering trials, 64 states and 8 standalone continuations verified. '
                'The engineering batch is delivered; the full scientific campaign remains paused. '
                'Protocols were frozen locally before execution; API registration is retrospective. '
                'Review performed by the assistant, not an external reproducer.'})
        excluded={'.research-records','publication','readback'}
        files=sorted(p for p in work.rglob('*') if p.is_file() and not set(p.relative_to(work).parts)&excluded
            and p.name not in ('originals.zip','manifest.json') and not p.name.endswith('.lock'))
        assert not any(p.name.endswith('.partial') for p in files)
        manifest={'schema':'threemind.r51a-evidence/1','members':[{'path':p.relative_to(work).as_posix(),
            'bytes':p.stat().st_size,'sha256':f.sha(p)} for p in files]}
        recorder.save_original('manifest.json',json.dumps(manifest,ensure_ascii=False,sort_keys=True).encode())
        pack=work/'originals.zip'
        if not pack.exists():
            assert shutil.disk_usage(work).free>25*2**30+2*sum(r['bytes'] for r in manifest['members'])+64*2**20
            part=work/'originals.zip.partial'
            with zipfile.ZipFile(part,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                for p in files+[work/'manifest.json']:
                    z.write(p,p.relative_to(work).as_posix())
            os.link(part,pack);part.unlink()
        verify(pack,manifest)
        for name,role,fmt in (('originals.zip','original','application/zip'),('manifest.json','manifest','application/json'),
                              ('audit-v2.json','analysis','application/json')):
            p=work/name
            recorder.attach({'logical_id':'r51a:'+name,'role':role,'label':'R51a '+name,'format':fmt,
                'byte_count':p.stat().st_size,'sha256':f.sha(p),
                'locator':{'kind':'file','resource_id':RESOURCE,'member':name}},request_id=ident('attach-'+name))
        recorder.synchronize(strict=True)
        args={'path':{'project':project,'experiment':recorder.experiment},'query':{'hashes':True}}
        verified=client.call('records.verify',args)
        assert verified['coverage']=='verified' and not verified['problems']
        for lang in ('zh','en'):
            for kind,filename in (('protocol',f'foundation-protocol-v2.{lang}.md'),('report',f'report.{lang}.md')):
                doc=client.request('GET',f'/api/v2/projects/{project}/research-documents/{ident("doc-"+kind+lang)}')
                assert len(doc['spec']['blocks'])==1 and doc['spec']['blocks'][0]['markdown']==(f.HERE/filename).read_text('utf-8')
        evidence=next(e for e in verified['evidence'] if e['logical_id']=='r51a:originals.zip')
        dest=work/'readback/originals.zip';dest.parent.mkdir(exist_ok=True)
        if not dest.exists():
            receipt=client.call('records.download',{'path':{'project':project,'evidence':evidence['id']}},
                output=dest,maximum=pack.stat().st_size)
            recorder.save_original('publication/download-receipt.json',json.dumps(receipt).encode())
        assert f.sha(dest)==f.sha(pack)
        verify(dest,manifest)
        recorder.finalize(request_id=ident('finalize-engineering-only'));recorder.synchronize(strict=True)
        final=client.call('records.verify',args)
        assert final['coverage']=='verified' and not final['problems'] and recorder.status['pending']==0
        result={'project':project,'record':recorder.experiment,'coverage':'verified','pending':0,
            'engineering_status':final['execution_status'],'campaign_status':'paused-performance',
            'archive_bytes':pack.stat().st_size,'archive_sha256':f.sha(pack),'members':len(manifest['members'])}
        recorder.save_original('publication/completion.json',json.dumps(result,indent=2).encode())
        print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True)
    publish(p.parse_args().work.resolve())
