"""Host-only resource guard tests; no Core, database or formal subject."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color/host_resource_guard.py'
spec = importlib.util.spec_from_file_location('e69_host_guard_test_module', PATH)
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)


def healthy():
    return {'commit_total_bytes': 10 * guard.GIB, 'commit_limit_bytes': 30 * guard.GIB,
            'physical_available_bytes': 12 * guard.GIB,
            'system_disk_free_bytes': 20 * guard.GIB, 'data_disk_free_bytes': 100 * guard.GIB}


def events(work):
    return [json.loads(line) for path in (work / 'host-resource-guard').glob('*.jsonl')
            for line in path.read_text(encoding='utf-8').splitlines()]


def states(*values):
    sequence = iter(values)
    return lambda *_: next(sequence)


def test_check_is_read_only_including_nonexistent_work(tmp_path):
    work = tmp_path / 'not-created'
    report = guard.check_resources(work, snapshot=healthy)
    assert report['safe'] and report['available_bytes']['commit'] == 20 * guard.GIB
    assert not work.exists()


@pytest.mark.parametrize(('field', 'value', 'violation'), [
    ('commit_total_bytes', 23 * guard.GIB, 'commit'),
    ('physical_available_bytes', 3 * guard.GIB, 'ram'),
    ('system_disk_free_bytes', 9 * guard.GIB, 'system_disk'),
    ('data_disk_free_bytes', 24 * guard.GIB, 'data_disk'),
])
def test_each_reserve_rejects_start_without_writing(tmp_path, field, value, violation):
    with pytest.raises(guard.ResourcePressure) as failure:
        guard.check_resources(tmp_path, snapshot=lambda: healthy() | {field: value})
    assert failure.value.report['violations'] == [violation]
    assert not list(tmp_path.iterdir())


def test_probe_error_is_fail_closed_and_does_not_become_zero_or_healthy(tmp_path):
    def failure():
        raise OSError('Windows probe unavailable')

    with pytest.raises(guard.ResourceUnavailable, match='Windows probe unavailable'):
        guard.check_resources(tmp_path, snapshot=failure)
    with pytest.raises(guard.ResourceUnavailable):
        guard.check_resources(tmp_path, snapshot=lambda: healthy() | {'commit_limit_bytes': 0})
    assert not list(tmp_path.iterdir())


def test_pressure_only_requests_stop_then_waits_for_original_host_exit(tmp_path):
    (tmp_path / 'subject').mkdir()
    flight = tmp_path / 'subject/in-flight.json'
    flight.write_text('original in-flight evidence', encoding='utf-8')
    sleeps = []

    def wait(seconds):
        sleeps.append(seconds)
        assert (tmp_path / 'STOP').exists()
        assert flight.read_text(encoding='utf-8') == 'original in-flight evidence'

    result = guard.watch(tmp_path, 77, 123., snapshot=lambda: healthy() | {'commit_total_bytes': 29 * guard.GIB},
                         process_probe=states('alive', 'alive', 'exited'), sleep=wait)
    assert result == 3 and sleeps == [1.]
    assert flight.read_text(encoding='utf-8') == 'original in-flight evidence'
    logged = events(tmp_path)
    assert [row['event'] for row in logged] == ['watch-started', 'pause-requested', 'target-exited']
    assert logged[1]['created_stop'] and logged[1]['in_flight']
    assert logged[1]['reason']['report']['violations'] == ['commit']


def test_existing_stop_is_preserved_exactly(tmp_path):
    (tmp_path / 'STOP').write_bytes(b'operator pause\r\nkeep me')
    guard.watch(tmp_path, 77, 123., snapshot=lambda: healthy() | {'physical_available_bytes': 0},
                process_probe=states('alive', 'alive', 'exited'), sleep=lambda _: None)
    assert (tmp_path / 'STOP').read_bytes() == b'operator pause\r\nkeep me'
    assert events(tmp_path)[1]['created_stop'] is False


@pytest.mark.parametrize(('state', 'code'), [('exited', 0), ('reused', 2)])
def test_missing_or_reused_pid_exits_without_any_writes(tmp_path, state, code):
    def forbidden():
        pytest.fail('resources should not be probed for an unrelated/exited host')

    assert guard.watch(tmp_path, 77, 123., snapshot=forbidden, process_probe=lambda *_: state) == code
    assert not list(tmp_path.iterdir())


def test_pid_reuse_after_start_never_stops_replacement(tmp_path):
    assert guard.watch(tmp_path, 77, 123., snapshot=healthy,
                       process_probe=states('alive', 'alive', 'reused'), sleep=lambda _: None) == 2
    assert not (tmp_path / 'STOP').exists()
    assert events(tmp_path)[-1]['event'] == 'target-reused'
    ready = json.loads((tmp_path / 'host-resource-guard/ready.json').read_text(encoding='utf-8'))
    assert ready['safe'] and ready['guard_pid'] == guard.os.getpid()
    assert ready['guard_started_at'] == guard.psutil.Process().create_time()
    assert ready['target_pid'] == 77 and ready['target_started_at'] == 123.


def test_probe_failure_requests_stop_and_exits_after_host_does(tmp_path):
    def unavailable():
        raise guard.ResourceUnavailable('GetPerformanceInfo failed')

    assert guard.watch(tmp_path, 77, 123., snapshot=unavailable,
                       process_probe=states('alive', 'alive', 'exited'), sleep=lambda _: None) == 0
    assert (tmp_path / 'STOP').exists()
    assert events(tmp_path)[1]['reason']['event'] == 'probe-unavailable'
    ready = json.loads((tmp_path / 'host-resource-guard/ready.json').read_text(encoding='utf-8'))
    assert ready['safe'] is False and ready['report'] is None


def test_recovered_resources_do_not_remove_stop_or_restart_host(tmp_path):
    samples = iter([healthy() | {'system_disk_free_bytes': 0}, healthy()])
    assert guard.watch(tmp_path, 77, 123., snapshot=lambda: next(samples),
                       process_probe=states('alive', 'alive', 'alive', 'exited'), sleep=lambda _: None) == 0
    assert (tmp_path / 'STOP').exists()
    assert events(tmp_path)[-1]['pressure_requested']


def test_pid_identity_uses_creation_time(monkeypatch):
    class Process:
        def create_time(self):
            return 124.

        def is_running(self):
            pytest.fail('different creation time is already a different process')

    monkeypatch.setattr(guard.psutil, 'Process', lambda _: Process())
    assert guard.target_state(77, 123.) == 'reused'


def test_unexpected_monitor_error_requests_stop_and_never_claims_ready(tmp_path):
    def broken_probe():
        raise RuntimeError('unexpected host probe failure')

    with pytest.raises(RuntimeError, match='unexpected host probe failure'):
        guard.watch(tmp_path, 77, 123., snapshot=broken_probe,
                    process_probe=lambda *_: 'alive', sleep=lambda _: None)
    assert (tmp_path / 'STOP').exists()
    assert not (tmp_path / 'host-resource-guard/ready.json').exists()
