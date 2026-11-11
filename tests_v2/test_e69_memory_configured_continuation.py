"""E69 host-policy checks using synthetic metadata; never loads a subject."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color'


@pytest.fixture
def subject(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(HERE))
    spec = importlib.util.spec_from_file_location('memory_configured_e69_test_module', HERE / 'memory_configured_continuation.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    work = tmp_path / 'original/continuations/r1'
    control = work / '.continuation'
    (control / 'source-reference').mkdir(parents=True)
    tools = {}
    for name in ('continuation.py', 'continuation_status.py', 'host_resource_guard.py'):
        shutil.copyfile(HERE / name, control / 'source-reference' / name)
        tools[name] = module.sha(HERE / name)
    (control / 'prepare-plan.json').write_text(json.dumps({'tools': tools, 'authorized': {'identity': module.IDENTITY}}))
    (work / 'continuation-envelope.json').write_text(json.dumps({
        'identity': module.IDENTITY, 'attempt': 'r1', 'work': str(work),
        'original_work': str(work.parents[1]), 'authorized_rollback_count': 1}))
    directory = control / 'host-policies'; directory.mkdir()
    previous_path = directory / module.PREVIOUS_POLICY_NAME
    previous_path.write_text(json.dumps({'source_sha256': module.sha(HERE / 'configured_continuation.py')}))
    monkeypatch.setattr(module, 'PREVIOUS_POLICY_SHA256', module.sha(previous_path))
    path = directory / module.POLICY_NAME
    data = {'schema': 'threemind.e69-host-policy/2', 'identity': module.IDENTITY, 'attempt': 'r1',
            'work': str(work), 'limits': dict(module.AUTHORIZED_LIMITS),
            'authorization_note': 'Synthetic fixture for explicitly authorized commit and C reserve 5 GiB.',
            'source_sha256': module.sha(HERE / 'memory_configured_continuation.py'),
            'prepare_plan_sha256': module.sha(control / 'prepare-plan.json'),
            'previous_policy_sha256': module.PREVIOUS_POLICY_SHA256}
    path.write_text(json.dumps(data))
    return module, work, path, data


def healthy(c_gib=7):
    return {'commit_total_bytes': 10 * 2**30, 'commit_limit_bytes': 30 * 2**30,
            'physical_available_bytes': 12 * 2**30,
            'system_disk_free_bytes': int(c_gib * 2**30), 'data_disk_free_bytes': 100 * 2**30}


def test_five_gib_policy_does_not_change_default_guard(subject):
    module, work, path, _ = subject
    policy = module.load_policy(work, expected_sha=module.sha(path))
    before = {p: p.read_bytes() for p in work.rglob('*') if p.is_file()}
    assert module.check(policy, snapshot=lambda: healthy() | {'commit_total_bytes': 24 * 2**30})['safe']
    with pytest.raises(module.guard.ResourcePressure):
        module.guard.check_resources(work, snapshot=healthy)
    assert module.guard.Limits().system_disk_gib == 10
    assert module.guard.Limits().commit_gib == 8
    assert before == {p: p.read_bytes() for p in work.rglob('*') if p.is_file()}


@pytest.mark.parametrize(('field', 'bad'), [
    ('system_disk_gib', 4), ('commit_gib', 8), ('ram_gib', 3), ('data_disk_gib', 24),
    ('system_disk_gib', float('nan')), ('system_disk_gib', True),
])
def test_no_other_override_is_authorized(subject, field, bad):
    module, work, path, data = subject
    data['limits'][field] = bad; path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='explicitly approved'):
        module.load_policy(work)


@pytest.mark.parametrize(('field', 'bad', 'message'), [
    ('identity', 'another-subject', 'not for this'), ('attempt', 'r2', 'not for this'),
    ('authorization_note', '', 'provenance'), ('source_sha256', '0' * 64, 'source changed'),
    ('prepare_plan_sha256', '0' * 64, 'preparation digest'),
])
def test_scope_and_source_must_match(subject, field, bad, message):
    module, work, path, data = subject
    data[field] = bad; path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=message):
        module.load_policy(work)


def test_policy_mutation_or_cross_work_use_rejected(subject, tmp_path):
    module, work, path, data = subject
    reviewed = module.sha(path)
    data['authorization_note'] += 'changed'; path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='digest differs'):
        module.load_policy(work, expected_sha=reviewed)
    with pytest.raises(ValueError, match='inside this continuation'):
        module.load_policy(tmp_path / 'other', path)


def test_original_guard_reference_must_remain_frozen(subject):
    module, work, _, _ = subject
    (work / '.continuation/source-reference/host_resource_guard.py').write_text('changed')
    with pytest.raises(ValueError, match='frozen continuation tool changed'):
        module.load_policy(work)


@pytest.mark.parametrize(('field', 'number', 'violation'), [
    ('system_disk_free_bytes', 5 * 2**30 - 1, 'system_disk'),
    ('commit_total_bytes', 25 * 2**30 + 1, 'commit'),
    ('physical_available_bytes', 3 * 2**30, 'ram'),
    ('data_disk_free_bytes', 24 * 2**30, 'data_disk'),
])
def test_new_policy_still_enforces_all_reserves(subject, field, number, violation):
    module, work, _, _ = subject
    policy = module.load_policy(work)
    with pytest.raises(module.guard.ResourcePressure) as failure:
        module.check(policy, snapshot=lambda: healthy() | {field: number})
    assert failure.value.report['violations'] == [violation]
    assert not (work / 'STOP').exists()


def test_watch_actual_limits_and_stop_preservation(subject):
    module, work, _, _ = subject
    policy = module.load_policy(work)
    states = iter(('alive', 'alive', 'alive', 'exited'))
    samples = iter((healthy(7), healthy(4)))
    (work / 'STOP').write_bytes(b'existing operator STOP\r\n')
    assert module.watch(policy, 123, 345., process_probe=lambda *_: next(states),
                        snapshot=lambda: next(samples), sleep=lambda _: None) == 0
    assert (work / 'STOP').read_bytes() == b'existing operator STOP\r\n'
    ready = module.read(work / 'host-resource-guard/ready.json')
    assert ready['report']['limits_bytes'] == policy.limits.bytes()
    events = [json.loads(line) for path in (work / 'host-resource-guard').glob('*.jsonl')
              for line in path.read_text().splitlines()]
    pressure = next(row for row in events if row['event'] == 'pause-requested')
    assert pressure['reason']['report']['violations'] == ['system_disk']


def test_run_delegates_once_to_original_runner_and_callback(subject, monkeypatch):
    module, work, _, _ = subject
    policy = module.load_policy(work)
    calls = []
    monkeypatch.setattr(module, 'resource_watch', lambda selected: ('guard', selected))
    def original_run(actual, *, watch):
        calls.append(actual)
        assert watch(actual) == ('guard', policy)
        return 'same original runner'
    monkeypatch.setitem(sys.modules, 'continuation', SimpleNamespace(run=original_run))
    assert module.run(policy) == 'same original runner' and calls == [work]


def test_ready_requires_correct_policy_limits_and_process_identity(subject):
    module, work, path, _ = subject
    policy = module.load_policy(work)
    candidate = SimpleNamespace(pid=99, create_time=lambda: 123.)
    command = [str(HERE / 'memory_configured_continuation.py'), 'watch', '--work', str(work), '--policy', str(path),
               '--policy-sha256', policy.sha256, '--pid', '88', '--started-at', '120.0']
    value = {'target_pid': 88, 'target_started_at': 120., 'guard_pid': 99, 'guard_started_at': 123.,
             'epoch': 124., 'safe': True, 'report': {'safe': True, 'limits_bytes': policy.limits.bytes()}}
    module.validate_ready(policy, value, candidate, command, 88, 120., 122.)
    with pytest.raises(ValueError, match='different limits'):
        module.validate_ready(policy, value | {'report': {'safe': True, 'limits_bytes': module.guard.Limits().bytes()}},
                              candidate, command, 88, 120., 122.)
    with pytest.raises(ValueError, match='timestamp differs'):
        module.validate_ready(policy, value | {'guard_started_at': 50.}, candidate, command, 88, 120., 122.)
    with pytest.raises(ValueError, match='timestamp differs'):
        module.validate_ready(policy, value | {'epoch': 100.}, candidate, command, 88, 120., 122.)
    wrong = [x if x != policy.sha256 else 'wrong-digest' for x in command]
    with pytest.raises(ValueError, match='command differs'):
        module.validate_ready(policy, value, candidate, wrong, 88, 120., 122.)


def test_six_gib_commit_passes_only_new_policy(subject):
    module, work, _, _ = subject
    policy = module.load_policy(work)
    sample = healthy(20) | {'commit_total_bytes': 24 * 2**30}
    assert module.check(policy, snapshot=lambda: sample)['safe']
    with pytest.raises(module.guard.ResourcePressure) as failure:
        module.guard.check_resources(work, snapshot=lambda: sample)
    assert failure.value.report['violations'] == ['commit']


def test_old_schema_and_limits_cannot_silently_be_adopted(subject):
    module, work, path, data = subject
    data['schema'] = 'threemind.e69-host-policy/1'
    data['limits']['commit_gib'] = 8
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='not for this'):
        module.load_policy(work)


def test_missing_new_policy_never_falls_back_to_previous(subject):
    module, work, path, _ = subject
    path.unlink()
    with pytest.raises(FileNotFoundError):
        module.load_policy(work)


def test_watch_new_commit_threshold_requests_boundary_pause(subject):
    module, work, _, _ = subject
    policy = module.load_policy(work)
    states = iter(('alive', 'alive', 'alive', 'exited'))
    samples = iter((healthy() | {'commit_total_bytes': 24 * 2**30},
                    healthy() | {'commit_total_bytes': 25 * 2**30 + 1}))
    assert module.watch(policy, 123, 345., process_probe=lambda *_: next(states),
                        snapshot=lambda: next(samples), sleep=lambda _: None) == 0
    stop = module.read(work / 'STOP')
    assert stop['report']['violations'] == ['commit']
    assert stop['report']['limits_bytes']['commit'] == 5 * 2**30
    assert module.read(work / 'host-resource-guard/ready.json')['safe']


@pytest.mark.parametrize('changed', ['previous_policy_sha256', 'previous_bytes', 'previous_source'])
def test_predecessor_must_remain_unchanged(subject, monkeypatch, changed):
    module, work, path, data = subject
    previous = work / '.continuation/host-policies' / module.PREVIOUS_POLICY_NAME
    if changed == 'previous_policy_sha256':
        data[changed] = '0' * 64
        path.write_text(json.dumps(data))
    elif changed == 'previous_bytes':
        previous.write_text('{}')
    else:
        previous.write_text(json.dumps({'source_sha256': '0' * 64}))
        monkeypatch.setattr(module, 'PREVIOUS_POLICY_SHA256', module.sha(previous))
        data['previous_policy_sha256'] = module.sha(previous)
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='prior'):
        module.load_policy(work)


def test_status_reports_new_limits_without_starting_subject(subject, monkeypatch):
    module, work, _, _ = subject
    policy = module.load_policy(work)
    before = {p: p.read_bytes() for p in work.rglob('*') if p.is_file()}
    monkeypatch.setitem(sys.modules, 'continuation_status', SimpleNamespace(
        continuation_status=lambda actual: {'processes': [], 'process_access_denied': []}))
    monkeypatch.setattr(module.psutil, 'process_iter', lambda *_: [])
    value = module.status(policy)
    assert value['configured_host_policy']['limits_bytes'] == {
        'commit': 5 * 2**30, 'ram': 4 * 2**30,
        'system_disk': 5 * 2**30, 'data_disk': 25 * 2**30}
    assert before == {p: p.read_bytes() for p in work.rglob('*') if p.is_file()}


def test_status_covers_both_wrappers_and_deduplicates_existing_process(subject, monkeypatch):
    module, work, _, _ = subject
    policy = module.load_policy(work)
    monkeypatch.setitem(sys.modules, 'continuation_status', SimpleNamespace(
        continuation_status=lambda actual: {'processes': [{'pid': 10}], 'process_access_denied': []}))
    def process(pid, name, action, selected_work=work):
        return SimpleNamespace(pid=pid, info={'name': 'python.exe'},
            cmdline=lambda: ['python.exe', str(HERE / name), action, '--work', str(selected_work)],
            create_time=lambda: 100., cpu_times=lambda: [1., 2.],
            memory_info=lambda: SimpleNamespace(rss=123))
    rows = [process(10, 'configured_continuation.py', 'run'),
            process(11, 'configured_continuation.py', 'watch'),
            process(12, 'memory_configured_continuation.py', 'run'),
            process(13, 'memory_configured_continuation.py', 'watch'),
            process(14, 'memory_configured_continuation.py', 'check'),
            process(15, 'configured_continuation.py', 'run', work.parent / 'different')]
    monkeypatch.setattr(module.psutil, 'process_iter', lambda *_: rows)
    assert [row['pid'] for row in module.status(policy)['processes']] == [10, 11, 12, 13]


@pytest.mark.parametrize('action', ['run', 'watch'])
def test_execution_cli_requires_reviewed_policy_digest(subject, monkeypatch, action):
    module, work, _, _ = subject
    monkeypatch.setattr(sys, 'argv', [module.__file__, action, '--work', str(work)])
    with pytest.raises(SystemExit) as failure:
        module.main()
    assert failure.value.code == 2


@pytest.mark.parametrize('action', ['check', 'status', 'run', 'watch'])
def test_all_cli_routes_receive_authorized_limits(subject, monkeypatch, action):
    module, work, path, _ = subject
    monkeypatch.setattr(sys, 'argv', [module.__file__, action, '--work', str(work),
        '--policy-sha256', module.sha(path), '--pid', '123', '--started-at', '345.0'])
    calls = []
    def selected(policy, *args):
        calls.append((policy, args))
        assert policy.limits.bytes() == {'commit': 5 * 2**30, 'ram': 4 * 2**30,
            'system_disk': 5 * 2**30, 'data_disk': 25 * 2**30}
        return 0 if action == 'watch' else {'safe': True}
    monkeypatch.setattr(module, action, selected)
    assert module.main() == 0
    assert len(calls) == 1
