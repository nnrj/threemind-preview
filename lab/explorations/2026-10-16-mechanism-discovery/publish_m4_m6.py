"""Reviewed M4/M6 delivery only; never load or advance an experimental subject.

The existing archive and ResearchRecorder APIs are reused unchanged. This
adapter recognizes the new host layouts and reads back the actual bilingual
document bodies before queuing finalization. Earlier publishers stay frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import psutil
import publish_mechanism as base

ROOT = base.ROOT
DATA = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery')
GLOBAL_LOCK = DATA / 'm2-pilot-v1'
NS = UUID('1bcd90f5-2958-4b51-94c4-bc4f9d86f92f')
PREFIX = 'mechanism-m4-m6-publication-v1:'
M4_CONTINUATION = 'continuations/c111-private3-20261017'
KINDS = {'m4-balanced-v2': 8, 'm6-historical-v1': 16}


def inside(root, relative):
    relative = Path(relative)
    target = (root / relative).resolve()
    if relative.is_absolute() or '..' in relative.parts or not target.is_relative_to(root.resolve()):
        raise ValueError('path is outside its declared root')
    return target


def check_hash(path, expected):
    if base.sha(path) != expected:
        raise ValueError('reviewed file changed: ' + str(path))


def validate_review(work, path, expected):
    check_hash(path, expected)
    review = base.read(path)
    if (review.get('schema') != 'threemind.m4-m6-publication-review/1'
            or review.get('reviewer') != 'assistant' or review.get('approved_for_publication') is not True):
        raise ValueError('explicit assistant publication review required')
    kind = review['batch']
    if kind not in KINDS or work != (DATA / kind).resolve() or Path(review['work']).resolve() != work:
        raise ValueError('wrong batch or work directory')
    for field in ('purpose', 'expectation', 'analysis', 'scientific_conclusion', 'meaning_for_ThreeMind'):
        if not str(review['scientific_review'].get(field, '')).strip():
            raise ValueError('incomplete scientific review: ' + field)
    files = review['reviewed_files']
    # Freeze this adapter and the reused archive and lock implementations too.
    required = {Path(__file__).resolve().relative_to(ROOT).as_posix(),
                Path(base.__file__).resolve().relative_to(ROOT).as_posix(), 'lab/tools/study_lock.py'}
    if not required <= set(files):
        raise ValueError('publication implementation not bound to review')
    for name, digest in files.items():
        check_hash(inside(ROOT, name), digest)
    originals = review['reviewed_originals']
    required = {'analysis-v1.json', 'audit-v1.json', 'runner-manifest.json', 'platform.json',
                '.research-records/identity.json', 'status.json'}
    required |= ({M4_CONTINUATION + '/plan.json'} if kind == 'm4-balanced-v2'
                 else {'inputs-manifest.json', 'apparatus.json', 'apparatus-review.json'})
    if not required <= set(originals):
        raise ValueError('analysis, independent audit or execution identity not bound to review')
    for name, digest in originals.items():
        check_hash(inside(work, name), digest)
    for name, digest in base.read(work / 'runner-manifest.json').items():
        check_hash(inside(ROOT, name), digest)
    if kind == 'm6-historical-v1':
        for name, digest in base.read(work / 'inputs-manifest.json').items():
            check_hash(inside(work, name), digest)
        apparatus = base.read(work / 'apparatus-review.json')
        if apparatus.get('accepted') is not True or base.read(work / 'apparatus.json').get('passed') is not True:
            raise ValueError('actual instrument acceptance required')
        check_hash(work / 'apparatus.json', apparatus['apparatus_sha256'])
        check_hash(work / 'runner-manifest.json', apparatus['runner_manifest_sha256'])
    else:
        for name, digest in base.read(work / M4_CONTINUATION / 'plan.json')['files'].items():
            check_hash(inside(ROOT, name), digest)
    platform = base.read(work / 'platform.json')
    identity = base.read(work / '.research-records/identity.json')
    if (platform['project_id'], identity['project'], identity['experiment']) != (
            review['project_id'], review['project_id'], review['record_id']):
        raise ValueError('research record identity mismatch')
    audit = base.read(work / 'audit-v1.json')
    flag = 'passed' if kind == 'm4-balanced-v2' else 'passed_integrity'
    if audit.get(flag) is not True:
        raise ValueError('independent file audit has not passed')
    reports = {}
    if set(review['reports']) != {'zh', 'en'}:
        raise ValueError('both reviewed language editions are required')
    for language, item in review['reports'].items():
        if item['scope'] not in ('repo', 'work'):
            raise ValueError('unknown report scope')
        report = inside(ROOT if item['scope'] == 'repo' else work, item['path'])
        check_hash(report, item['sha256'])
        reports[language] = report
    return review, platform, reports


def quiescent(work, kind):
    """Called under the existing global and study locks; historical STOP copies stay intact."""
    status = base.read(work / 'status.json')
    if (status['state'], status['completed'], status['total']) != ('awaiting-analysis', KINDS[kind], KINDS[kind]):
        raise RuntimeError('complete analysis boundary required')
    if any((work / name).exists() for name in ('STOP', 'in-flight.json', 'apparatus-in-flight.json')):
        raise RuntimeError('unresolved active marker; preserve and inspect')
    roots = [work / M4_CONTINUATION] if kind == 'm4-balanced-v2' else [work / 'hosts/apparatus', work / 'hosts/run']
    required_hosts = [root / 'host.json' for root in roots]
    if kind == 'm4-balanced-v2':
        required_hosts.append(work / 'host.json')
    if not all(path.is_file() for path in required_hosts):
        raise RuntimeError('registered supervisor host evidence missing')
    for root in roots:
        if (root / 'failure.json').exists():
            raise RuntimeError('unresolved supervisor failure')
        for ticket in (root / 'workers').glob('*/ticket.json'):
            completed = ticket.parent / 'completed.json'
            if not (ticket.parent / 'host.json').is_file() or not completed.is_file():
                raise RuntimeError('unfinished worker ticket')
            if base.read(completed).get('paused') is not False:
                raise RuntimeError('worker has an unresolved pause')
    hosts = sorted(work.rglob('host.json'))
    for path in hosts:
        host = base.read(path)
        if not isinstance(host['pid'], int) or host['pid'] <= 0 or float(host['created_at']) <= 0:
            raise ValueError('invalid recorded host identity')
        try:
            process = psutil.Process(host['pid'])
            if abs(process.create_time() - host['created_at']) < .01:
                raise RuntimeError('recorded computation host is still alive: ' + str(path))
        except psutil.NoSuchProcess:
            pass
        # AccessDenied and other inspection errors fail closed, never imply exit.
    return {'recorded_hosts_checked': len(hosts), 'complete_units': KINDS[kind], 'all_recorded_hosts_exited': True}


def request_id(record, suffix):
    return uuid5(NS, record + ':' + suffix)


def verify_coverage(verification, *, completed=False):
    if verification.get('coverage') != 'verified' or verification.get('problems'):
        raise RuntimeError('registered evidence did not verify')
    if completed and verification.get('execution_status') != 'completed':
        raise RuntimeError('record is not completed')


def readback_texts(client, platform, record, texts):
    rows = []
    for language, body in sorted(texts.items()):
        identity = str(request_id(record, 'report-doc:' + language))
        doc = client.request('GET', f'/api/v2/projects/{platform["project_id"]}/research-documents/{identity}')
        blocks = doc['spec']['blocks']
        if len(blocks) != 1 or blocks[0].get('markdown') != body:
            raise RuntimeError('actual report text readback mismatch: ' + language)
        rows.append({'language': language, 'identity': identity, 'revision': doc['revision'],
                     'markdown_sha256': hashlib.sha256(body.encode('utf-8')).hexdigest(), 'equal': True})
    return rows


def deliver(work, review, reports, platform, recorder, client, pack, manifest, attempt):
    """Failures retain durable queued requests and evidence; never queue an early finalize."""
    record = review['record_id']
    if str(recorder.experiment) != record:
        raise ValueError('active journal record differs from review')
    for relative, role, label, fmt in (
            ('originals-v1.zip', 'original', 'Complete originals and reviewed postprocessing', 'application/zip'),
            ('originals-manifest-v1.json', 'manifest', 'Per-member SHA256 manifest', 'application/json'),
            ('analysis-v1.json', 'analysis', 'Frozen scientific endpoints', 'application/json')):
        path = work / relative
        recorder.attach({'logical_id': PREFIX + relative, 'role': role, 'label': label, 'format': fmt,
                         'byte_count': path.stat().st_size, 'sha256': base.sha(path),
                         'locator': {'kind': 'file', 'resource_id': platform['resource_id'], 'member': relative}},
                        request_id=request_id(record, 'attach:' + relative))
    texts = {language: path.read_text(encoding='utf-8') for language, path in reports.items()}
    for language, body in sorted(texts.items()):
        recorder.text({'request_id': str(request_id(record, 'report:' + language)),
                       'identity': str(request_id(record, 'report-doc:' + language)), 'expected_revision': 0,
                       'kind': 'report', 'title': review['batch'] + ' scientific report ' + language, 'markdown': body})
    recorder.text({'request_id': str(request_id(record, 'note')), 'identity': str(request_id(record, 'note-doc')),
                   'expected_revision': 0, 'kind': 'note', 'title': review['batch'] + ' publication review',
                   'markdown': json.dumps(review['scientific_review'], ensure_ascii=False, indent=2)
                   + '\n\nReview by the assistant; not external researcher or human replication.'})
    recorder.synchronize(strict=True)
    if recorder.status['pending']:
        raise RuntimeError('pending research requests')
    args = {'path': {'project': platform['project_id'], 'experiment': record}, 'query': {'hashes': True}}
    verification = client.call('records.verify', args)
    verify_coverage(verification)
    archive_rows = [row for row in verification['evidence'] if row['logical_id'] == PREFIX + 'originals-v1.zip']
    if len(archive_rows) != 1:
        raise RuntimeError('ambiguous archive registration')
    destination = work / 'readback/originals-v1.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        if base.shutil.disk_usage(work).free < 25 * 2**30 + pack.stat().st_size + 64 * 2**20:
            raise RuntimeError('insufficient space for API readback and reserve')
        receipt = client.call('records.download', {'path': {'project': platform['project_id'], 'evidence': archive_rows[0]['id']}},
                              output=destination, maximum=pack.stat().st_size)
        recorder.save_original(attempt + '/download.json', json.dumps(receipt, sort_keys=True).encode())
    if base.shutil.disk_usage(work).free < 25 * 2**30 or base.sha(destination) != base.sha(pack):
        raise RuntimeError('archive readback mismatch or disk reserve violated')
    base.verify_archive(destination, manifest)
    text_receipts = readback_texts(client, platform, record, texts)
    receipt = {'archive_sha256': base.sha(pack), 'members': len(manifest['members']),
               'reports': text_receipts, 'pending': recorder.status['pending'], 'originals_verified': True}
    recorder.save_original(attempt + '/before-finalize.json', json.dumps(receipt, sort_keys=True).encode())
    # This is the first point at which finalization is even queued.
    recorder.finalize(request_id=request_id(record, 'finalize'))
    recorder.synchronize(strict=True)
    final = client.call('records.verify', args)
    verify_coverage(final, completed=True)
    if recorder.status['pending']:
        raise RuntimeError('pending requests after finalization')
    recorder.save_original('publication/final-verification.json', json.dumps(final, sort_keys=True).encode())
    return {'record': record, 'coverage': final['coverage'], 'pending': 0,
            'archive_sha256': receipt['archive_sha256'], 'members': receipt['members'], 'reports_read_back': 2}


def publish(work, review_path, expected):
    work, review_path = work.resolve(), review_path.resolve()
    review, platform, reports = validate_review(work, review_path, expected)
    if (work / 'publication/final-verification.json').exists():
        raise RuntimeError('already delivered; inspect the receipt, do not repeat publication')
    with base.worker_lock(GLOBAL_LOCK), base.worker_lock(work):
        hosts = quiescent(work, review['batch'])
        # Revalidate review bindings after taking the locks, before any publishing write.
        review, platform, reports = validate_review(work, review_path, expected)
        base.load_env()
        with base.OperationsClient.from_environment(source='ai') as client:
            recorder = base.ResearchRecorder(work, platform['project_id'], client=client)
            recorder.resume_recording()
            if str(recorder.experiment) != review['record_id']:
                raise ValueError('journal identity differs')
            recorder.save_original('postprocessing/publication-review-v1.json', review_path.read_bytes())
            recorder.save_original('postprocessing/host-exit-check-v1.json', json.dumps(hosts, sort_keys=True).encode())
            for name in review['reviewed_files']:
                recorder.save_original('postprocessing/sources/' + name, inside(ROOT, name).read_bytes())
            for language, path in reports.items():
                recorder.save_original('postprocessing/reports/report.' + language + '.md', path.read_bytes())
            manifest, pack = base.archive(work, recorder)
            attempt = 'publication/attempts/' + uuid4().hex
            return deliver(work, review, reports, platform, recorder, client, pack, manifest, attempt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--review-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.work, args.review, args.review_sha256), ensure_ascii=False))
