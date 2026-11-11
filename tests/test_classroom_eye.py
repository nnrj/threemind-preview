import numpy as np
from lab.tools.classroom_eye import DetailedClassroom
from lab.tools.grounded_classroom import GroundedClassroom
from lab.tools.shape_color_world import POSITIONS, Pointer


def test_legacy_equivalence_and_preserved_physical_ports():
    a,b=GroundedClassroom(),DetailedClassroom(resolution=4)
    for w in (a,b): w.set_scene([(3,0),(1,2),(2,3),(0,1)],5); w.marker=[.55,-.55]
    assert a.stimulus(a.observe()) == b.stimulus(b.observe())
    c=DetailedClassroom(resolution=6)
    assert c.channels[-36:]==a.channels[-36:]
    assert len(c.channels)==16*36+36 and len(set(c.channels))==len(c.channels)


def test_resolved_eye_restores_and_observer_labels_do_not_change_stimuli():
    a=DetailedClassroom(resolution=6); a.advance_physics((.4,-.7))
    b=DetailedClassroom.restore(a.state())
    assert a.stimulus(a.observe())==b.stimulus(b.observe())
    row=a.observe(); before=a.stimulus(row)
    row.update(items=['unrelated labels'],physical_background={'answer':'anything'})
    assert a.stimulus(row)==before
    assert len(a.observe(motor_only=True)['values'])==len(a.channels)
    assert np.all(np.array(a.observe(motor_only=True)['values'][:a.vision_width])==0)


def test_higher_resolution_does_not_multiply_angular_gain():
    for n in (4,6,8):
        w=DetailedClassroom(resolution=n); row=w.observe()
        assert np.isclose(row['visual_gain_per_channel']*w.vision_width,.03*256)
        assert len(row['values'])==len(w.channels)


def test_executor_reaches_its_selected_endpoint_in_the_physical_world():
    # Apparatus acceptance, not evidence that Core selects correctly.
    w=DetailedClassroom()
    for start in ((-.8,-.8),(-.8,.8),(.8,-.8),(.8,.8),(0.,0.)):
        for endpoint in POSITIONS:
            w.pointer=Pointer(*start)
            for _ in range(40):w.advance_physics(w.pointer.teacher_action(endpoint))
            assert np.linalg.norm(np.array(endpoint)-[w.pointer.x,w.pointer.y])<=.15
