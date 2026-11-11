"""One-shot M6 historical E53 host; existing study locks, API and storage.

Prepared only. Registration, N0 acceptance and a reviewed capacity receipt
are mandatory; M4 delivery is checked before any physical simulation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID, uuid5
import psutil
import pilot_m2 as m
import m6_historical_evidence as ev

HERE = Path(__file__).resolve().parent
WORK = Path('E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m6-historical-v1')
M4 = WORK.parent / 'm4-balanced-v2'
NS = UUID('80218163-4091-49c1-a6e1-9d3e902dfe4d')
PRIVATE_GIB = 3
ORIGINAL_BYTES = 2 * 2**30
MAX_SECONDS = 2 * 3600


def source_paths():
    # Importing the wrapper defines types, never creates a historical world.
    import m6_historical_state
    files = {HERE / name for name in (
        'pilot_m2.py', 'm6_historical_state.py', 'm6_historical_matching.py',
        'm6_historical_metrics.py', 'm6_historical_evidence.py', 'm6_historical_rig.py',
        'm6_historical_audit.py', 'm6_historical_instrument.py', 'm6_historical_analyze.py',
        'm6_historical_driver.py', 'test_m6_historical_state.py', 'test_m6_historical_matching.py',
        'test_m6_historical_metrics.py', 'test_m6_historical_evidence.py', 'test_m6_historical_driver.py',
        'm6-historical-protocol.zh.md', 'm6-historical-protocol.en.md')}
    files |= {m.ROOT / 'lab/tools/study_lock.py',
              m.ROOT / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py'}
    for name, module in list(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if name.startswith('lab.tools.') and filename and Path(filename).suffix == '.py':
            files.add(Path(filename).resolve())
    return sorted(files)


def provenance():
    review = m.read(m.ROOT / '.work/m6-e53-source-review-20261016.json')
    selection = m.read(m.ROOT / '.work/m6-effective-matching-review-20261017.json')
    old = m.ROOT / '.work/ocean-communication-20261006'
    expected_archive = 'd3e432fb2e59721b09fbad69b817cd89b1f5083ec4b4943388a9b4b05a3e3fdf'
    if review['archive_sha256'] != expected_archive or selection['source_archive_sha256'] != expected_archive:
        raise ValueError('historical archive provenance differs')
    if ev.file_sha(old / 'evidence.zip') != expected_archive:
        raise ValueError('historical original archive differs')
    if selection['selector_sha256'] != ev.file_sha(HERE / 'm6_historical_matching.py'):
        raise ValueError('pre-outcome selector changed')
    if selection['prior_integrity_receipt_sha256'] != ev.file_sha(m.ROOT / '.work/m6-e53-source-review-20261016.json'):
        raise ValueError('prior parent integrity receipt changed')
    for source in selection['source_files']:
        if ev.file_sha(ev.inside(m.ROOT, source['current_path'])) != source['sha256']:
            raise ValueError('historical final apparatus changed')
    parents = []
    for world in range(2):
        parent = old / 'cases' / f's{world}-joint-development/checkpoints/20000000'
        files = {}
        for row in review['sources'][world]['files']:
            path = ev.inside(old, row['path'])
            if path.parent != parent or ev.file_sha(path) != row['sha256']:
                raise ValueError('historical parent original changed')
            files[path.name] = row['sha256']
        if {p.name for p in parent.iterdir() if p.is_file()} != set(files):
            raise ValueError('historical parent membership changed')
        if selection['worlds'][world]['parent_path'] != parent.relative_to(m.ROOT).as_posix():
            raise ValueError('selection parent path differs')
        parents.append({'world': world, 'path': parent.relative_to(m.ROOT).as_posix(), 'files': files})
    return selection, parents


def register(work):
    work.mkdir(parents=True, exist_ok=True)
    with m.worker_lock(work), m.connection() as client:
        if (work / 'platform.json').exists():
            raise RuntimeError('already registered; inspect instead of repeating')
        selection, parents = provenance()
        title = '2026-10-17 机制发现 · M6历史交流通路因果补证'
        found = [p for p in client.call('projects.list', {}) if p['name'] == title]
        if len(found) > 1:
            raise RuntimeError('ambiguous project')
        project = found[0] if found else client.request('POST', '/api/v2/projects', body={'name': title})
        resource = 'mechanism-m6-historical-v1-20261017'
        m.original(work / 'platform.json', {'project_id': project['id'], 'resource_id': resource})
        m.original(work / 'selection.json', selection)
        m.original(work / 'historical-parents.json', parents)
        m.original(work / 'cases.json', ev.cases())
        inputs = {name: ev.file_sha(work / name) for name in ('selection.json', 'historical-parents.json', 'cases.json')}
        m.original(work / 'inputs-manifest.json', inputs)
        paths = source_paths()
        manifest = {path.relative_to(m.ROOT).as_posix(): ev.file_sha(path) for path in paths}
        m.original(work / 'runner-manifest.json', manifest)
        m.original(work / 'implementation.json', m.capture_implementation('native'))
        for path in paths:
            m.original(work / 'frozen' / path.relative_to(m.ROOT), {'utf8': path.read_text(encoding='utf-8')})
        recorder = m.ResearchRecorder(work, project['id'], client=client)
        recorder.register({'source_key': 'mechanism:m6-historical-v1:20261017', 'title': title,
                            'classification': 'development', 'execution_status': 'running', 'executor': 'ai',
                            'kernels': ['threemind.continuous-memory/2'],
                            'protocol': (HERE / 'm6-historical-protocol.zh.md').read_text(encoding='utf-8'),
                            'protocol_version': m.digest(manifest), 'required_roles': ['protocol', 'report', 'note'],
                            'metadata': {'work': str(work), 'historical_environments': 2, 'independent_new_origins': 0,
                                         'shared_founder_lineages': 3, 'causal_copies': 16, 'maximum_host_hours': 2,
                                         'maximum_original_GiB': 2, 'worker_private_GiB': 3,
                                         'inputs_manifest_sha256': m.digest(inputs),
                                         'Core_changed': False, 'E69_resumed': False}}, request_id=uuid5(NS, 'register'))
        recorder.synchronize(strict=True)
        client.request('POST', '/api/v2/storage/resources', body={
            'resource_id': resource, 'target_id': 'managed-research-experiments',
            'relative_path': '2026-10-16-mechanism-discovery/m6-historical-v1',
            'registered_work_path': str(work), 'writer_mode': 'cooperative', 'expected_revision': 0},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'resource'))})
        client.request('POST', '/api/v2/storage/record-evidence-grants',
            body={'project_id': project['id'], 'resource_id': resource},
            headers={'X-ThreeMind-Request-ID': str(uuid5(NS, 'grant'))})
        for lang in ('zh', 'en'):
            recorder.text({'request_id': str(uuid5(NS, 'protocol:' + lang)), 'identity': str(uuid5(NS, 'doc:' + lang)),
                           'expected_revision': 0, 'kind': 'protocol', 'title': 'M6 historical causal protocol ' + lang,
                           'markdown': (HERE / f'm6-historical-protocol.{lang}.md').read_text(encoding='utf-8')})
        recorder.synchronize(strict=True)
        print(json.dumps({'project': project['id'], 'record': recorder.experiment, 'status': recorder.status}), flush=True)


def prior_delivered():
    final = m.read(M4 / 'publication/final-verification.json')
    if (final.get('experiment_id') != '9d3589f3-663f-5a1a-be9a-5a8c6fcaf443'
            or final['execution_status'] != 'completed' or final['coverage'] != 'verified' or final.get('problems')):
        raise RuntimeError('M4 complete original-package delivery is required first')
    pending = M4 / '.research-records/pending'
    if pending.exists() and any(pending.glob('*.json')):
        raise RuntimeError('M4 still has persistent unsynchronized records')
    if any((M4 / path).exists() for path in ('STOP', 'in-flight.json')):
        raise RuntimeError('M4 has an unresolved marker')


def frozen_inputs(work):
    manifest = m.read(work / 'inputs-manifest.json')
    if set(manifest) != {'selection.json', 'historical-parents.json', 'cases.json'}:
        raise ValueError('frozen historical input manifest differs')
    for name, expected in manifest.items():
        if ev.file_sha(work / name) != expected:
            raise ValueError('frozen historical selection or parent changed: ' + name)
    if m.read(work / 'cases.json') != ev.cases():
        raise ValueError('frozen factorial differs')


def original_bytes(work):
    total = 0
    for path in work.rglob('*'):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            # Successful immutable publication unlinks only its own temporary
            # hard link. That race is not a missing scientific original.
            continue
    return total


class Guard(m.Guard):
    def __init__(self, work, evidence, remaining, private_gib, owner=None):
        super().__init__(work)
        self.evidence, self.remaining, self.private_gib = evidence, remaining, private_gib
        self.owner = owner

    def watch(self):
        while not self.stop.is_set():
            try:
                self.last = m.resource_check(self.work)
                private = psutil.Process().memory_info().private
                self.peak_private = max(self.peak_private, private)
                for key, value in self.last['available_bytes'].items():
                    self.minimum[key] = min(value, self.minimum.get(key, value))
                if self.owner is not None:
                    owner = psutil.Process(self.owner['pid'])
                    if abs(owner.create_time() - self.owner['created_at']) > .01:
                        raise RuntimeError('M6 supervisor disappeared or PID reused')
                if private > self.private_gib * 2**30:
                    raise RuntimeError('M6 registered host private-memory budget')
                if time.monotonic() - self.started > self.remaining:
                    raise RuntimeError('M6 cumulative two-hour host budget')
                if original_bytes(self.work) > ORIGINAL_BYTES:
                    raise RuntimeError('M6 registered 2GiB original-data budget')
            except Exception as exc:
                if not (self.work / 'STOP').exists():
                    try:
                        m.original(self.work / 'STOP', {'reason': str(exc), 'epoch': time.time(),
                                                      'last': self.last, 'pid': os.getpid()})
                    except (FileExistsError, RuntimeError):
                        if not (self.work / 'STOP').exists():
                            raise
                return
            self.stop.wait(1)

    def __exit__(self, *unused):
        self.stop.set()
        self.thread.join(3)
        m.original(self.evidence / 'resource-summary.json', {'peak_private_bytes': self.peak_private,
                    'minimum_available_bytes': self.minimum, 'wall_seconds': time.monotonic() - self.started,
                    'private_gib': self.private_gib, 'system_reserves_gib': [5, 4, 5, 25]})


def scheduled(phase):
    if phase == 'apparatus':
        from m6_historical_instrument import tasks
        return tasks()
    if phase == 'run':
        return ev.cases()
    raise ValueError('only apparatus or science run is supported')


def validate_ticket(work, ticket_path, supervisor):
    ticket_path = ticket_path.resolve()
    phase = supervisor['phase']
    root = work / 'hosts' / phase
    if not ticket_path.is_relative_to((root / 'workers').resolve()) or ticket_path.name != 'ticket.json':
        raise ValueError('ticket outside this one-shot phase')
    ticket = m.read(ticket_path)
    if ticket['supervisor'] != supervisor or ticket['phase'] != phase:
        raise ValueError('ticket identity differs')
    if type(ticket['index']) is not int or not 0 <= ticket['index'] < len(scheduled(phase)):
        raise ValueError('ticket index outside the preregistered schedule')
    if ticket['task'] != scheduled(phase)[ticket['index']]:
        raise ValueError('ticket differs from preregistered schedule')
    if ticket_path.parent.name != f'{ticket["index"]:02d}-{ticket["task"]["id"]}':
        raise ValueError('ticket path and task identity differ')
    process = psutil.Process(supervisor['pid'])
    expected = [str(Path(__file__).resolve()), phase, '--work', str(work)]
    if abs(process.create_time() - supervisor['created_at']) > .01 or not all(token in process.cmdline() for token in expected):
        raise RuntimeError('supervisor missing or PID reused')
    if not any(p.pid == process.pid and abs(p.create_time() - supervisor['created_at']) < .01 for p in psutil.Process().parents()):
        raise RuntimeError('worker not started by its registered supervisor')
    if (ticket_path.parent / 'host.json').exists():
        raise RuntimeError('worker ticket was already spent')
    return ticket


def worker(work, phase, ticket_path):
    import m6_historical_rig as rig
    import m6_historical_instrument as instrument
    m.frozen_check(work)
    frozen_inputs(work)
    supervisor = m.read(work / 'hosts' / phase / 'host.json')
    ticket = validate_ticket(work, ticket_path, supervisor)
    evidence, task = ticket_path.parent, ticket['task']
    with m.worker_lock(work), m.connection() as client:
        if any((work / name).exists() for name in ('STOP', 'in-flight.json')):
            raise RuntimeError('STOP/incomplete operation; no blind worker retry')
        m.original(evidence / 'host.json', {'pid': os.getpid(), 'created_at': psutil.Process().create_time(), 'command': sys.argv})
        recorder = m.recorder(work, client)
        def record(value):
            key = f'{phase}:{value["label"]}:{value["time_us"]}'
            recorder.append('result', key, value, request_id=uuid5(NS, 'boundary:' + key))
            recorder.synchronize()
        selection = m.read(work / 'selection.json')['worlds'][task['world']]
        paused, result = False, None
        with Guard(work, evidence, ticket['remaining_seconds'], PRIVATE_GIB, owner=supervisor) as guard:
            try:
                if rig.stopped(work, guard):
                    raise rig.BoundaryPause('stop before worker operation')
                if phase == 'apparatus' and task['route'] == 'parent':
                    parent = m.read(work / 'historical-parents.json')[task['world']]
                    result = rig.prepare_parent(work, selection, parent['files'], record=record)
                elif phase == 'apparatus':
                    result = instrument.route(work, task, selection, guard, record)
                else:
                    result = rig.run_branch(work, task, selection, guard, record)
            except rig.BoundaryPause:
                paused = True
        if (work / 'in-flight.json').exists():
            raise RuntimeError('worker returned with an incomplete operation')
        if result is not None:
            recorder.append('result', task['id'], result, request_id=uuid5(NS, 'result:' + task['id']))
            recorder.synchronize()
        m.original(evidence / 'completed.json', {'task': task, 'paused': paused or (work / 'STOP').exists(),
                    'result_sha256': m.digest(result) if result is not None else None,
                    'pending': recorder.status['pending'], 'epoch': time.time()})
        return 3 if paused or (work / 'STOP').exists() else 0


def capacity_forecast(work):
    """Conservative planning estimate from N0, not a promise about future size."""
    snapshots = [path.parent for path in (work / 'apparatus').rglob('complete.json')]
    if len(snapshots) != 22:
        raise ValueError('complete two-world N0 snapshots required')
    maximum_state = max(original_bytes(path) for path in snapshots)
    segments = [m.read(path)['final']['segments'] for path in (work / 'apparatus').rglob('result.json')]
    bytes_per_second = max(segment['bytes'] / ((segment['end_us'] - segment['start_us']) / 1e6)
                           for group in segments for segment in group)
    current = original_bytes(work)
    # Forty-eight scientific whole worlds; 160 seconds of raw trajectories.
    forecast = current + math_ceil(1.5 * (48 * maximum_state + 160 * bytes_per_second)) + 256 * 2**20
    required_free = max(0, forecast - current) + 2.02 * forecast + 25 * 2**30 + 64 * 2**20
    return {'original_bytes_now': current, 'maximum_N0_whole_bytes': maximum_state,
            'maximum_N0_trajectory_bytes_per_second': bytes_per_second, 'forecast_original_bytes': forecast,
            'required_free_data_bytes': math_ceil(required_free), 'fits_original_budget': forecast <= ORIGINAL_BYTES,
            'method': 'current originals + 1.5*(48*largest N0 whole + 160s*largest N0 trajectory rate) + 256MiB; archive/readback separately reserved'}


def math_ceil(value):
    import math
    return math.ceil(value)


def accepted_apparatus(work):
    review = m.read(work / 'apparatus-review.json')
    if (not m.read(work / 'apparatus.json')['passed'] or not review['accepted']
            or review['apparatus_sha256'] != ev.file_sha(work / 'apparatus.json')
            or review['runner_manifest_sha256'] != ev.file_sha(work / 'runner-manifest.json')):
        raise RuntimeError('review is not bound to this exact N0 evidence and frozen apparatus')


def phase_run(work, phase):
    import m6_historical_instrument as instrument
    with m.worker_lock(m.DEFAULT_WORK):
        with m.worker_lock(work):
            m.frozen_check(work)
            frozen_inputs(work)
            prior_delivered()
            root = work / 'hosts' / phase
            if root.exists() or any((work / name).exists() for name in ('STOP', 'in-flight.json', 'apparatus-in-flight.json')):
                raise RuntimeError('prior phase attempt or unresolved marker; do not repeat')
            resources = m.resource_check(work)
            for key in ('commit', 'ram'):
                if resources['available_bytes'][key] < resources['limits_bytes'][key] + 4 * 2**30:
                    raise RuntimeError('insufficient fresh-worker startup headroom')
            if phase == 'apparatus' and resources['available_bytes']['data_disk'] < 25 * 2**30 + 3 * ORIGINAL_BYTES + 64 * 2**20:
                raise RuntimeError('reserve the bounded originals, archive and API readback before N0')
            prior_wall = 0.
            if phase == 'run':
                accepted_apparatus(work)
                capacity = capacity_forecast(work)
                if not capacity['fits_original_budget'] or resources['available_bytes']['data_disk'] < capacity['required_free_data_bytes']:
                    raise RuntimeError('N0 capacity estimate does not fit originals/archive/readback/reserve')
                prior_wall = m.read(work / 'hosts/apparatus/resource-summary.json')['wall_seconds']
                m.original(work / 'science-capacity-preflight.json', capacity | {'resources': resources})
            root.mkdir(parents=True, exist_ok=False)
            supervisor = {'pid': os.getpid(), 'created_at': psutil.Process().create_time(), 'command': sys.argv, 'phase': phase}
            m.original(root / 'host.json', supervisor)
            if phase == 'apparatus':
                m.original(work / 'apparatus-in-flight.json', supervisor)
            m.atomic_json(work / 'status.json', {'state': 'running-' + phase, 'completed': 0, 'total': len(scheduled(phase))})
        started = time.monotonic()
        remaining = MAX_SECONDS - prior_wall
        done, failure = 0, None
        with Guard(work, root, remaining, 1) as guard:
            for index, task in enumerate(scheduled(phase)):
                if (work / 'STOP').exists():
                    break
                if not guard.thread.is_alive():
                    raise RuntimeError('supervisor guard disappeared')
                evidence = root / 'workers' / f'{index:02d}-{task["id"]}'
                evidence.mkdir(parents=True, exist_ok=False)
                ticket_path = evidence / 'ticket.json'
                m.original(ticket_path, {'supervisor': supervisor, 'phase': phase, 'index': index, 'task': task,
                                         'remaining_seconds': max(0., remaining - (time.monotonic() - started))})
                command = [sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), 'worker', '--work', str(work),
                           '--phase', phase, '--ticket', str(ticket_path)]
                with (evidence / 'stdout.log').open('xb') as out, (evidence / 'stderr.log').open('xb') as err:
                    process = subprocess.Popen(command, cwd=m.ROOT, stdout=out, stderr=err,
                                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    code = process.wait()
                if code not in (0, 3) or not (evidence / 'completed.json').exists():
                    failure = {'task': task, 'exit_code': code, 'evidence': str(evidence), 'epoch': time.time()}
                    m.original(root / 'failure.json', failure)
                    break
                if code == 3 or (work / 'STOP').exists():
                    break
                done += 1
                m.atomic_json(work / 'progress.json', {'phase': phase, 'completed': done, 'total': len(scheduled(phase)), 'last': task['id']})
                print(json.dumps({'phase': phase, 'completed': done, 'last': task['id']}), flush=True)
        completed = done == len(scheduled(phase)) and not (work / 'STOP').exists() and not failure
        if completed and phase == 'apparatus':
            result = instrument.verify(work)
            m.original(work / 'apparatus.json', result)
            if result['passed']:
                (work / 'apparatus-in-flight.json').unlink()
            else:
                failure = {'reason': 'N0 equality target failed; original marker retained'}
                m.original(root / 'failure.json', failure)
        state = 'requires-review' if failure else 'resource-paused' if not completed else 'awaiting-apparatus-review' if phase == 'apparatus' else 'awaiting-analysis'
        m.atomic_json(work / 'status.json', {'state': state, 'phase': phase, 'completed': done, 'total': len(scheduled(phase))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('register', 'apparatus', 'run', 'worker', 'status', 'check'))
    parser.add_argument('--work', type=Path, default=WORK)
    parser.add_argument('--phase', choices=('apparatus', 'run'))
    parser.add_argument('--ticket', type=Path)
    args = parser.parse_args()
    work = args.work.resolve()
    if work != WORK.resolve():
        raise ValueError('only this registered M6 workspace is supported')
    if args.command == 'register':
        register(work)
    elif args.command in ('apparatus', 'run'):
        phase_run(work, args.command)
    elif args.command == 'worker':
        if args.phase is None or args.ticket is None:
            parser.error('worker requires phase and ticket')
        sys.exit(worker(work, args.phase, args.ticket.resolve()))
    elif args.command == 'check':
        print(json.dumps(m.resource_check(work)))
    else:
        print(json.dumps({name: m.read(work / name) if (work / name).exists() else None
                          for name in ('status.json', 'progress.json', 'STOP', 'in-flight.json', 'apparatus-in-flight.json')}))
