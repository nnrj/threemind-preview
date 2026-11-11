import numpy as np
from lab.tools.whole_scene_classroom import WholeSceneClassroom, sensory_replay
from lab.tools.shape_color_world import Pointer, POSITIONS


def test_true_self_vision_and_versioned_restore():
    world=WholeSceneClassroom()
    a=world.observe(); world.pointer=Pointer(.48,-.38)
    b=world.observe()
    assert np.any(np.array(a['values'][:world.vision_width])!=b['values'][:world.vision_width])
    restored=WholeSceneClassroom.restore(world.state())
    assert world.stimulus(b)==restored.stimulus(restored.observe())
    world.visible_self=False; c=world.observe();world.pointer=Pointer(-.5,.3)
    assert c['values'][:world.vision_width]==world.observe()['values'][:world.vision_width]


def test_unified_eye_has_no_target_crop_or_teacher_coordinates():
    world=WholeSceneClassroom()
    a=world.observe(); stimulus=world.stimulus(a)
    a.update(items=['different observer labels'],positions=['unused'],teacher_marker=['answer'])
    assert world.stimulus(a)==stimulus
    before=world.observe();world.marker=(.5,-.5);after=world.observe()
    assert before['values'][world.vision_width:]==after['values'][world.vision_width:]
    assert before['values'][:world.vision_width]!=after['values'][:world.vision_width]
    world.set_scene([(0,0),(2,1)],positions=[(-.4,.2),(.3,-.1)])
    assert len(world.observe()['values'])==len(world.channels)


def test_contact_is_actual_reaction_and_replay_covers_all_body_feedback():
    world=WholeSceneClassroom(); rest=world.observe()
    world.pointer=Pointer(.99,0.,1.,0.);world.advance_physics((1.,0.))
    move=world.observe()
    assert world.contact_force[0]<0 and world.pointer.x==1.
    frozen=sensory_replay(move,rest,vision=False,body=False)
    assert world.stimulus(frozen)==world.stimulus(rest)
    vision=sensory_replay(move,rest,body=False)
    assert vision['values'][world.vision_width:]==rest['values'][world.vision_width:]


def test_camera_coordinate_roundtrip():
    world=WholeSceneClassroom()
    for column,row in ((2,4),(8,8),(12,11)):
        point=world.ground_point(column,row)
        assert np.allclose(world.project(point),[column,row])


def test_teacher_cue_is_optically_visible_at_every_teaching_position():
    world=WholeSceneClassroom();world.marker=None
    baseline=world.vision()['values']
    for position in POSITIONS:
        world.marker=list(position)
        assert world.vision()['values']!=baseline
    restored=WholeSceneClassroom.restore(world.state())
    assert restored.teacher_radius_m==.12
    old=world.state();old.pop('teacher_radius_m');old['marker']=None
    assert WholeSceneClassroom.restore(old).teacher_radius_m==.065
