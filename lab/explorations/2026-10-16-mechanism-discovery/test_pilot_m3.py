import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_m3 as p


def fixture(kind):
    case = {'id': 'synthetic-apparatus', 'kind': kind, 'seed': 716901,
            'history': 0, 'mode': 'H', 'delay': 1, 'cue': 'strong'}
    channels, _ = p.m.mapping(case['seed'])
    return case, {'mappings': channels, 'environment': {'schedule': p.m.schedule(case, channels)}}


@pytest.mark.parametrize('kind', p.KINDS)
def test_observation_and_serialized_resume_preserve_complete_baseline(kind):
    case, source = fixture(kind)
    plain, watched = p.Replay(case, source), p.Replay(case, source)
    plain.advance(20_000_000)
    watched.advance(10_000_000, frequent=True)
    whole = json.loads(p.m.encoded(watched.save()))
    watched = p.Replay(case, source, whole)
    watched.advance(20_000_000, frequent=True)
    assert p.m.digest(plain.save()) == p.m.digest(watched.save())
    assert watched.cursor == len(source['environment']['schedule'])
    # Hebbian coactivity also learns the declared simultaneous K/N final input.
    assert watched.model.updates == {'reactive': 0, 'finite-state': 32,
                                     'hebbian': 33, 'fixed-rnn-reader': 32}[kind]
    assert len(watched.rows) == 41


def test_forward_model_has_no_history_phase_or_answer_input_and_probe_lattice_matches_source():
    assert list(inspect.signature(p.Controller.step).parameters) == ['self', 'x']
    case, source = fixture('finite-state')
    replay = p.Replay(case, source)
    replay.advance(18_000_000)
    next_event = source['environment']['schedule'][replay.cursor]
    assert next_event['kind'] == 'probe'
    replay.advance(18_050_000)
    assert replay.rows[-1]['delivered_event_indices']
    before = replay.model.save()
    altered = case | {'id': 'unrelated-metadata', 'history': 1}
    duplicate = p.Replay(altered, source)
    duplicate.advance(18_050_000)
    assert duplicate.model.save() == before


def test_future_inputs_cannot_change_past_state():
    case, source = fixture('fixed-rnn-reader')
    altered = json.loads(p.m.encoded(source))
    altered['environment']['schedule'][-1]['stimulus']['intensity'] = 0.9
    a, b = p.Replay(case, source), p.Replay(case, altered)
    a.advance(10_000_000)
    b.advance(10_000_000)
    assert a.model.save() == b.model.save()


def test_reactive_impulse_does_not_learn_and_finite_memory_is_ternary():
    reactive = p.Controller('reactive', 1, 0, 1)
    finite = p.Controller('finite-state', 1, 0, 1)
    for sign in [1, -1]:
        x = np.zeros(8)
        x[0 if sign == 1 else 1], x[2] = .4, .4
        reactive.step(x)
        finite.step(x)
    assert reactive.updates == 0
    assert set(finite.memory).issubset({-1., 0., 1.})
    assert finite.memory[2] == -1
