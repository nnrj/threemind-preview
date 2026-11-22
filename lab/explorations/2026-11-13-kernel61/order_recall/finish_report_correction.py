"""Preserve the rejected metadata request and submit the documented correction."""
import json
from pathlib import Path
import sys
from uuid import UUID, uuid5

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report_correction as r
from threemind_lab.storage_files import file_lock


def main(work):
    s = r.s
    receipt = json.loads((work / 'publication/completion.json').read_bytes())
    ns = UUID('d5230456-a96e-5700-89fb-ce397c466c18')
    identity = str(uuid5(ns, 'r51n:report-document-en'))
    rejected = str(uuid5(ns, 'r51n:report-en-identifier-correction-20261114'))
    folder = work / 'postprocessing/report-correction-20261114'
    assert folder.is_dir() and not (folder / 'receipt.json').exists()
    s.base.load_env()
    with s.base.OperationsClient(url='http://127.0.0.1:8877', username=r.os.environ.get('THREEMIND_API_USERNAME'),
                                password=r.os.environ.get('THREEMIND_API_PASSWORD'), token=r.os.environ.get('THREEMIND_API_TOKEN'),
                                transport=r.httpx.HTTPTransport(trust_env=False), reuse_session=False, require_auth=True, source='ai') as client:
        path = f'/api/v2/projects/{receipt["project"]}/research-documents/{identity}'
        before = client.request('GET', path)
        assert before['revision'] == 1
        assert before['spec']['blocks'][0]['markdown'] == (HERE / 'report.v1.en.md').read_text('utf-8')
        try:
            client.call('records.receipt', {'path': {'project': receipt['project'], 'request_id': rejected}})
        except ValueError as exc:
            assert 'HTTP 404' in str(exc)
        else:
            raise RuntimeError('rejected request unexpectedly committed; inspect before proceeding')
        pending = work / '.research-records/pending' / (rejected + '.json')
        archived = folder / 'rejected-request.json'
        assert pending.resolve().is_relative_to(work.resolve()) and archived.resolve().is_relative_to(work.resolve())
        assert not archived.exists()
        with file_lock(work / '.research-records/journal.lock'):
            value = json.loads(pending.read_bytes())
            assert value['action'] == 'text' and value['body']['request_id'] == rejected
            assert value['body']['expected_revision'] == 1 and not value['body'].get('revision_reason')
            digest = s.sha(pending)
            pending.rename(archived)
            assert s.sha(archived) == digest
        s.blob(folder / 'finish_report_correction.py', Path(__file__).read_bytes())
        reason = 'Correct spaces accidentally inserted into the evidence path and record identifier; preserve English edition 1 and the original archive. No scientific change.'
        rec = s.base.ResearchRecorder(work, receipt['project'], client=client)
        rec.resume_recording()
        body = dict(value['body'], request_id=str(uuid5(ns, 'r51n:report-en-identifier-correction-with-reason-20261114')),
                    revision_reason=reason)
        rec.text(body)
        rec.synchronize(strict=True)
        after = client.request('GET', path)
        assert after['revision'] == 2 and after['spec']['blocks'][0]['markdown'] == (HERE / 'report.en.md').read_text('utf-8')
        verified = client.call('records.verify', {'path': {'project': receipt['project'], 'experiment': receipt['record']}, 'query': {'hashes': True}})
        assert verified['coverage'] == 'verified' and not verified['problems'] and rec.status['pending'] == 0
        assert s.sha(work / 'originals.zip') == receipt['archive_sha256']
        result = {'scope': reason, 'document': identity, 'old_revision': 1, 'new_revision': 2,
                  'old_sha256': s.sha(HERE / 'report.v1.en.md'), 'new_sha256': s.sha(HERE / 'report.en.md'),
                  'archive_unchanged': receipt['archive_sha256'], 'rejected_request_preserved': digest,
                  'coverage': 'verified', 'pending': 0, 'readback_exact': True}
        s.base.original(folder / 'receipt.json', result)
        print(json.dumps(result))


if __name__ == '__main__': main(Path(sys.argv[1]).resolve())
