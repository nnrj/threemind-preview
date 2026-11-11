import numpy as np
from lab.tools.retinal_choice import RetinalChoice


def test_regular_retina_uses_no_object_inventory_and_roundtrips(tmp_path):
    visual=list(range(64))
    model=RetinalChoice([*visual,91,92],visual,4,seed=7)
    x=np.random.default_rng(2).uniform(0,.1,(2,3,264)).astype('float32')
    before=model.predict(x)
    assert before.shape==(2,16)
    model.save(tmp_path/'reader')
    restored,layout=RetinalChoice.restore(tmp_path/'reader')
    assert np.allclose(before,restored.predict(x))
    assert layout.width==264


def test_training_feedback_does_not_modify_observed_values():
    visual=list(range(64));model=RetinalChoice([*visual,91],visual,4,seed=7)
    x=np.random.default_rng(9).uniform(0,.1,(2,3,260)).astype('float32');saved=x.copy()
    model.fit(x,[3,10],steps=2,batch_size=1)
    assert np.array_equal(x,saved)
