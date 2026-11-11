"""Repair frozen publisher requests with synthetic originals and an in-memory API."""
import copy
import importlib.util
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from threemind_lab.record_schema import AppendRecord, AttachRecord
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.research_records import digest
from threemind_lab.storage_files import StorageBusy, file_lock

HERE = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color'


def modules(monkeypatch):
    values = {}
    for name in ('journal', 'pipeline', 'publish', 'publish_resume'):
        spec = importlib.util.spec_from_file_location('e69_repair_test_' + name, HERE / (name + '.py'))
        value = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(value)
        monkeypatch.setitem(sys.modules, name, value)
        values[name] = value
    return values


class API:
    def __init__(self):
        self.saved, self.requests = {}, []
        self.wrong_receipt = False

    def call(self, operation, parameters, *, request_id=None):
        self.requests.append(operation)
        if operation == 'records.receipt':
            receipt = copy.deepcopy(self.saved[parameters['path']['request_id']])
            if self.wrong_receipt:
                receipt['fingerprint'] = 'not-the-committed-request'
            return receipt
        action = operation.removeprefix('records.')
        schema = {'attach': AttachRecord, 'append': AppendRecord}[action]
        body = schema.model_validate(parameters['body']).model_dump(mode='json')
        value = {'id': parameters['path']['experiment'], **body}
        fingerprint = digest({'action': action, 'value': value})
        if request_id in self.saved:
            if self.saved[request_id]['fingerprint'] != fingerprint:
                raise ValueError('record request ID belongs to different content')
            return {**self.saved[request_id]['result'], 'replayed': True}
        result = {'id': str(uuid5(UUID(value['id']), request_id)),
                  'content_hash': digest(body['evidence'] if action == 'attach' else body['content'])}
        self.saved[request_id] = {'action': action, 'fingerprint': fingerprint, 'result': result}
        return {**result, 'replayed': False}


class Storage:
    @contextmanager
    def writer(self, _resource):
        yield


def study_fixture(work, m):
    j = m['journal']

    class Study:
        attach, append = j.ResearchStudy.attach, j.ResearchStudy.append
        rid = j.ResearchStudy.rid

        def __init__(self):
            self.work, self.project = work, '47722b08-aa4b-4565-99af-c45b4700398c'
            self.client, self.storage = API(), Storage()
            self.recorder = ResearchRecorder(work, self.project, client=self.client)
            self.recorder.experiment = '69533969-d871-454a-86ba-f1999435f4a0'

        def sync(self, *, strict=False):
            return self.recorder.synchronize(strict=strict)

    study = Study()
    work.mkdir(exist_ok=True)
    latest = {'boundary_sha256': 'engineering-only-current-boundary', 'end_us': 100000}
    j.fixed_json(work / 'subject/latest.json', latest)
    j.fixed_json(work / 'computation-complete.json', {'latest': latest, 'time_us': 100000})
    j.fixed_json(work / 'analysis/verified-results.json', {'last_boundary': latest['boundary_sha256'], 'continuous': True})
    j.put(work / 'replays/engineering.mp4', b'not-media; synthetic receipt fixture only')
    j.fixed_json(work / 'replays/export.json', {
        'video': 'replays/engineering.mp4', 'sha256': j.sha(work / 'replays/engineering.mp4'),
        'activity_curves': ['activation', 'inhibition', 'direct', 'associative'],
        'core_advanced': False, 'full_decode_verified': True})
    manifest = {}
    for name in ('journal.py', 'publish.py', 'pipeline.py'):
        rel = (HERE.relative_to(HERE.parents[2]) / name).as_posix()
        j.put(work / 'source-reference' / rel, (HERE / name).read_bytes())
        manifest[rel] = j.sha(HERE / name)
    j.fixed_json(work / 'source-reference/manifest.json', manifest)
    j.fixed_json(work / 'platform.json', {'manifest_sha256': j.sha(work / 'source-reference/manifest.json')})
    original = work / 'a-original.json'
    j.fixed_json(original, {'fixture': 'science-original-unchanged'})
    study.attach(original, 'protocol', 'initial-teaching')
    study.sync(strict=True)
    return study, original


def test_frozen_publisher_failure_is_repaired_without_metadata_rewrite(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    study, original = study_fixture(tmp_path, m)
    request_id = study.rid('file:a-original.json')
    committed = copy.deepcopy(study.client.saved[request_id])
    original_bytes = original.read_bytes()
    source_hashes = {name: m['journal'].sha(HERE / name) for name in ('journal.py', 'publish.py', 'pipeline.py')}
    with pytest.raises(ValueError, match='different research content'):
        m['publish'].publish(study, 'originals')
    pending = study.recorder.control / 'pending' / (request_id + '.json')
    rejected = pending.read_bytes()
    result = m['publish_resume'].resume_publication(study)
    assert result['status']['pending'] == 0
    assert result['this_invocation']['conflicting_pending_archived'] >= 1
    assert not pending.exists()
    archived = list(Path(result['audit']).glob('pending-conflicts/*.pending.json'))
    assert any(path.read_bytes() == rejected for path in archived)
    assert study.client.saved[request_id] == committed
    assert original.read_bytes() == original_bytes
    assert {name: m['journal'].sha(HERE / name) for name in source_hashes} == source_hashes
    assert 'records.append' in study.client.requests
    assert m['journal'].read(tmp_path / 'originals-publication.json')['pending'] == 0
    count = len(study.client.saved)
    assert m['publish_resume'].resume_publication(study)['status']['pending'] == 0
    assert len(study.client.saved) == count


def test_existing_pending_keeps_role_and_stage_without_requeue(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    study, _ = study_fixture(tmp_path, m)
    path = tmp_path / 'new-stage.json'
    m['journal'].fixed_json(path, {'value': 'unsubmitted formal result'})
    study.attach(path, 'result', 'gaze-final')
    rid = study.rid('file:new-stage.json')
    pending = study.recorder.control / 'pending' / (rid + '.json')
    before = pending.read_bytes()
    adapter = m['publish_resume'].PreserveEvidence(study)
    adapter.attach(path, 'process', None)
    assert pending.read_bytes() == before
    study.sync(strict=True)
    receipt = m['journal'].read(study.recorder.control / 'receipts' / (rid + '.json'))
    assert receipt['request']['body']['evidence']['role'] == 'result'
    assert receipt['request']['body']['evidence']['stage_key'] == 'gaze-final'


def test_no_server_proof_does_not_remove_conflicting_request(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    study, original = study_fixture(tmp_path, m)
    study.attach(original, 'process')
    pending = study.recorder.control / 'pending' / (study.rid('file:a-original.json') + '.json')
    before = pending.read_bytes()
    study.client.wrong_receipt = True
    with pytest.raises(ValueError, match='server receipt'):
        m['publish_resume'].PreserveEvidence(study).attach(original)
    assert pending.read_bytes() == before
    assert not list((study.recorder.control / 'repairs').rglob('*.json'))


def test_evidence_changes_are_never_reconciled_as_metadata(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    study, original = study_fixture(tmp_path, m)
    original.write_bytes(b'changed bytes')
    with pytest.raises(ValueError, match='bytes, identity or locator'):
        m['publish_resume'].PreserveEvidence(study).attach(original)
    assert not list((study.recorder.control / 'pending').glob('*.json'))


@pytest.mark.parametrize('guard', ['runner', 'pipeline', 'in-flight', 'unfinished'])
def test_repair_refuses_live_or_incomplete_subject(tmp_path, monkeypatch, guard):
    m = modules(monkeypatch)
    study, _ = study_fixture(tmp_path, m)
    if guard in ('runner', 'pipeline'):
        with file_lock(tmp_path / (guard + '.lock')), pytest.raises(StorageBusy):
            m['publish_resume'].resume_publication(study)
    elif guard == 'in-flight':
        m['journal'].fixed_json(tmp_path / 'subject/in-flight.json', {'key': 'live'})
        with pytest.raises(ValueError, match='in-flight'):
            m['publish_resume'].resume_publication(study)
    else:
        (tmp_path / 'computation-complete.json').unlink()
        with pytest.raises(ValueError, match='completed computation'):
            m['publish_resume'].resume_publication(study)
    assert not list((study.recorder.control / 'repairs').rglob('*.json'))


def test_non_role_metadata_conflict_is_not_auto_repaired(tmp_path, monkeypatch):
    m = modules(monkeypatch)
    study, original = study_fixture(tmp_path, m)
    study.attach(original, 'process')
    path = study.recorder.control / 'pending' / (study.rid('file:a-original.json') + '.json')
    value = m['journal'].read(path)
    value['body']['evidence']['dependencies'] = ['unknown-new-dependency']
    path.write_text(json.dumps(value))
    before = path.read_bytes()
    with pytest.raises(ValueError, match='exceeds'):
        m['publish_resume'].PreserveEvidence(study).attach(original)
    assert path.read_bytes() == before
