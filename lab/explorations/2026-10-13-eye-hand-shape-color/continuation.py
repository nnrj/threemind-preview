"""Explicitly authorized E69 restoration, isolated from the interrupted originals.

Only the recorded 2004-second boundary is authorized here. This host wrapper does
not change the frozen classroom, curriculum, subject identity or Core dynamics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path
from uuid import UUID, uuid5

from journal import HERE, RESOURCE, BoundaryPause, ResearchStudy, encoded, fixed_json, put, read, sha

from threemind_lab.record_schema import AttachRecord
from threemind_lab.research_records import digest
from threemind_lab.storage_files import atomic_json, checked_path, file_lock

AUTHORIZED = {'sequence': 354, 'time_us': 2004000000, 'experienced_end_us': 2010000000,
              'boundary_sha256': 'df3722eac6cfcc11a3df807d64ffb8b0d37e151bdc604731ca790dd9f4e89465',
              'identity': 'e69-5.1-223', 'interrupted_key': 'gaze-cal-1:000058'}
ATTEMPT = 'r1'
TOOLS = ('continuation.py', 'continuation_status.py', 'host_resource_guard.py')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def chain_prefix(original):
    latest = read(original / 'subject/latest.json')
    require(all(latest[key] == AUTHORIZED[key] for key in ('sequence', 'boundary_sha256', 'identity')) and
            latest['end_us'] == AUTHORIZED['time_us'], 'original latest is not the exact authorized restoration boundary')
    chain, previous, keys = [], None, set()
    for sequence in range(latest['sequence'] + 1):
        row = read(original / 'subject/chain' / f'{sequence:06d}.json')
        payload = {k: v for k, v in row.items() if k != 'boundary_sha256'}
        require(hashlib.sha256(encoded(payload)).hexdigest() == row['boundary_sha256'], 'broken prefix boundary digest')
        require(row['sequence'] == sequence and row['identity'] == latest['identity'], 'prefix identity changed')
        require(row['key'] not in keys, 'repeated operation in prefix')
        keys.add(row['key'])
        require(row['description']['time_us'] == row['end_us'] and row['description']['identity'] == latest['identity'],
                'boundary description differs')
        require(row['end_us'] >= row['start_us'], 'prefix time moved backwards')
        if previous:
            require(row['parent'] == previous['boundary_sha256'] and row['start_us'] == previous['end_us'],
                    'prefix ancestry or time gap')
            require(row['description']['learning'].keys() == previous['description']['learning'].keys(), 'peripheral set changed')
        else:
            require(row['key'] == 'birth' and row['parent'] is None and row['start_us'] == row['end_us'] == 0,
                    'missing original blank birth')
        for name, counters in row['description']['learning'].items():
            require(counters['computed_updates'] == counters['committed_updates'], 'uncommitted peripheral learning')
            if previous:
                require(counters['committed_updates'] >= previous['description']['learning'][name]['committed_updates'],
                        'peripheral learning moved backwards')
        chain.append(row); previous = row
    require(previous == latest, 'original latest does not match its immutable chain record')
    return latest, chain


def verify_current(work, latest):
    folder = checked_path(work / 'subject' / latest['checkpoint'])
    require(folder.is_relative_to(work / 'subject'), 'unsafe current checkpoint')
    names = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    require(names == set(latest['files']), 'current checkpoint member inventory differs')
    for name, meta in latest['files'].items():
        path = checked_path(folder / name)
        require(path.is_relative_to(folder) and path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'],
                'current checkpoint hash or size differs: ' + name)
    complete = read(folder / 'complete.json')
    require(all(complete[k] == latest['description'][k] for k in ('identity', 'time_us', 'learning')), 'complete metadata differs')
    refs = read(folder / 'dependencies.json')['corpora']
    for ref in refs:
        path = checked_path(work / ref['path'])
        require(path.is_relative_to(work) and path.is_file() and sha(path) == ref['sha256'],
                'current complete-system dependency differs: ' + ref['path'])
    return refs


def verify_sources(original):
    source = original / 'source-reference'
    require(sha(source / 'manifest.json') == read(original / 'platform.json')['manifest_sha256'], 'frozen source manifest differs')
    repo = HERE.parents[2]
    for name, expected in read(source / 'manifest.json').items():
        require(sha(checked_path(repo / name)) == expected and sha(checked_path(source / name)) == expected,
                'frozen source changed: ' + name)


def prefix_files(original, chain):
    selected = {original / name for name in ('design.json', 'questions.json', 'curriculum-manifest.json')}
    for directory in ('source-reference', 'curricula'):
        selected.update(p for p in (original / directory).rglob('*') if p.is_file())
    keys = {b['key'] for b in chain}
    stages = {key.split(':')[0] for key in keys if ':' in key}
    for row in chain:
        selected.add(original / 'subject/chain' / f"{row['sequence']:06d}.json")
        checkpoint = checked_path(original / 'subject' / row['checkpoint'])
        require(checkpoint.is_relative_to(original / 'subject'), 'unsafe prefix checkpoint')
        for name, meta in row['files'].items():
            path = checked_path(checkpoint / name)
            require(path.is_relative_to(checkpoint) and path.is_file() and path.stat().st_size == meta['bytes'],
                    'prefix checkpoint member missing or wrong size')
            selected.add(path)
    for stage in stages:
        folder = original / 'stages' / stage
        for path in folder.rglob('*'):
            if not path.is_file():
                continue
            parts = path.relative_to(folder).parts
            name = path.name
            allowed = False
            if len(parts) == 1:
                if name in ('tasks.json', 'start.json', 'result.json', 'motor-plan.json', 'motor-result.json',
                            'words-plan.json', 'words-result.json'):
                    value = read(path)
                    for field in ('time_us', 'start_us', 'end_us'):
                        require(field not in value or value[field] <= AUTHORIZED['time_us'], 'stage metadata exceeds authorized prefix')
                    allowed = True
                elif name.endswith('.json') and '-' in path.stem:
                    head, block = path.stem.rsplit('-', 1)
                    allowed = f'{stage}:{head}:{block}' in keys
            elif len(parts) == 2:
                unit = name.removesuffix('.json.gz').removesuffix('.json').removesuffix('.npz')
                if parts[0] == 'clips' and unit.startswith(('gap-', 'reanswer-')):
                    kind, index = unit.split('-', 1); allowed = f'{stage}:{kind}:{index}' in keys
                elif parts[0] == 'reanswers':
                    allowed = f'{stage}:reanswer:{unit}' in keys
                elif parts[0] in ('clips', 'units', 'samples'):
                    allowed = f'{stage}:{unit}' in keys
            if allowed:
                selected.add(path)
    return sorted(checked_path(p) for p in selected)


@contextmanager
def ownership(original, work, storage):
    with ExitStack() as stack:
        for folder in (original, work):
            for name in ('pipeline.lock', 'runner.lock'):
                stack.enter_context(file_lock(folder / name))
        stack.enter_context(storage.writer(RESOURCE))
        yield


def prepare(original, *, authorization_note, storage=None):
    original = checked_path(Path(original).absolute())
    require(bool(authorization_note.strip()), 'explicit user authorization provenance is required')
    work = original / 'continuations' / ATTEMPT
    if storage is None:
        from threemind_lab.config import load_env
        from threemind_lab.research_storage import ResearchStorage
        load_env(); storage = ResearchStorage()
    with ownership(original, work, storage):
        if not (work / '.continuation/prepare-plan.json').exists():
            require(not any(p.is_file() and p.relative_to(work).as_posix() not in ('pipeline.lock', 'runner.lock')
                            for p in work.rglob('*')), 'unrecognized pre-existing continuation files; never merge a different attempt')
        latest, chain = chain_prefix(original)
        verify_sources(original)
        refs = verify_current(original, latest)
        flight = read(original / 'subject/in-flight.json')
        require(flight['key'] == AUTHORIZED['interrupted_key'] and flight['parent'] == latest['boundary_sha256'] and
                flight['start_us'] == AUTHORIZED['time_us'], 'original interrupted operation differs')
        stage, index = flight['key'].split(':')
        unit = read(original / 'stages' / stage / 'units' / (index + '.json'))
        require(unit['start_us'] == AUTHORIZED['time_us'] and unit['end_us'] == AUTHORIZED['experienced_end_us'],
                'interrupted experience window differs from the authorization')
        if (work / 'subject/latest.json').exists():
            require(read(work / 'subject/latest.json') == latest, 'continuation already advanced; use run, never prepare it again')
        selected = prefix_files(original, chain)
        selected_names = {p.relative_to(original).as_posix() for p in selected}
        require(all(ref['path'] in selected_names for ref in refs), 'prefix selection omitted a complete-system dependency')
        copied = ['platform.json', '.research-records/identity.json', 'subject/latest.json']
        files = []
        for path in selected:
            info = path.stat()
            files.append({'path': path.relative_to(original).as_posix(), 'mode': 'hardlink', 'bytes': info.st_size,
                          'device': info.st_dev, 'file_id': info.st_ino, 'mtime_ns': info.st_mtime_ns})
        for name in copied:
            path = original / name
            files.append({'path': name, 'mode': 'copy', 'bytes': path.stat().st_size, 'sha256': sha(path)})
        tools = {name: sha(HERE / name) for name in TOOLS}
        plan = {'schema': 'threemind.e69-continuation/1', 'attempt': ATTEMPT, 'original': str(original),
                'work': str(work), 'authorized': AUTHORIZED, 'authorization_note': authorization_note,
                'original_inflight_sha256': sha(original / 'subject/in-flight.json'), 'files': files, 'tools': tools}
        control = work / '.continuation'
        fixed_json(control / 'prepare-plan.json', plan)
        for name, expected in tools.items():
            put(control / 'source-reference' / name, (HERE / name).read_bytes())
            require(sha(control / 'source-reference' / name) == expected, 'continuation tool snapshot differs')
        for member in files:
            source = checked_path(original / member['path']); target = checked_path(work / member['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            if member['mode'] == 'hardlink':
                info = source.stat()
                require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) ==
                        (member['device'], member['file_id'], member['bytes'], member['mtime_ns']), 'source prefix changed during preparation')
                if not target.exists():
                    os.link(source, target)
                require(os.path.samefile(source, target), 'existing continuation prefix is not the planned immutable original')
            else:
                require(sha(source) == member['sha256'], 'mutable source changed during preparation')
                put(target, source.read_bytes())
                require(not os.path.samefile(source, target), 'mutable control file must not share an inode')
        verify_current(work, read(work / 'subject/latest.json'))
        envelope = {'schema': 'threemind.e69-continuation-context/1', 'attempt': ATTEMPT, 'same_individual': True,
                    'identity': latest['identity'], 'experiment': read(work / '.research-records/identity.json')['experiment'],
                    'original_work': str(original), 'work': str(work), 'restored_boundary': latest['boundary_sha256'],
                    'restored_sequence': latest['sequence'], 'restored_time_us': AUTHORIZED['time_us'],
                    'original_experience_end_us': AUTHORIZED['experienced_end_us'], 'authorized_rollback_count': 1,
                    'ordinary_history_uninterrupted': False, 'authorization_note': authorization_note,
                    'interrupted_originals_retained': True, 'new_birth': False,
                    'claim_precedence': 'This envelope is authoritative for historical continuity. Frozen runner fields '
                                        'full_continuity=true and rollback_count=0 describe its unmodified loop only, '
                                        'not the authorized restoration across this interruption.',
                    'prefix_semantics': 'Already committed stages are reused as evidence, not executed again. '
                                        'New namespace denotes a restored attempt of the same individual, not another student.',
                    'timing_note': 'Stage wall_seconds may include the interruption; use separately recorded computation timers.'}
        fixed_json(work / 'continuation-envelope.json', envelope)
        receipt = {'phase': 'prepared-authorized-continuation', 'attempt': ATTEMPT,
                   'prepare_plan_sha256': sha(control / 'prepare-plan.json'),
                   'envelope_sha256': sha(work / 'continuation-envelope.json'),
                   'shared_files': len(selected), 'shared_bytes': sum(p.stat().st_size for p in selected),
                   'copied_control_bytes': sum((work / p).stat().st_size for p in copied),
                   'originals_changed': False, 'simulation_advanced': False}
        allowed = {row['path'] for row in files} | {'pipeline.lock', 'runner.lock', '.continuation/prepare-plan.json',
                  '.continuation/prepared.json', 'continuation-envelope.json'} | {
                  '.continuation/source-reference/' + name for name in tools}
        require(all(p.relative_to(work).as_posix() in allowed for p in work.rglob('*') if p.is_file()),
                'unexpected file in prepared continuation; do not run an unreviewed prefix')
        fixed_json(control / 'prepared.json', receipt)
        return receipt


class ContinuationStudy(ResearchStudy):
    def __init__(self, work, **kwargs):
        self.context = read(Path(work) / 'continuation-envelope.json')
        self.attempt = self.context['attempt']
        self.member_prefix = 'continuations/' + self.attempt + '/'
        super().__init__(work, **kwargs)

    def rid(self, key):
        return str(uuid5(UUID(self.project), 'e69:continuation:' + self.attempt + ':' + key))

    def append(self, kind, key, content):
        value = dict(content)
        if 'full_continuity' in value:
            value['frozen_runner_full_continuity'] = value['full_continuity']
            value['full_continuity'] = False
        value['continuation_context'] = self.context
        value['reused_committed_prefix'] = kind == 'stage' and int(value.get('end_us', value.get('time_us', 0))) <= self.context['restored_time_us']
        return self.recorder.append(kind, 'continuation:' + self.attempt + ':' + key, value,
                                    request_id=self.rid(kind + ':' + key))

    def attach(self, path, role='process', stage=None):
        path = checked_path(Path(path).absolute()); name = path.relative_to(self.work).as_posix()
        member = self.member_prefix + name; request_id = self.rid('file:' + name)
        evidence = {'logical_id': 'file:' + member, 'role': role, 'label': member,
                    'format': ''.join(path.suffixes).lstrip('.') or 'opaque', 'byte_count': path.stat().st_size,
                    'sha256': sha(path), 'stage_key': 'continuation:' + self.attempt + ':' + stage if stage else None,
                    'locator': {'kind': 'file', 'resource_id': RESOURCE, 'member': member}}
        with file_lock(self.recorder.control / 'journal.lock'):
            pending = self.recorder.control / 'pending' / (request_id + '.json')
            committed = self.recorder.control / 'receipts' / (request_id + '.json')
            previous = read(committed)['request'] if committed.exists() else read(pending) if pending.exists() else None
            if previous:
                body = AttachRecord.model_validate(previous['body']).model_dump(mode='json')
                require(previous['action'] == 'attach' and previous['project'] == self.project and
                        previous['experiment'] == self.recorder.experiment and body['request_id'] == request_id,
                        'existing continuation attachment belongs to a different identity')
                old = body['evidence']
                require(all(old[k] == v for k, v in evidence.items() if k not in ('role', 'stage_key')),
                        'continuation evidence bytes or locator changed')
                if committed.exists():
                    require(read(committed)['result']['content_hash'] == digest(old), 'committed continuation evidence metadata differs')
                if pending.exists() and committed.exists():
                    require(read(pending) == previous, 'conflicting continuation resend requires explicit review')
                return request_id
        return self.recorder.attach(evidence, request_id=request_id)


@contextmanager
def resource_watch(work):
    import host_resource_guard
    import psutil
    host_resource_guard.check_resources(work)
    pid, started = os.getpid(), psutil.Process().create_time()
    logs = work / 'logs'; logs.mkdir(exist_ok=True)
    done = threading.Event()
    with (logs / 'resource-guard.stdout.log').open('ab') as output, (logs / 'resource-guard.stderr.log').open('ab') as error:
        process = subprocess.Popen([sys.executable, '-X', 'utf8', str(HERE / 'host_resource_guard.py'), 'watch',
                                    '--work', str(work), '--pid', str(pid), '--started-at', str(started)],
                                   stdout=output, stderr=error,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        launcher = psutil.Process(process.pid)
        launcher_started = launcher.create_time()
        guard_process = None
        watcher = None
        try:
            deadline = time.monotonic() + 30
            while True:
                require(process.poll() is None, 'resource guard exited before initialization')
                ready = work / 'host-resource-guard/ready.json'
                if ready.exists():
                    value = read(ready)
                    descendants = {p.pid for p in launcher.children(recursive=True)} | {launcher.pid}
                    if (value.get('guard_pid') in descendants and value.get('target_pid') == pid and
                            abs(value.get('target_started_at', 0) - started) < .01):
                        candidate = psutil.Process(value['guard_pid'])
                        command = candidate.cmdline()
                        def argument(name, arguments=command):
                            return arguments[arguments.index(name) + 1] if name in arguments else None
                        require(str(HERE / 'host_resource_guard.py') in command and
                                argument('--work') == str(work) and argument('--pid') == str(pid) and
                                argument('--started-at') == str(started), 'guard descendant command differs')
                        require(abs(value.get('guard_started_at', 0) - candidate.create_time()) < .01,
                                'guard PID creation time differs')
                        require(value.get('safe') is True, 'resource guard rejected initialization')
                        require(process.poll() is None and candidate.is_running(), 'resource guard exited during initialization')
                        guard_process = candidate
                        break
                require(time.monotonic() < deadline, 'resource guard did not become ready; no subject was loaded')
                time.sleep(.1)

            def supervise():
                while not done.wait(.5):
                    if process.poll() is not None or not guard_process.is_running():
                        failure = {'guard_pid': guard_process.pid, 'launcher_pid': process.pid,
                                   'exit_code': process.returncode, 'action': 'STOP-at-next-complete-boundary'}
                        host_resource_guard.request_stop(work, failure)
                        atomic_json(work / 'host-resource-guard/runner-monitor-failure.json', failure)
                        return

            watcher = threading.Thread(target=supervise, daemon=True)
            watcher.start()
            yield
        finally:
            done.set()
            if watcher:
                watcher.join(timeout=2)
            # A Windows venv launcher may own a separate Python guard child.
            # Stop only that tool tree, retaining each creation time against PID reuse.
            owned = []
            try:
                if launcher.create_time() == launcher_started:
                    owned.extend(launcher.children(recursive=True))
                    owned.append(launcher)
            except psutil.NoSuchProcess:
                pass
            if guard_process is not None and not any(p.pid == guard_process.pid for p in owned):
                owned.insert(0, guard_process)
            for helper in owned:
                try:
                    if helper.is_running():
                        helper.terminate()
                except psutil.NoSuchProcess:
                    pass
            psutil.wait_procs(owned, timeout=5)
            if process.poll() is None:
                process.wait(timeout=5)


def run(work, *, study_factory=ContinuationStudy, runner_factory=None, watch=resource_watch):
    from threemind_lab.config import load_env
    load_env()
    work = checked_path(Path(work).absolute())
    context = read(work / 'continuation-envelope.json')
    original = checked_path(Path(context['original_work']))
    require(work == original / 'continuations' / ATTEMPT and context['authorized_rollback_count'] == 1,
            'unexpected continuation identity')
    prepared = read(work / '.continuation/prepared.json')
    require(sha(work / '.continuation/prepare-plan.json') == prepared['prepare_plan_sha256'] and
            sha(work / 'continuation-envelope.json') == prepared['envelope_sha256'], 'continuation preparation changed')
    plan = read(work / '.continuation/prepare-plan.json')
    require(plan['authorized'] == AUTHORIZED, 'restoration authorization changed')
    for name, expected in plan['tools'].items():
        require(sha(HERE / name) == expected and sha(work / '.continuation/source-reference' / name) == expected,
                'prepared continuation tool changed: ' + name)
    study = study_factory(work)
    try:
        with ownership(original, work, study.storage):
            require((work / 'subject/latest.json').exists(), 'current subject missing; never create a replacement')
            require(not (work / 'subject/in-flight.json').exists(), 'continuation has uncommitted experience; no automatic rollback')
            if (work / 'STOP').exists():
                raise BoundaryPause('continuation STOP retained; explicit review required')
            study.verify_sources()
            verify_current(work, read(work / 'subject/latest.json'))
            study.append('correction', 'authorized-restoration', {'restoration': context, 'user_requested_continue': True})
            study.attach(work / 'continuation-envelope.json', 'protocol', 'authorized-restoration')
            study.sync()
            if not (work / 'computation-complete.json').exists():
                with watch(work):
                    if runner_factory is None:
                        from experiment import ClassroomRun, verify_curriculum
                        verify_curriculum(work)
                        runner_factory = ClassroomRun
                    atomic_json(work / 'continuation-status.json', {'phase': 'running', 'pid': os.getpid(), 'attempt': ATTEMPT})
                    atomic_json(work / 'continuation-run-start.json',
                                {'phase': 'about-to-load-current-complete-subject', 'pid': os.getpid(),
                                 'epoch': time.time(), 'latest': read(work / 'subject/latest.json'),
                                 'initial_authorized_restoration': AUTHORIZED,
                                 'actual_restoration_proof': 'subsequent committed whole-system boundary'})
                    runner_factory(study).run()
            completion = read(work / 'computation-complete.json')
            require(completion['latest'] == read(work / 'subject/latest.json'), 'completion differs from current whole subject')
            envelope = {'context': context, 'frozen_computation_receipt_sha256': sha(work / 'computation-complete.json'),
                        'authorized_rollback_count': 1, 'ordinary_history_uninterrupted': False,
                        'frozen_runner_rollback_count': completion.get('rollback_count'), 'current_time_us': completion['time_us']}
            fixed_json(work / 'continuation-complete-envelope.json', envelope)
            study.append('result', 'continuation-complete', envelope)
            study.attach(work / 'continuation-complete-envelope.json', 'result')
            study.sync()
            atomic_json(work / 'continuation-status.json', {'phase': 'awaiting-continuation-postprocessing',
                                                          'attempt': ATTEMPT, 'pid': os.getpid(), 'automatic_finalization': False})
            return envelope
    except BaseException as failure:
        atomic_json(work / 'continuation-status.json', {'phase': 'paused' if isinstance(failure, BoundaryPause) else 'attention-required',
                    'error': type(failure).__name__ + ': ' + str(failure), 'automatic_rollback': False, 'pid': os.getpid()})
        raise
    finally:
        study.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    p = commands.add_parser('prepare'); p.add_argument('--original', required=True, type=Path)
    p.add_argument('--authorization-note', required=True)
    p = commands.add_parser('run'); p.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    value = prepare(args.original, authorization_note=args.authorization_note) if args.action == 'prepare' else run(args.work)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    main()
