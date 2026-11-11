"""Register existing manual execution entries in their creation transaction."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid5

from .research_records import ResearchRecords


def register_execution(database, db, project, actor, kind, identity, title, protocol, *, executor='human',
                       classification='formal', question=None, metadata=None):
    """Index registration must succeed before an execution job becomes visible."""
    identity = UUID(str(identity))
    service = ResearchRecords(database)
    db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor['id']),))
    kernels = {protocol.get('kernel_id'), protocol.get('base', {}).get('kernel_id')}
    kernels.update(protocol.get(part, {}).get('kernel_id') for part in ('development', 'evaluation'))
    kernels.update(c.get('spec', {}).get('kernel_id') for c in protocol.get('conditions', []))
    spec = {'source_key': f'native-{kind}:{identity}', 'title': title, 'executor': executor,
            'classification': classification, 'question': question, 'experiment_date': datetime.now(UTC).date().isoformat(),
            'date_basis': 'UTC platform registration date before execution',
            'execution_status': 'planned', 'kernels': sorted(k for k in kernels if k),
            'protocol_version': protocol.get('schema'),
            'metadata': {'entry': 'platform-execution', 'runtime_kind': kind, 'runtime_id': str(identity),
                         'researcher_fields_pending': ['report', 'note'] if question else ['question', 'report', 'note'],
                         **(metadata or {})}}
    request = uuid5(identity, 'research-register')

    def save():
        result = service._register(db, project, actor, spec)
        index = result['id']
        raw = json.dumps(protocol, ensure_ascii=False, sort_keys=True)
        service._append(db, project, actor, index, {'request_id': request, 'kind': 'condition',
            'original_key': f'{kind}:{identity}:birth-protocol',
            'content': {'origin_kind': kind, 'origin_id': str(identity),
                        'protocol': protocol if len(raw.encode()) <= 512 * 1024 else {'original_record': str(identity)}}})
        if len(raw) <= 900000:
            service._save_text(db, project, actor, index, {'request_id': uuid5(identity, 'research-protocol'),
                'identity': uuid5(identity, 'research-protocol-text'), 'kind': 'protocol',
                'title': title + ' · Birth protocol', 'markdown': '```json\n' + raw + '\n```'})
        if kind == 'run':
            service._attach(db, project, actor, index, {'logical_id': f'run:{identity}', 'role': 'subject',
                'label': title, 'format': 'threemind.runtime-run', 'locator': {'kind': 'run', 'id': str(identity)}})
        return result

    return service._receipt(db, project, actor, request, 'native-register', {'spec': spec, 'protocol': protocol}, save)


def execution_finished(database, db, job, *, error=None, cancelled=False):
    """A local record update on job completion, with no runtime construction."""
    kind = job['kind']
    if kind not in ('run', 'study', 'ecology', 'evolution'):
        return
    native_id = job['run_id'] if kind == 'run' else job['params'].get('study_id' if kind == 'study' else 'campaign_id')
    if not native_id:
        return
    row = db.execute('SELECT id,created_by FROM research_experiments WHERE source_key=%s',
                     (f'native-{kind}:{native_id}',)).fetchone()
    if kind == 'run':
        parent = db.execute("SELECT spec->>'study_id' AS study FROM runs WHERE id=%s", (native_id,)).fetchone()
        for parent_kind, parent_id in (('study', parent['study'] if parent else None),
                                       ('evolution', job['params'].get('evolution_id')),
                                       ('assessment', job['params'].get('assessment_id'))):
            if parent_id:
                _parent_finished(database, db, job, parent_kind, str(parent_id), error=error, cancelled=cancelled)
    if not row:
        return
    actor = {'id': row['created_by']}
    service = ResearchRecords(database)
    status = 'cancelled' if cancelled else 'failed' if error else 'running' if kind == 'study' else 'completed'
    if kind in ('ecology', 'evolution') and not error and not cancelled:
        actual = db.execute(f'SELECT status FROM {kind}_campaigns WHERE id=%s', (native_id,)).fetchone()
        status = _status(actual['status'])
    checkpoint = None
    if kind == 'run':
        run = db.execute('SELECT status FROM runs WHERE id=%s', (native_id,)).fetchone()
        if not cancelled and not error and run['status'] in ('paused', 'blocked'):
            status = 'interrupted'
        checkpoint = db.execute('SELECT id,state_hash FROM checkpoints WHERE run_id=%s ORDER BY revision DESC LIMIT 1',
                                (native_id,)).fetchone()
    request = uuid5(UUID(str(job['id'])), 'research-completion')
    service._append(db, job['project_id'], actor, row['id'], {'request_id': request, 'kind': 'stage',
        'original_key': f'job:{job["id"]}:completion',
        'content': {'job_id': str(job['id']), 'execution_status': status, 'error': error,
                    'checkpoint': str(checkpoint['id']) if checkpoint else None}})
    if checkpoint:
        service._attach(db, job['project_id'], actor, row['id'], {'logical_id': f'checkpoint:{checkpoint["id"]}',
            'role': 'checkpoint', 'label': str(checkpoint['id']), 'format': 'threemind.checkpoint',
            'locator': {'kind': 'checkpoint', 'id': str(checkpoint['id'])}})
    db.execute('UPDATE research_experiments SET execution_status=%s,updated_at=now() WHERE id=%s', (status, row['id']))


def _status(value):
    return {'queued': 'planned', 'pending': 'planned', 'paused': 'interrupted', 'blocked': 'interrupted',
            'dead': 'completed', 'waiting': 'running', 'active': 'running', 'done': 'completed'}.get(value, value)


def _parent_finished(database, db, job, kind, identity, *, error, cancelled):
    index = db.execute('SELECT id,created_by FROM research_experiments WHERE source_key=%s',
                       (f'native-{kind}:{identity}',)).fetchone()
    if not index:
        return
    service, actor = ResearchRecords(database), {'id': index['created_by']}
    if kind == 'evolution':
        status = _status(db.execute('SELECT status FROM evolution_campaigns WHERE id=%s', (identity,)).fetchone()['status'])
        states = []
    else:
        join = "r.spec->>'study_id'=%s" if kind == 'study' else 'r.id IN (SELECT run_id FROM assessment_members WHERE batch_id=%s)'
        states = db.execute("SELECT j.status,r.status AS run_status,count(*) AS n FROM jobs j JOIN runs r ON r.id=j.run_id "
                            "WHERE j.kind='run' AND " + join + ' GROUP BY j.status,r.status ORDER BY j.status,r.status',
                            (identity,)).fetchall()
        remaining = any(s['status'] in ('pending', 'leased') for s in states)
        status = 'running' if remaining else 'failed' if any(s['status'] == 'failed' for s in states) else (
            'interrupted' if any(s['status'] == 'cancelled' or s['run_status'] in ('paused', 'blocked') for s in states)
            else 'completed')
    native_id = str(job['run_id'])
    service._append(db, job['project_id'], actor, index['id'],
                    {'request_id': uuid5(UUID(str(job['id'])), 'research-parent-completion'), 'kind': 'stage',
                     'original_key': f'child-job:{job["id"]}:completion',
                     'content': {'original_run_id': native_id, 'execution_status': status,
                                 'error': error, 'cancelled': cancelled, 'child_job_states': states}})
    service._attach(db, job['project_id'], actor, index['id'], {'logical_id': f'run:{native_id}', 'role': 'subject',
                    'label': native_id, 'format': 'threemind.runtime-run', 'locator': {'kind': 'run', 'id': native_id}})
    checkpoint = db.execute('SELECT id FROM checkpoints WHERE run_id=%s ORDER BY revision DESC LIMIT 1',
                            (native_id,)).fetchone()
    if checkpoint:
        service._attach(db, job['project_id'], actor, index['id'], {'logical_id': f'checkpoint:{checkpoint["id"]}',
                        'role': 'checkpoint', 'label': str(checkpoint['id']), 'format': 'threemind.checkpoint',
                        'locator': {'kind': 'checkpoint', 'id': str(checkpoint['id'])}})
    db.execute('UPDATE research_experiments SET execution_status=%s,updated_at=now() WHERE id=%s', (status, index['id']))
