import math

import pilot_m2_timing as t
import pytest


def test_sources_and_nested_count():
    p=t.parents()
    assert len(p)==16
    assert len({c['seed'] for c in p})==8
    assert {c['seed'] for c in p}.isdisjoint({c['seed'] for c in t.f.parents()})
    assert len(p)*len(t.CUES)*len(t.ARMS)==288


def test_timing_and_equal_dose_without_answer_channels():
    channels={s:i for i,s in enumerate('ABXYZWKN')}
    for cue,lag in t.CUES.items():
        events=t.probe_events(channels,32_000_000,cue)
        if not cue.startswith('XY-'):
            continue
        assert len(events)==(1 if lag==0 else 2)
        assert int(events[-1]['stimulus']['time_us'])==32_000_000+lag*1000
        stimuli=[t.m.Stimulus.from_dict(e['stimulus']) for e in events]
        assert sum(s.intensity*sum(v for _,v in s.channels) for s in stimuli)==1
        assert {c for s in stimuli for c,_ in s.channels}=={channels['X'],channels['Y']}


def test_clipped_decay_uses_floor_and_preserves_sign():
    assert t.decay_clipped(.004,1,.3,.004)==0
    assert t.decay_clipped(-.01,.01,.3,.004)==pytest.approx(-.01*math.exp(-.01/.3))


def test_forecast_has_no_outcome_or_case_argument(monkeypatch):
    # Independent synthetic arrivals distinguish simultaneous normalization from lagged accumulation.
    def mock(_graph,_channels,_cfg,cue,mix):
        value=.008 if cue=='XY-per' and mix==0 else .0041
        return {'response_at_110ms':{'receiver':value}}
    monkeypatch.setattr(t.f,'forecast',mock)
    cfg={'activation_tau':.3,'activation_floor':.004}
    assert t.forecast({}, {}, cfg,'XY-0','normalized')['at_second_arrival']==.0041
    assert t.forecast({}, {}, cfg,'XY-1','normalized')['at_second_arrival']>.008
    assert t.forecast({}, {}, cfg,'XY-25','normalized')['at_second_arrival']==.0041
    assert t.forecast({}, {}, cfg,'none','normalized')['at_second_arrival']==0


def test_unregistered_cue_rejected():
    with pytest.raises(ValueError):t.probe_events({},0,'XY-2')
