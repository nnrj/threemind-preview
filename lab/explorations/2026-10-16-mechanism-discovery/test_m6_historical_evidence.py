"""Synthetic rows and fake worlds only; no real individual is constructed."""
import copy
import gzip
import math
from types import SimpleNamespace
from uuid import uuid4
import pytest
import m6_historical_evidence as ev
import m6_historical_rig as rig
import m6_historical_audit as audit
import m6_historical_metrics as scoring


@pytest.fixture
def tmp_path():
    # Avoid pytest's mode-0700 temporary-root ACL path on this Windows host.
    # Each synthetic run is new and retained; no cleanup touches experiment data.
    folder = rig.m.ROOT / '.work' / ('m6-evidence-fixture-' + uuid4().hex)
    folder.mkdir()
    return folder


def row(when, value=.1):
    return {'action_time_us': when, 'time_us': when + ev.PERIOD_US,
            'actions': {str(i): [value, 0., 0.] for i in range(8)},
            'native': {'time_us': when + ev.PERIOD_US, 'inputs': [], 'events': []}}


def write(folder, start, frames):
    writer = ev.Trajectory(folder / f'{start}.jsonl.gz', start)
    for index in range(frames):
        writer.append(row(start + index * ev.PERIOD_US))
    receipt = writer.finish()
    return receipt | {'path': writer.path.name}


def test_full_factorial_is_explicit_and_unique():
    assert len(ev.cases()) == 16
    assert len({case['id'] for case in ev.cases()}) == 16
    for case in ev.cases():
        assert ev.checked_case(case) == case
    with pytest.raises(ValueError):
        ev.checked_case(ev.cases()[0] | {'world': 2})


def test_exact_stream_chain_and_primary_window(tmp_path):
    first = write(tmp_path, 20_000_000, 50)
    rest = write(tmp_path, 21_000_000, 450)
    check = ev.verify_chain(tmp_path, [first, rest], 20_000_000, 30_000_000)
    assert check['frames'] == 500 and len(check['primary']) == 50
    assert check['primary'][0]['actions']['0'] == [.1, 0., 0.]
    with pytest.raises(FileExistsError):
        ev.Trajectory(tmp_path / first['path'], 20_000_000)


def test_noncontiguous_stream_and_corrupt_receipt_rejected(tmp_path):
    first = write(tmp_path, 20_000_000, 2)
    rest = write(tmp_path, 20_060_000, 1)
    with pytest.raises(ValueError, match='noncontiguous'):
        ev.verify_chain(tmp_path, [first, rest], 20_000_000, 20_080_000)
    with pytest.raises(ValueError, match='receipt differs'):
        list(ev.read_segment(tmp_path / first['path'], first | {'raw_sha256': '0' * 64}))


def test_unfinished_stream_is_preserved_and_cannot_be_retried(tmp_path):
    path = tmp_path / 'segment.jsonl.gz'
    writer = ev.Trajectory(path, 20_000_000)
    writer.append(row(20_000_000))
    with pytest.raises(ValueError, match='unordered'):
        writer.append(row(20_000_000))
    writer.abort()
    assert writer.partial.is_file() and not path.exists()
    with pytest.raises(FileExistsError):
        ev.Trajectory(path, 20_000_000)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 1.1])
def test_nonfinite_and_out_of_range_actions_rejected(value):
    with pytest.raises(ValueError):
        ev.validate_row(row(20_000_000, value), 20_000_000)


def test_paths_cannot_escape_evidence_root(tmp_path):
    with pytest.raises(ValueError):
        ev.inside(tmp_path, '../different.txt')


def factorial(target=.05, matched=.09, baseline=.1):
    values = {'sham': baseline, 'target': target, 'matched': matched, 'restored': baseline}
    return {f'{mode}-{op}': [row(20_000_000 + j * 20_000, values[op] if mode == 'live' else 0.)
                             for j in range(50)] for mode in ev.MODES for op in ev.OPERATIONS}


@pytest.mark.parametrize('target,matched,baseline,exact,expected', [
    (.05, .09, .1, True, 'PASS'), (.09, .09, .1, True, 'FAIL'),
    (.05, .09, .001, True, 'MEASUREMENT_NOT_QUALIFIED'),
    (.05, .09, .1, False, 'MEASUREMENT_NOT_QUALIFIED')])
def test_independent_arithmetic_matches_primary_and_closes_all_outcomes(target, matched, baseline, exact, expected):
    arms = factorial(target, matched, baseline)
    restoration = {'live': exact, 'muted': True}
    direct = audit.independent_scores(arms, list(range(8)), restoration)
    primary = scoring.world_result(arms, list(range(8)), restoration)
    assert direct['verdict'] == primary['verdict'] == expected
    assert direct['measurement_valid'] == primary['measurement_valid']
    for key, value in direct['partner_action_rms'].items():
        assert math.isclose(value, primary['partner_action_rms'][key], rel_tol=1e-12, abs_tol=1e-12)


def fake_world(monkeypatch, work, stop_at=None, fail_at=None):
    world = SimpleNamespace(time_us=20_000_000, p=SimpleNamespace(period_us=20_000))
    world.metrics = lambda: {'time_us': world.time_us}
    monkeypatch.setattr(rig.state, 'canonical', lambda w: {'time_us': w.time_us})
    def save(w, folder):
        folder.mkdir(parents=True, exist_ok=False)
        value = {'time_us': w.time_us, 'canonical_sha256': rig.m.digest({'time_us': w.time_us})}
        rig.m.original(folder / 'complete.json', value)
        return value
    monkeypatch.setattr(rig.state, 'save_whole', save)
    def step(w, **unused):
        old = w.time_us
        w.time_us += 20_000
        if w.time_us == fail_at:
            raise ValueError('injected synthetic step failure')
        if w.time_us == stop_at:
            rig.m.original(work / 'STOP', {'reason': 'synthetic complete-boundary pause'})
        return row(old)
    monkeypatch.setattr(rig.state, 'physical_step', step)
    return world


def initial(work, world):
    return {'time_us': world.time_us, 'canonical_sha256': rig.m.digest({'time_us': world.time_us}), 'segments': []}


def test_resource_stop_saves_exact_last_physical_boundary(monkeypatch, tmp_path):
    guard = SimpleNamespace(thread=SimpleNamespace(is_alive=lambda: True))
    world = fake_world(monkeypatch, tmp_path, stop_at=20_060_000)
    before = initial(tmp_path, world)
    with pytest.raises(rig.BoundaryPause):
        rig.segment(tmp_path, tmp_path / 'branch', world, 21_000_000, 'synthetic', before, guard, lambda v: None)
    current = rig.m.read(tmp_path / 'current-boundary.json')
    assert world.time_us == current['time_us'] == 20_060_000
    assert current['parent_sha256'] == before['canonical_sha256']
    assert not (tmp_path / 'in-flight.json').exists() and (tmp_path / 'STOP').exists()
    checked = ev.verify_chain(tmp_path / 'branch', current['segments'], 20_000_000, 20_060_000)
    assert checked['frames'] == 3


def test_dead_host_inflight_and_partial_remain_for_review(monkeypatch, tmp_path):
    guard = SimpleNamespace(thread=SimpleNamespace(is_alive=lambda: True))
    world = fake_world(monkeypatch, tmp_path, fail_at=20_040_000)
    with pytest.raises(ValueError, match='synthetic step failure'):
        rig.segment(tmp_path, tmp_path / 'branch', world, 21_000_000, 'synthetic', initial(tmp_path, world), guard, lambda v: None)
    assert (tmp_path / 'in-flight.json').exists()
    assert (tmp_path / 'branch/trajectories/20000000.jsonl.gz.partial').exists()
    assert not (tmp_path / 'current-boundary.json').exists()


def test_missing_guard_does_not_start_a_segment(monkeypatch, tmp_path):
    world = fake_world(monkeypatch, tmp_path)
    guard = SimpleNamespace(thread=SimpleNamespace(is_alive=lambda: False))
    with pytest.raises(RuntimeError, match='guard disappeared'):
        rig.segment(tmp_path, tmp_path / 'branch', world, 21_000_000, 'synthetic', initial(tmp_path, world), guard, lambda v: None)
    assert world.time_us == 20_000_000 and not (tmp_path / 'in-flight.json').exists()


def test_both_restoration_modes_and_frozen_denominator_are_required():
    with pytest.raises(ValueError):
        audit.independent_scores(factorial(), list(range(8)), {'live': True})
    with pytest.raises(ValueError):
        audit.independent_scores(factorial(), [0, 0, 1], {'live': True, 'muted': True})
