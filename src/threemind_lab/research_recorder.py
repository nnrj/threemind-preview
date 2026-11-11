"""Durable observational recording for maintained experiment hosts.

It knows no Core, teacher, optimizer or simulation clock. A failed original-byte
write raises immediately. A service outage preserves requests for later sync.
"""

from __future__ import annotations

import hashlib
import os
from uuid import UUID, uuid4

from .data_catalog import wire
from .research_records import _key, digest
from .storage_files import atomic_json, checked_path, file_lock, read_json, under_root


class ResearchRecorder:
    def __init__(self, directory, project, *, client=None, service=None, actor=None):
        if (client is None) == (service is None):
            raise ValueError('select one canonical HTTP client or ResearchRecords service')
        self.directory, self.project = checked_path(directory), str(UUID(str(project)))
        self.client, self.service, self.actor = client, service, actor
        self.control = self.directory / '.research-records'
        self.control.mkdir(parents=True, exist_ok=True)
        self.experiment = None
        self.status = {'pending': 0, 'synced': 0, 'error': None}

    @classmethod
    def from_environment(cls, directory, project, *, url=None, profile=None, auth_directory=None, source='script'):
        """Use the shared protected API identity; credentials never enter the journal."""
        from .operations_client import OperationsClient

        client = OperationsClient.from_environment(url, profile=profile, directory=auth_directory, source=source)
        try:
            recorder = cls(directory, project, client=client)
            recorder._owns_client = True
            return recorder
        except Exception:
            client.close()
            raise

    def close(self):
        if getattr(self, '_owns_client', False):
            self.client.close()
            self._owns_client = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _queue(self, action, body, *, identity=None):
        body = wire(dict(body))
        request = str(UUID(str(body.get('request_id') or uuid4())))
        body['request_id'] = request
        value = {'schema': 'threemind.record-journal/1', 'project': self.project, 'experiment': identity or self.experiment,
                 'action': action, 'body': body}
        target = self.control / 'pending' / (request + '.json')
        with file_lock(self.control / 'journal.lock'):
            if target.exists() and read_json(target) != value:
                raise ValueError('journal request identity belongs to different content')
            if not target.exists():
                atomic_json(target, value)
        return request

    def register(self, spec, *, request_id=None):
        self.experiment = str(_key(self.project, 'research-experiment:' + spec['source_key']))
        self._queue('register', {'spec': spec, 'request_id': str(request_id or uuid4())})
        atomic_json(self.control / 'identity.json', {'project': self.project, 'experiment': self.experiment,
                                                   'source_key': spec['source_key']})
        return self.experiment

    def resume_recording(self):
        """Resume only the journal, never an experimental subject."""
        value = read_json(self.control / 'identity.json')
        if value['project'] != self.project:
            raise ValueError('record journal belongs to another project')
        self.experiment = value['experiment']
        return self.experiment

    def append(self, kind, original_key, content, *, request_id=None):
        if not self.experiment:
            raise ValueError('register the experiment before its stages')
        return self._queue('append', {'kind': kind, 'original_key': original_key, 'content': content,
                                      'request_id': str(request_id or uuid4())})

    def attach(self, evidence, *, request_id=None):
        if not self.experiment:
            raise ValueError('register the experiment before attaching originals')
        return self._queue('attach', {'evidence': evidence, 'request_id': str(request_id or uuid4())})

    def text(self, body):
        if not self.experiment:
            raise ValueError('register the experiment before its text')
        return self._queue('text', body)

    def finalize(self, status='completed', *, request_id=None):
        if not self.experiment:
            raise ValueError('register the experiment before finalization')
        return self._queue('finalize', {'execution_status': status, 'request_id': str(request_id or uuid4())})

    def save_original(self, relative, content):
        """Publish immutable originals durably before the host's next stage."""
        path = under_root(self.directory, relative)
        if path.is_relative_to(self.control):
            raise ValueError('original must not overwrite recorder control files')
        path.parent.mkdir(parents=True, exist_ok=True)
        content = bytes(content)
        sha = hashlib.sha256(content).hexdigest()
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ValueError('original exists with different bytes')
        else:
            temporary = path.with_name(path.name + '.' + uuid4().hex + '.partial')
            with temporary.open('xb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
            temporary.unlink()
        return {'path': str(path), 'member': relative, 'byte_count': len(content), 'sha256': sha}

    def synchronize(self, *, strict=False):
        import httpx
        import psycopg

        synced, error, failure_to_raise = 0, None, None
        with file_lock(self.control / 'journal.lock'):
            pending = self.control / 'pending'
            files = list(pending.glob('*.json')) if pending.exists() else []
            # Registration must precede stages even after a crash. Timestamp gives
            # actual enqueue order for all other durable requests.
            files.sort(key=lambda p: (read_json(p)['action'] != 'register', p.stat().st_mtime_ns, p.name))
            for path in files:
                value = read_json(path)
                action, body, identity = value['action'], value['body'], value['experiment']
                try:
                    if self.client is not None:
                        parameters = {'project': self.project}
                        if action != 'register':
                            parameters['experiment'] = identity
                        try:
                            result = self.client.call('records.' + action, {'path': parameters, 'body': body},
                                                      request_id=body['request_id'])
                        except (ValueError, httpx.HTTPError):
                            # Business receipts reconcile an HTTP middleware's
                            # unknown outcome without blind repeated execution.
                            receipt = self.client.call('records.receipt', {'path': {
                                'project': self.project, 'request_id': body['request_id']}})
                            from .record_schema import (
                                AppendRecord,
                                AttachRecord,
                                FinalizeRecord,
                                RegisterRecord,
                                SaveRecordText,
                            )
                            model = {'register': RegisterRecord, 'append': AppendRecord, 'attach': AttachRecord,
                                     'text': SaveRecordText, 'finalize': FinalizeRecord}[action]
                            expected = model.model_validate(body).model_dump(mode='json')
                            if action != 'register':
                                expected = {'id': identity, **expected}
                            if receipt['fingerprint'] != digest({'action': action, 'value': expected}):
                                raise ValueError('committed receipt belongs to different research content')
                            result = receipt['result']
                    else:
                        method = getattr(self.service, 'save_text' if action == 'text' else action)
                        args = (self.project, self.actor, body) if action == 'register' else (self.project, self.actor, identity, body)
                        result = method(*args)
                    atomic_json(self.control / 'receipts' / path.name, {'request': value, 'result': wire(result)})
                    path.unlink()
                    synced += 1
                except (ValueError, OSError, httpx.HTTPError, psycopg.Error) as failure:
                    error = str(failure)
                    if strict:
                        failure_to_raise = failure
                    break
            self.status = {'pending': len(list(pending.glob('*.json'))) if pending.exists() else 0,
                           'synced': synced, 'error': error}
            atomic_json(self.control / 'status.json', self.status)
        if failure_to_raise:
            raise failure_to_raise
        return self.status
