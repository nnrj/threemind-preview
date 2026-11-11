"""Calibrate reported direction against known physical arrangements, not a Core rule."""
import gzip
import json
import math

import numpy as np
import pytest

from lab.tools.ocean_contact import ContactOcean
from lab.tools.ocean_process import food_heading


@pytest.mark.parametrize('angle', [0.0, math.pi / 2])
def test_recorded_direction_uses_body_frame_and_water_relative_speed(tmp_path, angle):
    ocean = ContactOcean({'schema': 'threemind.ocean/3', 'founders': 1,
        'nutrient_initial': 0, 'founder_variation': 0, 'reproduction': False,
        'side_m': 1.2}, backend='reference')
    body = ocean.bodies[0]
    body.position = [.5, .5]
    body.angle = angle
    forward = np.array([math.cos(angle), math.sin(angle)])
    ocean.food = np.array([np.asarray(body.position) + .04 * forward])
    flow, _ = ocean.environment(body.position)
    body.velocity = list(flow + .006 * forward)
    _, raw = ocean.senses(0)
    path = tmp_path / 'inputs.jsonl.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as stream:
        stream.write(json.dumps({'inputs': [{'individual': 0, 'raw': raw, 'action': [.5, 0, 0]}]}) + '\n')
    result = food_heading(path, {0: 'test'})['test']
    assert result['gradient_samples'] == 1
    assert result['command_alignment'] == pytest.approx(1)
    assert result['toward_command'] == pytest.approx(.5)
    assert result['toward_velocity_m_s'] == pytest.approx(.006)
