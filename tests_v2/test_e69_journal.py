"""Isolated continuity and publication guards; no Core or real Lab database."""
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color/journal.py'
spec = importlib.util.spec_from_file_location('e69_journal_test_module', PATH)
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


def blank():
    return {'identity': 'engineering-e69', 'time_us': 0, 'nodes': 0, 'edges': 0,
            'learning': {'motor': {'computed_updates': 0, 'committed_updates': 0},
                         'words': {'computed_updates': 0, 'committed_updates': 0}},
            'body': {'eye': [0, 0], 'hand': [0, 0]}, 'history': [], 'rng': 223}


def save(system, folder):
    folder.mkdir()
    (folder / 'system.json').write_bytes(journal.encoded(system))


def open_journal(tmp_path, **kwargs):
    return journal.BoundaryJournal(
        tmp_path / 'subject', 'engineering-e69', kwargs.get('save', save), journal.read,
        copy.deepcopy, work=tmp_path, reserve_gib=0, reserve_memory_gib=0)


def new_journal(tmp_path, **kwargs):
    value = open_journal(tmp_path, **kwargs)
    value.restore_system = lambda folder: journal.read(folder / 'system.json')
    return value


def advance(system):
    system['time_us'] += 50000
    system['body']['eye'][0] += .1
    system['history'].append(system['time_us'])
    system['rng'] += 1
    return 'advanced'


def test_current_restore_keeps_whole_state_and_next_response(tmp_path):
    first = new_journal(tmp_path)
    first.open_current(blank)
    first.execute('q0', advance)
    resumed = new_journal(tmp_path)
    resumed.open_current(lambda: pytest.fail('must not rebirth'))
    assert resumed.system == first.system
    expected = copy.deepcopy(first.system)
    advance(expected)
    assert resumed.execute('q1', advance) == 'advanced'
    assert resumed.system == expected
    assert resumed.pointer['start_us'] == 50000
    assert resumed.pointer['end_us'] == 100000


def test_failed_operation_remains_dirty_and_blocks_replay(tmp_path):
    value = new_journal(tmp_path)
    value.open_current(blank)

    def fail(system):
        advance(system)
        raise RuntimeError('lost current operation')

    with pytest.raises(RuntimeError):
        value.execute('failed', fail)
    assert value.flight.exists()
    with pytest.raises(journal.ContinuityUncertain):
        new_journal(tmp_path).open_current(blank)
    with pytest.raises(journal.ContinuityUncertain):
        value.execute('retry', advance)
    assert journal.read(value.latest)['end_us'] == 0


def test_failed_save_keeps_dirty_evidence_and_current_pointer(tmp_path):
    def writer(system, folder):
        save(system, folder)
        if system['time_us']:
            raise OSError('disk unavailable')

    value = new_journal(tmp_path, save=writer)
    value.open_current(blank)
    with pytest.raises(OSError):
        value.execute('q0', advance)
    assert value.flight.exists()
    assert (tmp_path / 'subject/boundaries/000001/system.json').exists()
    assert journal.read(value.latest)['sequence'] == 0


def test_duplicate_operation_cannot_advance_subject(tmp_path):
    value = new_journal(tmp_path)
    value.open_current(blank)
    value.execute('q0', advance)
    with pytest.raises(ValueError, match='already committed'):
        value.execute('q0', advance)
    assert value.system['time_us'] == 50000


def test_stop_boundary_does_not_write_inflight_or_advance(tmp_path):
    value = new_journal(tmp_path)
    value.open_current(blank)
    (tmp_path / 'STOP').write_text('pause')
    with pytest.raises(journal.BoundaryPause):
        value.execute('q0', advance)
    assert not value.flight.exists()
    assert value.system['time_us'] == 0


def test_calibration_can_hold_clock_but_cannot_rollback_learning(tmp_path):
    value = new_journal(tmp_path)
    value.open_current(blank)

    def fit(system):
        system['learning']['motor'] = {'computed_updates': 100, 'committed_updates': 100}

    value.execute('fit0', fit)
    assert value.pointer['start_us'] == value.pointer['end_us'] == 0
    with pytest.raises(journal.ContinuityUncertain):
        value.execute('rollback', lambda system: system['learning']['motor'].update(committed_updates=50))
    assert value.flight.exists()


def test_corrupt_current_snapshot_and_unjournaled_state_are_rejected(tmp_path):
    value = new_journal(tmp_path)
    value.open_current(blank)
    value.system['body']['eye'][0] = .4
    with pytest.raises(journal.ContinuityUncertain, match='outside'):
        value.execute('q0', advance)
    assert not value.flight.exists()
    (tmp_path / 'subject/boundaries/000000/system.json').write_text('{}')
    with pytest.raises(journal.ContinuityUncertain, match='changed or is missing'):
        new_journal(tmp_path).open_current(blank)


def test_stale_writer_cannot_submit_after_other_writer(tmp_path):
    first = new_journal(tmp_path)
    first.open_current(blank)
    other = new_journal(tmp_path)
    other.open_current(blank)
    first.execute('q0', advance)
    with pytest.raises(journal.ContinuityUncertain, match='another writer'):
        other.execute('q1', advance)


def test_missing_current_pointer_cannot_create_replacement_subject(tmp_path):
    (tmp_path / 'subject').mkdir()
    (tmp_path / 'subject/partial.json').write_text('{}')
    with pytest.raises(journal.ContinuityUncertain, match='cannot rebirth'):
        new_journal(tmp_path).open_current(blank)


def test_recording_queues_durably_during_auth_failure_without_subject_work(tmp_path):
    from threemind_lab.record_schema import RegisterRecord
    from threemind_lab.research_recorder import ResearchRecorder

    class Offline:
        def call(self, *_args, **_kwargs):
            raise ValueError('authentication expired')

    record = ResearchRecorder(tmp_path, '5c89e028-d08f-4f91-aae0-8b369cb5a64e', client=Offline())
    request = '1c9a919b-7f43-4fc5-a657-164116a998f7'
    record.register({'source_key': 'engineering:e69-journal', 'title': 'engineering only'}, request_id=request)
    result = record.synchronize()
    assert result['pending'] == 1
    assert result['error'] == 'authentication expired'
    pending = json.loads((tmp_path / '.research-records/pending' / (request + '.json')).read_bytes())
    RegisterRecord.model_validate(pending['body'])
    resumed = ResearchRecorder(tmp_path, '5c89e028-d08f-4f91-aae0-8b369cb5a64e', client=Offline())
    assert resumed.resume_recording() == record.experiment


def prepare_fixture(tmp_path, monkeypatch):
    from threemind_lab import provenance
    from threemind_lab.record_schema import AttachRecord, RegisterRecord, SaveRecordText

    root = tmp_path / 'repository'
    here = root / 'lab/explorations/engineering-e69'
    here.mkdir(parents=True)
    for lang in ('zh', 'en'):
        path = root / 'docs' / lang / 'training-protocol.md'
        path.parent.mkdir(parents=True)
        path.write_text('engineering protocol')
        (here / f'design.{lang}.md').write_text('engineering study')
    design = here / 'design.json'
    design.write_text(json.dumps({'title': 'engineering E69', 'kernel_id': journal.KERNEL}))
    monkeypatch.setattr(journal, 'ROOT', root)
    monkeypatch.setattr(journal, 'HERE', here)
    monkeypatch.setattr(provenance, 'capture_implementation', lambda _: {'source_files': []})

    class Storage:
        def writable_root(self):
            return tmp_path / 'data'

    class Client:
        def __init__(self):
            self.rows, self.projects, self.resources, self.saved = [], [], [], {}
            self.created_projects = self.created_resources = 0
            self.read_calls = []

        def request(self, verb, endpoint, **kwargs):
            if endpoint == '/api/v2/me':
                return {'id': 'engineering'}
            if endpoint == '/api/v2/projects':
                if verb == 'GET':
                    return self.projects
                self.created_projects += 1
                self.projects.append({'id': '5c89e028-d08f-4f91-aae0-8b369cb5a64e', **kwargs['body']})
                return self.projects[-1]
            if endpoint == '/api/v2/storage':
                return {'targets': [{'id': 'managed-research-experiments',
                                     'configuration': {'path': str(Storage().writable_root() / 'experiments')}}],
                        'resources': self.resources}
            if endpoint == '/api/v2/storage/resources':
                self.created_resources += 1
                self.resources.append({'id': kwargs['body']['resource_id'], **kwargs['body']})
                return self.resources[-1]
            if endpoint == '/api/v2/storage/record-evidence-grants':
                return {'granted': True}
            raise AssertionError(endpoint)

        def call(self, operation, parameters, **kwargs):
            if operation == 'records.list':
                self.read_calls.append(operation)
                return {'rows': self.rows}
            schemas = {'records.register': RegisterRecord, 'records.attach': AttachRecord,
                       'records.text': SaveRecordText}
            schemas[operation].model_validate(parameters['body'])
            key = operation, kwargs['request_id']
            if key in self.saved:
                assert self.saved[key] == parameters
            self.saved[key] = copy.deepcopy(parameters)
            if operation == 'records.register':
                self.rows = [parameters['body']['spec']]
            return {'saved': True}

        def close(self):
            pass

    return here, Storage().writable_root() / 'experiments' / here.name, Client(), Storage()


def test_prepare_validates_e69_conflict_and_does_not_create_subject(tmp_path, monkeypatch):
    here, work, client, storage = prepare_fixture(tmp_path, monkeypatch)
    client.rows = [{'original_id': 'E69', 'source_key': 'different:study'}]
    with pytest.raises(ValueError, match='already assigned'):
        journal.ResearchStudy(work, here / 'design.json', prepare=True, client=client, storage=storage)
    assert client.created_projects == 0
    assert not work.exists()


def test_prepare_and_repeat_use_canonical_idempotent_requests(tmp_path, monkeypatch):
    here, work, client, storage = prepare_fixture(tmp_path, monkeypatch)
    study = journal.ResearchStudy(work, here / 'design.json', prepare=True, client=client, storage=storage)
    assert study.recorder.status['pending'] == 0
    assert not (work / 'subject').exists()
    count = len(client.saved)
    repeated = journal.ResearchStudy(work, here / 'design.json', prepare=True, client=client, storage=storage)
    assert repeated.recorder.experiment == study.recorder.experiment
    assert len(client.saved) == count
    assert client.created_projects == client.created_resources == 1
    assert len(client.read_calls) == 2
    (here / 'design.zh.md').write_text('changed protocol')
    with pytest.raises(ValueError, match='source changed'):
        study.verify_sources()


def test_native_binary_change_rejected_even_when_frozen_sources_are_unchanged(tmp_path, monkeypatch):
    from threemind_lab import provenance

    here, work, client, storage = prepare_fixture(tmp_path, monkeypatch)
    current = {'source_files': [], 'native_binary_sha256': 'a' * 64}
    monkeypatch.setattr(provenance, 'capture_implementation', lambda _: copy.deepcopy(current))
    study = journal.ResearchStudy(work, here / 'design.json', prepare=True, client=client, storage=storage)
    study.verify_sources()
    sources_before = journal.read(work / 'source-reference/manifest.json')
    current['native_binary_sha256'] = 'b' * 64
    with pytest.raises(ValueError, match='frozen execution environment changed: native_binary_sha256'):
        study.verify_sources()
    assert journal.read(work / 'source-reference/manifest.json') == sources_before
    assert not (work / 'subject').exists()


def test_registered_without_local_identity_never_recreates_subject(tmp_path, monkeypatch):
    here, work, client, storage = prepare_fixture(tmp_path, monkeypatch)
    client.rows = [{'original_id': 'E69', 'source_key': journal.SOURCE}]
    with pytest.raises(journal.ContinuityUncertain, match='local identity is missing'):
        journal.ResearchStudy(work, here / 'design.json', prepare=True, client=client, storage=storage)
    assert client.created_projects == 0


def load_sibling(name, monkeypatch):
    monkeypatch.setitem(sys.modules, 'journal', journal)
    module_spec = importlib.util.spec_from_file_location('e69_' + name, PATH.with_name(name + '.py'))
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_publisher_refuses_partial_subject_and_unreviewed_result(tmp_path, monkeypatch):
    publish = load_sibling('publish', monkeypatch)

    class Study:
        work = tmp_path

        def attach(self, *_args, **_kwargs):
            pytest.fail('must not publish before verification')

    study = Study()
    with pytest.raises(ValueError, match='unfinished'):
        publish.publish(study, 'originals')
    (tmp_path / 'computation-complete.json').write_text('{}')
    (tmp_path / 'subject').mkdir()
    (tmp_path / 'subject/in-flight.json').write_text('{}')
    with pytest.raises(ValueError, match='uncommitted'):
        publish.publish(study, 'originals')
    (tmp_path / 'subject/in-flight.json').unlink()
    with pytest.raises(ValueError, match='review receipt required'):
        publish.publish(study, 'reports')


def test_status_reads_publication_and_never_creates_subject(tmp_path, monkeypatch):
    status_module = load_sibling('status', monkeypatch)
    monkeypatch.setattr(status_module.psutil, 'process_iter', lambda *_args: iter(()))
    work = tmp_path / 'does-not-exist'
    value = status_module.status(work)
    assert value['exists'] is False
    assert value['pending'] == 0
    assert not work.exists()
    work.mkdir()
    (work / 'publication-status.json').write_text(json.dumps({'phase': 'completed'}))
    before = sorted(str(p) for p in work.rglob('*'))
    value = status_module.status(work)
    assert value['publication']['phase'] == 'completed'
    assert sorted(str(p) for p in work.rglob('*')) == before
