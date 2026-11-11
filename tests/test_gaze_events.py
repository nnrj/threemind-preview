import pytest
import numpy as np
from lab.tools.gaze_events import gaze_events
from lab.tools.eye_hand_world import motor_metrics


def test_brief_crossing_is_retained_and_not_called_slow_fixation():
    rows = [{'observation': {'eye_angle_rad': [angle, 0], 'eye_velocity_rad_s': [speed, 0]}}
            for angle, speed in [(.2, .3), (0, .3), (.2, .3), (0, 0), (0, 0)]]
    result = gaze_events(rows, [[0, 0]]*5)
    phase = result['phases'][0]
    assert phase['clear_center']['first_s'] == .05
    assert phase['clear_center']['fraction'] == .6
    assert phase['aligned_slow']['first_s'] == pytest.approx(.15)
    assert phase['aligned_slow']['longest_s'] == .1


def test_new_target_restarts_measurement_and_absence_remains_missing():
    rows = [{'observation': {'eye_angle_rad': [0, 0], 'eye_velocity_rad_s': [0, 0]}}]*6
    result = gaze_events(rows, [[0, 0]]*3+[[.2, 0]]*3)
    assert len(result['phases']) == 2
    assert result['phases'][0]['clear_center']['inside_at_start']
    assert result['phases'][1]['clear_center']['first_s'] is None
    assert result['phases'][1]['clear_center']['fraction'] == 0


def test_event_scoring_agrees_with_registered_process_metric():
    rng = np.random.default_rng(5)
    rows = [{'observation': {'eye_angle_rad': eye.tolist(), 'eye_velocity_rad_s': vel.tolist(),
                            'pointer': {'x': 0, 'y': 0}}}
            for eye, vel in zip(rng.uniform(-.2, .2, (100, 2)), rng.uniform(-.08, .08, (100, 2)))]
    targets = [[.05, 0]]*100
    events = gaze_events(rows, targets)['phases'][0]
    original = motor_metrics(rows, targets, [[0, 0]]*100)
    assert events['clear_center']['fraction'] == original['eye_center_fraction']
    assert events['aligned_slow']['fraction'] == original['eye_stable_fraction']
