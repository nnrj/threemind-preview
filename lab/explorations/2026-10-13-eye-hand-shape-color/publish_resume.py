"""Post-computation E69 publication repair; frozen experiment sources stay intact.

The frozen broad publisher reuses each file request ID with inferred role/stage.
This adapter retains the earlier journal metadata and only attaches missing files.
It never loads or resumes an organism and never changes committed research facts.
"""
from __future__ import annotations

import argparse
import hashlib
from contextlib import ExitStack
from pathlib import Path

from journal import HERE, RESOURCE, ResearchStudy, fixed_json, put, read, sha
from pipeline import validate_completed_step
from publish import publish

from threemind_lab.record_schema import AttachRecord
from threemind_lab.research_records import digest
from threemind_lab.storage_files import checked_path, file_lock

REPAIR = 'e69-preserve-evidence-metadata-v1'


def normalized_request(value):
    return AttachRecord.model_validate(value['body']).model_dump(mode='json')


class PreserveEvidence:
    """Delegate the existing publisher, preserving first recorded file semantics."""

    def __init__(self, study):
        self.study = study
        self.control = study.recorder.control
        self.audit = self.control / 'repairs' / REPAIR
        self.counts = {'existing_receipts': 0, 'retained_pending': 0, 'new_files': 0,
                       'conflicting_pending_archived': 0}

    def __getattr__(self, name):
        return getattr(self.study, name)

    def _validate(self, request, request_id, path):
        name = path.relative_to(self.work).as_posix()
        if (request.get('action') != 'attach' or request.get('project') != self.study.project or
                request.get('experiment') != self.study.recorder.experiment):
            raise ValueError('saved attachment request has a different owner or operation')
        body = normalized_request(request)
        evidence = body['evidence']
        expected = {'logical_id': 'file:' + name, 'label': name,
                    'format': ''.join(path.suffixes).lstrip('.') or 'opaque',
                    'byte_count': path.stat().st_size, 'sha256': sha(path),
                    'locator': {'kind': 'file', 'resource_id': RESOURCE, 'member': name}}
        if body['request_id'] != request_id or any(evidence[key] != value for key, value in expected.items()):
            raise ValueError('registered evidence bytes, identity or locator changed: ' + name)
        return body

    def _validate_committed(self, receipt, request_id, path):
        body = self._validate(receipt['request'], request_id, path)
        if receipt.get('result', {}).get('content_hash') != digest(body['evidence']):
            raise ValueError('local committed receipt does not match its original evidence metadata')
        return body

    def _archive_conflict(self, pending_path, pending, receipt, original_body, candidate_body):
        # Only the diagnosed role/stage rewrite is repairable automatically.
        allowed = {'role', 'stage_key'}
        original, candidate = original_body['evidence'], candidate_body['evidence']
        if any(original[k] != candidate[k] for k in original if k not in allowed):
            raise ValueError('pending evidence conflict exceeds the diagnosed role/stage mismatch')
        request_id = original_body['request_id']
        remote = self.study.client.call('records.receipt', {'path': {
            'project': self.study.project, 'request_id': request_id}})
        expected = digest({'action': 'attach', 'value': {
            'id': self.study.recorder.experiment, **original_body}})
        if (remote.get('fingerprint') != expected or remote.get('action') != 'attach' or
                remote.get('result', {}).get('content_hash') != receipt['result']['content_hash'] or
                remote.get('result', {}).get('id') != receipt['result'].get('id')):
            raise ValueError('server receipt does not prove the original metadata was committed')
        original_bytes = pending_path.read_bytes()
        pending_hash = hashlib.sha256(original_bytes).hexdigest()
        archive = self.audit / 'pending-conflicts' / (request_id + '-' + pending_hash)
        put(archive.with_suffix('.pending.json'), original_bytes)
        fixed_json(archive.with_suffix('.audit.json'), {
            'repair': REPAIR, 'request_id': request_id, 'pending_sha256': pending_hash,
            'original_request': receipt['request'], 'rejected_pending': pending,
            'server_receipt': remote,
            'reason': 'Frozen bulk publisher inferred role/stage for an already committed file request. '
                      'Preserve first committed metadata; remove only the archived conflicting resend from pending.',
            'committed_research_modified': False, 'organism_loaded': False})
        # The queue is locked, original bytes and proof are durable, and the
        # original request is already committed. No source/receipt is replaced.
        if sha(pending_path) != pending_hash:
            raise ValueError('pending request changed while archiving')
        pending_path.unlink()
        self.counts['conflicting_pending_archived'] += 1

    def attach(self, path, role='process', stage=None):
        path = checked_path(Path(path).absolute())
        name = path.relative_to(self.work).as_posix()
        request_id = self.study.rid('file:' + name)
        pending_path = self.control / 'pending' / (request_id + '.json')
        receipt_path = self.control / 'receipts' / (request_id + '.json')
        with file_lock(self.control / 'journal.lock'):
            pending = read(pending_path) if pending_path.exists() else None
            if receipt_path.exists():
                receipt = read(receipt_path)
                original_body = self._validate_committed(receipt, request_id, path)
                if pending is not None:
                    candidate = self._validate(pending, request_id, path)
                    if candidate != original_body:
                        self._archive_conflict(pending_path, pending, receipt, original_body, candidate)
                self.counts['existing_receipts'] += 1
                return request_id
            if pending is not None:
                self._validate(pending, request_id, path)
                self.counts['retained_pending'] += 1
                return request_id
        self.counts['new_files'] += 1
        return self.study.attach(path, role, stage)

    def sync(self, *, strict=False):
        # Register the repair as new evidence, without editing an old fact. The
        # digest keeps repeated publication idempotent, including interrupted runs.
        originals = [self.audit / 'repair-definition.json', *sorted((self.audit / 'pending-conflicts').glob('*.json'))]
        members = [{'path': p.relative_to(self.work).as_posix(), 'sha256': sha(p),
                    'bytes': p.stat().st_size} for p in originals]
        index = {'repair': REPAIR, 'members': members, 'committed_research_modified': False,
                 'simulation_advanced': False, 'organism_loaded': False}
        fingerprint = digest(index)
        manifest = self.audit / 'manifests' / (fingerprint + '.json')
        fixed_json(manifest, index)
        for path in [*originals, manifest]:
            self.attach(path, 'publication-audit', 'publication')
        self.study.append('correction', REPAIR + ':' + fingerprint, {
            'reason': 'Frozen bulk publication inferred file roles/stages which conflicted with original attachments. '
                      'This post-computation adapter preserves the original registered metadata and records any '
                      'removed conflicting resend with original bytes and server receipt proof.',
            'manifest': manifest.relative_to(self.work).as_posix(), 'sha256': sha(manifest),
            'committed_research_modified': False, 'simulation_advanced': False, 'organism_loaded': False})
        return self.study.sync(strict=strict)


def verify_frozen_publication_sources(work):
    sources = read(work / 'source-reference/manifest.json')
    platform = read(work / 'platform.json')
    if sha(work / 'source-reference/manifest.json') != platform['manifest_sha256']:
        raise ValueError('original frozen source manifest changed')
    # These modules are reused exactly as they were at formal registration.
    for name in ('journal.py', 'publish.py', 'pipeline.py'):
        relative = (HERE.relative_to(HERE.parents[2]) / name).as_posix()
        expected = sources[relative]
        if sha(HERE / name) != expected or sha(work / 'source-reference' / relative) != expected:
            raise ValueError('frozen publication source changed: ' + name)


def resume_publication(study, *, publisher=publish):
    work = study.work
    with ExitStack() as stack:
        # All official E69 execution entry points cooperate with these locks.
        # A live pipeline or writer is refused; it is never stopped or taken over.
        stack.enter_context(file_lock(work / 'pipeline.lock'))
        stack.enter_context(file_lock(work / 'runner.lock'))
        stack.enter_context(study.storage.writer(RESOURCE))
        if (work / 'subject/in-flight.json').exists():
            raise ValueError('in-flight experience exists; publication repair cannot resume a subject')
        for step, receipt in (('computation', 'computation-complete.json'),
                              ('analysis', 'analysis/verified-results.json'), ('video', 'replays/export.json')):
            if not (work / receipt).exists():
                raise ValueError('publication repair requires completed ' + step)
            validate_completed_step(work, step)
        verify_frozen_publication_sources(work)
        adapter = PreserveEvidence(study)
        fixed_json(adapter.audit / 'repair-definition.json', {
            'repair': REPAIR, 'tool_sha256': sha(Path(__file__)),
            'frozen_manifest_sha256': sha(work / 'source-reference/manifest.json'),
            'boundary_sha256': read(work / 'subject/latest.json')['boundary_sha256'],
            'purpose': 'Post-computation attachment idempotency repair; preserve earlier roles and stages.',
            'simulation_advanced': False, 'committed_research_modified': False})
        status = publisher(adapter, 'originals')
        fixed_json(adapter.audit / 'completed.json', {
            'repair': REPAIR, 'pending': status['pending'], 'simulation_advanced': False,
            'frozen_manifest_sha256': sha(work / 'source-reference/manifest.json')})
        return {'status': status, 'this_invocation': adapter.counts, 'audit': str(adapter.audit)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    study = ResearchStudy(args.work)
    try:
        import json
        print(json.dumps(resume_publication(study), ensure_ascii=False))
    finally:
        study.close()


if __name__ == '__main__':
    main()
