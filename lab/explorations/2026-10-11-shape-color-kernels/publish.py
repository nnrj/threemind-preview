"""Attach observational analysis, full replay and reports to the E67 record."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

from experiment import Study, RESOURCE, ROOT, HERE, read, sha, fixed_json


def originals(s):
    if not (s.work/'computation-complete.json').exists():raise ValueError('formal computation is incomplete')
    for ref in ('source-reference','source-reference-r2','source-reference-r3'):
        path=s.work/(ref+'.zip')
        if not path.exists():
            with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                for source in sorted((s.work/ref).rglob('*')):
                    if source.is_file():z.write(source,source.relative_to(s.work/ref).as_posix())
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:raise ValueError('source archive failed CRC verification')
            manifest=read(s.work/ref/'manifest.json')
            import hashlib
            for name,digest in manifest.items():
                if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('frozen source mismatch')
        s.attach(path,'implementation')
    # The birth freezes intentionally exclude later observational exporters.
    # Preserve the actual completed analysis/rendering implementation as well.
    tooling=s.work/'postprocessing-source.zip'
    names=('analyze.py','figures.py','replay.py','pipeline.py','performance_review.py','publish.py')
    manifest={name:sha(HERE/name) for name in names}
    if not tooling.exists():
        with zipfile.ZipFile(tooling,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in names:z.write(HERE/name,name)
            z.writestr('manifest.json',json.dumps(manifest,sort_keys=True))
    with zipfile.ZipFile(tooling) as z:
        if z.testzip() is not None:raise ValueError('postprocessing archive failed CRC')
        if json.loads(z.read('manifest.json'))!=manifest:raise ValueError('preserve the existing postprocessing edition')
        import hashlib
        if any(hashlib.sha256(z.read(name)).hexdigest()!=value for name,value in manifest.items()):
            raise ValueError('postprocessing source differs')
    s.attach(tooling,'implementation')
    evidence=s.work/'engineering-evidence';evidence.mkdir(exist_ok=True)
    src=ROOT/'.work/e67-preflight-r5/result.json';dest=evidence/'four-arm-preflight.json'
    if not dest.exists():shutil.copy2(src,dest)
    if sha(dest)!=sha(src):raise ValueError('preflight copy differs')
    s.attach(dest,'verification')
    # The deferred arm remains research evidence, including its partial course.
    for path in sorted((s.work/'arms/4-adaptive').rglob('*')):
        if path.is_file() and path.name!='resume.json' and '.partial' not in path.name:
            s.attach(path,'checkpoint' if any(x in path.parts for x in ('birth','checkpoints')) else 'process',
                     'arms/4-adaptive/initial-teaching')
    for folder,role in (('analysis','result'),('replays','replay')):
        for path in sorted((s.work/folder).rglob('*')):
            if path.is_file() and '.partial' not in path.name:s.attach(path,role)
    s.attach(s.work/'computation-complete.json','result')
    s.recorder.synchronize(strict=True)


def reports(s):
    complete=read(s.work/'computation-complete.json')
    if complete['arms']!=['2','3.1'] or complete['deferred_arms']!=['4-adaptive','4-legacy']:
        raise ValueError('final publication scope differs from the approved two-arm completion')
    report_bodies={lang:(HERE/f'report.{lang}.md').read_text(encoding='utf-8') for lang in ('zh','en')}
    if any('未发布草稿' in body or 'unpublished draft' in body for body in report_bodies.values()):
        raise ValueError('final report review is incomplete')
    s.recorder.append('correction','delivery-scope',dict(
        completed_arms=complete['arms'],deferred_arms=complete['deferred_arms'],
        note='Completion refers to protocol revision3. The original four-arm registration remains historical; neither /4 arm has a final shape/color score.',
        deferred_state={'4-adaptive':'Complete lesson48 checkpoint and65 recorded lesson clips retained; no continuation.',
                        '4-legacy':'Not formally born.'}),request_id=s.rid('delivery-scope'))
    for lang in ('zh','en'):
        s.recorder.text(dict(request_id=s.rid('final-report:'+lang),identity=s.rid('final-report-text:'+lang),
            expected_revision=0,kind='report',title=f'E67 /2 与 /3.1 形色教学与性能报告 · {lang}',markdown=report_bodies[lang]))
        diagnostic=HERE/f'performance-review.{lang}.md'
        s.recorder.text(dict(request_id=s.rid('performance-note:'+lang),identity=s.rid('performance-note-text:'+lang),
            expected_revision=0,kind='note',title=f'E67 /4 只读性能诊断 · {lang}',markdown=diagnostic.read_text(encoding='utf-8')))
    note=HERE/'notes.zh.md'
    s.recorder.text(dict(request_id=s.rid('research-note'),identity=s.rid('research-note-text'),expected_revision=0,
        kind='note',title='E67 实验执行与边界记录',markdown=note.read_text(encoding='utf-8')))
    s.recorder.synchronize(strict=True)
    import httpx
    # Full original-byte verification is a bounded read, not a 30-second UI query.
    s.client.client.timeout=httpx.Timeout(900)
    print('Verifying all registered evidence bytes through the authenticated API...',flush=True)
    verification=s.client.call('records.verify',{'path':{'project':s.project,'experiment':s.recorder.experiment},
                                                'query':{'hashes':True}})
    if verification['problems']:raise ValueError(json.dumps(verification['problems'],ensure_ascii=False))
    fixed_json(s.work/'delivery-verification.json',verification)
    s.recorder.finalize('completed',request_id=s.rid('finalize'))
    s.recorder.synchronize(strict=True)
    print(json.dumps({'experiment_id':s.recorder.experiment,'coverage':verification['coverage'],
                      'evidence':len(verification['evidence']),'referenced_bytes':verification['referenced_bytes']}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('originals','reports'))
    p.add_argument('--work',type=Path,required=True);args=p.parse_args();s=Study(args.work)
    try:
        with s.storage.writer(RESOURCE):
            if args.mode=='originals':originals(s)
            else:reports(s)
    finally:s.close()


if __name__=='__main__':main()
