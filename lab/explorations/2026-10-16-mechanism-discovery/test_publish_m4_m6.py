"""Synthetic publication fixtures only: no Core, scientific subject or network."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish_m4_m6 as p


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


@pytest.fixture
def work():
    # Keep all synthetic data; avoid system temp ACLs and never touch real work.
    path = p.ROOT / '.work' / ('publication-fixture-' + uuid4().hex)
    path.mkdir()
    return path


def hosts(work, kind):
    total = p.KINDS[kind]
    put(work / 'status.json', {'state': 'awaiting-analysis', 'completed': total, 'total': total})
    roots = [work / p.M4_CONTINUATION] if kind == 'm4-balanced-v2' else [work / 'hosts/apparatus', work / 'hosts/run']
    paths = [root / 'host.json' for root in roots]
    if kind == 'm4-balanced-v2':
        paths.append(work / 'host.json')
    for i, path in enumerate(paths):
        put(path, {'pid': i + 100, 'created_at': 20.0, 'command': ['fixture']})
    return paths


@pytest.mark.parametrize('kind', list(p.KINDS))
def test_nested_live_host_blocks_despite_stale_root(work, monkeypatch, kind):
    hosts(work, kind)
    monkeypatch.setattr(p.psutil, 'Process', lambda pid: SimpleNamespace(create_time=lambda: 20.0 if pid == 100 else 99.0))
    with pytest.raises(RuntimeError, match='still alive'):
        p.quiescent(work, kind)
    monkeypatch.setattr(p.psutil, 'Process', lambda pid: SimpleNamespace(create_time=lambda: 99.0))
    assert p.quiescent(work, kind)['all_recorded_hosts_exited']


def test_dead_host_and_access_denied_are_not_conflated(work, monkeypatch):
    hosts(work, 'm6-historical-v1')
    def missing(pid):
        raise p.psutil.NoSuchProcess(pid)
    monkeypatch.setattr(p.psutil, 'Process', missing)
    assert p.quiescent(work, 'm6-historical-v1')['recorded_hosts_checked'] == 2
    def denied(pid):
        raise p.psutil.AccessDenied(pid)
    monkeypatch.setattr(p.psutil, 'Process', denied)
    with pytest.raises(p.psutil.AccessDenied):
        p.quiescent(work, 'm6-historical-v1')


@pytest.mark.parametrize('marker', ['STOP', 'in-flight.json', 'apparatus-in-flight.json'])
def test_active_markers_block_and_stay_intact(work, marker):
    hosts(work, 'm4-balanced-v2')
    put(work / marker, {'original': True})
    with pytest.raises(RuntimeError, match='active marker'):
        p.quiescent(work, 'm4-balanced-v2')
    assert p.base.read(work / marker) == {'original': True}


@pytest.mark.parametrize('case', ['missing-host', 'partial-ticket', 'paused-ticket', 'failure', 'incomplete'])
def test_host_completion_evidence_required(work, case):
    paths = hosts(work, 'm6-historical-v1')
    if case == 'missing-host':
        # Only remove a synthetic fixture written in this test.
        paths[0].unlink()
    elif case == 'failure':
        put(paths[1].parent / 'failure.json', {'fixture': True})
    elif case == 'incomplete':
        put(work / 'status.json', {'state': 'awaiting-analysis', 'completed': 15, 'total': 16})
    else:
        folder = paths[1].parent / 'workers/001-fixture'
        put(folder / 'ticket.json', {})
        if case == 'paused-ticket':
            put(folder / 'host.json', {'pid': 1, 'created_at': 1})
            put(folder / 'completed.json', {'paused': True})
    with pytest.raises(RuntimeError):
        p.quiescent(work, 'm6-historical-v1')


def review_fixture(work, monkeypatch):
    repo, data = work / 'repo', work / 'data'
    repo.mkdir(); data.mkdir()
    batch = data / 'm6-historical-v1'
    batch.mkdir()
    # Publication implementation bindings use real locations; keep ROOT real.
    monkeypatch.setattr(p, 'DATA', data)
    platform = {'project_id': 'project-fixture', 'resource_id': 'resource-fixture'}
    for name, value in {
        'platform.json': platform, '.research-records/identity.json': {'project': 'project-fixture', 'experiment': 'record-fixture'},
        'analysis-v1.json': {}, 'audit-v1.json': {'passed_integrity': True}, 'runner-manifest.json': {},
        'status.json': {'state': 'awaiting-analysis', 'completed': 16, 'total': 16},
        'inputs-manifest.json': {}, 'apparatus.json': {'passed': True}}.items():
        put(batch / name, value)
    put(batch / 'apparatus-review.json', {'accepted': True, 'apparatus_sha256': p.base.sha(batch / 'apparatus.json'),
                                         'runner_manifest_sha256': p.base.sha(batch / 'runner-manifest.json')})
    files = [Path(p.__file__).resolve(), Path(p.base.__file__).resolve(), p.ROOT / 'lab/tools/study_lock.py']
    value = {'schema': 'threemind.m4-m6-publication-review/1', 'reviewer': 'assistant', 'approved_for_publication': True,
             'batch': batch.name, 'work': str(batch), 'project_id': 'project-fixture', 'record_id': 'record-fixture',
             'scientific_review': {key: 'Explicit synthetic review' for key in
                 ('purpose', 'expectation', 'analysis', 'scientific_conclusion', 'meaning_for_ThreeMind')},
             'reviewed_files': {f.relative_to(p.ROOT).as_posix(): p.base.sha(f) for f in files},
             'reviewed_originals': {f.relative_to(batch).as_posix(): p.base.sha(f) for f in batch.rglob('*.json')}, 'reports': {}}
    for language in ('zh', 'en'):
        report = batch / ('report.' + language + '.md')
        report.write_text('Synthetic conclusion ' + language, encoding='utf-8')
        value['reports'][language] = {'scope': 'work', 'path': report.name, 'sha256': p.base.sha(report)}
    review = work / 'review.json'
    put(review, value)
    return batch, review, value


def test_review_binds_work_identity_and_actual_report_bytes(work, monkeypatch):
    batch, review, value = review_fixture(work, monkeypatch)
    assert len(p.validate_review(batch, review, p.base.sha(review))[2]) == 2
    (batch / 'report.zh.md').write_text('silently changed', encoding='utf-8')
    with pytest.raises(ValueError, match='reviewed file changed'):
        p.validate_review(batch, review, p.base.sha(review))


@pytest.mark.parametrize('fault', ['missing-report', 'missing-conclusion', 'wrong-record', 'escaping-path', 'audit-failed', 'changed-source', 'wrong-apparatus'])
def test_incomplete_or_unbound_review_rejected(work, monkeypatch, fault):
    batch, path, review = review_fixture(work, monkeypatch)
    if fault == 'missing-report':
        review['reports'].pop('en')
    elif fault == 'missing-conclusion':
        review['scientific_review']['scientific_conclusion'] = ''
    elif fault == 'wrong-record':
        review['record_id'] = 'other'
    elif fault == 'escaping-path':
        review['reports']['zh']['path'] = '../outside.md'
    elif fault == 'changed-source':
        review['reviewed_files'][next(iter(review['reviewed_files']))] = '0' * 64
    elif fault == 'wrong-apparatus':
        put(batch / 'apparatus-review.json', {'accepted': True, 'apparatus_sha256': '0' * 64,
                                             'runner_manifest_sha256': p.base.sha(batch / 'runner-manifest.json')})
        review['reviewed_originals']['apparatus-review.json'] = p.base.sha(batch / 'apparatus-review.json')
    else:
        put(batch / 'audit-v1.json', {'passed_integrity': False})
        review['reviewed_originals']['audit-v1.json'] = p.base.sha(batch / 'audit-v1.json')
    put(path, review)
    with pytest.raises(ValueError):
        p.validate_review(batch, path, p.base.sha(path))


def delivery_fixture(work, monkeypatch, mismatch=None, pending=0):
    events = []
    for name in ('originals-manifest-v1.json', 'analysis-v1.json'):
        put(work / name, {})
    pack = work / 'originals-v1.zip'
    pack.write_bytes(b'synthetic archive')
    (work / 'readback').mkdir()
    (work / 'readback/originals-v1.zip').write_bytes(pack.read_bytes() if mismatch != 'archive' else b'corrupt')
    reports = {}
    for language in ('zh', 'en'):
        reports[language] = work / ('report.' + language + '.md')
        reports[language].write_text('Final scientific conclusion ' + language, encoding='utf-8')
    class Recorder:
        experiment = 'fixture-record'
        status = {'pending': pending}
        def attach(self, *args, **kwargs): events.append('attach')
        def text(self, *args, **kwargs): events.append('text')
        def synchronize(self, **kwargs): events.append('sync')
        def save_original(self, name, content): events.append('save:' + name)
        def finalize(self, **kwargs): events.append('finalize')
    class Client:
        def call(self, operation, args, **kwargs):
            assert operation == 'records.verify'
            events.append(operation)
            return {'coverage': 'verified', 'problems': [], 'execution_status': 'completed',
                    'evidence': [{'logical_id': p.PREFIX + 'originals-v1.zip', 'id': 'pack'}]}
        def request(self, method, route):
            assert method == 'GET'
            language = next(lang for lang in reports if str(p.request_id('fixture-record', 'report-doc:' + lang)) in route)
            events.append('read:' + language)
            return {'revision': 1, 'spec': {'blocks': [{'markdown': 'wrong' if mismatch == language else reports[language].read_text()}]}}
    monkeypatch.setattr(p.base.shutil, 'disk_usage', lambda _: SimpleNamespace(free=40 * 2**30))
    monkeypatch.setattr(p.base, 'verify_archive', lambda *args: events.append('verified-all-archive-members'))
    review = {'record_id': 'fixture-record', 'batch': 'm6-historical-v1', 'scientific_review': {'conclusion': 'fixture'}}
    args = (work, review, reports, {'project_id': 'project', 'resource_id': 'resource'}, Recorder(), Client(), pack,
            {'members': [{'path': 'fixture'}]}, 'publication/attempts/fixture')
    return events, args


def test_actual_archive_and_both_bodies_precede_finalize(work, monkeypatch):
    events, args = delivery_fixture(work, monkeypatch)
    result = p.deliver(*args)
    assert result['reports_read_back'] == 2 and result['pending'] == 0
    for step in ('verified-all-archive-members', 'read:zh', 'read:en', 'save:publication/attempts/fixture/before-finalize.json'):
        assert events.index(step) < events.index('finalize')
    assert events[-1] == 'save:publication/final-verification.json'


@pytest.mark.parametrize('mismatch', ['zh', 'en', 'archive'])
def test_readback_mismatch_never_queues_finalize(work, monkeypatch, mismatch):
    events, args = delivery_fixture(work, monkeypatch, mismatch)
    with pytest.raises(RuntimeError, match='mismatch'):
        p.deliver(*args)
    assert 'finalize' not in events
    assert (work / 'readback/originals-v1.zip').exists()


def test_pending_queue_prevents_finalization(work, monkeypatch):
    events, args = delivery_fixture(work, monkeypatch, pending=1)
    with pytest.raises(RuntimeError, match='pending'):
        p.deliver(*args)
    assert 'finalize' not in events


def test_readback_disk_reserve_prevents_finalization(work, monkeypatch):
    events, args = delivery_fixture(work, monkeypatch)
    monkeypatch.setattr(p.base.shutil, 'disk_usage', lambda _: SimpleNamespace(free=24 * 2**30))
    with pytest.raises(RuntimeError, match='reserve'):
        p.deliver(*args)
    assert 'finalize' not in events


def test_request_namespace_is_repeatable_and_separates_records():
    assert p.request_id('one', 'finalize') == p.request_id('one', 'finalize')
    assert p.request_id('one', 'finalize') != p.request_id('two', 'finalize')
    assert p.request_id('one', 'finalize') != p.request_id('one', 'report:zh')


def test_existing_archive_verifier_rejects_altered_member(work):
    import zipfile
    manifest = {'members': [{'path': 'original.txt', 'sha256': hashlib.sha256(b'original').hexdigest(), 'bytes': 8}]}
    pack = work / 'altered.zip'
    with zipfile.ZipFile(pack, 'x') as archive:
        archive.writestr('originals-manifest-v1.json', json.dumps(manifest))
        archive.writestr('original.txt', b'tampered')
    with pytest.raises(ValueError, match='archive member mismatch'):
        p.base.verify_archive(pack, manifest)
