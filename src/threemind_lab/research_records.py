"""An append-only research index. No engine construction or simulation actions.

Original identities and bytes remain authoritative. Request receipts are committed
in the same transaction as scientific registration, including text revisions.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from . import permissions
from .data_catalog import actor_id, authorized, wire
from .database import Conflict, Forbidden, NotFound
from .experiment_archive import canonical
from .record_schema import (
    AppendRecord,
    AttachRecord,
    BackfillPlan,
    ExperimentSpec,
    FinalizeRecord,
    RegisterRecord,
    SaveRecordText,
)

NAMESPACE = UUID('d96c2cd2-e660-4699-9d6e-740b877f4b46')


class _ChunkReader(io.RawIOBase):
    def __init__(self, values):
        self.values, self.pending = iter(values), memoryview(b'')

    def readable(self):
        return True

    def readinto(self, target):
        if not self.pending:
            self.pending = memoryview(next(self.values, b''))
        count = min(len(target), len(self.pending))
        target[:count] = self.pending[:count]
        self.pending = self.pending[count:]
        return count

    def close(self):
        close = getattr(self.values, 'close', None)
        if close:
            close()
        super().close()


def digest(value):
    return hashlib.sha256(canonical(wire(value))).hexdigest()


def _key(project, value):
    return uuid5(UUID(str(project)), value)


class ResearchRecords:
    def __init__(self, database):
        self.database = database
        self.storage = database.blobs.storage

    def _head(self, db, identity):
        row = db.execute('SELECT * FROM research_experiments WHERE id=%s', (identity,)).fetchone()
        if not row:
            raise NotFound('experiment is unavailable')
        return row

    def _receipt(self, db, project, actor, request, action, value, callback):
        fingerprint = digest({'action': action, 'value': value})
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,62))',
                   (f'record:{project}:{actor_id(actor)}:{request}',))
        old = db.execute('SELECT * FROM research_record_requests WHERE actor_id=%s AND request_id=%s',
                         (actor_id(actor), request)).fetchone()
        if old:
            if old['fingerprint'] != fingerprint:
                raise Conflict('record request ID belongs to different content')
            return old['result'] | {'replayed': True}
        result = wire(callback())
        db.execute('INSERT INTO research_record_requests(project_id,actor_id,request_id,action,fingerprint,result) '
                   'VALUES(%s,%s,%s,%s,%s,%s)',
                   (project, actor_id(actor), request, action, fingerprint, Jsonb(result)))
        return result | {'replayed': False}

    def receipt(self, project, actor, request):
        with authorized(self.database, project, actor) as db:
            row = db.execute('SELECT * FROM research_record_requests WHERE actor_id=%s AND request_id=%s',
                             (actor_id(actor), request)).fetchone()
            if not row:
                raise NotFound('no committed research-record receipt for this actor')
            return row

    def _register(self, db, project, actor, spec):
        spec = ExperimentSpec.model_validate(spec).model_dump(mode='json')
        identity = _key(project, 'research-experiment:' + spec['source_key'])
        sha = digest(spec)
        db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,62))', (str(identity),))
        old = db.execute('SELECT * FROM research_experiments WHERE source_key=%s', (spec['source_key'],)).fetchone()
        if old:
            if old['content_hash'] != sha:
                raise Conflict('source identity already registered with different facts; append a correction')
            return {'id': str(old['id']), 'project_id': str(project), 'content_hash': sha, 'existing': True}
        db.execute('INSERT INTO research_experiments(id,project_id,source_key,original_id,title,classification,'
                   'execution_status,experiment_date,executor,kernels,spec,content_hash,created_by) '
                   'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                   (identity, project, spec['source_key'], spec['original_id'], spec['title'], spec['classification'],
                    spec['execution_status'], spec['experiment_date'], spec['executor'], Jsonb(spec['kernels']),
                    Jsonb(spec), sha, actor_id(actor)))
        return {'id': str(identity), 'project_id': str(project), 'content_hash': sha, 'existing': False}

    def register(self, project, actor, body):
        body = RegisterRecord.model_validate(body)
        with authorized(self.database, project, actor, write=True) as db:
            return self._receipt(db, project, actor, body.request_id, 'register', body.model_dump(mode='json'),
                                 lambda: self._register(db, project, actor, body.spec))

    def list(self, actor, *, project=None, query='', kernel='', executor='', status='', coverage='',
             classification='', from_date=None, through_date=None, offset=0, limit=50):
        if not 0 <= offset <= 100000 or not 1 <= limit <= 200:
            raise ValueError('invalid experiment pagination')
        principal = permissions.resolve_actor(self.database, actor)
        if principal.get('delegation_id') and not permissions._resource_allowed(principal, [{'kind': 'project', 'id': str(project)}] if project else []):
            raise Forbidden('窄范围委托不能读取全部实验索引')
        scopes = {g['scope'] for g in principal['permissions'] if g['action'] == 'experiments.read'}
        global_read = principal['superadmin'] or 'all_projects' in scopes
        if not global_read and 'member_projects' not in scopes:
            raise Forbidden('当前账号没有实验索引读取权限')
        conditions, args = ['(%s OR m.user_id IS NOT NULL)'], [actor_id(actor), global_read]
        for field, value in [('e.project_id', project), ('e.executor', executor), ('e.execution_status', status),
                             ('e.coverage', coverage), ('e.classification', classification)]:
            if value:
                conditions.append(field + '=%s')
                args.append(value)
        if not classification:
            conditions.append("e.classification<>'development'")
        if query:
            conditions.append("strpos(lower(e.title||' '||coalesce(e.original_id,'')||' '||e.source_key),lower(%s))>0")
            args.append(query)
        if kernel:
            conditions.append('e.kernels ? %s')
            args.append(kernel)
        for value, op in [(from_date, '>='), (through_date, '<=')]:
            if value:
                conditions.append('e.experiment_date' + op + '%s')
                args.append(value)
        with self.database.tx(read_only=True) as db:
            permissions.set_context(db, principal, action='experiments.read')
            db.execute("SELECT set_config('tm.permission_all_projects',%s,true)", ('true' if global_read else 'false',))
            db.execute("SELECT set_config('tm.permission_domain','experiments',true)")
            db.execute("SELECT set_config('tm.record_user_id',%s,true)", (str(actor_id(actor)),))
            clause = ' FROM research_experiments e JOIN projects p ON p.id=e.project_id '
            clause += 'LEFT JOIN members m ON m.project_id=p.id AND m.user_id=%s WHERE ' + ' AND '.join(conditions)
            total = db.execute('SELECT count(*) AS n' + clause, tuple(args)).fetchone()['n']
            rows = db.execute('SELECT e.id,e.project_id,p.name AS project_name,m.role,e.original_id,e.title,e.source_key,'
                              'e.classification,e.execution_status,e.coverage,e.experiment_date,e.executor,e.kernels,'
                              'e.created_at,e.updated_at' + clause +
                              ' ORDER BY e.experiment_date DESC NULLS LAST,e.id LIMIT %s OFFSET %s',
                              tuple(args) + (limit, offset)).fetchall()
        return {'rows': rows, 'total': total, 'more': offset + len(rows) < total,
                'scope': 'all-authorized-projects' if project is None else 'project', 'offset': offset, 'limit': limit}

    def detail(self, project, actor, identity):
        with authorized(self.database, project, actor) as db:
            row = self._head(db, identity)
            counts = db.execute('SELECT kind,count(*) AS count FROM research_record_entries WHERE experiment_id=%s GROUP BY kind',
                                (identity,)).fetchall()
            row['entry_counts'] = counts
            row['evidence_count'] = db.execute('SELECT count(*) AS n FROM research_record_evidence WHERE experiment_id=%s',
                                               (identity,)).fetchone()['n']
            row['latest_verification'] = db.execute("SELECT content FROM research_record_entries WHERE experiment_id=%s "
                                                   "AND kind='stage' AND content->>'operation'='verification' ORDER BY recorded_at DESC LIMIT 1",
                                                   (identity,)).fetchone()
            return row

    def entries(self, project, actor, identity, *, kind=None, offset=0, limit=50):
        if not 0 <= offset <= 100000 or not 1 <= limit <= 200:
            raise ValueError('invalid entry pagination')
        with authorized(self.database, project, actor) as db:
            self._head(db, identity)
            rows = db.execute('SELECT * FROM research_record_entries WHERE experiment_id=%s AND (%s::text IS NULL OR kind=%s) '
                              'ORDER BY recorded_at,id LIMIT %s OFFSET %s', (identity, kind, kind, limit + 1, offset)).fetchall()
        return {'rows': rows[:limit], 'more': len(rows) > limit}

    def _append(self, db, project, actor, identity, body):
        body = AppendRecord.model_validate(body)
        self._head(db, identity)
        sha = digest(body.content)
        old = db.execute('SELECT * FROM research_record_entries WHERE experiment_id=%s AND kind=%s AND original_key=%s',
                         (identity, body.kind, body.original_key)).fetchone()
        if old:
            if old['content_hash'] != sha:
                raise Conflict('entry identity belongs to different content; append a separate correction')
            return {'id': str(old['id']), 'content_hash': sha}
        key = _key(identity, 'entry:' + body.kind + ':' + body.original_key)
        db.execute('INSERT INTO research_record_entries(id,project_id,experiment_id,kind,original_key,content,content_hash,actor_id) '
                   'VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                   (key, project, identity, body.kind, body.original_key, Jsonb(body.content), sha, actor_id(actor)))
        return {'id': str(key), 'content_hash': sha}

    def append(self, project, actor, identity, body):
        body = AppendRecord.model_validate(body)
        with authorized(self.database, project, actor, write=True) as db:
            return self._receipt(db, project, actor, body.request_id, 'append', {'id': str(identity), **body.model_dump(mode='json')},
                                 lambda: self._append(db, project, actor, identity, body))

    def grant_resource(self, project, actor, resource):
        self.storage.resource(resource)
        with authorized(self.database, project, actor, write=True) as db:
            admin = db.execute('SELECT admin FROM users WHERE id=%s', (actor_id(actor),)).fetchone()
            if not admin or not admin['admin']:
                raise Forbidden('only a host administrator can grant original-file access')
            db.execute('INSERT INTO research_evidence_grants(project_id,resource_id,actor_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',
                       (project, resource, actor_id(actor)))
        return {'project_id': str(project), 'resource_id': resource}

    def _attach(self, db, project, actor, identity, evidence):
        from .record_schema import EvidenceSpec

        self._head(db, identity)
        value = EvidenceSpec.model_validate(evidence).model_dump(mode='json')
        location = value['locator']
        kind = location.get('kind')
        if set(location) - {'kind', 'id', 'revision', 'content_hash', 'resource_id', 'member', 'reason', 'entry'}:
            raise ValueError('unsupported evidence locator fields')
        refs, private = {}, None
        if kind == 'file':
            resource = location.get('resource_id')
            if not db.execute('SELECT 1 FROM research_evidence_grants WHERE resource_id=%s', (resource,)).fetchone():
                raise Forbidden('original resource is not granted to this project')
            self.storage.resource(resource)
            # Resolve a safe path even if the file has disappeared; it is still recorded as a gap.
            self._file_path(location)
        elif kind in ('document', 'note'):
            revision = location.get('revision')
            if not isinstance(revision, int) or revision < 1:
                raise ValueError('text evidence must select a fixed positive revision')
            table, foreign = ('research_document_versions', 'document_id') if kind == 'document' else ('note_versions', 'note_id')
            row = db.execute(f'SELECT * FROM {table} WHERE {foreign}=%s AND revision=%s', (location['id'], revision)).fetchone()
            if not row:
                raise NotFound('fixed text evidence is unavailable to this actor')
            if location.get('content_hash') and location['content_hash'] != row['content_hash']:
                raise Conflict('fixed text evidence hash differs')
            location['content_hash'] = row['content_hash']
            refs[foreign], refs[kind + '_revision'] = row[foreign], revision
            if kind == 'note':
                private = row['owner_id']
        elif kind in ('artifact', 'run', 'checkpoint'):
            table = {'artifact': 'artifacts', 'run': 'runs', 'checkpoint': 'checkpoints'}[kind]
            fields = 'id,sha256,bytes' if kind == 'artifact' else 'id'
            row = db.execute(f'SELECT {fields} FROM {table} WHERE id=%s', (location.get('id'),)).fetchone()
            if not row:
                raise NotFound('evidence is unavailable in this project')
            refs[kind + '_id'] = row['id']
            if kind == 'artifact':
                if value['sha256'] and value['sha256'] != row['sha256']:
                    raise Conflict('artifact original hash differs')
                value['sha256'], value['byte_count'] = row['sha256'], int(row['bytes'])
                carrier = db.execute('SELECT metadata FROM artifacts WHERE id=%s', (row['id'],)).fetchone()
                if carrier['metadata'].get('private') or db.execute("SELECT 1 FROM data_private_carriers WHERE kind='artifact' AND carrier_id=%s", (row['id'],)).fetchone():
                    private = actor_id(actor)
        elif kind == 'missing':
            if not location.get('reason'):
                raise ValueError('missing evidence needs an explicit reason')
        else:
            raise ValueError('use a registered file, fixed text, artifact, run, checkpoint or explicit missing reference')
        sha = digest(value)
        old = db.execute('SELECT id,content_hash FROM research_record_evidence WHERE experiment_id=%s AND logical_id=%s',
                         (identity, value['logical_id'])).fetchone()
        if old:
            if old['content_hash'] != sha:
                raise Conflict('logical evidence identity belongs to different bytes or metadata')
            return {'id': str(old['id']), 'content_hash': sha}
        key = _key(identity, 'evidence:' + value['logical_id'])
        db.execute('INSERT INTO research_record_evidence(id,project_id,experiment_id,logical_id,role,label,format,byte_count,sha256,'
                   'locator,stage_key,dependencies,private_actor_id,document_id,document_revision,note_id,note_revision,'
                   'artifact_id,run_id,checkpoint_id,content_hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                   (key, project, identity, value['logical_id'], value['role'], value['label'], value['format'], value['byte_count'],
                    value['sha256'], Jsonb(location), value['stage_key'], Jsonb(value['dependencies']), private,
                    refs.get('document_id'), refs.get('document_revision'), refs.get('note_id'), refs.get('note_revision'),
                    refs.get('artifact_id'), refs.get('run_id'), refs.get('checkpoint_id'), sha))
        return {'id': str(key), 'content_hash': sha}

    def attach(self, project, actor, identity, body):
        body = AttachRecord.model_validate(body)
        with authorized(self.database, project, actor, write=True) as db:
            return self._receipt(db, project, actor, body.request_id, 'attach', {'id': str(identity), **body.model_dump(mode='json')},
                                 lambda: self._attach(db, project, actor, identity, body.evidence))

    def evidence(self, project, actor, identity, *, offset=0, limit=50):
        if not 0 <= offset <= 100000 or not 1 <= limit <= 200:
            raise ValueError('invalid evidence pagination')
        with authorized(self.database, project, actor) as db:
            self._head(db, identity)
            rows = db.execute('SELECT * FROM research_record_evidence WHERE experiment_id=%s ORDER BY role,logical_id LIMIT %s OFFSET %s',
                              (identity, limit + 1, offset)).fetchall()
        return {'rows': rows[:limit], 'more': len(rows) > limit}

    def evidence_row(self, project, actor, evidence):
        with authorized(self.database, project, actor) as db:
            row = db.execute('SELECT * FROM research_record_evidence WHERE id=%s', (evidence,)).fetchone()
            if not row:
                raise NotFound('evidence is missing or not visible to this actor')
            return row

    def _file_path(self, locator):
        return self.storage.resolve_member(locator['resource_id'], locator.get('member'))

    def chunks(self, project, actor, evidence):
        from .blob_store import object_chunks

        row = self.evidence_row(project, actor, evidence)
        location, sha, count = row['locator'], hashlib.sha256(), 0
        if location['kind'] == 'file':
            path = self._file_path(location)
            try:
                stream = path.open('rb')
            except OSError as error:
                raise NotFound('original evidence file is unavailable') from error
            with stream:
                while part := stream.read(1024 * 1024):
                    sha.update(part)
                    count += len(part)
                    yield part
        elif location['kind'] == 'artifact':
            for part in object_chunks(self.database, project, 'artifact', location['id'], actor=actor_id(actor)):
                sha.update(part)
                count += len(part)
                yield part
        elif location['kind'] == 'package':
            from .data_bundles import DataBundles
            with DataBundles(self.database)._open(project, actor, location['id']) as reader:
                for part in reader.chunks(location['entry']):
                    sha.update(part)
                    count += len(part)
                    yield part
        else:
            raise ValueError('this evidence is a structured reference; use its text or runtime endpoint')
        if row['byte_count'] is not None and count != int(row['byte_count']) or row['sha256'] and sha.hexdigest() != row['sha256']:
            raise Conflict('original evidence no longer matches its registered hash/size')

    def preview(self, project, actor, evidence, *, offset=0, limit=50):
        if not 0 <= offset <= 100000 or not 1 <= limit <= 100:
            raise ValueError('invalid preview pagination')
        row = self.evidence_row(project, actor, evidence)
        if row['locator']['kind'] in ('run', 'checkpoint'):
            with authorized(self.database, project, actor) as db:
                if row['run_id']:
                    fact = db.execute('SELECT id AS run_id,name,time_us,revision,state_hash,status FROM runs WHERE id=%s',
                                      (row['run_id'],)).fetchone()
                else:
                    fact = db.execute('SELECT run_id,id AS checkpoint_id,time_us,revision,state_hash FROM checkpoints WHERE id=%s',
                                      (row['checkpoint_id'],)).fetchone()
            if not fact:
                raise NotFound('original runtime record is missing')
            return {'format': row['format'], 'runtime': fact, 'starts_running': False}
        if row['locator']['kind'] in ('document', 'note'):
            with authorized(self.database, project, actor) as db:
                table, foreign = ('research_document_versions', 'document_id') if row['document_id'] else ('note_versions', 'note_id')
                result = db.execute(f'SELECT * FROM {table} WHERE {foreign}=%s AND revision=%s',
                                    (row[foreign], row['locator']['revision'])).fetchone()
            return {'format': row['format'], 'text': result.get('spec', result.get('body')), 'fixed_revision': row['locator']['revision']}
        if row['locator']['kind'] == 'missing':
            raise NotFound(row['locator']['reason'])
        name = row['label'].lower()
        if name.endswith(('.jsonl', '.jsonl.gz')):
            # Stream bounded rows; never load a whole trajectory or execute pickle.
            raw = io.BufferedReader(_ChunkReader(self.chunks(project, actor, evidence)))
            stream = gzip.GzipFile(fileobj=raw) if name.endswith('.gz') else raw
            rows, scanned = [], 0
            try:
                while scanned < offset + limit + 1:
                    line = stream.readline(1024 * 1024 + 1)
                    if not line:
                        break
                    if len(line) > 1024 * 1024:
                        raise ValueError('one process row exceeds preview budget; download the original')
                    if scanned >= offset:
                        rows.append(json.loads(line))
                    scanned += 1
            finally:
                stream.close()
                raw.close()
            return {'format': 'jsonl', 'rows': rows[:limit], 'more': len(rows) > limit, 'offset': offset,
                    'integrity': 'page-only; use verify for full-byte validation'}
        if name.endswith(('.md', '.txt', '.json', '.json.gz')):
            maximum = 1024 * 1024
            data = bytearray()
            for part in self.chunks(project, actor, evidence):
                data.extend(part)
                if len(data) > maximum:
                    raise ValueError('text exceeds 1 MiB preview budget; download its original')
            if name.endswith('.gz'):
                with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
                    data = stream.read(maximum + 1)
                if len(data) > maximum:
                    raise ValueError('expanded text exceeds preview budget')
            return {'format': row['format'], 'text': data.decode('utf-8-sig'), 'integrity': 'full-byte'}
        return {'format': row['format'], 'supported': False, 'message': 'Opaque original preserved; use its manifest and download.'}

    def _save_text(self, db, project, actor, identity, body):
        from . import notebooks, research_documents

        body = SaveRecordText.model_validate(body)
        self._head(db, identity)
        if body.expected_revision and not body.revision_reason:
            raise ValueError('a revised report/note must state its revision reason')
        if body.kind == 'note':
            from .note_schema import body_links
            note_body = {'format': 'markdown', 'text': body.markdown}
            try:
                body_links(note_body)
            except ValueError:
                # Preserve historical relative links verbatim as literal source,
                # without weakening the notebook's URL/reference validation.
                note_body = {'format': 'document', 'content': {'type': 'doc', 'content': [
                    {'type': 'codeBlock', 'attrs': {'language': 'markdown'},
                     'content': [{'type': 'text', 'text': body.markdown}]}]}}
            result = notebooks.save_note(self.database, project, actor_id(actor), body.identity, {
                'operation_id': body.request_id, 'expected_revision': body.expected_revision,
                'title': body.title, 'kind': 'note', 'body': note_body,
            }, transaction=db)
            family = 'note'
        else:
            result = research_documents.save(self.database, project, actor_id(actor), body.identity, {
                'operation_id': body.request_id, 'expected_revision': body.expected_revision,
                'spec': {'kind': 'report' if body.kind == 'report' else 'record', 'title': body.title,
                         'sources': [], 'blocks': [{'id': 'original-text', 'type': 'commentary',
                                                  'section': 'other', 'markdown': body.markdown}]}, 'review': 'draft',
            }, transaction=db)
            family = 'document'
        ref = self._attach(db, project, actor, identity, {
            'logical_id': f'{body.kind}:{body.identity}:r{result["revision"]}', 'role': body.kind,
            'label': body.title, 'format': 'text/markdown', 'locator': {'kind': family, 'id': str(body.identity),
                                                                      'revision': result['revision']},
        })
        if body.revision_reason:
            self._append(db, project, actor, identity, {'request_id': body.request_id, 'kind': 'correction',
                'original_key': f'text:{body.identity}:r{result["revision"]}',
                'content': {'revision_reason': body.revision_reason, 'text_id': str(body.identity), 'revision': result['revision']}})
        return {'text': wire(result), 'evidence': ref}

    def save_text(self, project, actor, identity, body):
        body = SaveRecordText.model_validate(body)
        with authorized(self.database, project, actor, write=True) as db:
            return self._receipt(db, project, actor, body.request_id, 'text', {'id': str(identity), **body.model_dump(mode='json')},
                                 lambda: self._save_text(db, project, actor, identity, body))

    def verify(self, project, actor, identity, *, hashes=False):
        head = self.detail(project, actor, identity)
        with authorized(self.database, project, actor) as db:
            rows = db.execute('SELECT * FROM research_record_evidence WHERE experiment_id=%s ORDER BY logical_id', (identity,)).fetchall()
            hidden = db.execute('SELECT EXISTS(SELECT 1 FROM research_record_private_counts '
                                'WHERE experiment_id=%s AND actor_id<>%s) AS yes', (identity, actor_id(actor))).fetchone()['yes']
        problems = [{'kind': 'declared-gap', 'message': gap} for gap in head['spec']['missing']]
        if hidden and not permissions.resolve_actor(self.database, actor)['superadmin']:
            problems.append({'kind': 'private-evidence-unavailable', 'message': 'Some personal originals belong to another author.'})
        roles = {row['role'] for row in rows}
        for role in head['spec']['required_roles']:
            if role not in roles:
                problems.append({'kind': 'missing-role', 'role': role})
        logical = {r['logical_id'] for r in rows}
        checked, referenced_bytes = [], 0
        for row in rows:
            location, status = row['locator'], 'reference-checked'
            try:
                if location['kind'] == 'missing':
                    raise NotFound(location['reason'])
                if location['kind'] == 'file':
                    path = self._file_path(location)
                    if not path.is_file():
                        raise NotFound('original file is missing')
                    if row['byte_count'] is not None and path.stat().st_size != int(row['byte_count']):
                        raise Conflict('original file size differs')
                    if not row['sha256']:
                        problems.append({'kind': 'unknown-hash', 'logical_id': row['logical_id']})
                if location['kind'] in ('file', 'artifact', 'package') and hashes:
                    for _ in self.chunks(project, actor, row['id']):
                        pass
                    status = 'hash-verified'
                for dependency in row['dependencies']:
                    if dependency not in logical:
                        problems.append({'kind': 'missing-dependency', 'logical_id': row['logical_id'], 'dependency': dependency})
                referenced_bytes += int(row['byte_count'] or 0)
            except (ValueError, OSError, Conflict, NotFound) as error:
                status = 'unavailable'
                problems.append({'kind': 'unavailable-evidence', 'logical_id': row['logical_id'], 'message': str(error)})
            checked.append({'id': str(row['id']), 'logical_id': row['logical_id'], 'status': status})
        return {'experiment_id': str(identity), 'execution_status': head['execution_status'],
                'coverage': 'partial' if problems else 'verified' if hashes else 'indexed',
                'hashes_checked': hashes, 'problems': problems, 'evidence': checked,
                'referenced_bytes': referenced_bytes, 'original_data_recovered': False,
                'scope': 'registered references and declared gaps; uncollected research data is not reconstructed'}

    def finalize(self, project, actor, identity, body):
        body = FinalizeRecord.model_validate(body)
        # Validation is observational and stays outside the recording transaction.
        verification = self.verify(project, actor, identity)
        summary = {k: v for k, v in verification.items() if k not in ('evidence', 'problems')}
        summary.update(evidence_checked=len(verification['evidence']), problem_count=len(verification['problems']),
                       problems=verification['problems'][:100], problems_truncated=len(verification['problems']) > 100)
        with authorized(self.database, project, actor, write=True) as db:
            def commit():
                self._head(db, identity)
                self._append(db, project, actor, identity, {'request_id': body.request_id, 'kind': 'stage',
                    'original_key': 'finalize:' + str(body.request_id), 'content': {'operation': 'verification', **summary}})
                db.execute('UPDATE research_experiments SET execution_status=%s,coverage=%s,updated_at=now() WHERE id=%s',
                           (body.execution_status, verification['coverage'], identity))
                return verification | {'execution_status': body.execution_status, 'finalized': True}
            return self._receipt(db, project, actor, body.request_id, 'finalize', {'id': str(identity), **body.model_dump(mode='json')}, commit)

    def backfill_plan(self, project, actor, body):
        body = BackfillPlan.model_validate(body)
        raw = body.model_dump(mode='json')
        # Validate without writing any experimental rows.
        for item in body.records:
            ExperimentSpec.model_validate(item['spec'])
            for entry in item.get('entries', []):
                AppendRecord.model_validate(entry)
            for entry in item.get('evidence', []):
                AttachRecord.model_validate(entry)
            for entry in item.get('texts', []):
                SaveRecordText.model_validate(entry)
            if set(item) - {'spec', 'entries', 'evidence', 'texts'}:
                raise ValueError('unsupported backfill fields')
        if len(canonical(raw)) > 4 * 1024 * 1024:
            raise ValueError('backfill batch exceeds 4 MiB; split it into smaller batches')
        sha = digest({'source_manifest_hash': body.source_manifest_hash, 'records': body.records})
        key = _key(project, 'backfill:' + str(actor_id(actor)) + ':' + sha)
        with authorized(self.database, project, actor, write=True) as db:
            def save():
                db.execute('INSERT INTO research_backfill_batches(id,project_id,actor_id,plan,plan_hash) VALUES(%s,%s,%s,%s,%s) '
                           'ON CONFLICT(project_id,actor_id,plan_hash) DO NOTHING',
                           (key, project, actor_id(actor), Jsonb(raw), sha))
                return {'id': str(key), 'plan_hash': sha, 'records': len(body.records), 'state': 'preview', 'writes_experiments': False}
            return self._receipt(db, project, actor, body.request_id, 'backfill-plan', raw, save)

    def backfill_apply(self, project, actor, batch, body):
        from .record_schema import ApplyBackfill
        body = ApplyBackfill.model_validate(body)
        with authorized(self.database, project, actor, write=True) as db:
            def apply():
                row = db.execute('SELECT * FROM research_backfill_batches WHERE id=%s AND actor_id=%s FOR UPDATE',
                                 (batch, actor_id(actor))).fetchone()
                if not row or row['plan_hash'] != body.plan_hash:
                    raise Conflict('backfill preview is missing or hash differs')
                if row['state'] == 'applied':
                    return row['result'] | {'batch_replayed': True}
                results = []
                for item in row['plan']['records']:
                    result = self._register(db, project, actor, item['spec'])
                    identity = result['id']
                    for entry in item.get('entries', []):
                        self._append(db, project, actor, identity, entry)
                    for entry in item.get('texts', []):
                        self._save_text(db, project, actor, identity, entry)
                    for entry in item.get('evidence', []):
                        self._attach(db, project, actor, identity, entry['evidence'])
                    results.append(result)
                result = {'id': str(batch), 'plan_hash': body.plan_hash, 'state': 'applied', 'records': results,
                          'starts_running': False, 'originals_copied': 0}
                db.execute("UPDATE research_backfill_batches SET state='applied',result=%s WHERE id=%s", (Jsonb(result), batch))
                return result
            return self._receipt(db, project, actor, body.request_id, 'backfill-apply', body.model_dump(mode='json'), apply)

    def restore_archive(self, db, project, actor, reader, payload, identity, identities, bundle, origin):
        """Projection under a new index identity; originals remain in the package.

        Referencing imported package members avoids making a second large copy.
        Unsupported live-runtime objects retain read-only origin references.
        """
        row = payload['record']
        spec = dict(row['spec'])
        spec['source_key'] = f'import:{bundle}:' + digest({'original_source_key': spec['source_key']})
        spec['metadata'] = dict(spec['metadata']) | {'import_origin': {
            k: v for k, v in origin.items() if k != 'original'} | {'source_content_hash': row['content_hash']}}
        spec = ExperimentSpec.model_validate(spec).model_dump(mode='json')
        sha = digest(spec)
        db.execute('INSERT INTO research_experiments(id,project_id,source_key,original_id,title,classification,execution_status,'
                   'coverage,experiment_date,executor,kernels,spec,content_hash,created_by) '
                   'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                   (identity, project, spec['source_key'], row['original_id'], row['title'], row['classification'], row['execution_status'],
                    'partial' if row['coverage'] == 'partial' or spec['missing'] else 'indexed',
                    row['experiment_date'], row['executor'], Jsonb(row['kernels']), Jsonb(spec), sha, actor_id(actor)))
        for entry in payload.get('entries', []):
            self._append(db, project, actor, identity, {'request_id': _key(identity, entry['id']), 'kind': entry['kind'],
                'original_key': entry['original_key'], 'content': entry['content']})
        for entry in payload.get('evidence', []):
            location = dict(entry['locator'])
            private = actor_id(actor) if entry.get('private_actor_id') else None
            refs, size, checksum = {}, entry['byte_count'], entry['sha256']
            kind = location['kind']
            if kind in ('document', 'note', 'artifact'):
                location['id'] = identities[kind + ':' + location['id']]
                refs[{'document': 'document_id', 'note': 'note_id', 'artifact': 'artifact_id'}[kind]] = location['id']
                if kind in ('document', 'note'):
                    refs[kind + '_revision'] = location['revision']
                    table, foreign = ('research_document_versions', 'document_id') if kind == 'document' else ('note_versions', 'note_id')
                    location['content_hash'] = db.execute(f'SELECT content_hash FROM {table} WHERE {foreign}=%s AND revision=%s',
                                                         (location['id'], location['revision'])).fetchone()['content_hash']
            elif kind in ('file', 'package'):
                location = {'kind': 'package', 'id': str(bundle), 'entry': entry['bytes_entry']}
                refs['data_bundle_id'] = bundle
            elif kind in ('run', 'checkpoint'):
                # These are archived facts, not reconstructed executable runs.
                source_id = entry.get('run_id')
                if kind == 'checkpoint':
                    target = next((o for o in reader.objects.values() if o['kind'] == 'run' and
                                   any(c['id'] == entry['checkpoint_id'] for c in reader.rows(reader.json(o['payload'])['tables']['checkpoints']))), None)
                else:
                    target = reader.objects.get('run:' + source_id)
                if not target:
                    raise ValueError('archived runtime dependency is missing')
                file = target['payload']
                location = {'kind': 'package', 'id': str(bundle), 'entry': file}
                refs['data_bundle_id'] = bundle
                size, checksum = reader.files[file]['bytes'], reader.files[file]['sha256']
            key = _key(identity, 'evidence:' + entry['logical_id'])
            db.execute('INSERT INTO research_record_evidence(id,project_id,experiment_id,logical_id,role,label,format,byte_count,sha256,'
                       'locator,stage_key,dependencies,private_actor_id,document_id,document_revision,note_id,note_revision,'
                       'artifact_id,data_bundle_id,content_hash) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                       (key, project, identity, entry['logical_id'], entry['role'], entry['label'], entry['format'], size, checksum,
                        Jsonb(location), entry['stage_key'], Jsonb(entry['dependencies']), private, refs.get('document_id'),
                        refs.get('document_revision'), refs.get('note_id'), refs.get('note_revision'), refs.get('artifact_id'),
                        refs.get('data_bundle_id'), digest({'origin': entry['content_hash'], 'locator': location})))
        # Preserve the complete read-only runtime dependency closure as package
        # member references. Re-exporting an imported index must retain table
        # bytes, not just the JSON descriptor pointing into its old package.
        from .data_catalog import NATIVE
        pending, seen = [origin['origin_object_id']], set()
        while pending:
            object_id = pending.pop()
            if object_id in seen:
                continue
            seen.add(object_id)
            item = reader.objects[object_id]
            pending.extend(d['object_id'] for d in item['dependencies'] if d['object_id'] in reader.objects)
            if item['kind'] in NATIVE:
                continue
            payload_file = item['payload']
            archived = reader.json(payload_file)
            members = {payload_file, *archived.get('tables', {}).values()}
            members.update(archived[k] for k in ('rows_entry', 'versions_entry', 'bytes_entry') if k in archived)
            for member in sorted(members):
                file = reader.files[member]
                logical = 'archive:' + object_id + ':' + hashlib.sha256(member.encode()).hexdigest()[:16]
                location = {'kind': 'package', 'id': str(bundle), 'entry': member}
                private = actor_id(actor) if reader.manifest['recovery'].get('private') or item.get('private') else None
                db.execute('INSERT INTO research_record_evidence(id,project_id,experiment_id,logical_id,role,label,format,'
                           'byte_count,sha256,locator,dependencies,private_actor_id,data_bundle_id,content_hash) '
                           'VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                           (_key(identity, 'evidence:' + logical), project, identity, logical, 'archived-runtime',
                            object_id + ' · ' + member, 'jsonl' if member.endswith('.jsonl') else 'json' if member.endswith('.json') else 'opaque',
                            file['bytes'], file['sha256'], Jsonb(location), Jsonb([]), private, bundle,
                            digest({'original_object': object_id, 'original_member': member, 'sha256': file['sha256']})))
        return sha
