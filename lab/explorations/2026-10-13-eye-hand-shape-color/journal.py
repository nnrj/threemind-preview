"""E69 durable complete-subject boundaries and canonical research recording.

No Core imports, simulation calls or rollback recovery live in this module.
An uncommitted experience is an error requiring a human continuity decision.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from threemind_lab.storage_files import atomic_json, checked_path, file_lock, under_root

EXPERIMENT = 'E69'
RESOURCE = 'research:e69-eye-hand-shape-color'
SOURCE = 'lab-exploration:' + HERE.name
KERNEL = 'threemind.continuous-memory/5.1'


def implementation_identity():
    from importlib.metadata import version

    from threemind_lab.provenance import capture_implementation
    value=capture_implementation('native')
    value['research_packages']={name:version(name) for name in ('torch','safetensors')}
    return value


def read(path):
    return json.loads(Path(path).read_bytes())


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def put(path, content):
    """Publish immutable bytes; never overwrite old scientific evidence."""
    path = checked_path(Path(path).absolute())
    content = bytes(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError('original content conflict: ' + str(path))
        return
    temporary = path.with_name(path.name + '.partial')
    with temporary.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    # Hard-link publication refuses an existing destination on every platform.
    os.link(temporary, path)
    temporary.unlink()


def fixed_json(path, value):
    put(path, encoded(value))


def manifest(folder):
    folder = checked_path(Path(folder).absolute())
    result = {}
    for path in sorted(folder.rglob('*')):
        checked_path(path)
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = {
                'bytes': path.stat().st_size, 'sha256': sha(path)}
    if not result:
        raise ValueError('a complete boundary must contain state files')
    return result


class ContinuityUncertain(RuntimeError):
    pass


class BoundaryPause(RuntimeError):
    pass


class BoundaryJournal:
    """Serialize explicit operations and save their complete current result.

    save_system(system, folder) must save every component into a NEW folder.
    restore_system(folder) must restore it; describe_system(system) returns
    identity, time_us and learning {head: {computed_updates, committed_updates}}.
    The caller owns the physical and scientific definition of the whole system.
    """
    def __init__(self, root, identity, save_system, restore_system, describe_system,
                 *, work=None, reserve_gib=25, reserve_memory_gib=2):
        self.root = checked_path(Path(root).absolute())
        self.work = checked_path(Path(work or root).absolute())
        self.root.mkdir(parents=True, exist_ok=True)
        self.identity = str(identity)
        self.save_system, self.restore_system, self.describe_system = save_system, restore_system, describe_system
        self.latest = self.root / 'latest.json'
        self.flight = self.root / 'in-flight.json'
        self.lock = self.root / '.journal.lock'
        self.reserve_gib, self.reserve_memory_gib = reserve_gib, reserve_memory_gib
        self.pointer = self.system = None
        self.keys = set()

    def _description(self):
        d = json.loads(encoded(self.describe_system(self.system)))
        if d.get('identity') != self.identity or not isinstance(d.get('time_us'), int) or d['time_us'] < 0:
            raise ValueError('complete subject identity/time is required')
        if not isinstance(d.get('learning'), dict):
            raise TypeError('all personal peripheral learning counters must be declared')
        for name, counts in d['learning'].items():
            computed, committed = counts.get('computed_updates'), counts.get('committed_updates')
            if not isinstance(computed, int) or computed < 0 or committed != computed:
                raise ContinuityUncertain('peripheral state rollback or invalid counters: ' + name)
        return d

    def _validate_chain(self):
        previous = None
        for sequence, path in enumerate(sorted((self.root / 'chain').glob('*.json'))):
            current = read(path)
            content = {k: v for k, v in current.items() if k != 'boundary_sha256'}
            if (path.stem != f'{sequence:06d}' or current['sequence'] != sequence or
                    current['identity'] != self.identity or
                    hashlib.sha256(encoded(content)).hexdigest() != current['boundary_sha256']):
                raise ContinuityUncertain('broken identity or boundary chain')
            if current['key'] in self.keys:
                raise ContinuityUncertain('repeated operation in boundary chain')
            self.keys.add(current['key'])
            if previous:
                if current['parent'] != previous['boundary_sha256'] or current['start_us'] != previous['end_us']:
                    raise ContinuityUncertain('broken complete-state ancestry')
            elif current['key'] != 'birth' or current['parent'] is not None or current['start_us'] != 0:
                raise ContinuityUncertain('missing blank birth boundary')
            if current['end_us'] < current['start_us']:
                raise ContinuityUncertain('simulated time rollback')
            previous = current
        if previous != self.pointer:
            raise ContinuityUncertain('latest pointer differs from the complete chain')

    def open_current(self, factory):
        with file_lock(self.lock):
            if self.system is not None:
                raise ValueError('subject is already open in this journal')
            if self.flight.exists():
                raise ContinuityUncertain('uncommitted experience; do not clear or replay: ' + str(self.flight))
            if self.latest.exists():
                self.pointer = read(self.latest)
                self._validate_chain()
                folder = under_root(self.root, self.pointer['checkpoint'])
                if manifest(folder) != self.pointer['files']:
                    raise ContinuityUncertain('current complete state changed or is missing')
                self.system = self.restore_system(folder)
                if self._description() != self.pointer['description']:
                    raise ContinuityUncertain('restored complete state metadata does not match current boundary')
                return self.system
            if any(p.name != self.lock.name for p in self.root.iterdir()):
                raise ContinuityUncertain('existing subject files without a current boundary; cannot rebirth')
            self.system = factory()
            d = self._description()
            if d['time_us'] != 0 or any(v['computed_updates'] for v in d['learning'].values()):
                raise ValueError('new formal subject must start completely blank')
            if d.get('nodes', 0) != 0 or d.get('edges', 0) != 0:
                raise ValueError('new formal Core must start blank')
            atomic_json(self.flight, {'key': 'birth', 'parent': None, 'start_us': 0, 'pid': os.getpid()})
            self._commit('birth', d)
            return self.system

    def guard(self):
        if (self.work / 'STOP').exists():
            raise BoundaryPause('STOP requested at the current complete boundary')
        if shutil.disk_usage(self.root).free < self.reserve_gib * 2**30:
            raise BoundaryPause(f'reserve {self.reserve_gib} GiB free disk')
        import psutil
        if psutil.virtual_memory().available < self.reserve_memory_gib * 2**30:
            raise BoundaryPause(f'reserve {self.reserve_memory_gib} GiB available memory')

    def _commit(self, key, before):
        after = self._description()
        if after['time_us'] < before['time_us'] or after['learning'].keys() != before['learning'].keys():
            raise ContinuityUncertain('time rollback or a changed peripheral set')
        for name, values in before['learning'].items():
            if after['learning'][name]['committed_updates'] < values['committed_updates']:
                raise ContinuityUncertain('peripheral learning rolled back: ' + name)
        seq = 0 if self.pointer is None else self.pointer['sequence'] + 1
        folder = self.root / 'boundaries' / f'{seq:06d}'
        folder.parent.mkdir(parents=True, exist_ok=True)
        self.save_system(self.system, folder)
        if self._description() != after:
            raise ContinuityUncertain('saving changed the declared current subject state')
        for path in folder.rglob('*'):
            checked_path(path)
            if path.is_file():
                with path.open('r+b') as stream:
                    os.fsync(stream.fileno())
        state = {'sequence': seq, 'key': key, 'identity': self.identity,
                 'start_us': before['time_us'], 'end_us': after['time_us'],
                 'parent': self.pointer['boundary_sha256'] if self.pointer else None,
                 'checkpoint': folder.relative_to(self.root).as_posix(),
                 'description': after, 'files': manifest(folder)}
        state['boundary_sha256'] = hashlib.sha256(encoded(state)).hexdigest()
        fixed_json(self.root / 'chain' / f'{seq:06d}.json', state)
        atomic_json(self.latest, state)
        self.pointer = state
        self.keys.add(key)
        self.flight.unlink()  # Only a committed operation can remove its own marker.
        atomic_json(self.work / 'progress.json', {
            'pid': os.getpid(), 'identity': self.identity, 'key': key, 'sequence': seq,
            'sim_s': after['time_us'] / 1e6, 'updated_epoch': time.time(),
            'free_disk_GiB': shutil.disk_usage(self.root).free / 2**30})

    def execute(self, key, operation):
        with file_lock(self.lock):
            if self.system is None or self.pointer is None:
                raise ValueError('open the complete current subject first')
            if self.flight.exists() or read(self.latest) != self.pointer:
                raise ContinuityUncertain('uncommitted experience or another writer changed the current boundary')
            if not key or key in self.keys or key == 'birth':
                raise ValueError('operation key already committed or invalid; no automatic replay')
            self.guard()
            before = self._description()
            if before != self.pointer['description']:
                raise ContinuityUncertain('live state changed outside a declared operation')
            atomic_json(self.flight, {'key': key, 'parent': self.pointer['boundary_sha256'],
                                      'start_us': before['time_us'], 'pid': os.getpid()})
            result = operation(self.system)
            self._commit(key, before)
            return result


class _DeferredClient:
    """A saved subject can open while authentication is unavailable."""
    def __init__(self):
        self.value = None

    def _get(self):
        if self.value is None:
            from threemind_lab.operations_client import OperationsClient
            self.value = OperationsClient.from_environment(source='ai')
            self.value.client.timeout = 120
        return self.value

    def call(self, *args, **kwargs):
        return self._get().call(*args, **kwargs)

    def request(self, *args, **kwargs):
        return self._get().request(*args, **kwargs)

    def close(self):
        if self.value is not None:
            self.value.close()


class ResearchStudy:
    """Canonical index and referenced originals; contains no subject factory."""
    def __init__(self, work, design_path=None, *, prepare=False, client=None, storage=None):
        from threemind_lab.config import load_env
        from threemind_lab.research_recorder import ResearchRecorder
        from threemind_lab.research_storage import ResearchStorage
        load_env()
        self.work = checked_path(Path(work).absolute())
        self.design_path = Path(design_path or HERE / 'design.json').resolve()
        frozen_design = self.work / 'design.json'
        self.design = read(frozen_design if frozen_design.exists() and not prepare else self.design_path)
        if self.design.get('kernel_id', KERNEL) != KERNEL:
            raise ValueError('E69 is registered for continuous-memory/5.1 only')
        self.storage = storage or ResearchStorage()
        self.client = client or _DeferredClient()
        if prepare:
            self._prepare()
        self.meta = read(self.work / 'platform.json')
        self.project = self.meta['project_id']
        self.recorder = ResearchRecorder(self.work, self.project, client=self.client)
        if (self.recorder.control / 'identity.json').exists():
            self.recorder.resume_recording()
        elif prepare:
            self.recorder.register({
                'source_key': SOURCE, 'original_id': EXPERIMENT,
                'title': self.design.get('title', 'E69 连续眼动、手眼协调与形色学习'),
                'executor': 'ai', 'execution_status': 'running',
                'experiment_date': self.design.get('experiment_date', '2026-10-13'),
                'kernels': [self.design.get('kernel_id', KERNEL)],
                'question': self.design.get('question', '连续完整个体能否学会注视、指认及形色回答？'),
                'protocol': (HERE / 'design.zh.md').read_text(encoding='utf-8'),
                'protocol_version': sha(self.design_path),
                'metadata': self.design.get('metadata', {}) | {
                    'continuous': True, 'rollback_authorized': False,
                    'source_path': HERE.relative_to(ROOT).as_posix(), 'design_sha256': sha(self.design_path)}},
                request_id=self.rid('register'))
        else:
            raise ValueError('formal registration receipt missing; run explicit prepare first')
        if prepare:
            self.publish_protocol()
            self.sync(strict=True)

    def rid(self, key):
        return str(uuid5(UUID(self.project), 'e69:' + key))

    def _prepare(self):
        self.client.request('GET', '/api/v2/me')
        listing = self.client.call('records.list', {'query': {'query': EXPERIMENT, 'limit': 100}})
        if any(r.get('original_id') == EXPERIMENT and r.get('source_key') != SOURCE for r in listing['rows']):
            raise ValueError('E69 is already assigned to a different research experiment')
        existing_records = [r for r in listing['rows'] if r.get('original_id') == EXPERIMENT]
        if existing_records and not (self.work / 'platform.json').exists():
            raise ContinuityUncertain('E69 is registered but its local identity is missing; inspect original evidence before recovery')
        self.work.mkdir(parents=True, exist_ok=True)
        if (self.work / 'platform.json').exists():
            if read(self.work / 'platform.json')['design_sha256'] != sha(self.design_path):
                raise ValueError('registered design differs; cannot silently revise a formal subject protocol')
            self.verify_sources()
            return
        title = self.design.get('title', 'E69 连续眼动、手眼协调与形色学习')
        projects = [r for r in self.client.request('GET', '/api/v2/projects') if r['name'] == title]
        if len(projects) > 1:
            raise ValueError('ambiguous project title')
        project = projects[0] if projects else self.client.request('POST', '/api/v2/projects', body={'name': title})
        self.project = str(project['id'])
        root = self.storage.writable_root() / 'experiments'
        if self.work.parent != root.resolve():
            raise ValueError('formal originals must use the managed experiments root')
        overview = self.client.request('GET', '/api/v2/storage')
        target = next(t for t in overview['targets'] if t['id'] == 'managed-research-experiments')
        if Path(target['configuration']['path']).resolve() != root.resolve():
            raise ValueError('managed storage root mismatch')
        existing = [r for r in overview['resources'] if r['id'] == RESOURCE]
        if existing:
            if existing[0]['relative_path'] != self.work.name or existing[0]['target_id'] != target['id']:
                raise ValueError('existing research resource points elsewhere')
        else:
            self.client.request('POST', '/api/v2/storage/resources', body={
                'resource_id': RESOURCE, 'target_id': target['id'], 'relative_path': self.work.name,
                'writer_mode': 'cooperative', 'expected_revision': 0})
        self.client.request('POST', '/api/v2/storage/record-evidence-grants', body={
            'project_id': self.project, 'resource_id': RESOURCE})
        implementation = implementation_identity()
        paths = set(HERE.glob('*.py')) | set(HERE.glob('design.*'))
        paths |= set((ROOT / 'lab' / 'tools').glob('*.py'))
        paths |= {ROOT / p for p in implementation['source_files']}
        paths |= {ROOT / p for p in self.design.get('source_files', [])}
        paths |= {ROOT / 'docs' / lang / 'training-protocol.md' for lang in ('zh', 'en')}
        sources = {}
        for path in sorted(paths):
            path = path.resolve()
            if not path.is_relative_to(ROOT):
                raise ValueError('frozen source must reside in the repository')
            name = path.relative_to(ROOT).as_posix()
            put(self.work / 'source-reference' / name, path.read_bytes())
            sources[name] = sha(path)
        fixed_json(self.work / 'source-reference' / 'manifest.json', sources)
        fixed_json(self.work / 'design.json', self.design)
        fixed_json(self.work / 'platform.json', {
            'project_id': self.project, 'resource_id': RESOURCE, 'source_key': SOURCE,
            'design_sha256': sha(self.design_path), 'implementation': implementation,
            'manifest_sha256': sha(self.work / 'source-reference' / 'manifest.json')})

    def verify_sources(self):
        for name, expected in read(self.work / 'source-reference' / 'manifest.json').items():
            if sha(ROOT / name) != expected or sha(self.work / 'source-reference' / name) != expected:
                raise ValueError('frozen source changed: ' + name)
        recorded=read(self.work/'platform.json')['implementation']
        current=implementation_identity()
        for key in ('native_binary_sha256','python','platform','machine','packages','research_packages'):
            if recorded.get(key)!=current.get(key):
                raise ValueError('frozen execution environment changed: '+key)

    def attach(self, path, role='process', stage=None):
        path = checked_path(Path(path).absolute())
        name = path.relative_to(self.work).as_posix()
        self.recorder.attach({
            'logical_id': 'file:' + name, 'role': role, 'label': name,
            'format': ''.join(path.suffixes).lstrip('.') or 'opaque',
            'byte_count': path.stat().st_size, 'sha256': sha(path), 'stage_key': stage,
            'locator': {'kind': 'file', 'resource_id': RESOURCE, 'member': name}},
            request_id=self.rid('file:' + name))

    def append(self, kind, key, content):
        return self.recorder.append(kind, key, content, request_id=self.rid(kind + ':' + key))

    def text(self, key, kind, title, markdown, *, revision=0):
        return self.recorder.text({
            'request_id': self.rid('text:' + key + ':' + str(revision)),
            'identity': self.rid('text-identity:' + key), 'expected_revision': revision,
            'kind': kind, 'title': title, 'markdown': markdown})

    def publish_protocol(self):
        for lang in ('zh', 'en'):
            path = HERE / f'design.{lang}.md'
            self.text('protocol:' + lang, 'protocol', 'E69 三阶段连续学习 / Protocol ' + lang,
                      path.read_text(encoding='utf-8'))
        for name in ('platform.json', 'design.json', 'source-reference/manifest.json'):
            self.attach(self.work / name, 'protocol')

    def sync(self, *, strict=False):
        status = self.recorder.synchronize(strict=strict)
        atomic_json(self.work / 'sync-status.json', status)
        return status

    def close(self):
        self.client.close()
