import numpy as np
import pytest
import torch
from lab.tools.activity_controller import ActivityController


def test_selected_model_reports_actual_held_out_error():
    torch.set_num_threads(1)
    rng=np.random.default_rng(8);x=rng.normal(size=(16,4,3)).astype('float32')
    y=np.tanh(x[:,-1,:2]);vx=x[:4]*.8;vy=np.tanh(vx[:,-1,:2])
    head=ActivityController(3,2,regression=True,seed=4)
    result=head.fit(x,y,steps=51,validation=(vx,vy))
    assert result['training_count']==16 and result['validation_count']==4
    assert result['loss']==pytest.approx(float(np.mean((head.predict(vx)-vy)**2)),abs=1e-6)
    assert result['training_loss']==pytest.approx(float(np.mean((head.predict(x)-y)**2)),abs=1e-6)


def test_invalid_validation_does_not_silently_become_training_selection():
    head=ActivityController(3,2,regression=True)
    with pytest.raises(ValueError,match='held-out'):
        head.fit(np.zeros((4,4,3)),np.zeros((4,2)),steps=1,
                 validation=(np.empty((0,4,3)),np.empty((0,2))))
