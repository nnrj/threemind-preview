"""Read original historical sources; produce fixed, reviewable backfill inputs.

Never import historical runners, instantiate engines or load model state. The
inventory is deliberately a separate adapter, so frozen experiments stay frozen.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from uuid import UUID, uuid5

from threemind_kernels.registry import kernel_catalog
from threemind_lab.config import ROOT
from threemind_lab.data_catalog import wire
from threemind_lab.database import LOCAL_USER
from threemind_lab.research_records import digest

NAMESPACE = UUID('50cfc527-d747-4c9a-bc37-55897d44df57')
EARLY_PROJECTS = [
    '900840b0-d00d-450c-9669-72600cea7c40', '8c69053a-125e-4fbd-80a8-5a028abb8a9c',
    '7c4fb6f2-ca29-4cd8-9a4c-f112ddbff1dd', '5f779f43-ab27-4638-bb11-458a43598637',
    'a9bd83bb-3d57-4eab-859d-68312f6b2b17', '194a2f1f-4912-435b-b94e-d8ac64fe4788',
    '62fd8734-a42a-4950-84d3-496c3bded189', '2dabc73f-1f27-498b-83ae-93c4c6e10c1c',
    '006772a5-86e9-4f01-bcd2-2d5f48f7a70e', 'cb3a2d4a-f8a2-440e-9182-75148e9454a8',
    'e769cd2d-c636-41b0-a266-6af1cca4b805', 'cbde2d48-284d-4294-9184-89f439923547',
    '59aee7a1-5248-417f-a03b-b56f858a04d9', 'df63c577-3b39-4642-87c5-2e9e1b05f165',
    '92548061-22c0-4bd9-b283-c4e1e7f4360d', 'd27d28d0-55f1-4783-99fd-e3a503ec1573',
    '36029e2c-2f4c-4f21-9aa5-376b0701c044', 'c49b4ad2-3d53-486a-b124-433e5491df36',
    '91dfc963-f441-49b7-8dc6-65dba73ab2cb', '242ff8e9-f7d5-4d89-8964-cff06ca8fdf0',
    '2561276a-6460-4c52-910b-e92ef516e335', '5e4f46e7-5d55-44de-a2b6-9707e2057387',
]
EXTRA_FORMAL = {'532e9e84-9454-46ef-bcb5-b5d80ca8916f'}
UNPUBLISHED = {'2026-10-08-retention-kernel', '2026-10-08-retention-repair',
               '2026-10-08-retention-telemetry-text', '2026-10-09-local-events-v4'}
RECENT_ROOTS = {
    '2026-10-08-retention-kernel': ['.work/retention-v3'],
    '2026-10-08-retention-repair': [],
    '2026-10-08-retention-telemetry-text': [],
    '2026-10-09-local-events-v4': ['.work/local-v4-validation-20261009'],
}
SKIP_FILES = {'STOP', 'usage.json', 'budget.json', '.report-revisions.lock'}


def identity(key):
    return str(uuid5(NAMESPACE, key))


def file_identity(path):
    sha, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while block := stream.read(1024**2):
            sha.update(block)
            size += len(block)
    return {'path': path.relative_to(ROOT).as_posix(), 'byte_count': size, 'sha256': sha.hexdigest(),
            'format': ''.join(path.suffixes).lstrip('.') or 'opaque'}


def source_files(directory):
    for path in sorted(directory.rglob('*')):
        if path.is_symlink() or not path.is_file() or path.name in SKIP_FILES:
            continue
        if any(p in {'__pycache__', '.research-records', 'node_modules'} for p in path.relative_to(directory).parts):
            continue
        if path.suffix in ('.pyc', '.tmp', '.log') or '.partial' in path.name:
            continue
        if re.search(r'credential|secret|password|token|\.env', path.name, re.IGNORECASE):
            continue
        yield path


def role(path):
    name = path.name.lower()
    if name.endswith('.md'):
        if name.startswith(('report', 'followup-report')):
            return 'report'
        if 'design' in name or 'protocol' in name or 'registration' in name:
            return 'protocol'
        return 'note'
    if 'checkpoint' in name or 'state' in name or name.endswith(('.pt', '.npz')):
        return 'checkpoint'
    if name.endswith(('.py', '.rs')):
        return 'implementation'
    if 'result' in name or 'analysis' in name or 'verification' in name:
        return 'result'
    return 'process'


def scan_sources(database):
    """Fixed source scope plus all authorized database projects, SELECT only."""
    projects = {str(p['id']): wire(p) for p in database.projects({'id': LOCAL_USER})}
    legal_kernels = {k['kernel_id'] for k in kernel_catalog()}
    register = (ROOT / 'docs/zh/history/sources/source-register.md').read_text(encoding='utf-8')
    old_ids = {folder: eid for eid, folder in re.findall(r'\| (E\d+) \|[^\n]*lab/explorations/([^/]+)/', register)}
    mapping = {f'E{i:02d}': p for i, p in enumerate(EARLY_PROJECTS, 1)}
    items, assigned = [], set()
    for directory in sorted((ROOT / 'lab/explorations').iterdir()):
        if not directory.is_dir():
            continue
        md = {p.name: p.read_text(encoding='utf-8-sig') for p in directory.glob('*.md')}
        design = next((n for n in ('design.zh.md', 'protocol.md', 'design.md') if n in md), None)
        report = next((n for n in ('report.zh.md', 'report.md') if n in md), None)
        original = old_ids.get(directory.name)
        title_text = md.get(report or design, '')
        header = title_text.splitlines()[0].lstrip('# ').strip() if title_text else directory.name
        own_id = re.match(r'(E\d+(?:[–—-]E?\d+)?)\s*[：: ]', header)
        if own_id:
            original = own_id[1]
        proposal = directory.name.endswith('four-field-reproduction')
        if proposal:
            original = None  # Its reserved E64 was reassigned; keep the draft distinct.
        project = mapping.get(original)
        choices = [p for p in projects.values() if original and re.match(re.escape(original) + r'(?:\s|[：:])', p['name'])]
        # E50's original and revision have separate historical project identities.
        if choices:
            project = next((p['id'] for p in choices if '修订' in p['name']), choices[0]['id'])
        work_roots = set()
        for path in directory.glob('*.py'):
            text = path.read_text(encoding='utf-8-sig')
            work_roots.update(m.group(1) for m in re.finditer(r'["\']\.work/([^/"\']+)', text))
            work_roots.update(m.group(1) for m in re.finditer(r'["\']\.work["\']\s*/\s*["\']([^/"\']+)', text))
        valid_roots = []
        for name in sorted(work_roots):
            root = ROOT / '.work' / name
            if root.is_dir():
                valid_roots.append(root.relative_to(ROOT).as_posix())
                platform = root / 'platform.json'
                if platform.is_file() and platform.stat().st_size <= 1024**2:
                    value = json.loads(platform.read_bytes())
                    candidate = value.get('project_id')
                    # Only an explicit platform identity from this runner's work
                    # directory may settle an otherwise unnumbered association.
                    source = value.get('settings', {}).get('sources')
                    own_source = source and Path(source).resolve() == directory.resolve()
                    if not project and candidate in projects and own_source:
                        project = candidate
        if directory.name in UNPUBLISHED or proposal:
            project = None
            valid_roots = [s for s in RECENT_ROOTS.get(directory.name, []) if (ROOT / s).is_dir()]
        elif project:
            valid_roots = [s for s in valid_roots if (ROOT / s / 'platform.json').is_file()
                and json.loads((ROOT / s / 'platform.json').read_bytes()).get('project_id') == project]
        if project:
            assigned.add(str(project))
        declared = re.findall(r'(?:threemind\.)?[a-z][a-z-]+/\d+(?:\.\d+)?', '\n'.join(md.values()))
        kernels = sorted({k if k.startswith('threemind.') else 'threemind.' + k for k in declared}
                         & legal_kernels)
        if 'retention-' in directory.name or 'local-events' in directory.name:
            kernels += ['threemind.continuous-memory/4' if 'local-events' in directory.name else 'threemind.continuous-memory/3']
            if 'telemetry-text' in directory.name:
                kernels += ['threemind.continuous-memory/2']
        items.append({'source_key': 'lab-exploration:' + directory.name, 'source_path': directory.relative_to(ROOT).as_posix(),
            'project_id': str(project) if project else None, 'original_id': original,
            'title': header[:200], 'classification': 'proposal' if proposal else 'formal',
            'execution_status': 'planned' if proposal else 'unknown',
            'execution_basis': 'unstarted draft explicitly documented' if proposal else 'original report; execution stages verified separately',
            'experiment_date': directory.name[:10], 'date_basis': 'source directory date; stage times remain in originals',
            'design': design, 'report': report, 'kernels': sorted(set(kernels)), 'work_roots': valid_roots,
            'files': [file_identity(p) | {'role': role(p)} for p in source_files(directory)]})
    for path in sorted((ROOT / 'lab/zh').glob('*.md')):
        number = re.match(r'(\d{3})_', path.name)
        if not number:
            continue
        # These are early experimental notebooks, not newly fabricated E numbers.
        title = path.read_text(encoding='utf-8').splitlines()[0].lstrip('# ').strip()
        english = next(iter((ROOT / 'lab/en').glob(number[1] + '_*.md')), None)
        files = [file_identity(p) | {'role': 'note'} for p in (path, english) if p]
        items.append({'source_key': 'early-notebook:' + number[1], 'source_path': path.relative_to(ROOT).as_posix(),
            'project_id': None, 'original_id': 'N' + number[1].lstrip('0').zfill(2), 'title': title[:200],
            'classification': 'formal', 'execution_status': 'unknown', 'experiment_date': path.name[4:14],
            'date_basis': 'original notebook date', 'execution_basis': 'contemporaneous preliminary notebook; no reconstructed execution',
            'kernels': [], 'work_roots': [], 'files': files, 'design': None, 'report': None})
    unassigned = []
    for key, project in projects.items():
        if key in assigned:
            continue
        if key in EXTRA_FORMAL or re.match(r'^E\d+(?:[–—-]E?\d+)?\s', project['name']):
            unassigned.append(key)
            items.append({'source_key': 'historical-project:' + key, 'source_path': None, 'project_id': key,
                'original_id': re.match(r'^(E\d+)', project['name'])[1] if re.match(r'^E\d+', project['name']) else None,
                'title': project['name'], 'classification': 'formal', 'execution_status': 'unknown',
                'experiment_date': None, 'date_basis': 'original date unresolved', 'execution_basis': 'native database originals',
                'kernels': [], 'work_roots': [], 'files': [], 'design': None, 'report': None})
    included = assigned | set(unassigned)
    projects_ledger = [p | {'disposition': 'formal-source-linked' if key in included else 'development-or-tooling',
        'basis': 'explicit historical source/project identity' if key in included else 'project name and prior development inventory; originals retained, not deleted'}
        for key, p in projects.items()]
    # Non-experiment research notes and diagnostics are explicitly accounted for.
    auxiliary = [file_identity(p) | {'disposition': 'research-context-or-engineering-validation', 'role': role(p)}
        for folder in ('lab/memos', 'lab/validations', 'lab/ai-debug', 'lab/demonstrations', 'docs/benchmarks') if (ROOT / folder).exists()
        for p in source_files(ROOT / folder)]
    result = {'schema': 'threemind.historical-record-inventory/1', 'date': '2026-10-10',
        'scope': ['lab/explorations', 'lab/zh', 'lab/en', 'history source register', 'authorized native projects',
                  'relocation register', 'lab/memos', 'lab/validations', 'lab/ai-debug'],
        'items': items, 'projects': projects_ledger, 'auxiliary': auxiliary,
        'relocations': file_identity(ROOT / 'lab/artifact-index/2026-10-09-relocations.json')}
    result['inventory_hash'] = digest(result)
    return result


def native_facts(database, project):
    """Small authoritative metadata and fixed revisions, no large body arrays."""
    with database.tx(project, read_only=True) as db:
        db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(LOCAL_USER),))
        documents = db.execute('SELECT v.document_id AS id,v.revision,v.content_hash,d.title,d.kind '
            'FROM research_document_versions v JOIN research_documents d ON d.id=v.document_id ORDER BY v.document_id,v.revision').fetchall()
        notes = db.execute('SELECT v.note_id AS id,v.revision,v.content_hash,n.title,v.body->>\'format\' AS format '
            'FROM note_versions v JOIN notes n ON n.id=v.note_id ORDER BY v.note_id,v.revision').fetchall()
        artifacts = db.execute('SELECT id,name,media_type,bytes,sha256,metadata FROM artifacts ORDER BY created_at,id').fetchall()
        runs = db.execute("SELECT id,name,parent_id,origin_kind,origin_hash,origin_checkpoint_id,status,revision,time_us,created_at,"
            "spec->>'kernel_id' AS kernel_id,spec->'config' AS config,spec->>'seed' AS seed FROM runs ORDER BY created_at,id").fetchall()
        studies = db.execute('SELECT id,name,protocol,protocol_hash,created_at FROM studies ORDER BY created_at,id').fetchall()
    return wire({'documents': documents, 'notes': notes, 'artifacts': artifacts, 'runs': runs, 'studies': studies})
