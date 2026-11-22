"""Publish this study to the existing local API and verify a full archive readback."""
import json
import shutil
from pathlib import Path
from uuid import uuid5
import zipfile
import apparatus as a
import study
from threemind_lab.research_recorder import ResearchRecorder

TAG='AS63-03'

def resource(client):
    overview=client.request('GET','/api/v2/storage')
    target=next(t for t in overview['targets'] if t['kind']=='filesystem'
        and Path(t['configuration']['path']).resolve()==a.WORK.parent.resolve())
    identity='as63-03-20261118'
    existing=next((r for r in overview['resources'] if r['id']==identity),None)
    if existing is None:
        existing=client.request('POST','/api/v2/storage/resources',body={'resource_id':identity,
            'target_id':target['id'],'relative_path':a.WORK.name,'registered_work_path':str(a.WORK),
            'writer_mode':'cooperative','expected_revision':0})
    assert existing['locator']['target_id']==target['id'] and existing['locator']['relative_path']==a.WORK.name
    client.request('POST','/api/v2/storage/record-evidence-grants',body={'project_id':a.PROJECT,'resource_id':identity})
    return identity

def verify(pack,manifest):
    with zipfile.ZipFile(pack) as archive:
        names=archive.namelist()
        assert len(names)==len(set(names))
        assert set(names)=={m['path'] for m in manifest['members']}|{'manifest.json'}
        assert json.loads(archive.read('manifest.json'))==manifest
        for row in manifest['members']:
            import hashlib
            h=hashlib.sha256();size=0
            with archive.open(row['path']) as stream:
                for block in iter(lambda:stream.read(2**20),b''): h.update(block);size+=len(block)
            assert size==row['bytes'] and h.hexdigest()==row['sha256'],row['path']

def main():
    completion=a.WORK/'publication/completion.json'
    if completion.exists(): print(completion.read_text('utf8'));return
    assert a.read(a.WORK/'science-complete.json')['stages']==312
    assert a.read(a.WORK/'analysis-v1/audit.json')['passed']
    assert a.read(a.WORK/'analysis-v1/independent-check.json')['passed']
    study.frozen_check()
    ident=lambda s:uuid5(a.NS,s)
    with study.client_context() as client:
        rid=resource(client)
        rec=ResearchRecorder(a.WORK,a.PROJECT,client=client)
        rec.resume_recording()
        for p in a.HERE.iterdir():
            if p.suffix in ('.py','.md','.json','.csv') and p.name not in ('delivery.json',):
                rec.save_original('delivery-tools/'+p.name,p.read_bytes())
        for p in (a.HERE/'figures').iterdir():
            if p.is_file():rec.save_original('delivery-figures/'+p.name,p.read_bytes())
        for lang in ('zh','en'):
            rec.text({'identity':str(ident('report-document-'+lang)),'request_id':str(ident('report-'+lang)),
                'expected_revision':0,'kind':'report','title':TAG+' report '+lang,
                'markdown':(a.HERE/f'report.{lang}.md').read_text('utf8')})
        rec.text({'identity':str(ident('note-document')),'request_id':str(ident('note')),'expected_revision':0,
            'kind':'note','title':TAG+' provenance and scope',
            'markdown':'Author-authorized matched comparison of /1, default 6.3 and saved S101/bypass. '
            'Energy-model confounding and an inactive supplier timer were found during apparatus checks; '
            'all original failed checks remain in the archive. The formal version-2 protocol disables energy '
            'simulation for every research subject. Genuine kernel and birth identities remain intact. '
            'Historical input records and historical-ID motor bindings are provenance-linked. '
            'No production Core/default changes, old report overwrites, manuscript edits or unrelated experiments. '
            'Automated verification and analysis are by the same assistant, not external replication.'})
        excluded={'.research-records','publication','readback','__pycache__'}
        files=sorted(p for p in a.WORK.rglob('*') if p.is_file()
            and not set(p.relative_to(a.WORK).parts)&excluded
            and p.name not in ('originals.zip','manifest.json') and not p.name.endswith('.lock'))
        assert not any(p.name.endswith('.partial') for p in files)
        total=sum(p.stat().st_size for p in files)
        assert total<2**30
        assert shutil.disk_usage(a.WORK).free>25*2**30+total*2+64*2**20
        manifest={'schema':'ring-mechanism63/original-manifest/1','tag':TAG,
            'members':[{'path':p.relative_to(a.WORK).as_posix(),'bytes':p.stat().st_size,'sha256':a.sha(p)} for p in files]}
        a.save(a.WORK/'manifest.json',manifest)
        pack=a.WORK/'originals.zip'
        print(f'Packaging {len(files)} originals, {total} bytes',flush=True)
        if not pack.exists():
            part=a.WORK/'originals.zip.partial'
            with zipfile.ZipFile(part,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
                for p in files+[a.WORK/'manifest.json']:archive.write(p,p.relative_to(a.WORK).as_posix())
            verify(part,manifest);part.rename(pack)
        verify(pack,manifest)
        for name,role,fmt in (('originals.zip','original','application/zip'),('manifest.json','manifest','application/json'),
                             ('analysis-v1/analysis.json','analysis','application/json')):
            p=a.WORK/name
            rec.attach({'logical_id':TAG+':'+name,'role':role,'label':TAG+' '+name,'format':fmt,
                'byte_count':p.stat().st_size,'sha256':a.sha(p),
                'locator':{'kind':'file','resource_id':rid,'member':name}},request_id=ident('attach-'+name))
        for p in sorted((a.WORK/'delivery-figures').glob('*.png')):
            name=p.relative_to(a.WORK).as_posix()
            rec.attach({'logical_id':TAG+':'+name,'role':'figure','label':TAG+' '+p.name,'format':'image/png',
                'byte_count':p.stat().st_size,'sha256':a.sha(p),
                'locator':{'kind':'file','resource_id':rid,'member':name}},request_id=ident('attach-'+name))
        rec.synchronize(strict=True)
        args={'path':{'project':a.PROJECT,'experiment':rec.experiment},'query':{'hashes':True}}
        checked=client.call('records.verify',args)
        assert checked['coverage']=='verified' and not checked['problems']
        row=next(x for x in checked['evidence'] if x['logical_id']==TAG+':originals.zip')
        readback=a.WORK/'readback/originals.zip';readback.parent.mkdir(exist_ok=True)
        print('Downloading full archive through API',flush=True)
        if not readback.exists():client.call('records.download',{'path':{'project':a.PROJECT,'evidence':row['id']}},
                                           output=readback,maximum=pack.stat().st_size)
        assert a.sha(readback)==a.sha(pack);verify(readback,manifest)
        for lang in ('zh','en'):
            doc=client.request('GET',f'/api/v2/projects/{a.PROJECT}/research-documents/{ident("report-document-"+lang)}')
            assert doc['spec']['blocks'][0]['markdown']==(a.HERE/f'report.{lang}.md').read_text('utf8')
        rec.finalize(request_id=ident('finalize'));rec.synchronize(strict=True)
        checked=client.call('records.verify',args)
        assert checked['coverage']=='verified' and not checked['problems'] and rec.status['pending']==0
        result={'project':a.PROJECT,'record':rec.experiment,'resource_id':rid,'coverage':'verified','pending':0,
                'members':len(files),'raw_bytes':total,'archive_bytes':pack.stat().st_size,'archive_sha256':a.sha(pack),
                'complete_api_readback':True,'bilingual_report_readback':True}
        a.save(completion,result);a.save(a.HERE/'delivery.json',result)
        print(json.dumps(result),flush=True)

if __name__=='__main__':main()
