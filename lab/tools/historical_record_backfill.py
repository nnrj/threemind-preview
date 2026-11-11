"""Apply a reviewed historical inventory through the canonical record service."""

from __future__ import annotations

import json
import re
from pathlib import Path

from threemind_lab.config import ROOT
from threemind_lab.database import LOCAL_USER, Conflict, NotFound
from threemind_lab.record_schema import FinalizeRecord
from threemind_lab.research_records import ResearchRecords, digest
from threemind_lab.storage_files import atomic_json

from .historical_record_inventory import file_identity, identity, native_facts, role, source_files


def request(key):
    return identity('record-request:' + key)


def register_project(database, source):
    """New platform identities are explicit; never pretend to recover an old ID."""
    if source['project_id']:
        database.authorize({'id': LOCAL_USER}, source['project_id'], write=True)
        return source['project_id']
    project = identity('historical-platform-project:' + source['source_key'])
    name = '历史补录 · ' + source['title'][:110]
    with database.tx(project) as db:
        old = db.execute('SELECT id,name,owner_id FROM projects WHERE id=%s', (project,)).fetchone()
        if old and (old['name'] != name or old['owner_id'] != LOCAL_USER):
            raise Conflict('historical registration project belongs to another identity')
        if not old:
            db.execute('INSERT INTO projects(id,name,owner_id) VALUES(%s,%s,%s)', (project, name, LOCAL_USER))
            db.execute("INSERT INTO members VALUES(%s,%s,'owner')", (project, LOCAL_USER))
            db.execute("INSERT INTO audit(user_id,action,resource) VALUES(%s,'research.backfill.project',%s)", (LOCAL_USER, project))
    return project


def grant_path(service, project, path):
    storage = service.storage
    root = path if path.is_dir() else path.parent
    # One reviewed batch reuses its already granted roots. Attach still checks
    # project authorization for every reference; this avoids rereading the host
    # registry and reissuing the same grant for every original file.
    cache = getattr(service, '_historical_granted_roots', {})
    for registered, resource_id in cache.get(str(project), {}).items():
        if root.is_relative_to(registered) or path == registered:
            return resource_id, registered

    def remember(resource_id, registered):
        cache.setdefault(str(project), {})[registered] = resource_id
        service._historical_granted_roots = cache
        return resource_id, registered

    # Existing relocated resources and original grants take precedence.
    for resource in storage.resources():
        registered = storage.resolve_locator(resource['locator'])
        if root.is_relative_to(registered) or path == registered:
            service.grant_resource(project, {'id': LOCAL_USER}, resource['id'])
            return remember(resource['id'], registered)
    target = 'historical-source:' + digest(str(root.parent))[:24]
    try:
        storage.target(target)
    except ValueError:
        storage.register_target(root.parent, 'Historical scientific originals', target_id=target)
    resource_id = 'historical-source:' + digest(str(root))[:24]
    resource = storage.register_resource(resource_id, storage.locator(target, root.name), writer_mode='sealed')
    service.grant_resource(project, {'id': LOCAL_USER}, resource_id)
    return remember(resource['id'], root)


def native_references(facts):
    for family in ('documents', 'notes', 'artifacts'):
        for row in facts[family]:
            kind = {'documents': 'document', 'notes': 'note', 'artifacts': 'artifact'}[family]
            revision = row.get('revision')
            location = {'kind': kind, 'id': row['id']}
            if revision:
                location |= {'revision': int(revision), 'content_hash': row['content_hash']}
            label = row.get('title') or row.get('name') or row['id']
            purpose = 'note' if kind == 'note' else 'original-archive' if kind == 'artifact' and row['media_type'] in (
                'application/zip', 'application/gzip', 'application/x-tar', 'application/octet-stream') else 'process'
            if kind == 'document':
                purpose = 'report' if row['kind'] == 'report' else 'protocol'
            yield {'request_id': request(f'{kind}:{row["id"]}:{revision}'), 'evidence': {
                'logical_id': f'{kind}:{row["id"]}' + (f':r{revision}' if revision else ''),
                'role': purpose, 'label': label[:500], 'format': row.get('media_type') or row.get('format') or 'text/markdown',
                'locator': location, 'byte_count': int(row['bytes']) if kind == 'artifact' else None,
                'sha256': row['sha256'] if kind == 'artifact' else None}}


def backfill_one(database, source, inventory_hash, output, *, preview_only=False):
    """Stable receipts permit crash recovery at each bounded batch boundary."""
    target = output / (digest(source['source_key'])[:24] + '.json')
    reviewed = output.parent / 'preview' / target.name
    if not preview_only and (target.exists() or reviewed.exists()):
        preview = json.loads((target if target.exists() else reviewed).read_bytes())
        if preview['source'] != source or preview['body']['source_manifest_hash'] != inventory_hash:
            raise Conflict('fixed backfill source differs; review a separate correction')
        project = register_project(database, source)
        service = ResearchRecords(database)
        if not target.exists():
            # Freeze all scientific facts before registration changes the database.
            roots = []
            if source['source_path']:
                p = ROOT / source['source_path']
                roots.append(p if p.is_dir() else p.parent)
            roots += [ROOT / s for s in source['work_roots']]
            for root in roots:
                if root.is_dir():
                    grant_path(service, project, root)
            for reference in preview['evidence']:
                ref = reference['evidence']
                if ref['locator'].get('resource_id') == 'pending-grant':
                    path = ROOT / ref['label']
                    actual = file_identity(path)
                    if actual['sha256'] != ref['sha256'] or actual['byte_count'] != ref['byte_count']:
                        raise Conflict('original bytes changed since the reviewed inventory: ' + ref['label'])
                    resource, root = grant_path(service, project, path)
                    ref['locator'] = {'kind': 'file', 'resource_id': resource, 'member': path.relative_to(root).as_posix()}
            atomic_json(target, preview)
        return apply_prepared(database, preview, inventory_hash, target)
    if not preview_only:
        raise ValueError('create and review a preview before applying historical sources')
    if preview_only and not source['project_id']:
        project = identity('historical-platform-project:' + source['source_key'])
        facts = {'documents': [], 'notes': [], 'artifacts': [], 'runs': [], 'studies': []}
    else:
        project = source['project_id'] if preview_only else register_project(database, source)
        facts = native_facts(database, project)
    service = ResearchRecords(database)
    directory = ROOT / source['source_path'] if source['source_path'] else None
    if directory and directory.is_file():
        directory = directory.parent
    paths = {f['path']: f for f in source['files']}
    # Already archived Git originals retain their current logical resource.
    resource_name = 'archived-study:' + source['source_key'].removeprefix('lab-exploration:')
    try:
        archived = service.storage.resolve_resource(resource_name)
    except ValueError:
        archived = None
    if archived and archived.is_dir():
        for p in source_files(archived):
            paths.setdefault(p.relative_to(ROOT).as_posix(), file_identity(p) | {'role': role(p)})
    has_archive = any('zip' in a['media_type'] or a['name'].lower().endswith(('.zip', '.tar', '.tar.gz')) or 'archive' in a['name'].lower() or
                      'evidence' in a['name'].lower() for a in facts['artifacts'])
    if not has_archive:
        for relative in source['work_roots']:
            root = ROOT / relative
            # Never collect dependency runtimes or another experiment's input.
            if re.search(r'venv|deps|native|pytest|config$', root.name):
                continue
            for p in source_files(root):
                paths.setdefault(p.relative_to(ROOT).as_posix(), file_identity(p) | {'role': role(p)})
    notes = bool(facts['notes']) or any(f['role'] == 'note' for f in paths.values())
    has_protocol = bool(source.get('design')) or any(d['kind'] == 'record' for d in facts['documents'])
    missing = []
    if not source['project_id']:
        missing.append('No original platform project identity identified; this is a later platform registration. Original case/checkpoint identities remain in their carriers.')
    if not has_protocol:
        missing.append('No independently preserved preregistered protocol identified; later notebooks/reports are not substituted for it.')
    if not has_archive and not facts['runs'] and not any(f['role'] in ('process', 'checkpoint') for f in paths.values()):
        missing.append('No original process/checkpoint carrier identified; descriptions cannot reconstruct missing model states.')
    if not notes:
        missing.append('No original scientific notebook identified.')
    if source['classification'] == 'proposal':
        missing = ['Unstarted conditional draft; no execution data should exist. E64 was reassigned to centered restart.']
    protocol = (directory / source['design']).read_text(encoding='utf-8-sig') if source.get('design') else None
    report = (directory / source['report']).read_text(encoding='utf-8-sig') if source.get('report') else None
    status = 'planned' if source['classification'] == 'proposal' else 'interrupted' if source['original_id'] == 'E07' else (
        'completed' if report and (facts['artifacts'] or facts['runs'] or any(f['role'] == 'result' for f in paths.values())) else 'unknown')
    kernels = set(source['kernels']) | {r['kernel_id'] for r in facts['runs'] if r['kernel_id']}
    if not kernels and source['classification'] != 'proposal':
        missing.append('Kernel identity is not established in the index; original configurations are preserved and no current default is substituted.')
    spec = {'source_key': source['source_key'], 'original_id': source['original_id'], 'title': source['title'],
        'classification': source['classification'], 'execution_status': status, 'experiment_date': source['experiment_date'],
        'date_basis': source['date_basis'], 'executor': 'ai' if source['source_key'].startswith('lab-exploration:') else 'unknown',
        'kernels': sorted(kernels), 'protocol': protocol[:200000] if protocol else None,
        'protocol_version': paths[(directory / source['design']).relative_to(ROOT).as_posix()]['sha256'] if protocol else None,
        'conclusion': report[:200000] if report else None, 'missing': missing,
        'metadata': {'source_path': source['source_path'], 'original_project_id': source['project_id'],
            'source_document': (directory / (source.get('report') or source.get('design'))).relative_to(ROOT).as_posix()
                if directory and (source.get('report') or source.get('design')) else source['source_path'],
            'platform_registration_kind': 'reuse-original' if source['project_id'] else 'later-index-identity',
            'backfill_date': '2026-10-10', 'inventory_hash': inventory_hash, 'execution_basis': source['execution_basis'],
            'native_counts': {k: len(v) for k, v in facts.items()}, 'original_files': len(paths),
            'whole_system_continuity': 'as documented in originals; no new recovery or subject reconstruction'}}
    texts = []
    # Existing publications/notes are reused; new small texts are only added
    # where no corresponding native family exists. Exact source text is retained.
    reports = sorted([f for f in source['files'] if f['role'] == 'report'],
                     key=lambda f: (0 if '.r' not in Path(f['path']).name else 1, f['path']))
    revision_by_language = {}
    for f in [*reports, *[s for s in source['files'] if s['role'] in ('protocol', 'note')]]:
        purpose = f['role']
        if purpose == 'report' and any(d['kind'] == 'report' for d in facts['documents']):
            continue
        if purpose == 'protocol' and has_protocol and facts['documents']:
            continue
        if purpose == 'note' and facts['notes']:
            continue
        path = ROOT / f['path']
        if path.suffix != '.md' or f['byte_count'] > 900000:
            continue
        name = path.name
        lang = 'en' if '.en.' in name or '/en/' in f['path'] else 'zh'
        is_report_series = purpose == 'report' and re.fullmatch(r'report(?:\.r\d+)?\.(?:zh|en)\.md', name)
        key = source['source_key'] + (':report:' + lang if is_report_series else ':text:' + f['path'])
        previous = revision_by_language.get(key, 0)
        texts.append({'request_id': request(key + ':' + f['sha256']), 'identity': identity(key),
            'expected_revision': previous, 'kind': purpose, 'title': (source['title'] + ' · ' + name)[:200],
            'markdown': path.read_text(encoding='utf-8-sig'),
            'revision_reason': 'Preserved source revision: ' + name if previous else None})
        revision_by_language[key] = previous + 1
    # Always distinguish this later inventory note from original scientific notes.
    texts.append({'request_id': request(source['source_key'] + ':backfill-note:' + inventory_hash),
        'identity': identity(source['source_key'] + ':backfill-note'), 'kind': 'note',
        'title': ('补录说明（2026-10-10） · ' + source['title'])[:200],
        'markdown': '这是 2026-10-10 的资料补录说明，不是原实验笔记，也不补造运行过程。\n\n'
            + '原件、报告修订和已有个体身份均保留；原始执行日期与补录日期分开。\n\n'
            + '\n'.join('- ' + s for s in missing)})
    evidence = list(native_references(facts))
    file_refs = []
    if not preview_only:
        roots = ([directory] if directory else []) + ([archived] if archived else [])
        if not has_archive:
            roots += [ROOT / s for s in source['work_roots'] if (ROOT / s).is_dir()]
        for root in roots:
            grant_path(service, project, root)
    for f in paths.values():
        path = ROOT / f['path']
        ref = {'logical_id': 'original-file:' + f['path'], 'role': f['role'], 'label': f['path'],
               'format': f['format'], 'sha256': f['sha256'], 'byte_count': f['byte_count']}
        if preview_only:
            ref['locator'] = {'kind': 'file', 'resource_id': 'pending-grant', 'member': f['path']}
        else:
            resource, root = grant_path(service, project, path)
            ref['locator'] = {'kind': 'file', 'resource_id': resource, 'member': path.relative_to(root).as_posix()}
        file_refs.append({'request_id': request(source['source_key'] + ':' + ref['logical_id']), 'evidence': ref})
    body = {'request_id': request(source['source_key'] + ':plan:' + inventory_hash), 'source_manifest_hash': inventory_hash,
            'records': [{'spec': spec, 'texts': texts}]}
    # Bounded individual references are appended after registration, so a large
    # native cohort need not be forced into one giant JSON transaction.
    preview = {'source': source, 'project_id': project, 'body': body, 'evidence': evidence + file_refs,
               'native_runs': facts['runs'], 'native_studies': facts['studies'], 'bytes_copied': 0}
    atomic_json(target, preview)
    if preview_only:
        return {'source_key': source['source_key'], 'project_id': project, 'preview': str(target),
                'references': len(evidence) + len(file_refs), 'native_runs': len(facts['runs']), 'missing': missing}
    return apply_prepared(database, preview, inventory_hash, target)


def apply_prepared(database, preview, inventory_hash, target):
    """Resume from immutable preview facts, not from the now-modified index."""
    source, project, body = preview['source'], preview['project_id'], preview['body']
    actor, service = {'id': LOCAL_USER}, ResearchRecords(database)
    facts = {'runs': preview['native_runs'], 'studies': preview['native_studies']}
    plan = service.backfill_plan(project, actor, body)
    applied = service.backfill_apply(project, actor, plan['id'], {'request_id': request(source['source_key'] + ':apply:' + inventory_hash),
        'plan_hash': plan['plan_hash']})
    index = applied['records'][0]['id']
    final_body = FinalizeRecord.model_validate({
        'request_id': request(source['source_key'] + ':finalize:' + inventory_hash),
        'execution_status': body['records'][0]['spec']['execution_status']}).model_dump(mode='json')
    # A committed completion receipt witnesses the original verification. Resume
    # it by content identity rather than reissuing tens of thousands of entries.
    # Fresh integrity checks remain explicit verify operations, not a side effect
    # of replaying an already committed batch after a lost response or restart.
    try:
        receipt = service.receipt(project, actor, final_body['request_id'])
    except NotFound:
        receipt = None
    if receipt is not None:
        fingerprint = digest({'action': 'finalize', 'value': {'id': str(index), **final_body}})
        if receipt['action'] != 'finalize' or receipt['fingerprint'] != fingerprint:
            raise Conflict('completed backfill receipt belongs to different content')
        verified = receipt['result']
        if verified.get('experiment_id') != str(index) or not verified.get('finalized'):
            raise Conflict('completed backfill receipt has an invalid experiment identity')
        result = completed_result(preview, index, plan, verified) | {'replayed_verification': True}
        atomic_json(target.with_suffix('.receipt.json'), result)
        return result
    for ref in preview['evidence']:
        service.attach(project, actor, index, ref)
    for row in facts['runs']:
        service.append(project, actor, index, {'request_id': request(source['source_key'] + ':subject:' + row['id']),
            'kind': 'subject', 'original_key': 'native-run:' + row['id'], 'content': row})
        service.attach(project, actor, index, {'request_id': request(source['source_key'] + ':run:' + row['id']),
            'evidence': {'logical_id': 'native-run:' + row['id'], 'role': 'subject', 'label': row['name'],
            'format': 'threemind.runtime-run', 'locator': {'kind': 'run', 'id': row['id']}}})
    for row in facts['studies']:
        service.append(project, actor, index, {'request_id': request(source['source_key'] + ':condition:' + row['id']),
            'kind': 'condition', 'original_key': 'native-study:' + row['id'], 'content': row})
    verified = service.finalize(project, actor, index, final_body)
    result = completed_result(preview, index, plan, verified)
    atomic_json(target.with_suffix('.receipt.json'), result)
    return result


def completed_result(preview, index, plan, verified):
    return {'source_key': preview['source']['source_key'], 'project_id': preview['project_id'], 'id': index, 'plan': plan,
        'execution_status': preview['body']['records'][0]['spec']['execution_status'], 'coverage': verified['coverage'],
        'references': len(preview['evidence']) + len(preview['native_runs']),
        'native_subjects': len(preview['native_runs']), 'missing': verified['problems'], 'originals_copied': 0}
