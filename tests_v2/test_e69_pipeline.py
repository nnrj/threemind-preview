"""Pipeline fault boundaries with synthetic receipts; never runs an organism."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / 'lab/explorations/2026-10-13-eye-hand-shape-color'


def modules(monkeypatch):
    values = {}
    for name in ('journal', 'pipeline'):
        spec = importlib.util.spec_from_file_location('e69_pipeline_test_' + name, HERE / (name + '.py'))
        value = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(value)
        monkeypatch.setitem(sys.modules, name, value)
        values[name] = value
    return values['journal'], values['pipeline']


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def registration(work):
    put(work / '.research-records/identity.json', {'engineering_only': True})
    put(work / 'platform.json', {'engineering_only': True})


def finished(work):
    latest = {'boundary_sha256': 'synthetic-boundary-hash', 'end_us': 400000}
    put(work / 'subject/latest.json', latest)
    put(work / 'computation-complete.json', {'latest': latest, 'time_us': latest['end_us']})


def commands(work, journal):
    calls = []

    def command(script, args, target):
        assert target == work
        calls.append((script, args))
        if script == 'experiment.py':
            assert args == ['run']
            finished(work)
        elif script == 'analyze.py':
            put(work / 'analysis/verified-results.json', {
                'last_boundary': 'synthetic-boundary-hash', 'continuous': True})
        elif script == 'replay.py':
            video = work / 'replays/tool-test.mp4'
            video.parent.mkdir()
            video.write_bytes(b'tool test receipt only; no media or subject')
            put(work / 'replays/export.json', {
                'video': 'replays/tool-test.mp4', 'sha256': journal.sha(video),
                'activity_curves': ['activation', 'inhibition', 'direct', 'associative'],
                'core_advanced': False, 'full_decode_verified': True})
        elif script == 'publish.py':
            assert args == ['originals']
            put(work / 'originals-publication.json', {
                'last_boundary': 'synthetic-boundary-hash', 'pending': 0,
                'analysis_sha256': journal.sha(work / 'analysis/verified-results.json'),
                'export_sha256': journal.sha(work / 'replays/export.json')})
        else:
            pytest.fail('unexpected tool')

    return command, calls


def test_missing_steps_once_and_no_automatic_finalization(tmp_path, monkeypatch):
    journal, pipeline = modules(monkeypatch)
    registration(tmp_path)
    command, calls = commands(tmp_path, journal)
    assert pipeline.run_pipeline(tmp_path, command=command) == 'awaiting-report-review'
    assert [name for name, _ in calls] == ['experiment.py', 'analyze.py', 'replay.py', 'publish.py']
    assert not (tmp_path / 'publication-status.json').exists()
    before = len(calls)
    assert pipeline.run_pipeline(tmp_path, command=command) == 'awaiting-report-review'
    assert len(calls) == before


def test_complete_subject_never_reexecutes_after_postprocess_failure(tmp_path, monkeypatch):
    journal, pipeline = modules(monkeypatch)
    registration(tmp_path)
    finished(tmp_path)
    before = (tmp_path / 'subject/latest.json').read_bytes()
    put(tmp_path / 'host-status.json', {'error': 'BoundaryPause: obsolete previous pause'})

    def failure(script, args, work):
        assert script == 'analyze.py'
        raise subprocess.CalledProcessError(1, ['synthetic-analyze'])

    with pytest.raises(subprocess.CalledProcessError):
        pipeline.run_pipeline(tmp_path, command=failure)
    assert (tmp_path / 'subject/latest.json').read_bytes() == before
    assert journal.read(tmp_path / 'pipeline-status.json')['phase'] == 'attention-required'
    command, calls = commands(tmp_path, journal)
    pipeline.run_pipeline(tmp_path, command=command)
    assert [name for name, _ in calls] == ['analyze.py', 'replay.py', 'publish.py']


def test_dirty_inflight_is_preserved_and_blocks_all_commands(tmp_path, monkeypatch):
    journal, pipeline = modules(monkeypatch)
    registration(tmp_path)
    marker = tmp_path / 'subject/in-flight.json'
    put(marker, {'key': 'experienced-but-not-committed'})
    before = marker.read_bytes()
    with pytest.raises(journal.ContinuityUncertain, match='in-flight'):
        pipeline.run_pipeline(tmp_path, command=lambda *_: pytest.fail('must not run'))
    assert marker.read_bytes() == before
    assert journal.read(tmp_path / 'pipeline-status.json')['automatic_rollback'] is False


def test_corrupt_completion_is_not_permission_to_restart(tmp_path, monkeypatch):
    journal, pipeline = modules(monkeypatch)
    registration(tmp_path)
    finished(tmp_path)
    put(tmp_path / 'computation-complete.json', {'latest': {'boundary_sha256': 'other'}})
    with pytest.raises(journal.ContinuityUncertain, match='computation receipt'):
        pipeline.run_pipeline(tmp_path, command=lambda *_: pytest.fail('must not run'))


def test_stop_and_safe_resource_pause_are_visible(tmp_path, monkeypatch):
    journal, pipeline = modules(monkeypatch)
    registration(tmp_path)
    (tmp_path / 'STOP').touch()
    with pytest.raises(journal.BoundaryPause):
        pipeline.run_pipeline(tmp_path, command=lambda *_: pytest.fail('must not run'))
    assert journal.read(tmp_path / 'pipeline-status.json')['phase'] == 'paused'
    (tmp_path / 'STOP').unlink()

    def resource_pause(script, _args, work):
        assert script == 'experiment.py'
        put(work / 'host-status.json', {'error': 'BoundaryPause: disk reserve reached'})
        raise subprocess.CalledProcessError(1, ['synthetic-experiment'])

    with pytest.raises(subprocess.CalledProcessError):
        pipeline.run_pipeline(tmp_path, command=resource_pause)
    assert journal.read(tmp_path / 'pipeline-status.json')['phase'] == 'paused'
    put(tmp_path / 'subject/in-flight.json', {'key': 'unresolved'})
    with pytest.raises(journal.ContinuityUncertain):
        pipeline.run_pipeline(tmp_path, command=resource_pause)
    assert journal.read(tmp_path / 'pipeline-status.json')['phase'] == 'attention-required'


def test_pipeline_and_existing_host_lock_are_exclusive(tmp_path, monkeypatch):
    from threemind_lab.storage_files import StorageBusy, file_lock

    _, pipeline = modules(monkeypatch)
    registration(tmp_path)
    for lock in ('pipeline.lock', 'runner.lock'):
        with file_lock(tmp_path / lock), pytest.raises(StorageBusy):
            pipeline.run_pipeline(tmp_path, command=lambda *_: pytest.fail('must not run'))


def test_never_invents_registration(tmp_path, monkeypatch):
    _, pipeline = modules(monkeypatch)
    with pytest.raises(ValueError, match='registration'):
        pipeline.run_pipeline(tmp_path, command=lambda *_: pytest.fail('must not run'))
    assert not list(tmp_path.iterdir())
