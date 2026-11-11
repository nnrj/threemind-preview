"""Authenticated r4 publication; no premature two-arm experiment finalization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from experiment import Study, RESOURCE, ROOT, HERE, read, sha, fixed_json
from analyze_four import ARMS


def archive(s, folder):
    path = s.work/(folder+'.zip')
    frozen = s.work/folder
    manifest = read(frozen/'manifest.json')
    if not path.exists():
        temporary = path.with_suffix('.partial')
        if temporary.exists():
            raise ValueError('inspect interrupted archive before retrying: '+str(temporary))
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for source in sorted(frozen.rglob('*')):
                if source.is_file():
                    z.write(source, source.relative_to(frozen).as_posix())
        temporary.rename(path)
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('source archive failed CRC')
        for name, expected in manifest.items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise ValueError('archived source differs: '+name)
    s.attach(path, 'implementation')


def metadata(s):
    """Comparable logical row representation, explicitly not physical DB pages."""
    path = {'project': s.project, 'experiment': s.recorder.experiment}
    totals = {arm: {'entries': 0, 'evidence': 0, 'json_bytes': 0} for arm in ARMS}
    totals['shared'] = {'entries': 0, 'evidence': 0, 'json_bytes': 0}
    def owner(row):
        key = str(row.get('original_key', ''))
        member = str(row.get('locator', {}).get('member', ''))
        for arm in ARMS:
            if (key.startswith('arms/'+arm+'/') or key in ('subject:'+arm, 'condition:'+arm)
                    or member.startswith(('arms/'+arm+'/', 'replays/'+arm+'/'))):
                return arm
        return 'shared'
    for kind in ('entries', 'evidence'):
        offset = 0
        while True:
            page = s.client.call('records.'+kind, {'path': path, 'query': {'offset': offset, 'limit': 200}})
            for row in page['rows']:
                target = totals[owner(row)]
                target[kind] += 1
                target['json_bytes'] += len(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                                       separators=(',', ':'), default=str).encode('utf-8'))
            if not page['more']:
                break
            offset += len(page['rows'])
    return dict(schema='threemind.e67-record-size/1', rows=totals,
        interpretation='UTF-8 canonical JSON representation of authorized entry and evidence rows at this snapshot. Not PostgreSQL disk allocation, compression, indexes, WAL, receipts or text revision bodies; do not add to file allocation and call it exact total disk use.',
        shared_database_pages='Not uniquely attributable to a model; explicitly unmeasured, not zero.',
        core_advanced=False)


def originals(s):
    complete = read(s.work/'computation-complete-r4.json')
    if complete['arms'] != list(ARMS):
        raise ValueError('four completed arms required')
    archive(s, 'source-reference-r4')
    for folder, role in (('analysis-r4', 'result'), ('replays', 'replay')):
        for path in sorted((s.work/folder).rglob('*')):
            if path.is_file() and '.partial' not in path.name:
                s.attach(path, role)
    s.attach(s.work/'computation-complete-r4.json', 'result')
    s.recorder.synchronize(strict=True)
    measurement = s.work/'analysis-r4/platform-record-size.json'
    if not measurement.exists():
        fixed_json(measurement, metadata(s))
    s.attach(measurement, 'result')
    s.recorder.synchronize(strict=True)


def reports(s):
    if read(s.work/'computation-complete-r4.json')['arms'] != list(ARMS):
        raise ValueError('do not finalize a partial experiment')
    if not (s.work/'replays/four-arm-export.json').is_file():
        raise ValueError('four video exports required')
    bodies = {lang: (HERE/f'report-four.{lang}.md').read_text(encoding='utf-8') for lang in ('zh', 'en')}
    if any('未发布草稿' in body or 'unpublished draft' in body for body in bodies.values()):
        raise ValueError('final report review incomplete')
    s.recorder.append('correction', 'delivery-scope-r4', dict(completed_arms=list(ARMS),
        protocol_revision=4, note='Four matched-course subjects completed. Earlier protocols and two-arm derived outputs remain preserved. Supplementary training, if any, is separately identified.'),
        request_id=s.rid('delivery-scope-r4'))
    for lang in ('zh', 'en'):
        s.recorder.text(dict(request_id=s.rid('four-report:'+lang), identity=s.rid('four-report-text:'+lang),
            expected_revision=0, kind='report', title=f'E67 三版内核、四组形色与规模对照 · {lang}', markdown=bodies[lang]))
    s.recorder.text(dict(request_id=s.rid('research-note-r4'), identity=s.rid('research-note-text-r4'),
        expected_revision=0, kind='note', title='E67 实验执行与四组续行记录',
        markdown=(HERE/'notes.zh.md').read_text(encoding='utf-8')))
    s.recorder.synchronize(strict=True)
    import httpx
    s.client.client.timeout = httpx.Timeout(900)
    verification = s.client.call('records.verify', {'path': {'project': s.project, 'experiment': s.recorder.experiment},
                                                      'query': {'hashes': True}})
    if verification['problems']:
        raise ValueError(json.dumps(verification['problems'], ensure_ascii=False))
    fixed_json(s.work/'delivery-verification-r4.json', verification)
    s.recorder.finalize('completed', request_id=s.rid('finalize-r4'))
    s.recorder.synchronize(strict=True)
    print(json.dumps(dict(experiment=s.recorder.experiment, coverage=verification['coverage'],
                          evidence=len(verification['evidence']), referenced_bytes=verification['referenced_bytes'])), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('originals', 'reports'))
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    s = Study(args.work)
    try:
        with s.storage.writer(RESOURCE):
            (originals if args.mode == 'originals' else reports)(s)
    finally:
        s.close()


if __name__ == '__main__':
    main()
