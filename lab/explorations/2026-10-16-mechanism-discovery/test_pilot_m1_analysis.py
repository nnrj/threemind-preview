"""Tests use synthetic records and fake interventions, never research subjects."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_m2 as analysis
import pilot_m1 as m1


def test_origins_and_declared_copies_do_not_multiply_n():
    cases = m1.parents()
    assert len(cases) == 16
    assert len({c['seed'] for c in cases}) == 8
    assert not ({c['seed'] for c in cases} & {c['seed'] for c in m1.base.cases()})
    assert 817001 not in {c['seed'] for c in cases}
    rows = [{'case': {'origin': o, 'history': h}, 'value': 2 if h == 0 else -4}
            for o in range(8) for h in (0, 1)]
    assert analysis.paired_values(rows, 'value') == [3]*8
    with pytest.raises(ValueError, match='duplicate history'):
        analysis.paired_values(rows+[rows[0]], 'value')
    with pytest.raises(ValueError, match='eight independent'):
        analysis.paired_values(rows[:-1], 'value')


def test_missing_expression_not_imputed_as_success():
    rows = [{'case': {'origin': o, 'history': h}, 'value': None if o == 0 else 0.}
            for o in range(8) for h in (0, 1)]
    values = analysis.paired_values(rows, 'value')
    assert len(values) == 7
    assert analysis.describe(values, 1)['n'] == 7
    assert analysis.describe([], 1)['mean'] is None


class FakeSubject:
    def __init__(self, illicit=False):
        self.engine = self
        self.state = {'core': {'silenced_edges': [], 'time_us': '18000000', 'weight': .1}, 'body': None}
        self.illicit = illicit
    def save(self):
        return copy.deepcopy(self.state)
    def intervene(self, *, edges, action):
        self.state['core']['silenced_edges'] = sorted(edges) if action == 'silence' else []
        if self.illicit:
            self.state['core']['weight'] += .01


def test_mask_whitelist_and_zero_time_reversal():
    selection = {'groups': {k: [{'edge': [1, 3]}, {'edge': [2, 3]}] for k in ('target', 'matched')}}
    for arm in m1.ARMS:
        s = FakeSubject()
        report = m1.apply_mask(s, selection, arm)
        assert s.state['core']['time_us'] == '18000000'
        if arm in ('intact', 'sham', 'restored'):
            assert report['before_sha256'] == report['after_sha256']
    with pytest.raises(RuntimeError, match='non-mask'):
        m1.apply_mask(FakeSubject(illicit=True), selection, 'target')


def test_matching_uses_preprobe_activity_and_rejects_residual():
    channels = dict(zip('XYZWABKN', range(8)))
    nodes = [{'id': i, 'channel': i, 'activation': 0.} for i in range(8)]
    edges = [{'source': a, 'target': b, 'weight': .1} for group in ((0, 1, 4), (2, 3, 5))
             for a in group for b in group if a != b]
    stats = {'n': 10, 'sums': dict.fromkeys(channels, 1.)}
    result = m1.select_edges({'nodes': nodes, 'edges': edges}, channels, 0, stats)
    assert result['matching_passed']
    stats['sums']['A'] = 5.
    result = m1.select_edges({'nodes': nodes, 'edges': edges}, channels, 0, stats)
    assert not result['matching_passed']
    assert abs(result['residuals']['teaching_mean_differences'][1]-.4) < 1e-12


def test_lineage_diff_discloses_clock_and_mapping_changes():
    a = {'core': {'time_us': '18000000', 'silenced_edges': []}, 'mappings': {'A': 1}}
    b = copy.deepcopy(a)
    b['core']['time_us'] = '18000001'
    b['mappings']['A'] = 2
    assert m1.differences(a, b) == ['core.time_us', 'mappings.A']
