"""Safety/material tests use fake state; real engine acceptance is separately recorded."""
import importlib.util
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pilot_m2', HERE/'pilot_m2.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


@pytest.fixture
def tmp_path():
    p = m.ROOT/'.work/mechanism-preparation-20261016'/('pilot-fixture-'+uuid4().hex)
    p.mkdir(parents=True)
    return p


def test_independent_delay_cohorts_and_nested_arms():
    rows = m.cases()
    assert len(rows) == len({r['id'] for r in rows}) == 640
    seeds = [{r['seed'] for r in rows if r['delay'] == d} for d in m.DELAY]
    assert all(len(s) == 8 for s in seeds)
    assert len(set.union(*seeds)) == 32
    assert all(sum(r['seed'] == s for r in rows) == 20 for s in set.union(*seeds))
    assert 716001 not in set.union(*seeds)


@pytest.mark.parametrize('cue', m.CUES)
def test_opposite_histories_identical_probe_payloads(cue):
    case = m.cases()[0] | {'cue': cue}
    channels, _ = m.mapping(case['seed'])
    a = m.schedule(case, channels)
    b = m.schedule(case | {'history': 1}, channels)
    assert [r for r in a if r['kind'] != 'teaching'] == [r for r in b if r['kind'] != 'teaching']
    probe = [r['stimulus'] for r in a if r['kind'] == 'probe']
    assert all(c not in (channels['A'], channels['B']) for p in probe for c, _ in p['channels'])


def test_dose_matching_and_teaching_count():
    case = m.cases()[0]
    channels, _ = m.mapping(case['seed'])
    doses = {}
    for cue in m.CUES:
        rows = m.schedule(case | {'cue': cue}, channels)
        assert len([r for r in rows if r['kind'] == 'teaching']) == 32
        doses[cue] = sum(r['stimulus']['intensity']*sum(v for _, v in r['stimulus']['channels'])
                         for r in rows if r['kind'] == 'probe')
        assert all(set(r['stimulus']) == {'time_us', 'channels', 'intensity'} for r in rows)
    assert doses == {'none': 0, 'weak': .4, 'strong': .8, 'joint-total': .4, 'joint-per': .8}


def test_reader_depends_on_activity_not_node_identity_or_order():
    channels, _ = m.mapping(716001)
    nodes = [{'id': 101, 'channel': channels['A'], 'activation': .7},
             {'id': 2, 'channel': channels['B'], 'activation': .2},
             {'id': 8, 'channel': channels['X'], 'activation': 900}]
    assert m.project(nodes, channels) == m.project(nodes[::-1], channels)
    assert m.project(nodes, channels)['activation'] == [.7, .2]


def test_originals_cannot_be_replaced(tmp_path):
    path = tmp_path/'x.json'
    m.original(path, {'a': 1})
    m.original(path, {'a': 1})
    with pytest.raises(RuntimeError, match='original differs'):
        m.original(path, {'a': 2})
    assert json.loads(path.read_bytes()) == {'a': 1}


def test_subject_does_not_inject_probe_before_preprobe_boundary():
    class Engine:
        time_us = 0
        life = 'alive'
        def __init__(self):
            self.sent = []
        def inject(self, stimulus):
            assert stimulus.time_us >= self.time_us
            self.sent.append(stimulus.to_dict())
        def advance_to(self, t):
            assert t >= self.time_us
            self.time_us = t
        def observation_nodes(self):
            return []
    case = m.cases()[0] | {'cue': 'weak'}
    s = object.__new__(m.Subject)
    s.case, s.engine = case, Engine()
    s.channels, s.rng = m.mapping(case['seed'])
    s.events, s.cursor, s.rows, s.actuator = m.schedule(case, s.channels), 0, [], None
    s.advance(s.probe_start)
    assert s.events[s.cursor]['kind'] == 'probe'
    assert not any(p['time_us'] == str(s.probe_start) and p['intensity'] == .4 for p in s.engine.sent)
    s.advance(s.probe_start+2_000_000)
    assert s.cursor == len(s.events)
    assert len(s.rows) == 41
    assert len([p for p in s.engine.sent if p['time_us'] == str(s.probe_start) and p['intensity'] == .4]) == 1
    with pytest.raises(ValueError, match='no reversal'):
        s.advance(0)
