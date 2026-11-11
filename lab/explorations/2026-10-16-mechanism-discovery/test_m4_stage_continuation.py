"""Continuation scheduling and unchanged per-host/system stop behavior."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import pytest
import m4_continuation_plan as p
import m4_continuation_host as h


def test_c111_continues_exactly_the_next_unexecuted_block():
    done=list(p.ORDINARY[:p.ORDINARY.index('teach-0-7')+1])
    assert p.decide(0,done)=={'origin':0,'stage':'teach-1-0','parent':'teach-0-7'}


def test_complete_ordinary_course_then_selection_before_confirmation():
    for k,label in enumerate(p.ORDINARY):
        step=p.decide(2,p.ORDINARY[:k])
        if label=='confirmation':
            assert step['stage']=='selection' and step['parent']=='development'
            step=p.decide(2,p.ORDINARY[:k],selection=True)
        assert step['stage']==label
        assert step['parent']==(None if k==0 else p.ORDINARY[k-1])
    assert p.decide(2,p.ORDINARY,True)['stage']=='causal-preparation'


def test_causal_restorations_only_use_registered_reference():
    for k,label in enumerate(p.CAUSAL):
        step=p.decide(0,p.ORDINARY+p.CAUSAL[:k],True,{'eligible':True})
        arm,part=label.rsplit('-',1)
        assert step['stage']==label and step['parent']==('confirmation' if part=='initial' else arm+'-initial')
    assert p.decide(0,p.ORDINARY+p.CAUSAL,True,{'eligible':True})['stage']=='finish'
    assert p.decide(0,p.ORDINARY+p.CAUSAL,True,{'eligible':True},True) is None
    assert p.decide(0,p.ORDINARY,True,{'eligible':False})['stage']=='finish'
    assert p.decide(0,p.ORDINARY,True,{'eligible':False},True) is None


@pytest.mark.parametrize('done,selection,decision,result',[
    (('birth','pre'),False,None,False),
    (('birth','birth'),False,None,False),
    (('birth','unknown'),False,None,False),
    (('birth',),True,None,False),
    (('birth',),False,{'eligible':True},False),
    (p.ORDINARY,False,None,False),
    (p.ORDINARY,True,{'eligible':True},True),
    (p.ORDINARY+('eye-initial',),True,{'eligible':True},False),
    (p.ORDINARY+('sham-initial',),True,{'eligible':False},False),
])
def test_incomplete_or_reordered_state_is_never_replayed(done,selection,decision,result):
    with pytest.raises(ValueError):p.decide(0,done,selection,decision,result)


@pytest.mark.parametrize('private,elapsed,fault,reason',[
    (3*2**30+1,0,None,'3GiB'),(0,101,None,'eight-hour'),(0,0,RuntimeError('probe failure'),'probe failure')])
def test_resource_guard_preserves_original_stop_and_no_inflight_mutation(private,elapsed,fault,reason):
    folder=(h.m.ROOT/'.work'/('m4-continuation-guard-'+uuid4().hex)).resolve();folder.mkdir()
    g=h.Guard(folder,folder,private_gib=3,remaining_seconds=100)
    with patch.object(h.m,'resource_check',side_effect=fault,return_value={'available_bytes':{'commit':9*2**30}}), \
         patch.object(h.psutil,'Process',return_value=SimpleNamespace(memory_info=lambda:SimpleNamespace(private=private))), \
         patch.object(h.time,'monotonic',return_value=g.started+elapsed):g.watch()
    original=(folder/'STOP').read_bytes()
    assert reason in h.m.read(folder/'STOP')['reason'] and not (folder/'in-flight.json').exists()
    with patch.object(h.m,'resource_check',side_effect=RuntimeError('later failure')):g.watch()
    assert original==(folder/'STOP').read_bytes()


def test_causal_stage_keeps_results_for_frozen_analysis():
    import m4_stage_continuation as stages
    folder=(h.m.ROOT/'.work'/('m4-continuation-causal-'+uuid4().hex)).resolve();folder.mkdir()
    engine=SimpleNamespace(time_us=255000000)
    a=SimpleNamespace(branch={'name':'sham'},session=SimpleNamespace(engine=engine),
                      motor=SimpleNamespace(committed_updates=1920))
    tasks=[{'id':'confirmation-0'},{'id':'confirmation-1'}]
    ended=[]
    u=SimpleNamespace(a=a,folder=folder,bank={'confirmation':tasks},begin=lambda label:None,
                      end=lambda label,extra:ended.append((label,extra)))
    def trial(subject,task):
        engine.time_us+=18000000
        return [{'task':task['id']}],None,{'task':task['id'],'correct':False},None
    with patch.object(stages.rig.course,'trial',side_effect=trial), \
         patch.object(stages.rig,'equivalent_sha',return_value='fixture'):
        stages.causal_final(u,'sham')
    assert [h.m.read(folder/'causal/sham'/task['id']/'result.json') for task in tasks]==[
        {'task':task['id'],'correct':False} for task in tasks]
    assert ended[0][0]=='sham-final' and len(ended[0][1]['trajectory_hashes'])==2
