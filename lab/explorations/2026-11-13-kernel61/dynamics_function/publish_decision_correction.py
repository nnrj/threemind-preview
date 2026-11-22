"""Append the R51t4 terminology correction; preserve the verified original package."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid5
import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanism as h
s = h.s
NS = UUID('09310744-81a2-57be-8f98-56c27ebeaee4')


def publish(work):
    receipt = work / 'publication/report-r2-completion.json'
    if receipt.exists():
        print(receipt.read_text('utf8')); return
    done = h.read(work / 'publication/completion.json')
    assert done['coverage'] == 'verified' and done['pending'] == 0
    old_manifest = s.sha(work / 'manifest.json')
    folder = HERE / 'decision_report'
    old_reports = {lang: s.sha(folder / f'report.{lang}.md') for lang in ('zh', 'en')}
    cfg = h.e.base.image(work / 'cases/b0/pair/s0/reference/initial.tmind').to_dict()['config']
    fields = {k: cfg[k] for k in ('edge_consolidation_enabled', 'retention_growth_enabled', 'retention_relaxation_enabled')}
    assert fields == {'edge_consolidation_enabled': True, 'retention_growth_enabled': False, 'retention_relaxation_enabled': False}
    s.base.load_env()
    with s.base.worker_lock(work), s.base.OperationsClient(url='http://127.0.0.1:8877',
            username=os.environ.get('THREEMIND_API_USERNAME'), password=os.environ.get('THREEMIND_API_PASSWORD'),
            token=os.environ.get('THREEMIND_API_TOKEN'), transport=httpx.HTTPTransport(trust_env=False),
            require_auth=True, source='ai') as client:
        rec = s.base.ResearchRecorder(work, done['project'], client=client)
        rec.resume_recording()
        for lang in ('zh', 'en'):
            text = (folder / f'report-r2.{lang}.md').read_text('utf8')
            rec.save_original(f'publication/report-r2.{lang}.md', text.encode('utf8'))
            ident = uuid5(NS, 'report-document-' + lang)
            rec.text({'identity': str(ident), 'request_id': str(uuid5(NS, 'report-' + lang)),
                'expected_revision': 0, 'kind': 'report', 'title': 'R51t4 dated report revision 2 ' + lang,
                'markdown': text})
        rec.append('correction', 'r51t4:weight-strengthening-description',
            {'correct_configuration_fields': fields, 'scientific_results_unchanged': True,
             'original_manifest_sha256': old_manifest, 'original_reports_sha256': old_reports},
            request_id=uuid5(NS, 'correction-event'))
        rec.synchronize(strict=True)
        for lang in ('zh', 'en'):
            doc = client.request('GET', f'/api/v2/projects/{done["project"]}/research-documents/{uuid5(NS, "report-document-" + lang)}')
            assert doc['spec']['blocks'][0]['markdown'] == (folder / f'report-r2.{lang}.md').read_text('utf8')
        rec.finalize(request_id=uuid5(NS, 'finalize-r2')); rec.synchronize(strict=True)
        check = client.call('records.verify', {'path': {'project': done['project'], 'experiment': rec.experiment}, 'query': {'hashes': True}})
        assert check['coverage'] == 'verified' and not check['problems'] and rec.status['pending'] == 0
        assert s.sha(work / 'manifest.json') == old_manifest
        assert all(s.sha(folder / f'report.{lang}.md') == old_reports[lang] for lang in ('zh', 'en'))
        result = {'coverage': 'verified', 'pending': 0, 'record': rec.experiment,
                  'correct_configuration_fields': fields, 'original_manifest_unchanged': True,
                  'original_reports_unchanged': True, 'scientific_results_unchanged': True}
        s.base.original(receipt, result); print(json.dumps(result))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--work', type=Path, required=True)
    publish(p.parse_args().work)
