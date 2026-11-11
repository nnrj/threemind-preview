"""Publish SAT Core exclusions only, with full local API readback and immutable originals."""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
import psutil
import httpx
from urllib.parse import urlsplit
import study as d
sys.path.insert(0,str(d.ROOT/'lab/explorations/2026-10-16-mechanism-discovery'))
from publish_mechanism import archive,verify_archive

def local_connection(work):
    # This is local record keeping and loopback readback, not external publication.
    d.base.load_env()
    db=urlsplit(os.environ.get("THREEMIND_DATABASE_URL",""))
    assert db.hostname in ("127.0.0.1","localhost","::1") and db.port==5433
    registry=d.load(d.ROOT/"data/storage-control/registry.json")
    resource=registry["resources"]["sat-core-exclusion-20261101-v1"]
    assert Path(resource["registered_work_path"]).resolve()==work
    locator=resource["locator"]
    assert locator["target_id"]=="managed-research-experiments"
    target=registry["targets"][locator["target_id"]]["versions"][str(locator["config_revision"])]
    assert target["kind"]=="filesystem"
    assert (Path(target["configuration"]["path"])/locator["relative_path"]).resolve()==work
    return d.base.OperationsClient(url="http://127.0.0.1:8877",
        username=os.environ.get("THREEMIND_API_USERNAME"),password=os.environ.get("THREEMIND_API_PASSWORD"),
        token=os.environ.get("THREEMIND_API_TOKEN"),transport=httpx.HTTPTransport(trust_env=False),
        reuse_session=False,require_auth=True,source="ai")

def publish(work,review_path):
    review=d.load(review_path)
    assert review['reviewer']=='assistant' and review['approved_for_publication'] is True
    assert Path(review['work']).resolve()==work
    for rel,h in review['reviewed_files'].items():
        assert d.sha(d.ROOT/rel)==h,rel
    assert d.sha(work/'analysis-v1.json')==review['analysis_sha256']
    for rel,h in review.get('reviewed_originals',{}).items():
        assert d.sha(work/rel)==h,rel
    if (work/'publication/completion.json').exists():
        print(json.dumps(d.load(work/'publication/completion.json')));return
    with d.base.worker_lock(work):
        d.frozen(work);d.base.resource_check(work)
        host=d.load(work/'host.json')
        if psutil.pid_exists(host['pid']) and abs(psutil.Process(host['pid']).create_time()-host['created_at'])<.01:
            raise RuntimeError('scientific host is alive')
        assert not any((work/p).exists() for p in ('in-flight.json','apparatus-in-flight.json','STOP'))
        assert d.load(work/'status.json')==dict(state='awaiting-analysis',origins_completed=8)
        with local_connection(work) as client:
            r=d.recorder(work,client);platform=d.load(work/'platform.json')
            r.save_original('postprocessing/review.json',review_path.read_bytes())
            for rel in review['reviewed_files']:
                r.save_original('postprocessing/repo/'+rel,(d.ROOT/rel).read_bytes())
            manifest,pack=archive(work,r)
            for rel,role,fmt in [('originals-v1.zip','original','application/zip'),
                                 ('originals-manifest-v1.json','manifest','application/json'),
                                 ('analysis-v1.json','analysis','application/json')]:
                p=work/rel
                r.attach(dict(logical_id='sat-core-v3:'+rel,role=role,label='3-SAT '+rel,format=fmt,
                              byte_count=p.stat().st_size,sha256=d.sha(p),
                              locator=dict(kind='file',resource_id=platform['resource_id'],member=rel)),
                         request_id=d.ident('publication-attach:'+rel))
            for lang in ('zh','en'):
                rel=review['reports'][lang]
                r.text(dict(request_id=str(d.ident('report-'+lang)),identity=str(d.ident('report-doc-'+lang)),
                            expected_revision=0,kind='report',title='SAT Core exclusion v3 report '+lang,
                            markdown=(d.ROOT/rel).read_text(encoding='utf-8-sig')))
            r.text(dict(request_id=str(d.ident('publication-note')),identity=str(d.ident('publication-note-doc')),
                        expected_revision=0,kind='note',title='SAT Core exclusion v3 review and continuity',
                        markdown=review['review_note']))
            r.synchronize(strict=True)
            args=dict(path=dict(project=platform['project_id'],experiment=r.experiment),query=dict(hashes=True))
            verified=client.call('records.verify',args)
            assert verified['coverage']=='verified' and not verified['problems']
            document_checks=[]
            for kind in ('protocol','report'):
                for lang in ('zh','en'):
                    identity=str(d.ident(kind+'-doc-'+lang))
                    content=client.request('GET',f"/api/v2/projects/{platform['project_id']}/research-documents/{identity}")
                    blocks=content['spec']['blocks']
                    rel=(d.HERE/f'protocol.{lang}.md') if kind=='protocol' else (d.ROOT/review['reports'][lang])
                    assert len(blocks)==1 and blocks[0]['markdown']==rel.read_text(encoding='utf-8-sig')
                    document_checks.append(dict(kind=kind,language=lang,id=identity,revision=content['revision'],text_equal=True))
            r.save_original('publication/document-readback.json',json.dumps(document_checks,sort_keys=True).encode())
            evidence=next(e for e in verified['evidence'] if e['logical_id']=='sat-core-v3:originals-v1.zip')
            dest=work/'readback/originals-v1.zip';dest.parent.mkdir(exist_ok=True)
            if not dest.exists():
                receipt=client.call('records.download',dict(path=dict(project=platform['project_id'],evidence=evidence['id'])),
                                    output=dest,maximum=pack.stat().st_size)
                r.save_original('publication/download-receipt.json',json.dumps(receipt,sort_keys=True).encode())
            assert d.sha(dest)==d.sha(pack);verify_archive(dest,manifest)
            d.base.resource_check(work)
            r.save_original('publication/verification-before-finalize.json',json.dumps(verified,sort_keys=True).encode())
            r.finalize(request_id=d.ident('publication-finalize'));r.synchronize(strict=True)
            final=client.call('records.verify',args)
            assert final['execution_status']=='completed' and final['coverage']=='verified' and not final['problems'] and r.status['pending']==0
            r.save_original('publication/final-verification.json',json.dumps(final,sort_keys=True).encode())
            summary=dict(record=r.experiment,project=platform['project_id'],pending=0,coverage=final['coverage'],
                         execution_status=final['execution_status'],archive_bytes=pack.stat().st_size,
                         archive_sha256=d.sha(pack),members=len(manifest['members']),documents_read_back=4,
                         review='assistant; arithmetic independently recomputed; not human or external replication')
            r.save_original('publication/completion.json',json.dumps(summary,sort_keys=True,indent=2).encode())
            print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=d.WORK);p.add_argument('--review',type=Path,required=True)
    a=p.parse_args();publish(a.work.resolve(),a.review.resolve())
