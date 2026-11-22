"""Append an audited storage correction without replacing original evidence."""
import argparse
import json
from pathlib import Path

import deliver as d


def publish(work):
    completion = work / 'publication/allocation-correction.json'
    if completion.exists():
        print(completion.read_text('utf-8'))
        return
    previous = d.read(work / 'publication/completion.json')
    audit = d.read(work / 'storage-allocation-audit.json')
    assert audit['final_allocation_ratio'] < 2
    assert previous['campaign_status'] == 'paused-performance'
    with d.f.base.worker_lock(work), d.connection() as client:
        recorder = d.f.base.ResearchRecorder(work, previous['project'], client=client)
        recorder.resume_recording()
        for name in ('storage_audit.py', 'publish_storage_correction.py'):
            recorder.save_original('tools/' + name, (d.f.HERE / name).read_bytes())
        for lang in ('zh', 'en'):
            text = (d.f.HERE / f'report.{lang}.md').read_text('utf-8')
            recorder.save_original(f'revisions/report-r2.{lang}.md', text.encode())
            recorder.text({'request_id': str(d.ident('storage-report-r2-' + lang)),
                           'identity': str(d.ident('doc-report' + lang)), 'expected_revision': 1,
                           'revision_reason': 'Distinguish file length from FileStandardInfo allocation; preserve all original measurements.',
                           'kind': 'report', 'title': 'R51a report ' + lang, 'markdown': text})
        p = work / 'storage-allocation-audit.json'
        recorder.attach({'logical_id': 'r51a:storage-allocation-audit', 'role': 'analysis',
                         'label': 'R51a actual Windows allocated storage', 'format': 'application/json',
                         'byte_count': p.stat().st_size, 'sha256': d.f.sha(p),
                         'locator': {'kind': 'file', 'resource_id': d.RESOURCE, 'member': p.name}},
                        request_id=d.ident('attach-storage-allocation-audit'))
        recorder.synchronize(strict=True)
        args = {'path': {'project': previous['project'], 'experiment': recorder.experiment}, 'query': {'hashes': True}}
        verified = client.call('records.verify', args)
        assert verified['coverage'] == 'verified' and not verified['problems']
        evidence = next(e for e in verified['evidence'] if e['logical_id'] == 'r51a:storage-allocation-audit')
        dest = work / 'readback/storage-allocation-audit.json'
        if not dest.exists():
            client.call('records.download', {'path': {'project': previous['project'], 'evidence': evidence['id']}},
                        output=dest, maximum=p.stat().st_size)
        assert d.f.sha(dest) == d.f.sha(p)
        for lang in ('zh', 'en'):
            doc = client.request('GET', f'/api/v2/projects/{previous["project"]}/research-documents/{d.ident("doc-report" + lang)}')
            assert doc['revision'] == 2
            assert doc['spec']['blocks'][0]['markdown'] == (d.f.HERE / f'report.{lang}.md').read_text('utf-8')
        assert recorder.status['pending'] == 0
        result = {'project': previous['project'], 'record': recorder.experiment, 'coverage': 'verified',
                  'pending': 0, 'report_revision': 2, 'campaign_status': 'paused-performance',
                  'allocation_ratio': audit['final_allocation_ratio'], 'allocation_audit_sha256': d.f.sha(p)}
        recorder.save_original('publication/allocation-correction.json', json.dumps(result, indent=2).encode())
        print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    publish(parser.parse_args().work.resolve())
