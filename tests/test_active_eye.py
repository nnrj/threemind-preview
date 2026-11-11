import numpy as np
import pytest
from lab.tools.active_eye import ActiveEyeClassroom,EyeConfig,scan_angle
from lab.tools.foveal_choice import FovealChoice
from lab.tools.foveal_sequence import FovealSequence


def test_fixed_receptors_moving_eye_and_complete_restore():
    w=ActiveEyeClassroom();ports=w.channels;before=w.observe()
    for _ in range(8):w.advance_physics(eye_action=(.5,-.3))
    after=w.observe();r=ActiveEyeClassroom.restore(w.state())
    assert len(ports)==314 and w.channels==ports
    assert before['values'][:w.vision_width]!=after['values'][:w.vision_width]
    assert w.stimulus(after)==r.stimulus(r.observe())
    w.advance_physics((.2,-.1),eye_action=(-.4,.7));r.advance_physics((.2,-.1),eye_action=(-.4,.7))
    assert w.state()==r.state()


def test_metadata_cannot_change_input_and_eye_feedback_is_measured():
    w=ActiveEyeClassroom();row=w.observe();stim=w.stimulus(row)
    row.update(items=['answer'],positions=['target'],teacher_marker=['hidden'],eye_angle_rad=[9,9])
    assert w.stimulus(row)==stim
    w.advance_physics(eye_action=(1,0));moved=w.observe()
    assert any(moved['values'][-10:]) and moved['physical_background']
    assert len(set(w.channels))==len(w.channels)
    with pytest.raises(ValueError):w.advance_physics(eye_action=(float('nan'),0))


def test_ray_geometry_roundtrip_and_limits():
    w=ActiveEyeClassroom()
    for _ in range(30):w.advance_physics(eye_action=(1,-1))
    assert max(abs(w.eye_angle))<=w.eye_config.angle_limit_rad
    for i in (0,17,35,42,67):assert np.allclose(w.project(w.ground_point(i)),w.retinal_centers[i])
    assert np.allclose(scan_angle(2),scan_angle(2))
    with pytest.raises(ValueError):EyeConfig(center_half_width=.3)


def test_sparse_reader_preserves_inputs_and_restores(tmp_path):
    w=ActiveEyeClassroom();m=FovealChoice(w.channels,w.channels[:w.vision_width],w.retinal_centers,w.retinal_widths,seed=9)
    x=np.random.default_rng(5).uniform(0,.1,(2,2,m.layout.width)).astype('float32');old=x.copy()
    m.fit(x,[5,23],steps=2,batch_size=1)
    assert np.array_equal(x,old) and m.predict(x).shape==(2,68)
    assert m.select(np.zeros_like(x[0])) is None
    m.save(tmp_path/'head');r,_=FovealChoice.restore(tmp_path/'head')
    assert np.allclose(m.predict(x),r.predict(x))


def test_motor_execution_uses_acquisition_geometry_and_no_answer():
    w=ActiveEyeClassroom();row=w.observe();r=17;direction=w.selected_ray(r,row)
    for _ in range(4):w.advance_physics(eye_action=(1,0))
    assert np.array_equal(direction,w.selected_ray(r,row))
    a=w.execute_eye_selection(r,row);h=w.execute_hand_selection(r,row)
    row.update(items=['different answer'],positions=[[99,99]],teacher_marker=[99,99])
    assert np.array_equal(a,w.execute_eye_selection(r,row))
    assert np.array_equal(h,w.execute_hand_selection(r,row))
    assert not w.execute_eye_selection(None,row).any() and not w.execute_hand_selection(None,row).any()


def test_eye_can_hold_center_with_finite_retinal_resolution():
    w=ActiveEyeClassroom();row=w.observe()
    for r in (14,15,20,21):assert np.allclose(w.execute_eye_selection(r,row),0.)
    assert np.linalg.norm(w.execute_eye_selection(0,row))>0


def test_complete_temporal_reader_has_no_32_sample_truncation(tmp_path):
    w=ActiveEyeClassroom();m=FovealSequence(w.channels,w.channels[:w.vision_width],w.retinal_centers,w.retinal_widths,seed=9)
    x=np.zeros((1,60,m.layout.width),dtype='float32');x[0,3,0]=.3;x[0,37,1]=.2;old=x.copy()
    m.fit(x,[5],steps=1,batch_size=1)
    assert np.array_equal(x,old) and m.predict(x).shape==(1,68)
    m.save(tmp_path/'sequence');r,_=FovealSequence.restore(tmp_path/'sequence')
    assert np.allclose(m.predict(x),r.predict(x))
    with pytest.raises(ValueError):r.predict(np.zeros((1,65,m.layout.width),dtype='float32'))
