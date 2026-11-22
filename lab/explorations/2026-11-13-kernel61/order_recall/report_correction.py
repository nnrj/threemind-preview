"""One-time editorial correction; preserves the delivered archive and version 1."""
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid5
import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import support as s


def main(work):
    receipt = json.loads((work / 'publication/completion.json').read_bytes())
    assert receipt['coverage'] == 'verified' and receipt['pending'] == 0
    ns = UUID('d5230456-a96e-5700-89fb-ce397c466c18')
    identity = str(uuid5(ns, 'r51n:report-document-en'))
    old = (HERE / 'report.v1.en.md').read_text('utf-8')
    corrected = (HERE / 'report.en.md').read_text('utf-8')
    assert 'kernel 60-revalidation' in old and 'kernel 60-revalidation' not in corrected
    folder = work / 'postprocessing/report-correction-20261114'
    folder.mkdir(parents=True, exist_ok=False)
    for name in ('report.v1.en.md', 'report.en.md', 'report_correction.py'):
        s.blob(folder / name, (HERE / name).read_bytes())
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=os.environ.get('THREEMIND_API_USERNAME'),
                                password=os.environ.get('THREEMIND_API_PASSWORD'), token=os.environ.get('THREEMIND_API_TOKEN'),
                                transport=httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        path = f'/api/v2/projects/{receipt["project"]}/research-documents/{identity}'
        before = client.request('GET', path)
        assert before['revision'] == 1 and before['spec']['blocks'][0]['markdown'] == old
        rec = s.base.ResearchRecorder(work, receipt['project'], client=client)
        rec.resume_recording()
        rec.text({'identity': identity, 'request_id': str(uuid5(ns, 'r51n:report-en-identifier-correction-20261114')),
                  'expected_revision': 1, 'kind': 'report', 'title': 'r51n report en', 'markdown': corrected})
        rec.synchronize(strict=True)
        after = client.request('GET', path)
        assert after['revision'] == 2 and after['spec']['blocks'][0]['markdown'] == corrected
        verified = client.call('records.verify', {'path': {'project': receipt['project'], 'experiment': receipt['record']}, 'query': {'hashes': True}})
        assert verified['coverage'] == 'verified' and not verified['problems'] and rec.status['pending'] == 0
        result = {'scope': 'English identifier spacing only; no scientific change', 'document': identity,
                  'old_revision': 1, 'new_revision': 2, 'old_sha256': s.sha(HERE / 'report.v1.en.md'),
                  'new_sha256': s.sha(HERE / 'report.en.md'), 'archive_unchanged': receipt['archive_sha256'],
                  'coverage': verified['coverage'], 'pending': rec.status['pending'], 'readback_exact': True}
        s.base.original(folder / 'receipt.json', result)
        print(json.dumps(result))


if __name__ == '__main__': main(Path(sys.argv[1]).resolve())
