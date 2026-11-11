from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from threemind_lab.api import create_app
from threemind_lab.config import Settings
from threemind_lab.database import LOCAL_USER, Conflict, Forbidden
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.research_records import ResearchRecords
from threemind_lab.research_storage import ResearchStorage


def subject(database):
    actor = {'id': LOCAL_USER}
    project = database.create_project(actor, 'Historical evidence')['id']
    return actor, project, ResearchRecords(database)


def register(service, project, actor, **changes):
    return service.register(project, actor, {'request_id': str(uuid4()), 'spec': {
        'source_key': 'E64-original', 'original_id': 'E64', 'title': 'Negative result preserved',
        'execution_status': 'completed', 'executor': 'ai', **changes,
    }})['id']


def test_atomic_receipts_and_fixed_text_revisions(database):
    actor, project, service = subject(database)
    body = {'request_id': str(uuid4()), 'spec': {'source_key': 'origin', 'title': 'original'}}
    first = service.register(project, actor, body)
    assert service.register(project, actor, body)['replayed']
    with pytest.raises(Conflict):
        service.register(project, actor, body | {'spec': body['spec'] | {'title': 'invented'}})
    text = {'request_id': str(uuid4()), 'identity': str(uuid4()), 'kind': 'report', 'title': 'Original report',
            'markdown': 'Original negative result\n', 'expected_revision': 0}
    original = service.save_text(project, actor, first['id'], text)
    assert service.save_text(project, actor, first['id'], text)['replayed']
    revised = text | {'request_id': str(uuid4()), 'expected_revision': 1, 'markdown': 'Location correction\n',
                      'revision_reason': 'Original file reference changed'}
    service.save_text(project, actor, first['id'], revised)
    with database.tx(project) as db:
        versions = db.execute('SELECT revision,spec FROM research_document_versions WHERE document_id=%s ORDER BY revision',
                              (text['identity'],)).fetchall()
        assert versions[0]['spec']['blocks'][0]['markdown'] == text['markdown']
        assert len(versions) == 2
        assert db.execute('SELECT count(*) AS n FROM runs').fetchone()['n'] == 0
    assert service.receipt(project, actor, text['request_id'])['result']['text']['content_hash'] == original['text']['content_hash']
    assert service.receipt(project, actor, body['request_id'])['result']['id'] == first['id']
    literal = '[Original relative citation](../old/protocol.md)\n'
    note = service.save_text(project, actor, first['id'], {'request_id': str(uuid4()), 'identity': str(uuid4()),
        'kind': 'note', 'title': 'Historical original', 'markdown': literal})
    with database.tx(project) as db:
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(LOCAL_USER),))
        saved = db.execute('SELECT body FROM note_versions WHERE note_id=%s', (note['text']['id'],)).fetchone()['body']
    assert saved['content']['content'][0]['content'][0]['text'] == literal


def test_file_permissions_hashes_and_private_notes(database, tmp_path):
    actor, project, service = subject(database)
    storage = ResearchStorage(tmp_path / 'control', repository_root=tmp_path)
    target = storage.register_target(tmp_path / 'experiments', target_id='originals')
    root = Path(target['configuration']['path']) / 'originals'
    root.mkdir(parents=True)
    content = b'{"value":1}\n{"value":2}\n'
    (root / 'process.jsonl').write_bytes(content)
    storage.register_resource('original', storage.locator('originals', 'originals'), writer_mode='sealed')
    database.blobs.storage = storage
    service = ResearchRecords(database)
    identity = register(service, project, actor)
    import hashlib
    evidence = {'request_id': str(uuid4()), 'evidence': {'logical_id': 'process-original', 'label': 'process.jsonl',
        'role': 'process', 'format': 'jsonl', 'byte_count': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
        'locator': {'kind': 'file', 'resource_id': 'original', 'member': 'process.jsonl'}}}
    with pytest.raises(Forbidden):
        service.attach(project, actor, identity, evidence)
    service.grant_resource(project, actor, 'original')
    ref = service.attach(project, actor, identity, evidence)
    assert b''.join(service.chunks(project, actor, ref['id'])) == content
    assert service.preview(project, actor, ref['id'], limit=1)['rows'] == [{'value': 1}]
    assert service.preview(project, actor, ref['id'], offset=1, limit=1)['rows'] == [{'value': 2}]
    text = {'request_id': str(uuid4()), 'identity': str(uuid4()), 'expected_revision': 0, 'kind': 'note',
            'title': 'private title', 'markdown': 'private original'}
    service.save_text(project, actor, identity, text)
    from threemind_lab.auth import create_user
    other = create_user(database, 'other_reader', 'long enough password')
    with database.tx() as db:
        db.execute("INSERT INTO members VALUES(%s,%s,'viewer')", (project, other['id']))
    assert len(service.evidence(project, other, identity)['rows']) == 1
    (root / 'process.jsonl').write_bytes(b'corrupted')
    result = service.verify(project, actor, identity, hashes=True)
    assert result['coverage'] == 'partial'
    assert any(p['kind'] == 'unavailable-evidence' for p in result['problems'])


def test_global_index_backfill_and_api_catalog(database):
    actor, project, service = subject(database)
    second = database.create_project(actor, 'Other research')['id']
    register(service, project, actor)
    register(service, second, actor, source_key='early', original_id='E01')
    register(service, second, actor, source_key='scratch', classification='development')
    preview = {'request_id': str(uuid4()), 'source_manifest_hash': '1' * 64, 'records': [{
        'spec': {'source_key': 'unstarted', 'title': 'Draft not executed', 'classification': 'proposal'},
        'entries': [{'request_id': str(uuid4()), 'kind': 'gap', 'original_key': 'missing',
                     'content': {'reason': 'no original execution trace'}}],
    }]}
    plan = service.backfill_plan(project, actor, preview)
    assert service.list(actor)['total'] == 2
    applied = service.backfill_apply(project, actor, plan['id'], {'request_id': str(uuid4()), 'plan_hash': plan['plan_hash']})
    assert applied['originals_copied'] == 0
    service.backfill_apply(project, actor, plan['id'], {'request_id': str(uuid4()), 'plan_hash': plan['plan_hash']})
    assert service.list(actor)['total'] == 3
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        assert client.get('/api/v2/research-experiments').json()['total'] == 3
        rows = client.get('/api/v2/research-experiments', params={'project': str(second)}).json()['rows']
        assert len(rows) == 1
        ids = {o['id'] for o in client.get('/api/v2/operations/catalog').json()['operations']}
        assert {'records.register', 'records.append', 'records.attach', 'records.backfill_apply', 'records.receipt'} <= ids


def test_durable_recorder_outage_and_resume(database, tmp_path):
    actor, project, service = subject(database)
    recorder = ResearchRecorder(tmp_path / 'experiment', project, service=service, actor=actor)
    recorder.register({'source_key': 'journal', 'title': 'Journal survives interruption', 'executor': 'ai'})
    recorder.append('stage', 'teaching', {'actual': 'original stage preserved'})
    original_register = service.register
    import psycopg
    service.register = lambda *args: (_ for _ in ()).throw(psycopg.OperationalError('database unavailable'))
    assert recorder.synchronize()['pending'] == 2
    assert recorder.status['error'] == 'database unavailable'
    service.register = original_register
    saved = recorder.save_original('observations.txt', b'recorded original\n')
    assert Path(saved['path']).read_bytes() == b'recorded original\n'
    assert recorder.synchronize(strict=True)['pending'] == 0
    resumed = ResearchRecorder(tmp_path / 'experiment', project, service=service, actor=actor)
    resumed.resume_recording()
    assert resumed.experiment == recorder.experiment
    assert resumed.synchronize()['synced'] == 0
    assert len(service.entries(project, actor, recorder.experiment)['rows']) == 1
    with pytest.raises(ValueError):
        recorder.save_original('observations.txt', b'overwritten')


def test_http_sdk_cli_share_receipts_after_lost_response(database, tmp_path, monkeypatch, capsys):
    import json
    from contextlib import nullcontext

    import httpx

    from threemind_lab import records_cli
    from threemind_lab.operations_client import OperationsClient

    actor, project, service = subject(database)
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as transport:
        client = OperationsClient()
        client.client.close()
        client.client = transport
        recorder = ResearchRecorder(tmp_path / 'http', project, client=client)
        identity = recorder.register({'source_key': 'shared-entry', 'title': 'Same research record', 'executor': 'ai'})
        recorder.synchronize(strict=True)
        request = recorder.append('stage', 'actual-stage', {'actual': 'original fact'})
        call = client.call
        lost = False

        def interrupted_call(operation, arguments, **kwargs):
            nonlocal lost
            result = call(operation, arguments, **kwargs)
            if operation == 'records.append' and not lost:
                lost = True
                raise httpx.ReadError('response lost after commit')
            return result

        monkeypatch.setattr(client, 'call', interrupted_call)
        assert recorder.synchronize(strict=True)['pending'] == 0
        assert len(service.entries(project, actor, identity)['rows']) == 1
        monkeypatch.setattr(records_cli, 'connect', lambda _: nullcontext(client))
        records_cli.main(['receipt', '--project', str(project), '--request-id', request])
        receipt = json.loads(capsys.readouterr().out)
        assert UUID(receipt['result']['id']) == service.entries(project, actor, identity)['rows'][0]['id']
        recorder.append('stage', 'actual-stage', {'actual': 'conflicting fact'}, request_id=request)
        with pytest.raises(ValueError, match='different research content'):
            recorder.synchronize(strict=True)
        assert recorder.status['pending'] == 1
        assert service.entries(project, actor, identity)['rows'][0]['content'] == {'actual': 'original fact'}


def test_experiment_bundle_roundtrip_with_original_and_revision_chain(database, tmp_path, monkeypatch):
    import hashlib
    import io
    from tempfile import TemporaryFile
    from types import SimpleNamespace

    from threemind_lab.blob_store import BlobStore
    from threemind_lab.data_bundles import DataBundles
    from threemind_lab.data_catalog import DataCatalog

    storage = ResearchStorage(tmp_path / 'control', repository_root=tmp_path)
    database.blobs = BlobStore(storage)
    target = storage.register_target(tmp_path / 'experiments')
    root = tmp_path / 'experiments' / 'study'
    root.mkdir(parents=True)
    raw = b'original independent scientific bytes\r\n'
    (root / 'original.bin').write_bytes(raw)
    storage.register_resource('study', storage.locator(target['id'], 'study'), writer_mode='sealed')
    actor, project, service = subject(database)
    identity = register(service, project, actor)
    service.grant_resource(project, actor, 'study')
    service.attach(project, actor, identity, {'request_id': str(uuid4()), 'evidence': {
        'logical_id': 'original', 'role': 'process', 'label': 'original.bin', 'format': 'opaque',
        'byte_count': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
        'locator': {'kind': 'file', 'resource_id': 'study', 'member': 'original.bin'}}})
    report = str(uuid4())
    for revision, text in enumerate(('Original negative result', 'Location correction; result unchanged')):
        service.save_text(project, actor, identity, {'request_id': str(uuid4()), 'identity': report,
            'expected_revision': revision, 'kind': 'report', 'title': 'Report', 'markdown': text,
            'revision_reason': 'Source path corrected' if revision else None})
    service.save_text(project, actor, identity, {'request_id': str(uuid4()), 'identity': str(uuid4()),
        'kind': 'note', 'title': 'Private research note', 'markdown': 'Exact personal original'})
    from threemind_lab.protocols import RunSpec
    from threemind_runtime.host import create_engine
    runtime = database.create_run(project, 'Original isolated runtime carrier',
                                  RunSpec(kernel_id='threemind.continuous-memory/3').model_dump())
    image = create_engine(backend='reference', kernel_id='threemind.continuous-memory/3').capture_state()
    database.save_checkpoint(project, runtime['id'], image, expected_revision=0)
    service.attach(project, actor, identity, {'request_id': str(uuid4()), 'evidence': {
        'logical_id': 'runtime-original', 'role': 'subject', 'label': 'Original runtime',
        'format': 'threemind.runtime-run', 'locator': {'kind': 'run', 'id': str(runtime['id'])}}})
    catalog, bundles = DataCatalog(database), DataBundles(database)
    # This tiny record-format fixture is independent of the production 15 GiB
    # scratch reserve, which has its own transfer/space guard coverage.
    monkeypatch.setattr(DataBundles, '_scratch', lambda self: TemporaryFile(dir=tmp_path))  # noqa: SIM115 -- caller owns/uses context
    # Preserve cancellation/lease checks while giving the tiny fixture a scratch
    # probe path independent of this machine's large live-backup reserve.
    monkeypatch.setenv('THREEMIND_SCRATCH_DIR', str(tmp_path / 'unused-host-scratch'))
    plan = catalog.export_plan(project, actor, {'resources': [{'kind': 'experiment', 'id': identity}]})
    assert plan['private']

    def lease(p, job):
        with database.tx(p) as db:
            return db.execute("UPDATE jobs SET status='leased',worker_id='records-test',generation=generation+1,"
                "lease_until=clock_timestamp()+interval '5 minutes' WHERE id=%s RETURNING *", (job['id'],)).fetchone()

    exported = bundles._export_job(SimpleNamespace(db=database), lease(project, bundles.export(project, actor, plan['id'], uuid4())))
    package = b''.join(bundles.chunks(project, actor, exported['bundle_id']))
    destination = database.create_project(actor, 'Imported original research')['id']
    imported = bundles.import_register(destination, actor, io.BytesIO(package), uuid4())
    job = lease(destination, bundles.restore_records(destination, actor, imported['id'], uuid4()))
    restored = bundles._restore_job(SimpleNamespace(db=database), job)
    mapping = next(m for m in restored['mappings'] if m['kind'] == 'experiment')
    original = service.detail(project, actor, identity)
    recovered = service.detail(destination, actor, mapping['new_id'])
    assert recovered['spec']['metadata']['import_origin']['source_id'] == identity
    assert recovered['spec']['conclusion'] == original['spec']['conclusion']
    refs = service.evidence(destination, actor, mapping['new_id'])['rows']
    original_ref = next(r for r in refs if r['logical_id'] == 'original')
    assert b''.join(service.chunks(destination, actor, original_ref['id'])) == raw
    assert {r['document_revision'] for r in refs if r['document_id']} == {1, 2}
    assert any(r['private_actor_id'] for r in refs)
    archived_states = next(r for r in refs if r['role'] == 'archived-runtime' and r['label'].endswith('/state_chunks.jsonl'))
    state_bytes = b''.join(service.chunks(destination, actor, archived_states['id']))
    assert state_bytes
    assert bundles._restore_job(SimpleNamespace(db=database), job)['replayed']
    with database.tx(destination) as db:
        assert db.execute('SELECT count(*) AS n FROM runs').fetchone()['n'] == 0
    repeated_plan = catalog.export_plan(destination, actor, {'resources': [{'kind': 'experiment', 'id': mapping['new_id']}]})
    repeated_export = bundles._export_job(SimpleNamespace(db=database), lease(destination, bundles.export(destination, actor, repeated_plan['id'], uuid4())))
    final_project = database.create_project(actor, 'Reimported intact research')['id']
    final_package = b''.join(bundles.chunks(destination, actor, repeated_export['bundle_id']))
    final_import = bundles.import_register(final_project, actor, io.BytesIO(final_package), uuid4())
    final_result = bundles._restore_job(SimpleNamespace(db=database), lease(final_project, bundles.restore_records(final_project, actor, final_import['id'], uuid4())))
    final_identity = next(m['new_id'] for m in final_result['mappings'] if m['kind'] == 'experiment')
    final_states = next(r for r in service.evidence(final_project, actor, final_identity)['rows'] if r['logical_id'] == archived_states['logical_id'])
    assert b''.join(service.chunks(final_project, actor, final_states['id'])) == state_bytes
    with database.tx(final_project) as db:
        assert db.execute('SELECT count(*) AS n FROM runs').fetchone()['n'] == 0


def test_manual_entry_creates_index_before_job_is_visible(database):
    actor, project, service = subject(database)
    with TestClient(create_app(Settings(database_url=database.test_url), database)) as client:
        reply = client.post(f'/api/v2/projects/{project}/runs', json={'name': 'Manual experiment',
            'spec': {'duration_s': 1}, 'record_executor': 'human'})
        assert reply.status_code == 201, reply.text
        run = reply.json()
        index = service.list(actor)['rows'][0]
        assert index['executor'] == 'human'
        detail = service.detail(project, actor, index['id'])
        assert detail['spec']['metadata']['runtime_id'] == run['id']
        assert any(e['run_id'] == UUID(run['id']) for e in service.evidence(project, actor, index['id'])['rows'])
        temporary = client.post(f'/api/v2/projects/{project}/runs', json={'name': 'Temporary tooling check',
            'spec': {'duration_s': 1}, 'record_executor': 'ai', 'record_classification': 'development'})
        assert temporary.status_code == 201, temporary.text
        assert service.list(actor)['total'] == 1
        assert service.list(actor, classification='development')['total'] == 1


def test_recording_and_verification_do_not_change_same_input_core_trajectory(database, tmp_path):
    from threemind_core import Stimulus
    from threemind_runtime.host import create_engine

    actor, project, service = subject(database)
    journal = ResearchRecorder(tmp_path / 'trajectory', project, service=service, actor=actor)
    identity = journal.register({'source_key': 'isolated-invariance', 'title': 'Engineering invariant',
                                 'executor': 'ai', 'classification': 'development'})
    journal.synchronize(strict=True)
    baseline = create_engine(backend='reference', kernel_id='threemind.continuous-memory/4')
    recorded = create_engine(backend='reference', kernel_id='threemind.continuous-memory/4')
    for step, time in enumerate((0, 100000, 230000, 400000)):
        for engine in (baseline, recorded):
            engine.inject(Stimulus(time, ((11, 0.8), (12, 0.3))))
            engine.advance_to(time + 50000)
        journal.append('stage', str(step), {'original_input_time_us': str(time)})
        journal.synchronize(strict=True)
        service.verify(project, actor, identity)
        assert baseline.capture_state().digest == recorded.capture_state().digest


def test_large_verification_has_bounded_durable_summary(database, monkeypatch):
    actor, project, service = subject(database)
    identity = register(service, project, actor)
    verification = {'experiment_id': identity, 'execution_status': 'completed', 'coverage': 'indexed',
                    'hashes_checked': False, 'problems': [], 'referenced_bytes': 0,
                    'evidence': [{'id': str(uuid4()), 'logical_id': 'original-' + 'x' * 300} for _ in range(10000)]}
    monkeypatch.setattr(service, 'verify', lambda *args, **kwargs: verification)
    result = service.finalize(project, actor, identity, {'request_id': str(uuid4())})
    assert result['finalized']
    summary = service.detail(project, actor, identity)['latest_verification']['content']
    assert summary['evidence_checked'] == 10000
    assert 'evidence' not in summary


def test_historical_adapter_retries_fixed_preview_without_recounting_new_texts(database, tmp_path, monkeypatch):
    from lab.tools import historical_record_backfill as adapter
    from lab.tools import historical_record_inventory as inventory
    from threemind_lab.blob_store import BlobStore
    monkeypatch.setattr(adapter, 'ROOT', tmp_path)
    monkeypatch.setattr(inventory, 'ROOT', tmp_path)
    database.blobs = BlobStore(ResearchStorage(tmp_path / 'control', repository_root=tmp_path))
    root = tmp_path / 'lab' / 'explorations' / 'historical'
    root.mkdir(parents=True)
    (root / 'protocol.md').write_text('Original protocol\n', encoding='utf-8')
    (root / 'report.zh.md').write_text('Original negative result\n', encoding='utf-8')
    (root / 'execution.md').write_text('[Original citation](protocol.md)\n', encoding='utf-8')
    source = {'source_key': 'adapter-original', 'source_path': root.relative_to(tmp_path).as_posix(),
        'project_id': None, 'original_id': 'Original-1', 'title': 'Original evidence', 'classification': 'formal',
        'execution_status': 'unknown', 'experiment_date': '2026-07-25', 'date_basis': 'original notebook',
        'execution_basis': 'Original report', 'design': 'protocol.md', 'report': 'report.zh.md',
        'work_roots': [], 'kernels': [], 'files': [inventory.file_identity(p) | {'role': inventory.role(p)}
                                                for p in root.iterdir()]}
    out = tmp_path / 'backfill'
    adapter.backfill_one(database, source, '2' * 64, out / 'preview', preview_only=True)
    first = adapter.backfill_one(database, source, '2' * 64, out / 'apply')

    def committed_batch_must_not_repeat(*args, **kwargs):
        raise AssertionError('A completed batch must resume its committed receipt')

    monkeypatch.setattr(ResearchRecords, 'attach', committed_batch_must_not_repeat)
    monkeypatch.setattr(ResearchRecords, 'verify', committed_batch_must_not_repeat)
    # The database completion receipt also survives loss of the local receipt.
    (out / 'apply' / (adapter.digest(source['source_key'])[:24] + '.receipt.json')).unlink()
    second = adapter.backfill_one(database, source, '2' * 64, out / 'apply')
    assert first['id'] == second['id']
    assert second['replayed_verification'] is True
    service = ResearchRecords(database)
    assert service.list({'id': LOCAL_USER})['total'] == 1
    with database.tx(first['project_id']) as db:
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(LOCAL_USER),))
        assert db.execute('SELECT count(*) AS n FROM research_document_versions').fetchone()['n'] == 2
        assert db.execute('SELECT count(*) AS n FROM note_versions').fetchone()['n'] == 2
        assert db.execute('SELECT count(*) AS n FROM runs').fetchone()['n'] == 0
    original_receipt = ResearchRecords.receipt

    def conflicting_receipt(self, *args, **kwargs):
        return original_receipt(self, *args, **kwargs) | {'fingerprint': '0' * 64}

    monkeypatch.setattr(ResearchRecords, 'receipt', conflicting_receipt)
    with pytest.raises(Conflict, match='completed backfill receipt'):
        adapter.backfill_one(database, source, '2' * 64, out / 'apply')
