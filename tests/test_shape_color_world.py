import numpy as np
import pytest

from lab.tools.shape_color_world import ShapeColorWorld,Pointer
from lab.tools.activity_controller import ActivityLayout,ActivityController


def test_no_semantic_labels_in_input_and_recovery():
    w=ShapeColorWorld();w.marker=[.3,-.4]
    obs=w.observe();stim=w.stimulus(obs)
    before=stim.to_dict()
    obs.update(items=[['fake','label']]*4,teacher_marker=['answer'])
    assert w.stimulus(obs).to_dict()==before
    restored=ShapeColorWorld.restore(w.state())
    assert restored.stimulus(restored.observe()).to_dict()==before
    assert len(w.channels)==272 and len(set(w.channels))==272


def test_geometry_distinct_color_independent():
    w=ShapeColorWorld();w.set_scene([(s,4) for s in range(4)])
    values=np.asarray(w.vision()['values']).reshape(4,16,4)
    for a in range(4):
        for b in range(a):assert not np.allclose(values[a,:,0],values[b,:,0])
    w.set_scene([(s,0) for s in range(4)])
    colored=np.asarray(w.vision()['values']).reshape(4,16,4)
    assert np.allclose(colored[:,:,0],values[:,:,0])
    assert not np.allclose(colored[:,:,1:],values[:,:,1:])


def test_pointer_mechanics_and_teacher_separate():
    p=Pointer(-.8,.6);target=np.array([.6,-.5])
    for _ in range(40):p.step(p.teacher_action(target))
    assert np.linalg.norm(target-[p.x,p.y])<.15
    with pytest.raises(ValueError):p.step([float('nan'),0])


def test_adapter_no_question_parameter_raw_values_restore(tmp_path):
    import torch
    layout=ActivityLayout([17])
    obs={'nodes':[{'channel':17,'activation':.7,'inhibition':.3,'direct':.8,'associative':.2}]}
    assert np.allclose(layout.frame(obs),[.7,.3,.8,.2])
    model=ActivityController(4,2,regression=True)
    x=np.array([[layout.frame(obs)]*4])
    expected=model.predict(x)
    model.save(tmp_path/'adapter',[17]);restored,_=ActivityController.restore(tmp_path/'adapter')
    assert np.allclose(restored.predict(x),expected)
    with pytest.raises(TypeError):model.predict(x,target=[1,2])


def test_imitation_distinct_ports_and_restore():
    from lab.tools.imitation_world import ImitationWorld
    w=ImitationWorld();w.teacher=Pointer(.7,-.4,.2,-.3)
    assert not set(w.channels[256:272]) & set(w.channels[272:])
    before=w.stimulus(w.observe()).to_dict()
    after=ImitationWorld.restore(w.state()).stimulus(w.observe()).to_dict()
    assert before==after
    own=dict(zip(w.channels[256:272],w.observe()['values'][256:272]))
    w.teacher=Pointer(-.2,.3)
    assert dict(zip(w.channels[256:272],w.observe()['values'][256:272]))==own


def test_reader_explicit_exclusion_not_silent_unknowns():
    n={'channel':17,'activation':1.,'inhibition':0.,'direct':.2,'associative':0.}
    with pytest.raises(ValueError):ActivityLayout([18]).frame({'nodes':[n]})
    assert np.all(ActivityLayout([18],excluded_channels=[17]).frame({'nodes':[n]})==0)
