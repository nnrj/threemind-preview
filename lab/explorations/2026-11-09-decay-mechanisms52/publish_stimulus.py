"""R46b publication through the existing API after complete local review."""
import argparse
import json
from pathlib import Path
import stimulus_study as study
from publish_assay import archive,verify_archive

e=study.a


def publish(work,review_path):
    review=e.load(review_path)
    assert review['reviewer']=='assistant' and review['approved_for_publication'] is True
    assert Path(review['work']).resolve()==work
    for rel,h in review['reviewed_files'].items():assert e.sha(e.ROOT/rel)==h,rel
    assert {'analysis-v1.json','independent-audit-v1.json','storage-inventory-v1.json'}<=set(review['reviewed_originals'])
    for rel,h in review['reviewed_originals'].items():
        p=(work/rel).resolve();p.relative_to(work);assert e.sha(p)==h,rel
    if (work/'publication/completion.json').exists():
        print(json.dumps(e.load(work/'publication/completion.json')));return
    with e.base.worker_lock(work):
        study.frozen(work);e.base.resource_check(work)
        assert study.operational.dead(e.load(work/'host.json'))
        assert not any((work/n).exists() for n in ('STOP','in-flight.json'))
        assert e.load(work/'status.json')==dict(state='awaiting-analysis',sequences_completed=960)
        assert e.load(work/'independent-audit-v1.json')['passed']
        with e.connection() as client:
            platform=e.load(work/'platform.json');registry=e.load(e.ROOT/'data/storage-control/registry.json')
            resource=registry['resources'][study.RESOURCE]
            assert Path(resource['registered_work_path']).resolve()==work
            loc=resource['locator'];assert loc['target_id']=='managed-research-experiments'
            target=registry['targets'][loc['target_id']]['versions'][str(loc['config_revision'])]
            assert target['kind']=='filesystem' and (Path(target['configuration']['path'])/loc['relative_path']).resolve()==work
            recorder=e.base.ResearchRecorder(work,platform['project_id'],client=client);recorder.resume_recording()
            recorder.save_original('postprocessing/review.json',review_path.read_bytes())
            for rel in review['reviewed_files']:recorder.save_original('postprocessing/repo/'+rel,(e.ROOT/rel).read_bytes())
            manifest,pack=archive(work,recorder)
            for rel,role,fmt in (('originals-v1.zip','original','application/zip'),('originals-manifest-v1.json','manifest','application/json'),('analysis-v1.json','analysis','application/json')):
                p=work/rel
                recorder.attach(dict(logical_id='decay52-stimulus-v1:'+rel,role=role,label='Strong stimulus and connection novelty '+rel,
                    format=fmt,byte_count=p.stat().st_size,sha256=e.sha(p),
                    locator=dict(kind='file',resource_id=study.RESOURCE,member=rel)),request_id=study.ident('publication-attach:'+rel))
            for lang in ('zh','en'):
                recorder.text(dict(request_id=str(study.ident('report-'+lang)),identity=str(study.ident('report-doc-'+lang)),
                    expected_revision=0,kind='report',title='R46b strong stimulus and connection novelty '+lang,
                    markdown=(e.ROOT/review['reports'][lang]).read_text('utf-8')))
            recorder.text(dict(request_id=str(study.ident('publication-note')),identity=str(study.ident('publication-note-doc')),
                expected_revision=0,kind='note',title='R46b complete-state and arithmetic review',markdown=review['review_note']))
            recorder.synchronize(strict=True)
            args=dict(path=dict(project=platform['project_id'],experiment=recorder.experiment),query=dict(hashes=True))
            verified=client.call('records.verify',args)
            assert verified['coverage']=='verified' and not verified['problems']
            checks=[]
            for kind in ('protocol','report'):
                for lang in ('zh','en'):
                    doc=str(study.ident(kind+'-doc-'+lang))
                    body=client.request('GET',f"/api/v2/projects/{platform['project_id']}/research-documents/{doc}")
                    path=e.HERE/f'stimulus_protocol.{lang}.md' if kind=='protocol' else e.ROOT/review['reports'][lang]
                    assert len(body['spec']['blocks'])==1 and body['spec']['blocks'][0]['markdown']==path.read_text('utf-8')
                    checks.append(dict(kind=kind,language=lang,id=doc,revision=body['revision'],text_equal=True))
            recorder.save_original('publication/document-readback.json',json.dumps(checks,sort_keys=True).encode())
            evidence=next(x for x in verified['evidence'] if x['logical_id']=='decay52-stimulus-v1:originals-v1.zip')
            dest=work/'readback/originals-v1.zip';dest.parent.mkdir(exist_ok=True)
            if not dest.exists():
                receipt=client.call('records.download',dict(path=dict(project=platform['project_id'],evidence=evidence['id'])),output=dest,maximum=pack.stat().st_size)
                recorder.save_original('publication/download-receipt.json',json.dumps(receipt,sort_keys=True).encode())
            assert e.sha(dest)==e.sha(pack);verify_archive(dest,manifest);e.base.resource_check(work)
            recorder.save_original('publication/verification-before-finalize.json',json.dumps(verified,sort_keys=True).encode())
            recorder.finalize(request_id=study.ident('publication-finalize'));recorder.synchronize(strict=True)
            final=client.call('records.verify',args)
            assert final['execution_status']=='completed' and final['coverage']=='verified' and not final['problems'] and recorder.status['pending']==0
            recorder.save_original('publication/final-verification.json',json.dumps(final,sort_keys=True).encode())
            out=dict(record=recorder.experiment,project=platform['project_id'],pending=0,coverage='verified',execution_status='completed',
                archive_bytes=pack.stat().st_size,archive_sha256=e.sha(pack),members=len(manifest['members']),documents_read_back=4,
                review='Executing assistant and separate original-JSON arithmetic implementation; not external replication.')
            recorder.save_original('publication/completion.json',json.dumps(out,sort_keys=True,indent=2).encode())
            print(json.dumps(out))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=study.WORK);p.add_argument('--review',type=Path,required=True)
    args=p.parse_args();publish(args.work.resolve(),args.review.resolve())
