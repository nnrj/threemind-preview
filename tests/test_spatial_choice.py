import numpy as np
from lab.tools.spatial_choice import SpatialChoice


def test_permuting_physical_fields_permutates_choices_without_new_labels():
    # Native field IDs are deliberately not contiguous/sorted.
    visual=[15,9,24,3,17,8,11,5]
    model=SpatialChoice([*visual,31,32],visual,seed=1)
    x=np.random.default_rng(4).normal(size=(3,8,40)).astype('float32')
    before=model.predict(x);swapped=x.copy();order=[2,0,3,1]
    for dst,src in enumerate(order):
        for a,b in zip(visual[dst*2:dst*2+2],visual[src*2:src*2+2]):
            ia,ib=model.layout.index[a]*4,model.layout.index[b]*4
            swapped[:,:,ia:ia+4]=x[:,:,ib:ib+4]
    assert np.allclose(model.predict(swapped),before[:,order],atol=1e-6)
