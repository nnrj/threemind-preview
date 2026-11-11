"""Authorized recovery tooling with a synthetic subject, never a formal organism."""
import copy
import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from threemind_lab.record_schema import AppendRecord, AttachRecord
from threemind_lab.research_records import digest
from threemind_lab.storage_files import StorageBusy, file_lock

HERE = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color'


def modules(monkeypatch):
    result = {}
    for name in ('journal', 'continuation'):
        spec = importlib.util.spec_from_file_location('e69_continuation_test_' + name, HERE / (name + '.py'))
        value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
        monkeypatch.setitem(sys.modules, name, value); result[name] = value
    return result['journal'], result['continuation']


class Storage:
    @contextmanager
    def writer(self, _resource):
        yield


class API:
    def __init__(self):
        self.saved = {}

    def close(self):
        pass

    def call(self, operation, parameters, *, request_id=None):
        action = operation.removeprefix('records.')
        body = {'append': AppendRecord, 'attach': AttachRecord}[action].model_validate(parameters['body']).model_dump(mode='json')
        fingerprint = digest({'action': action, 'body': body})
        if request_id in self.saved:
            assert self.saved[request_id]['fingerprint'] == fingerprint
            return self.saved[request_id]['result']
        result = {'content_hash': digest(body['evidence'] if action == 'attach' else body['content']), 'id': request_id}
        self.saved[request_id] = {'fingerprint': fingerprint, 'body': body, 'result': result}
        return result


def fixture(tmp_path, monkeypatch):
    j, c = modules(monkeypatch)
    original = tmp_path / 'original'; original.mkdir()
    state = {'identity': 'engineering-e69', 'time_us': 0, 'history': [],
             'learning': {'motor': {'computed_updates': 0, 'committed_updates': 0},
                          'words': {'computed_updates': 0, 'committed_updates': 0}}, 'refs': []}

    def describe(system):
        return {key: copy.deepcopy(system[key]) for key in ('identity', 'time_us', 'learning')}

    def save(system, folder):
        folder.mkdir()
        (folder / 'complete.json').write_bytes(j.encoded(describe(system)))
        (folder / 'system.json').write_bytes(j.encoded(system))
        (folder / 'dependencies.json').write_bytes(j.encoded({'corpora': system['refs']}))

    def restore(folder):
        return j.read(folder / 'system.json')

    ledger = j.BoundaryJournal(original / 'subject', state['identity'], save, restore, describe,
                              work=original, reserve_gib=0, reserve_memory_gib=0)
    ledger.open_current(lambda: state)

    def teach(system):
        system['time_us'] = 50000; system['history'].append('actual initial experience')
        j.fixed_json(original / 'stages/gaze-initial/units/000000.json', {'start_us': 0, 'end_us': 50000})
        j.put(original / 'stages/gaze-initial/clips/000000.json.gz', b'synthetic original teaching bytes')

    ledger.execute('gaze-initial:000000', teach)
    j.fixed_json(original / 'stages/gaze-initial/tasks.json', [{'id': 'teaching'}])
    j.fixed_json(original / 'stages/gaze-initial/start.json', {'time_us': 0})
    j.fixed_json(original / 'stages/gaze-initial/result.json', {'start_us': 0, 'end_us': 50000})

    def calibrate(system):
        system['time_us'] = 100000; system['history'].append('actual calibration experience')
        sample = original / 'stages/gaze-cal-1/samples/000057.npz'
        j.put(sample, b'immutable synthetic calibration original')
        system['refs'].append({'path': sample.relative_to(original).as_posix(), 'sha256': j.sha(sample)})
        j.fixed_json(original / 'stages/gaze-cal-1/units/000057.json', {'start_us': 50000, 'end_us': 100000})
        j.put(original / 'stages/gaze-cal-1/clips/000057.json.gz', b'synthetic calibration process')
        j.fixed_json(original / 'stages/gaze-cal-1/samples/000057.json', {'ref': system['refs'][-1]})

    ledger.execute('gaze-cal-1:000057', calibrate)
    j.fixed_json(original / 'stages/gaze-cal-1/tasks.json', [{'id': '57'}, {'id': '58'}])
    j.fixed_json(original / 'stages/gaze-cal-1/start.json', {'time_us': 50000})
    j.fixed_json(original / 'subject/in-flight.json', {'key': 'gaze-cal-1:000058',
                 'parent': ledger.pointer['boundary_sha256'], 'start_us': 100000, 'pid': 123})
    j.fixed_json(original / 'stages/gaze-cal-1/units/000058.json', {'start_us': 100000, 'end_us': 150000})
    for name in ('clips/000058.json.gz', 'samples/000058.npz', 'samples/000058.json'):
        j.put(original / 'stages/gaze-cal-1' / name, b'original interrupted experience, retained')
    (original / 'subject/boundaries/000003.partial').mkdir()
    (original / 'STOP').touch()
    j.fixed_json(original / 'design.json', {'kernel_id': j.KERNEL, 'subject_identity': state['identity']})
    j.fixed_json(original / 'questions.json', {'frozen': 'questions'})
    j.fixed_json(original / 'curriculum-manifest.json', {})
    j.fixed_json(original / 'curricula/gaze-initial.json', [{'id': 'teaching'}])
    relative = (HERE.relative_to(HERE.parents[2]) / 'journal.py').as_posix()
    j.put(original / 'source-reference' / relative, (HERE / 'journal.py').read_bytes())
    j.fixed_json(original / 'source-reference/manifest.json', {relative: j.sha(HERE / 'journal.py')})
    j.fixed_json(original / 'platform.json', {'project_id': '47722b08-aa4b-4565-99af-c45b4700398c',
                 'manifest_sha256': j.sha(original / 'source-reference/manifest.json')})
    j.fixed_json(original / '.research-records/identity.json', {
        'project': '47722b08-aa4b-4565-99af-c45b4700398c', 'experiment': '69533969-d871-454a-86ba-f1999435f4a0',
        'source_key': j.SOURCE})
    monkeypatch.setattr(c, 'AUTHORIZED', {'sequence': 2, 'time_us': 100000, 'experienced_end_us': 150000,
                       'boundary_sha256': ledger.pointer['boundary_sha256'], 'identity': state['identity'],
                       'interrupted_key': 'gaze-cal-1:000058'})
    return j, c, original, save, restore, describe


def test_prepare_links_only_complete_prefix_and_copies_controls(tmp_path, monkeypatch):
    j, c, original, *_ = fixture(tmp_path, monkeypatch)
    before = {p.relative_to(original).as_posix(): j.sha(p) for p in original.rglob('*') if p.is_file()}
    receipt = c.prepare(original, authorization_note='synthetic explicit authorization', storage=Storage())
    work = original / 'continuations/r1'
    assert receipt == c.prepare(original, authorization_note='synthetic explicit authorization', storage=Storage())
    assert not (work / 'STOP').exists() and not (work / 'subject/in-flight.json').exists()
    assert not (work / 'stages/gaze-cal-1/units/000058.json').exists()
    assert not (work / 'subject/boundaries/000003.partial').exists()
    assert os.path.samefile(original / 'stages/gaze-cal-1/samples/000057.npz', work / 'stages/gaze-cal-1/samples/000057.npz')
    for name in ('subject/latest.json', 'platform.json', '.research-records/identity.json'):
        assert not os.path.samefile(original / name, work / name)
        assert (original / name).read_bytes() == (work / name).read_bytes()
    assert all(j.sha(original / name) == sha for name, sha in before.items())
    assert j.read(work / 'continuation-envelope.json')['authorized_rollback_count'] == 1
    assert not list((work / '.research-records').glob('pending/*.json'))


def test_prepare_interruption_resumes_same_plan_only(tmp_path, monkeypatch):
    _, c, original, *_ = fixture(tmp_path, monkeypatch)
    link = c.os.link; calls = []

    def fail_once(source, target):
        calls.append(str(source))
        if len(calls) == 5:
            raise OSError('synthetic interruption')
        return link(source, target)

    monkeypatch.setattr(c.os, 'link', fail_once)
    with pytest.raises(OSError, match='synthetic interruption'):
        c.prepare(original, authorization_note='explicit', storage=Storage())
    monkeypatch.setattr(c.os, 'link', link)
    work = original / 'continuations/r1'
    assert not (work / '.continuation/prepared.json').exists()
    c.prepare(original, authorization_note='explicit', storage=Storage())
    with pytest.raises(ValueError, match='conflict'):
        c.prepare(original, authorization_note='different authorization', storage=Storage())


def test_unknown_attempt_files_and_corrupt_dependency_are_rejected(tmp_path, monkeypatch):
    j, c, original, *_ = fixture(tmp_path, monkeypatch)
    work = original / 'continuations/r1'
    j.fixed_json(work / 'stages/other/result.json', {'untrusted': True})
    with pytest.raises(ValueError, match='unrecognized'):
        c.prepare(original, authorization_note='explicit', storage=Storage())
    (work / 'stages/other/result.json').unlink()
    (original / 'stages/gaze-cal-1/samples/000057.npz').write_bytes(b'changed')
    with pytest.raises(ValueError, match='dependency'):
        c.prepare(original, authorization_note='explicit', storage=Storage())


def make_study(c, work, client):
    value = c.ContinuationStudy(work, client=client, storage=Storage())
    value.verify_sources = lambda: c.verify_sources(work.parents[1])
    return value


def test_record_namespace_preserves_e69_identity_and_attachment_roles(tmp_path, monkeypatch):
    j, c, original, *_ = fixture(tmp_path, monkeypatch)
    c.prepare(original, authorization_note='explicit', storage=Storage())
    work = original / 'continuations/r1'; client = API(); study = make_study(c, work, client)
    study.append('stage', 'gaze-initial', {'end_us': 50000})
    study.append('subject', 'blank-5.1', {'full_continuity': True})
    study.attach(work / 'design.json', 'protocol', 'birth')
    study.sync(strict=True)
    count = len(client.saved)
    study.attach(work / 'design.json', 'process')
    study.sync(strict=True)
    assert len(client.saved) == count
    rows = [v['body'] for v in client.saved.values()]
    evidence = next(v['evidence'] for v in rows if 'evidence' in v)
    assert evidence['logical_id'] == 'file:continuations/r1/design.json'
    assert evidence['locator']['member'] == 'continuations/r1/design.json'
    assert evidence['role'] == 'protocol' and evidence['stage_key'] == 'continuation:r1:birth'
    stage = next(v for v in rows if v.get('kind') == 'stage')
    assert stage['original_key'] == 'continuation:r1:gaze-initial'
    assert stage['content']['reused_committed_prefix']
    subject = next(v['content'] for v in rows if v.get('kind') == 'subject')
    assert subject['full_continuity'] is False and subject['frozen_runner_full_continuity'] is True
    assert study.recorder.experiment == j.read(original / '.research-records/identity.json')['experiment']


def test_run_restores_latest_once_with_guard_and_truthful_envelope(tmp_path, monkeypatch):
    j, c, original, save, restore, describe = fixture(tmp_path, monkeypatch)
    c.prepare(original, authorization_note='explicit rollback then continue', storage=Storage())
    work = original / 'continuations/r1'; client = API(); events = []

    @contextmanager
    def watch(target):
        assert target == work
        events.append('guard-ready'); yield; events.append('guard-closed')

    class Runner:
        def __init__(self, study):
            assert events == ['guard-ready']
            assert any(v['body'].get('original_key') == 'continuation:r1:authorized-restoration' for v in client.saved.values())
            self.ledger = j.BoundaryJournal(work / 'subject', 'engineering-e69', save, restore, describe,
                                           work=work, reserve_gib=0, reserve_memory_gib=0)
            self.state = self.ledger.open_current(lambda: pytest.fail('must not rebirth'))
            assert self.state['history'] == ['actual initial experience', 'actual calibration experience']

        def run(self):
            def experience(system):
                system['time_us'] = 150000; system['history'].append('authorized replay as separate attempt')
                j.fixed_json(work / 'stages/gaze-cal-1/units/000058.json', {'new_attempt': True})
            self.ledger.execute('gaze-cal-1:000058', experience)
            j.fixed_json(work / 'computation-complete.json', {'latest': self.ledger.pointer,
                         'time_us': 150000, 'rollback_count': 0})

    value = c.run(work, study_factory=lambda path: make_study(c, path, client), runner_factory=Runner, watch=watch)
    assert value['authorized_rollback_count'] == 1 and value['frozen_runner_rollback_count'] == 0
    assert events == ['guard-ready', 'guard-closed']
    assert j.read(original / 'subject/latest.json')['end_us'] == 100000
    assert j.read(original / 'stages/gaze-cal-1/units/000058.json')['end_us'] == 150000
    assert j.read(work / 'stages/gaze-cal-1/units/000058.json') == {'new_attempt': True}
    assert j.read(work / 'continuation-status.json')['phase'] == 'awaiting-continuation-postprocessing'
    c.run(work, study_factory=lambda path: make_study(c, path, client),
          runner_factory=lambda *_: pytest.fail('complete subject must not load'), watch=lambda *_: pytest.fail('no guard needed'))


def test_guard_failure_does_not_load_subject_or_clear_marker(tmp_path, monkeypatch):
    j, c, original, *_ = fixture(tmp_path, monkeypatch)
    c.prepare(original, authorization_note='explicit', storage=Storage())
    work = original / 'continuations/r1'; client = API()

    @contextmanager
    def failure(_work):
        raise RuntimeError('guard unsafe')
        yield

    with pytest.raises(RuntimeError, match='guard unsafe'):
        c.run(work, study_factory=lambda path: make_study(c, path, client),
              runner_factory=lambda *_: pytest.fail('must not load'), watch=failure)
    assert j.read(work / 'subject/latest.json')['end_us'] == 100000
    assert (original / 'subject/in-flight.json').exists()
    j.fixed_json(work / 'subject/in-flight.json', {'key': 'uncertain new attempt'})
    with pytest.raises(ValueError, match='uncommitted'):
        c.run(work, study_factory=lambda path: make_study(c, path, client), runner_factory=lambda *_: pytest.fail('must not load'), watch=failure)


def test_original_writer_lock_prevents_preparation(tmp_path, monkeypatch):
    _, c, original, *_ = fixture(tmp_path, monkeypatch)
    with file_lock(original / 'runner.lock'), pytest.raises(StorageBusy):
        c.prepare(original, authorization_note='explicit', storage=Storage())
