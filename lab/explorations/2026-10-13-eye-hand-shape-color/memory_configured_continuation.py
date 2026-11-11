"""E69/r1 authorized commit reserve 5 GiB; never changes subject dynamics.

This separately versioned host entrypoint preserves the prior C-disk policy and
its frozen wrapper. It only changes the authorized commit reserve from 8 to
5 GiB; physical RAM/C-disk/data-disk remain 4/5/25 GiB. The frozen continuation
owns all subject loading, locks, continuity and execution.
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
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import host_resource_guard as guard
import psutil

HERE = Path(__file__).resolve().parent
POLICY_NAME = 'commit-5gib-c-drive-5gib-v1.json'
PREVIOUS_POLICY_NAME = 'c-drive-5gib-v1.json'
PREVIOUS_POLICY_SHA256 = '6ea282fdfe68641ca9d1940f55d8d51b636f0aa87bd0ade2e266ccc2a1f7b7f6'
IDENTITY = 'e69-5.1-223'
AUTHORIZED_LIMITS = {'commit_gib': 5, 'ram_gib': 4, 'system_disk_gib': 5, 'data_disk_gib': 25}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Policy:
    work: Path
    path: Path
    sha256: str
    limits: guard.Limits


def load_policy(work, policy=None, expected_sha=None):
    """Check the explicit scope, approved values and frozen tool bytes read-only."""
    work = Path(work).resolve()
    directory = work / '.continuation/host-policies'
    path = Path(policy).resolve() if policy else directory / POLICY_NAME
    require(path.parent == directory, 'policy must be inside this continuation host-policies directory')
    actual_sha = sha(path)
    require(expected_sha is None or actual_sha == expected_sha, 'host policy digest differs')
    value = read(path)
    require(set(value) == {'schema', 'identity', 'attempt', 'work', 'limits', 'authorization_note',
                           'source_sha256', 'prepare_plan_sha256', 'previous_policy_sha256'}, 'unexpected host policy fields')
    require(value['schema'] == 'threemind.e69-host-policy/2' and value['identity'] == IDENTITY and
            value['attempt'] == 'r1' and Path(value['work']).resolve() == work,
            'host policy is not for this E69 r1 individual')
    require(value['limits'] == AUTHORIZED_LIMITS and
            all(type(number) in (int, float) for number in value['limits'].values()),
            'only the explicitly approved 5/4/5/25 GiB host reserves are supported')
    previous_path = directory / PREVIOUS_POLICY_NAME
    require(value['previous_policy_sha256'] == PREVIOUS_POLICY_SHA256 == sha(previous_path),
            'prior host policy changed or is not the reviewed predecessor')
    previous = read(previous_path)
    require(previous['source_sha256'] == sha(HERE / 'configured_continuation.py'),
            'prior configured host source changed')
    require(isinstance(value['authorization_note'], str) and value['authorization_note'].strip(),
            'explicit user authorization provenance required')
    require(value['source_sha256'] == sha(Path(__file__)), 'configured host source changed')
    plan_path = work / '.continuation/prepare-plan.json'
    require(value['prepare_plan_sha256'] == sha(plan_path), 'continuation preparation digest differs')
    plan, context = read(plan_path), read(work / 'continuation-envelope.json')
    require(context['identity'] == IDENTITY and context['attempt'] == 'r1' and
            Path(context['work']).resolve() == work and
            work == Path(context['original_work']).resolve() / 'continuations/r1' and
            context['authorized_rollback_count'] == 1 and plan['authorized']['identity'] == IDENTITY,
            'policy target is not the approved continuation')
    for name in ('continuation.py', 'continuation_status.py', 'host_resource_guard.py'):
        require(sha(HERE / name) == plan['tools'][name] ==
                sha(work / '.continuation/source-reference' / name), 'frozen continuation tool changed: ' + name)
    return Policy(work, path, actual_sha, guard.Limits(**value['limits']))


def check(policy, **kwargs):
    return guard.check_resources(policy.work, limits=policy.limits, **kwargs)


def watch(policy, pid, started_at, **kwargs):
    return guard.watch(policy.work, pid, started_at, limits=policy.limits, **kwargs)


def argument(arguments, name):
    return arguments[arguments.index(name) + 1] if name in arguments else None


def validate_ready(policy, value, candidate, command, pid, started, launched_at):
    require(str(Path(__file__).resolve()) in command and 'watch' in command and
            argument(command, '--work') == str(policy.work) and
            argument(command, '--policy') == str(policy.path) and
            argument(command, '--policy-sha256') == policy.sha256 and
            argument(command, '--pid') == str(pid) and argument(command, '--started-at') == str(started),
            'configured guard descendant command differs')
    require(value.get('target_pid') == pid and abs(value.get('target_started_at', 0) - started) < .01 and
            value.get('guard_pid') == candidate.pid and
            abs(value.get('guard_started_at', 0) - candidate.create_time()) < .01 and
            value.get('epoch', 0) >= launched_at, 'configured guard ready identity or timestamp differs')
    require(value.get('safe') is True and value.get('report', {}).get('safe') is True and
            value['report'].get('limits_bytes') == policy.limits.bytes(),
            'configured guard rejected initialization or used different limits')


@contextmanager
def resource_watch(policy):
    """Launch the same guard with explicit limits; supervise only host processes."""
    check(policy)
    pid, started = os.getpid(), psutil.Process().create_time()
    logs = policy.work / 'logs'; logs.mkdir(exist_ok=True)
    done, watcher, candidate = threading.Event(), None, None
    with (logs / 'memory-configured-guard.stdout.log').open('ab') as output, \
            (logs / 'memory-configured-guard.stderr.log').open('ab') as error:
        launched_at = time.time()
        process = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), 'watch',
                                   '--work', str(policy.work), '--policy', str(policy.path),
                                   '--policy-sha256', policy.sha256, '--pid', str(pid),
                                   '--started-at', str(started)], stdout=output, stderr=error,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        launcher = psutil.Process(process.pid)
        launcher_started = launcher.create_time()
        try:
            deadline = time.monotonic() + 30
            while True:
                require(process.poll() is None, 'configured guard exited before initialization')
                ready = policy.work / 'host-resource-guard/ready.json'
                if ready.exists():
                    value = read(ready)
                    descendants = {p.pid for p in launcher.children(recursive=True)} | {launcher.pid}
                    if value.get('guard_pid') in descendants:
                        candidate = psutil.Process(value['guard_pid'])
                        validate_ready(policy, value, candidate, candidate.cmdline(), pid, started, launched_at)
                        require(process.poll() is None and candidate.is_running(), 'configured guard exited during initialization')
                        break
                require(time.monotonic() < deadline, 'configured guard never became ready; no subject loaded')
                time.sleep(.1)

            guard_started = candidate.create_time()

            def supervise():
                while not done.wait(.5):
                    try:
                        healthy = process.poll() is None and guard.target_state(candidate.pid, guard_started) == 'alive'
                    except guard.ResourceUnavailable:
                        healthy = False
                    if not healthy:
                        guard.request_stop(policy.work, {'event': 'memory-configured-monitor-failed', 'epoch': time.time(),
                            'guard_pid': candidate.pid, 'launcher_pid': process.pid,
                            'policy_sha256': policy.sha256, 'action': 'STOP-at-next-complete-boundary'})
                        return

            watcher = threading.Thread(target=supervise, daemon=True)
            watcher.start()
            yield
        finally:
            done.set()
            if watcher:
                watcher.join(timeout=2)
            owned = []
            try:
                if launcher.create_time() == launcher_started:
                    owned.extend(launcher.children(recursive=True)); owned.append(launcher)
            except psutil.NoSuchProcess:
                pass
            if candidate is not None and not any(p.pid == candidate.pid for p in owned):
                owned.insert(0, candidate)
            for helper in owned:
                try:
                    if helper.is_running():
                        helper.terminate()
                except psutil.NoSuchProcess:
                    pass
            psutil.wait_procs(owned, timeout=5)
            if process.poll() is None:
                process.wait(timeout=5)


def run(policy):
    import continuation
    # The original runner keeps its identity/source checks, whole-system loading,
    # locks and boundary semantics; no defaults are monkeypatched.
    return continuation.run(policy.work, watch=lambda work: resource_watch(policy))


def status(policy):
    from continuation_status import continuation_status
    value = continuation_status(policy.work)
    value['configured_host_policy'] = {'previous_policy_sha256': PREVIOUS_POLICY_SHA256, 'path': str(policy.path), 'sha256': policy.sha256,
                                       'limits_bytes': policy.limits.bytes()}
    entrypoints = {str(HERE / name).casefold() for name in (
        'configured_continuation.py', 'memory_configured_continuation.py')}
    known_pids = {process['pid'] for process in value['processes']}
    for process in psutil.process_iter(['name']):
        if not process.info['name'] or 'python' not in process.info['name'].lower():
            continue
        try:
            command = process.cmdline()
            if any(part.casefold() in entrypoints for part in command) and str(policy.work) in command and any(
                    action in command for action in ('run', 'watch')):
                if process.pid not in known_pids:
                    value['processes'].append({'pid': process.pid, 'started_at': process.create_time(), 'cmd': command,
                                              'cpu_s': sum(process.cpu_times()[:2]), 'rss': process.memory_info().rss})
                    known_pids.add(process.pid)
        except psutil.AccessDenied:
            value['process_access_denied'].append(process.pid)
        except psutil.NoSuchProcess:
            pass
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'run', 'watch', 'status'))
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--policy-sha256')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--started-at', type=float)
    args = parser.parse_args()
    if args.action in ('run', 'watch') and not args.policy_sha256:
        parser.error('run/watch require the reviewed immutable --policy-sha256')
    if args.action == 'watch' and (args.pid is None or args.started_at is None):
        parser.error('watch requires --pid and --started-at')
    try:
        policy = load_policy(args.work, args.policy, args.policy_sha256)
        if args.action == 'watch':
            return watch(policy, args.pid, args.started_at)
        value = {'check': check, 'run': run, 'status': status}[args.action](policy)
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except (guard.ResourceUnavailable, guard.ResourcePressure, OSError, ValueError) as exc:
        print(json.dumps({'safe': False, 'error': type(exc).__name__ + ': ' + str(exc),
                          'report': exc.report if isinstance(exc, guard.ResourcePressure) else None}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
