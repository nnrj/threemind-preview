"""Publish only RT63-01 to the existing local service; verify full archive bytes."""
import hashlib
import json
from pathlib import Path
import zipfile
from uuid import uuid5
import study as s
from threemind_lab.research_recorder import ResearchRecorder


def verify(pack, manifest):
    with zipfile.ZipFile(pack) as z:
        assert len(z.namelist()) == len(set(z.namelist()))
        assert set(z.namelist()) == {m['path'] for m in manifest['members']} | {'manifest.json'}
        assert json.loads(z.read('manifest.json')) == manifest
        for member in manifest['members']:
            data = z.read(member['path'])
            assert len(data) == member['bytes'] and hashlib.sha256(data).hexdigest() == member['sha256']


def main():
    completion = s.WORK / 'publication/completion.json'
    if completion.exists():
        print(completion.read_text('utf8')); return
    s.frozen_check()
    assert s.read(s.WORK / 'science-complete.json')['stages'] == 144
    assert s.read(s.WORK / 'analysis-v1/analysis.json')['audit']['passed']
    ident = lambda name: uuid5(s.NS, name)
    with s.client_context() as client:
        overview = client.request('GET', '/api/v2/storage')
        target = next(t for t in overview['targets'] if t['kind'] == 'filesystem'
                      and Path(t['configuration']['path']).resolve() == s.WORK.parent.resolve())
        rid = 'rt63-01-20261118'
        existing = next((r for r in overview['resources'] if r['id'] == rid), None)
        if existing is None:
            existing = client.request('POST', '/api/v2/storage/resources', body={'resource_id': rid,
                'target_id': target['id'], 'relative_path': s.WORK.name, 'registered_work_path': str(s.WORK),
                'writer_mode': 'cooperative', 'expected_revision': 0})
        assert existing['locator']['target_id'] == target['id']
        assert existing['locator']['relative_path'] == s.WORK.name
        client.request('POST', '/api/v2/storage/record-evidence-grants', body={'project_id': s.PROJECT, 'resource_id': rid})
        rec = ResearchRecorder(s.WORK, s.PROJECT, client=client)
        rec.resume_recording()
        rec.append('result', 'rt63-01-complete', {'completion': s.read(s.WORK / 'science-complete.json'),
                   'summary': s.read(s.HERE / 'summary.json')}, request_id=ident('result-complete'))
        for p in s.HERE.iterdir():
            if p.suffix in ('.py', '.md', '.json', '.csv') and p.name != 'delivery.json':
                rec.save_original('delivery-tools/' + p.name, p.read_bytes())
        for p in (s.HERE / 'figures').iterdir():
            if p.is_file():
                rec.save_original('delivery-figures/' + p.name, p.read_bytes())
        for lang in ('zh', 'en'):
            rec.text({'identity': str(ident('report-document-' + lang)), 'request_id': str(ident('report-' + lang)),
                      'expected_revision': 0, 'kind': 'report', 'title': s.TAG + ' report ' + lang,
                      'markdown': (s.HERE / f'report.{lang}.md').read_text('utf8')})
        rec.text({'identity': str(ident('note-document')), 'request_id': str(ident('note')), 'expected_revision': 0,
                  'kind': 'note', 'title': s.TAG + ' provenance and continuity',
                  'markdown': 'Author-authorized small mechanism study of three temporal-input questions. '
                  '24 main subjects ran continuously to 34 internal seconds. 120 declared single-probe copies '
                  'tested matched cues, no-cue controls, shams, and weight-only exchanges. Originals remain intact. '
                  'Current 6.3 defaults and addressing were unchanged. Four anonymous-code blocks yielded identical '
                  'deterministic values and are not a population sample with stochastic variation. Immediate '
                  'differences passed at both intensities; retained weight differences were re-expressed only '
                  'after the stronger history under this fixed cue. Verification was automated by the same '
                  'executing assistant, not external replication. No manuscript edit or unrelated experiment.'})
        excluded = {'.research-records', 'publication', 'readback', '__pycache__'}
        files = sorted(p for p in s.WORK.rglob('*') if p.is_file()
                       and not set(p.relative_to(s.WORK).parts) & excluded
                       and p.name not in ('manifest.json', 'originals.zip') and not p.name.endswith('.lock'))
        assert not any(p.name.endswith('.partial') for p in files)
        size = sum(p.stat().st_size for p in files)
        assert size < 256 * 2**20
        manifest = {'schema': 'repeat-timing63/original-manifest/1', 'tag': s.TAG,
                    'members': [{'path': p.relative_to(s.WORK).as_posix(), 'bytes': p.stat().st_size,
                                 'sha256': s.sha(p)} for p in files]}
        s.save(s.WORK / 'manifest.json', manifest)
        pack = s.WORK / 'originals.zip'
        if not pack.exists():
            partial = s.WORK / 'originals.zip.partial'
            with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_STORED) as z:
                for p in files + [s.WORK / 'manifest.json']:
                    z.write(p, p.relative_to(s.WORK).as_posix())
            verify(partial, manifest)
            partial.rename(pack)
        verify(pack, manifest)
        for name, role, fmt in (('originals.zip', 'original', 'application/zip'),
                                ('manifest.json', 'manifest', 'application/json'),
                                ('analysis-v1/analysis.json', 'analysis', 'application/json')):
            p = s.WORK / name
            rec.attach({'logical_id': s.TAG + ':' + name, 'role': role, 'label': s.TAG + ' ' + name,
                        'format': fmt, 'byte_count': p.stat().st_size, 'sha256': s.sha(p),
                        'locator': {'kind': 'file', 'resource_id': rid, 'member': name}},
                       request_id=ident('attach-' + name))
        rec.synchronize(strict=True)
        args = {'path': {'project': s.PROJECT, 'experiment': rec.experiment}, 'query': {'hashes': True}}
        check = client.call('records.verify', args)
        assert check['coverage'] == 'verified' and not check['problems']
        row = next(r for r in check['evidence'] if r['logical_id'] == s.TAG + ':originals.zip')
        readback = s.WORK / 'readback/originals.zip'
        readback.parent.mkdir(exist_ok=True)
        if not readback.exists():
            client.call('records.download', {'path': {'project': s.PROJECT, 'evidence': row['id']}},
                        output=readback, maximum=pack.stat().st_size)
        assert s.sha(readback) == s.sha(pack)
        verify(readback, manifest)
        for lang in ('zh', 'en'):
            doc = client.request('GET', f'/api/v2/projects/{s.PROJECT}/research-documents/{ident("report-document-"+lang)}')
            assert doc['spec']['blocks'][0]['markdown'] == (s.HERE / f'report.{lang}.md').read_text('utf8')
        rec.finalize(request_id=ident('finalize'))
        rec.synchronize(strict=True)
        check = client.call('records.verify', args)
        assert check['coverage'] == 'verified' and not check['problems'] and rec.status['pending'] == 0
        result = {'project': s.PROJECT, 'record': rec.experiment, 'resource_id': rid, 'coverage': 'verified',
                  'pending': 0, 'members': len(files), 'raw_bytes': size, 'archive_bytes': pack.stat().st_size,
                  'archive_sha256': s.sha(pack), 'complete_api_readback': True, 'bilingual_report_readback': True}
        s.save(completion, result)
        s.save(s.HERE / 'delivery.json', result)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
