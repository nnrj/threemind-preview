import numpy as np
import torch
import pytest
from lab.tools.developmental_motor import DevelopmentalMotor
from lab.tools.rehearsal_memory import RehearsalMemory


@pytest.mark.parametrize('policy',RehearsalMemory.MODES)
def test_training_policy_preserves_weights_and_resumes_next_update(tmp_path,policy):
    torch.set_num_threads(2)
    a=DevelopmentalMotor([1,2,3,4,5],[1,2,3,4],identity='same',seed=62,capacity=16)
    rng=np.random.default_rng(9);x=rng.normal(size=(16,20)).astype('float32')
    for i in range(20):a.teach(x+i/100,np.array([.1,-.2,i/40,-.3],dtype='float32'))
    before={k:v.clone() for k,v in a.state_dict().items()};steps=a.steps
    a.configure_rehearsal(policy)
    assert steps==a.steps and all(torch.equal(before[k],v) for k,v in a.state_dict().items())
    for i in range(3):a.teach(x,np.array([.3,.1,-.5,.2],dtype='float32'))
    a.save(tmp_path/'motor');b=DevelopmentalMotor.restore(tmp_path/'motor')
    assert a.teach(x,np.zeros(4,dtype='float32'))==b.teach(x,np.zeros(4,dtype='float32'))
    assert len(a.replay_x)==len(b.replay_x)==16
    assert a.rehearsal.state()==b.rehearsal.state()
    assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())


def test_representative_anchors_survive_new_demonstrations():
    r=RehearsalMemory('representative',16,2)
    x,y=r.initialize([np.array([i]) for i in range(16)],[np.array([i]) for i in range(16)],correct=np.ones(16,bool))
    old=[v.copy() for v in x[:8]]
    for i in range(30):r.append(x,y,np.array([i+100]),np.array([0]))
    assert all(np.array_equal(a,b) for a,b in zip(old,x[:8]))
    idx=r.indices(16,16,np.random.default_rng(3))
    assert sum(idx<8)==8 and len(x)==16


def test_explicit_recent_policy_matches_legacy_fifo(tmp_path):
    torch.set_num_threads(2)
    a=DevelopmentalMotor([1,2,3,4],[1,2,3,4],identity='legacy',seed=17,capacity=16)
    x=np.random.default_rng(2).normal(size=(16,16)).astype('float32');y=np.zeros(4,dtype='float32')
    a.teach(x,y);a.save(tmp_path/'legacy');b=DevelopmentalMotor.restore(tmp_path/'legacy')
    b.configure_rehearsal('recent')
    for _ in range(17):assert a.teach(x,y)==b.teach(x,y)
    assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())
