"""Synthetic protocol and isolation checks; no scientific subject is advanced."""
import copy
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_m2_fusion as f


def test_origins_intensities_and_causal_denominators():
    parents = f.parents()
    assert len(parents) == 16
    assert len({p['origin'] for p in parents}) == 8
    assert not ({p['seed'] for p in parents} & {p['seed'] for p in f.m.cases()})
    assert len(parents)*len(f.CUES)*len(f.ARMS) == 448
    assert sorted({p['teaching_intensity'] for p in parents}) == [.25, .35, .45, .55]
    assert all(p['delay'] == 15 and p['mode'] == 'S' for p in parents)


def test_current_cues_have_fixed_declared_doses_and_no_answer():
    channels, _ = f.m.mapping(917100)
    expected = {'none': 0, 'X-low': .25, 'X': .5, 'Y': .5, 'XY-total': .5, 'XY-per': 1., 'X-total': 1.}
    for cue, entries in f.CUES.items():
        assert sum(v for _, v in entries) == expected[cue]
        assert all(s not in 'AB' for s, _ in entries)
        assert all(channels[s] != channels['A'] and channels[s] != channels['B'] for s, _ in entries)
    for p in f.parents():
        events = f.schedule(p, channels)
        taught = [x for x in events if x['kind'] == 'teaching']
        assert len(taught) == 32 and all(x['stimulus']['intensity'] == p['teaching_intensity'] for x in taught)
        assert not any(x['kind'] == 'probe' for x in events)


def test_predictor_rejects_total_dose_rescue_below_per_edge_floor():
    graph = {'nodes': [{'id': i, 'channel': i} for i in range(4)],
             'edges': [{'source': 2, 'target': 0, 'weight': .012}, {'source': 3, 'target': 0, 'weight': .012}]}
    cfg = {'direct_gain': 1., 'activation_tau': 1e30, 'propagation_rate': 10., 'stp_utilization': 1., 'activation_floor': .004}
    channels = {'A': 0, 'B': 1, 'X': 2, 'Y': 3}
    # Each weak arrival is .003: jointly above .004 only if illegally summed before transmission.
    for mix in (0., 1.):
        prediction = f.forecast(graph, channels, cfg, 'XY-total', mix)['response_at_110ms']
        assert prediction['receiver'] == 0.
        assert prediction['total-dose'] == pytest.approx(.006)
    assert f.forecast(graph, channels, cfg, 'XY-per', 0.)['response_at_110ms']['receiver'] == pytest.approx(.012)
    assert f.forecast(graph, channels, cfg, 'XY-per', 1.)['response_at_110ms']['receiver'] == pytest.approx(.006)


@dataclass
class Config:
    context_mix: float = 1.


class Engine:
    def __init__(self):
        self.time_us = 32_000_000
        self.config = Config()
    def reconfigure(self, config):
        self.config = config


class FakeSubject:
    def __init__(self, case, saved=None):
        self.case = case
        self.engine = Engine()
        self.probe_start = 32_000_000
        self.channels = {'X': 10, 'Y': 11}
        self.events = saved['environment']['schedule'] if saved else [{'kind': 'past'}, {'kind': 'future'}]
        self.cursor = 1
        self.rows = saved['recent_activity'] if saved else [{'past': True}]
        self.branch = None
    def save(self):
        return {'case': self.case, 'core': {'config': {'context_mix': self.engine.config.context_mix}},
                'environment': {'schedule': self.events}, 'recent_activity': self.rows, 'branch': self.branch}


def test_fork_does_not_alias_parent_activity_or_past_inputs(monkeypatch):
    parent = FakeSubject({'history': 0})
    before = copy.deepcopy(parent.save())
    monkeypatch.setattr(f, 'Subject', FakeSubject)
    child, audit = f.fork(parent, 'XY-per', 'summed')
    child.rows.append({'new': True})
    child.events[0]['new-field'] = 'child-only'
    assert parent.save() == before
    assert audit['parent_time_us'] == 32_000_000
    assert child.engine.config.context_mix == 0.


def test_declared_reversal_and_double_sham(monkeypatch):
    monkeypatch.setattr(f, 'Subject', FakeSubject)
    parent = FakeSubject({'history': 0})
    a, _ = f.fork(parent, 'X', 'restored')
    b, _ = f.fork(parent, 'X', 'double-sham')
    aa, bb = a.save(), b.save()
    aa.pop('branch'); bb.pop('branch')
    assert aa == bb


def test_primary_110ms_is_not_posthoc_peak_or_late_score():
    rows = [{'time_us': 32_000_000+t*1000, 'response': .006 if t == 110 else .008 if t == 200 else 0.}
            for t in range(1, 2001)]
    saved = {'case': {'delay': 15, 'history': 0}, 'recent_activity': rows, 'branch': None}
    result = f.endpoint(saved, {'declared': 'before-cue'})
    assert result['response_110ms'] == .006
    assert result['peak_abs'] == .008
    assert result['late_mean'] == 0.
    assert result['grid_frames'] == 2000
