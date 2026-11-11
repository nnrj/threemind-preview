import numpy as np
import pytest
import torch
from lab.tools.centered_recognition import CenteredWorld,CenteredSystem
from lab.tools.centered_recognition import PersonalVocabulary


def test_one_physical_object_without_answer_leakage_and_restore():
    w=CenteredWorld();w.present(2,3);ob=w.observe();actual=w.stimulus(ob)
    assert len(ob['items'])==1 and len(ob['values'])==len(w.channels)
    assert np.max(np.abs(w.project(w.positions[0])))<1e-8
    ob.update(answer='anything',items=[(0,0)],question='made up')
    assert w.stimulus(ob)==actual
    for _ in range(4):w.advance_physics()
    r=CenteredWorld.restore(w.state());assert r.state()==w.state()
    assert r.stimulus(r.observe())==w.stimulus(w.observe())
    with pytest.raises(ValueError):w.advance_physics((1.,0.))


def test_whole_recognizer_next_teacher_update_is_preserved(tmp_path):
    torch.set_num_threads(2);a=CenteredSystem(seed=639)
    a.session.world.present(0,0)
    for _ in range(3):a.step(label=4)
    a.save(tmp_path/'whole');b=CenteredSystem.restore(tmp_path/'whole')
    assert np.array_equal(a.words.predict(a.window()),b.words.predict(b.window()))
    a.step(label=4);b.step(label=4)
    assert a.session.snapshot()==b.session.snapshot()
    assert a.words.steps==b.words.steps
    assert all(torch.equal(v,b.words.state_dict()[k]) for k,v in a.words.state_dict().items())
    assert a.words.predict(a.window()*0) is None


def test_question_calibration_keeps_optimizer_and_sampling_on_restore(tmp_path):
    torch.set_num_threads(2)
    a=PersonalVocabulary([1,2,3,4],[1,2,3,4],'calibration',seed=640)
    x=np.random.default_rng(1).normal(size=(3,16,16)).astype('float32');y=np.array([0,1,2])
    optimizer=a.optimizer;a.teach(x[0],0);prior=a.steps
    a.readout_profile='whole-question'
    a.calibrate(x,y,updates=3)
    assert a.optimizer is optimizer and a.steps==prior+3
    a.save(tmp_path/'words');b=PersonalVocabulary.restore(tmp_path/'words')
    assert b.readout_profile=='whole-question'
    a.calibrate(x,y,updates=1);b.calibrate(x,y,updates=1)
    assert all(torch.equal(v,b.state_dict()[k]) for k,v in a.state_dict().items())
