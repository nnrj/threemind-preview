import pilot_m2_phase as p
import pytest


def fixture():
    channels={s:i for i,s in enumerate('ABXY')}
    graph={'nodes':[{'id':i,'channel':i} for i in range(4)],
           'edges':[{'source':i,'target':0,'weight':1.} for i in (2,3)]}
    cfg={'activation_tau':1.,'activation_floor':.004,'propagation_interval_us':100000,
         'delay_us':10000,'propagation_phase':'aligned','direct_gain':1.,
         'propagation_rate':1.,'stp_utilization':1.}
    return graph,channels,cfg


def test_exact_boundary_then_crossing():
    g,c,cfg=fixture()
    at=p.forecast(g,c,cfg,'p99-d1','summed')
    after=p.forecast(g,c,cfg,'p99-d2','summed')
    assert at['first_cycle_sources']==['X','Y']
    assert after['first_cycle_sources']==['X']
    assert at['response_at_110ms']['phase-aware']-after['response_at_110ms']['phase-aware']==pytest.approx(.05)
    assert after['response_at_110ms']['all-same-cycle']>after['response_at_110ms']['phase-aware']


def test_route_gate_precedes_summation():
    g,c,cfg=fixture(); cfg['activation_floor']=.06
    # Two individually .05-or-less routes may not rescue each other.
    assert p.forecast(g,c,cfg,'p99-d1','summed')['response_at_110ms']['phase-aware']==0


def test_registered_sources_and_bounded_doses():
    assert len(p.parents())==16
    assert len({c['seed'] for c in p.parents()})==8
    assert len(p.parents())*len(p.CUES)*len(p.ARMS)==672
    assert {c['delay'] for c in p.parents()}=={23}
    _,c,_=fixture()
    for cue in p.CUES:
        events=p.probe_events(c,40_000_000,cue)
        if cue=='none':
            assert events==[]
            continue
        stimuli=[p.m.Stimulus.from_dict(e['stimulus']) for e in events]
        assert sum(s.intensity*sum(v for _,v in s.channels) for s in stimuli)==1
        assert {k for s in stimuli for k,_ in s.channels}=={c['X'],c['Y']}
        assert int(stimuli[-1].time_us)==40_000_000+sum(p.CUES[cue])*1000


def test_wrong_clock_configuration_rejected():
    g,c,cfg=fixture(); cfg['propagation_phase']='asynchronous'
    with pytest.raises(ValueError):p.forecast(g,c,cfg,'p99-d1','summed')


def test_none_and_undefined_material():
    g,c,cfg=fixture()
    assert p.forecast(g,c,cfg,'none','summed')['response_at_110ms']=={'phase-aware':0.,'all-same-cycle':0.}
    with pytest.raises(ValueError):p.probe_events(c,0,'unregistered')
