"""Publish this reviewed local study; no loading or advancement of subjects."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import zipfile
import psutil
import experiment as e
from publish_mechanism import verify_archive


def archive(work,r):
    excluded={'.research-records','publication','readback'}
    files=sorted(p for p in work.rglob('*') if p.is_file()
        and not set(p.relative_to(work).parts)&excluded
        and p.name not in ('originals-v1.zip','originals-v1.zip.partial','originals-manifest-v1.json')
        and not p.name.endswith('.lock')
        and not (p.parent==work and p.name.startswith('api-') and p.suffix=='.log'))
    if any(p.name.endswith('.partial') for p in files):raise RuntimeError('unfinished original')
    manifest=dict(schema='threemind.context-original-manifest/1',
        excluded_runtime_logs='live API access logs; preserved at work root, not scientific inputs',
        members=[dict(path=p.relative_to(work).as_posix(),bytes=p.stat().st_size,sha256=e.sha(p)) for p in files])
    r.save_original('originals-manifest-v1.json',json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2).encode())
    pack=work/'originals-v1.zip'
    if not pack.exists():
        if shutil.disk_usage(work).free<25*2**30+2.02*sum(x['bytes'] for x in manifest['members'])+64*2**20:
            raise RuntimeError('original/archive/readback allowance')
        part=work/'originals-v1.zip.partial'
        with zipfile.ZipFile(part,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in files+[work/'originals-manifest-v1.json']:z.write(p,p.relative_to(work).as_posix())
        os.link(part,pack);part.unlink()
    verify_archive(pack,manifest)
    return manifest,pack


def publish(work,review_path):
    review=e.load(review_path)
    assert review['reviewer']=='assistant' and review['approved_for_publication'] is True
    assert Path(review['work']).resolve()==work
    for rel,h in review['reviewed_files'].items():assert e.sha(e.ROOT/rel)==h,rel
    assert e.sha(work/'analysis-v1.json')==review['analysis_sha256']
    required={'analysis-v1.json','integrity-audit-v1.json','score-audit-v1.json','summary-v1.json',
              'port-diagnostic-v1.json.gz','storage-inventory-v1.json','postprocessing/automatic-analysis.json'}
    assert required<=set(review['reviewed_originals'])
    for rel,h in review['reviewed_originals'].items():
        p=(work/rel).resolve();p.relative_to(work)
        assert e.sha(p)==h,rel
    if (work/'publication/completion.json').exists():
        print(json.dumps(e.load(work/'publication/completion.json')));return
    with e.base.worker_lock(work):
        e.frozen(work);e.base.resource_check(work)
        host=e.load(work/'host.json')
        if psutil.pid_exists(host['pid']) and abs(psutil.Process(host['pid']).create_time()-host['created_at'])<.01:
            raise RuntimeError('scientific host still alive')
        assert not any((work/p).exists() for p in ('in-flight.json','STOP'))
        assert e.load(work/'status.json')==dict(state='awaiting-analysis',origins_completed=e.N)
        with e.connection() as c:
            platform=e.load(work/'platform.json')
            registry=e.load(e.ROOT/'data/storage-control/registry.json')
            resource=registry['resources'][e.RESOURCE]
            assert Path(resource['registered_work_path']).resolve()==work
            loc=resource['locator'];assert loc['target_id']=='managed-research-experiments'
            target=registry['targets'][loc['target_id']]['versions'][str(loc['config_revision'])]
            assert target['kind']=='filesystem'
            assert (Path(target['configuration']['path'])/loc['relative_path']).resolve()==work
            r=e.base.ResearchRecorder(work,platform['project_id'],client=c);r.resume_recording()
            r.save_original('postprocessing/review.json',review_path.read_bytes())
            for rel in review['reviewed_files']:r.save_original('postprocessing/repo/'+rel,(e.ROOT/rel).read_bytes())
            manifest,pack=archive(work,r)
            for rel,role,fmt in [('originals-v1.zip','original','application/zip'),
                ('originals-manifest-v1.json','manifest','application/json'),('analysis-v1.json','analysis','application/json')]:
                p=work/rel
                r.attach(dict(logical_id='context-v1:'+rel,role=role,label='Context revision '+rel,format=fmt,
                    byte_count=p.stat().st_size,sha256=e.sha(p),
                    locator=dict(kind='file',resource_id=e.RESOURCE,member=rel)),request_id=e.ident('publication-attach:'+rel))
            for lang in ('zh','en'):
                r.text(dict(request_id=str(e.ident('report-'+lang)),identity=str(e.ident('report-doc-'+lang)),
                    expected_revision=0,kind='report',title='Context judgments and active observation '+lang,
                    markdown=(e.ROOT/review['reports'][lang]).read_text(encoding='utf-8')))
            r.text(dict(request_id=str(e.ident('publication-note')),identity=str(e.ident('publication-note-doc')),
                expected_revision=0,kind='note',title='Context v1 review and continuity',markdown=review['review_note']))
            r.synchronize(strict=True)
            args=dict(path=dict(project=platform['project_id'],experiment=r.experiment),query=dict(hashes=True))
            verified=c.call('records.verify',args)
            assert verified['coverage']=='verified' and not verified['problems']
            checks=[]
            for kind in ('protocol','report'):
                for lang in ('zh','en'):
                    doc=str(e.ident(kind+'-doc-'+lang))
                    body=c.request('GET',f"/api/v2/projects/{platform['project_id']}/research-documents/{doc}")
                    p=e.HERE/f'protocol.{lang}.md' if kind=='protocol' else e.ROOT/review['reports'][lang]
                    assert body['spec']['blocks']==[dict(markdown=p.read_text(encoding='utf-8'))] or (
                        len(body['spec']['blocks'])==1 and body['spec']['blocks'][0]['markdown']==p.read_text(encoding='utf-8'))
                    checks.append(dict(kind=kind,language=lang,id=doc,revision=body['revision'],text_equal=True))
            r.save_original('publication/document-readback.json',json.dumps(checks,sort_keys=True).encode())
            evidence=next(x for x in verified['evidence'] if x['logical_id']=='context-v1:originals-v1.zip')
            dest=work/'readback/originals-v1.zip';dest.parent.mkdir(exist_ok=True)
            if not dest.exists():
                receipt=c.call('records.download',dict(path=dict(project=platform['project_id'],evidence=evidence['id'])),
                               output=dest,maximum=pack.stat().st_size)
                r.save_original('publication/download-receipt.json',json.dumps(receipt,sort_keys=True).encode())
            assert e.sha(dest)==e.sha(pack);verify_archive(dest,manifest)
            e.base.resource_check(work)
            r.save_original('publication/verification-before-finalize.json',json.dumps(verified,sort_keys=True).encode())
            r.finalize(request_id=e.ident('publication-finalize'));r.synchronize(strict=True)
            final=c.call('records.verify',args)
            assert final['execution_status']=='completed' and final['coverage']=='verified' and not final['problems'] and r.status['pending']==0
            r.save_original('publication/final-verification.json',json.dumps(final,sort_keys=True).encode())
            out=dict(record=r.experiment,project=platform['project_id'],pending=0,coverage='verified',execution_status='completed',
                archive_bytes=pack.stat().st_size,archive_sha256=e.sha(pack),members=len(manifest['members']),documents_read_back=4,
                review='assistant review and separately recomputed arithmetic; not external or human replication')
            r.save_original('publication/completion.json',json.dumps(out,sort_keys=True,indent=2).encode())
            print(json.dumps(out))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=e.WORK);p.add_argument('--review',type=Path,required=True)
    a=p.parse_args();publish(a.work.resolve(),a.review.resolve())
