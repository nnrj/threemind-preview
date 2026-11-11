"""Injected guard faults, boundary preservation and interpretable conclusions."""
import copy
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import pytest
import m4_balanced_driver as d
import m4_balanced_rig as rig
from m4_balanced_analyze import evaluate


def folder():
    w=(d.m.ROOT/'.work'/('m4-balanced-safety-'+uuid4().hex)).resolve()
    w.mkdir();return w


@pytest.mark.parametrize('fault,private,elapsed,reason',[
    (RuntimeError('resource probe failed'),0,0,'resource probe failed'),
    (None,3*2**30+1,0,'3GiB'),
    (None,0,8*3600+1,'eight-hour')])
def test_guard_only_requests_stop(fault,private,elapsed,reason):
    w=folder();g=d.StudyGuard(w)
    proc=SimpleNamespace(memory_info=lambda:SimpleNamespace(private=private))
    with patch.object(d.m,'resource_check',side_effect=fault,return_value={'available_bytes':{'commit':9*2**30}}), \
         patch.object(d.psutil,'Process',return_value=proc), \
         patch.object(d.time,'monotonic',return_value=g.started+elapsed):
        g.watch()
    assert reason in d.m.read(w/'STOP')['reason']
    assert {p.name for p in w.iterdir()}=={'STOP'}
    original=(w/'STOP').read_bytes()
    with patch.object(d.m,'resource_check',side_effect=RuntimeError('second fault')):g.watch()
    assert (w/'STOP').read_bytes()==original


def test_stop_cannot_start_a_unit_or_bypass_a_dead_guard():
    w=folder();alive=SimpleNamespace(thread=SimpleNamespace(is_alive=lambda:True))
    u=rig.Unit(w,0,alive,lambda value:None)
    d.m.original(w/'STOP',{'reason':'user pause'})
    with pytest.raises(rig.BoundaryPause):u.begin('pre')
    assert not (w/'in-flight.json').exists()
    v=rig.Unit(folder(),0,SimpleNamespace(thread=SimpleNamespace(is_alive=lambda:False)),lambda value:None)
    with pytest.raises(RuntimeError,match='guard absent'):v.begin('pre')
    assert not (v.work/'in-flight.json').exists()


def test_complete_state_precedes_pause_and_preserves_evidence():
    w=folder();events=[]
    def save(path):
        d.m.original(path/'complete.json',{'canonical_sha256':'fixture-only','time_us':123})
        events.append('saved')
    u=rig.Unit(w,0,SimpleNamespace(),lambda value:events.append('recorded'))
    u.a=SimpleNamespace(save=save,session=SimpleNamespace(engine=SimpleNamespace(time_us=123)),
                        motor=SimpleNamespace(committed_updates=2),words=SimpleNamespace(committed_updates=0))
    d.m.original(w/'in-flight.json',{'unit':0,'stage':'fixture'})
    d.m.original(w/'STOP',{'reason':'test pressure after a complete stage'})
    with pytest.raises(rig.BoundaryPause):u.end('fixture')
    assert events==['saved','recorded'] and not (w/'in-flight.json').exists()
    assert d.m.read(w/'current-boundary.json')['canonical_sha256']=='fixture-only'
    assert (w/'STOP').exists() and (u.folder/'states/fixture/complete.json').exists()


def test_goals_close_without_turning_missing_baselines_into_null_evidence():
    rows=[{'origin':i,'valid':True,'causal_eligible':True,
           **{k:{'qualified':True} for k in ('G1','G2','G3')}} for i in range(8)]
    assert evaluate(rows)['verdict']=='PASS'
    for i in range(3):rows[i]['causal_eligible']=False;rows[i]['G3']['qualified']=False
    a=evaluate(rows)
    assert a['goals']['G1']['verdict']=='PASS' and a['goals']['G2']['verdict']=='PASS'
    assert a['goals']['G3']['verdict']=='INSUFFICIENT_VALID_BASELINES' and a['verdict']=='TARGET_NOT_MET'
    for r in rows:r['causal_eligible']=True
    assert evaluate(rows)['goals']['G3']['verdict']=='FAIL'
    rows[0]['origin']=1
    with pytest.raises(AssertionError):evaluate(rows)
