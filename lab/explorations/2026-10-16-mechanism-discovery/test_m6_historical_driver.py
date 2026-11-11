"""Pure host/receipt fixtures: never launch a process or construct a Core."""
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
import pytest
import m6_historical_driver as d
import m6_historical_analyze as analyze
import m6_historical_audit as audit


@pytest.fixture
def folder():
    path = d.m.ROOT / '.work' / ('m6-host-fixture-' + uuid4().hex)
    path.mkdir()
    return path


@pytest.mark.parametrize('private,elapsed,size,fault,fragment', [
    (3 * 2**30 + 1, 0, 0, None, 'private-memory'),
    (0, 101, 0, None, 'two-hour'),
    (0, 0, 2 * 2**30 + 1, None, 'original-data'),
    (0, 0, 0, RuntimeError('synthetic probe failure'), 'synthetic probe failure')])
def test_resource_guard_never_clears_stop_or_advances_subject(folder, private, elapsed, size, fault, fragment):
    guard = d.Guard(folder, folder, 100, 3)
    with patch.object(d.m, 'resource_check', side_effect=fault, return_value={'available_bytes': {'commit': 9 * 2**30}}), \
         patch.object(d.psutil, 'Process', return_value=SimpleNamespace(memory_info=lambda: SimpleNamespace(private=private))), \
         patch.object(d.time, 'monotonic', return_value=guard.started + elapsed), \
         patch.object(d, 'original_bytes', return_value=size):
        guard.watch()
    first = (folder / 'STOP').read_bytes()
    assert fragment in d.m.read(folder / 'STOP')['reason']
    assert not (folder / 'in-flight.json').exists()
    with patch.object(d.m, 'resource_check', side_effect=RuntimeError('later event')):
        guard.watch()
    assert (folder / 'STOP').read_bytes() == first


def test_instrument_and_science_are_distinct_fixed_schedules():
    n0 = d.scheduled('apparatus')
    science = d.scheduled('run')
    assert len(n0) == 10 and len(science) == 16
    assert n0[0]['route'] == n0[5]['route'] == 'parent'
    assert [row['route'] for row in n0[1:5]] == ['plain', 'observed', 'paused', 'restored']
    assert not {row['id'] for row in n0} & {row['id'] for row in science}
    with pytest.raises(ValueError):
        d.scheduled('resume')


def test_m4_complete_delivery_is_mandatory(folder, monkeypatch):
    monkeypatch.setattr(d, 'M4', folder)
    path = folder / 'publication/final-verification.json'
    d.m.original(path, {'execution_status': 'completed', 'coverage': 'verified', 'problems': [],
                        'experiment_id': '9d3589f3-663f-5a1a-be9a-5a8c6fcaf443'})
    d.prior_delivered()
    d.m.original(folder / 'STOP', {'reason': 'test'})
    with pytest.raises(RuntimeError):
        d.prior_delivered()


def test_old_or_spoofed_worker_ticket_is_rejected_before_process_use(folder):
    owner = {'phase': 'run', 'pid': 1, 'created_at': 2.}
    ticket = folder / 'hosts/run/workers/00-w0-live-sham/ticket.json'
    d.m.original(ticket, {'phase': 'run', 'supervisor': owner, 'index': -1, 'task': d.scheduled('run')[-1]})
    with pytest.raises(ValueError, match='index outside'):
        d.validate_ticket(folder, ticket, owner)


def test_capacity_rejects_incomplete_n0(folder):
    with pytest.raises(ValueError, match='complete two-world'):
        d.capacity_forecast(folder)


def test_review_must_match_exact_n0_and_source_manifest(folder):
    d.m.original(folder / 'apparatus.json', {'passed': True})
    d.m.original(folder / 'runner-manifest.json', {'fixture': 'frozen'})
    d.m.original(folder / 'apparatus-review.json', {'accepted': True, 'apparatus_sha256': 'wrong',
                   'runner_manifest_sha256': d.ev.file_sha(folder / 'runner-manifest.json')})
    with pytest.raises(RuntimeError, match='bound to this exact'):
        d.accepted_apparatus(folder)


def test_frozen_factorial_and_selection_cannot_change(folder):
    for name, value in [('selection.json', {'before_outcomes': True}),
                        ('historical-parents.json', []), ('cases.json', d.ev.cases())]:
        d.m.original(folder / name, value)
    manifest = {name: d.ev.file_sha(folder / name) for name in ('selection.json', 'historical-parents.json', 'cases.json')}
    d.m.original(folder / 'inputs-manifest.json', manifest)
    d.frozen_inputs(folder)
    # This is a synthetic disposable fixture, never an experiment original.
    (folder / 'selection.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='selection or parent changed'):
        d.frozen_inputs(folder)


def test_each_scientific_outcome_has_explicit_meaning():
    for verdict in ('PASS', 'FAIL', 'MEASUREMENT_NOT_QUALIFIED'):
        result = {'verdict': verdict}
        assert len(analyze.scientific_conclusion(result, 'zh')) > 80
        assert len(analyze.scientific_conclusion(result, 'en')) > 120
    assert '证实' in analyze.scientific_conclusion({'verdict': 'PASS'}, 'zh')
    assert '否定' in analyze.scientific_conclusion({'verdict': 'FAIL'}, 'zh')
    assert '装置条件不合格' in analyze.scientific_conclusion({'verdict': 'MEASUREMENT_NOT_QUALIFIED'}, 'zh')


def test_initial_audit_rejects_undeclared_body_change():
    context = {'coverage': {'material': {'enclosure': {'group': {'community': {'world': {
        'protocol': {'hearing_mode': 'live'}, 'core_hashes': {'1': 'old'}, 'body_x': .1}}}}}}}
    before = {'context': context, 'extras': {}}
    import copy
    after = copy.deepcopy(before)
    audit.state.base(after['context'])['core_hashes']['1'] = 'new'
    old = {'time_us': 20_000_000, 'canonical_sha256': 'a'}
    new = {'time_us': 20_000_000, 'canonical_sha256': 'b'}
    operation = {'eligible': [1], 'mode': 'live', 'before_sha256': 'a', 'after_sha256': 'b',
                 'operations': [{'body': 1, 'before_sha256': 'old', 'after_sha256': 'new'}]}
    selection = {'rows': [{'body': 1, 'valid': True}]}
    audit.audit_initial((before, old), (after, new), operation, selection)
    audit.state.base(after['context'])['body_x'] = .2
    with pytest.raises(ValueError, match='undeclared whole-world'):
        audit.audit_initial((before, old), (after, new), operation, selection)
