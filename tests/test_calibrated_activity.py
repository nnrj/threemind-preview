import numpy as np
import torch
from lab.tools.activity_controller import ActivityController
from lab.tools.calibrated_activity import CalibratedActivity


def test_calibration_restores_original_architecture_and_learning(tmp_path):
    torch.set_num_threads(2)
    head=CalibratedActivity((1,2,3),('a','b'),'individual',seed=223)
    old=ActivityController(12,2,seed=223)
    x=np.random.default_rng(71).normal(size=(8,8,12)).astype('float32');y=np.arange(8)%2
    np.testing.assert_array_equal(head.predict(x),old.predict(x))
    head.calibrate(x,y,steps=8);head.save(tmp_path/'head')
    restored=CalibratedActivity.restore(tmp_path/'head')
    assert restored.identity=='individual'
    first=head.calibrate(x,y,steps=8);second=restored.calibrate(x,y,steps=8)
    assert first==second
    np.testing.assert_array_equal(head.predict(x),restored.predict(x))


def test_fixed_recognition_round_trip_retains_next_response(tmp_path):
    from lab.tools.recognition_session import RecognitionSystem
    a=RecognitionSystem()
    for _ in range(3):a.session.tick()
    a.save(tmp_path/'whole');b=RecognitionSystem.restore(tmp_path/'whole')
    left=a.session.tick();right=b.session.tick()
    assert left['stimulus']==right['stimulus']
    assert left['activity']==right['activity']
    np.testing.assert_array_equal(a.words.predict(np.zeros((1,8,a.words.features),'float32')),
                                  b.words.predict(np.zeros((1,8,b.words.features),'float32')))


def test_last_state_calibration_keeps_every_update_and_rng(tmp_path):
    torch.set_num_threads(2)
    x=np.random.default_rng(17).normal(size=(9,8,12)).astype('float32');y=np.arange(9)%2
    a=CalibratedActivity((1,2,3),('a','b'),'continuous',seed=223)
    b=CalibratedActivity((1,2,3),('a','b'),'continuous',seed=223)
    a.continue_calibration(x,y,steps=13)
    b.continue_calibration(x,y,steps=5);b.save(tmp_path/'boundary')
    b=CalibratedActivity.restore(tmp_path/'boundary')
    b.continue_calibration(x,y,steps=8)
    assert a.committed_updates==a.computed_updates==b.committed_updates==b.computed_updates==13
    np.testing.assert_array_equal(a.predict(x),b.predict(x))
    assert torch.equal(a.learning_rng,b.learning_rng)
    for key,value in a.optimizer.state_dict()['state'].items():
        for field,tensor in value.items():
            assert torch.equal(tensor,b.optimizer.state_dict()['state'][key][field])


def test_last_state_calibration_pause_preserves_completed_updates():
    torch.set_num_threads(2)
    x=np.zeros((2,8,12),'float32');y=np.array([0,1])
    a=CalibratedActivity((1,2,3),('a','b'),'continuous',seed=223)
    b=CalibratedActivity((1,2,3),('a','b'),'continuous',seed=223)
    import pytest
    def stop():
        if a.computed_updates==3: raise RuntimeError('boundary pause')
    with pytest.raises(RuntimeError,match='boundary pause'):
        a.continue_calibration(x,y,steps=10,check=stop)
    b.continue_calibration(x,y,steps=3)
    assert a.committed_updates==a.computed_updates==3
    np.testing.assert_array_equal(a.predict(x),b.predict(x))
    assert torch.equal(a.learning_rng,b.learning_rng)
