import copy

import numpy as np
import pytest

from lab.tools.sensory_calibration import SensoryResponseLibrary, matched_frames, paired_visual, process_vector
from threemind_core import Stimulus


def test_dose_interventions_preserve_amount_and_separate_modalities():
    original = [{"stimulus": Stimulus(0, ((1, 0.6), (2, 0.3)), 0.5)}]
    frozen = copy.deepcopy(original)
    repeated = matched_frames(original, 5, repetitions=5)
    combined = paired_visual(repeated, Stimulus(0, ((9, 0.5),(10,0.5),(11,0.5),(12,0.5))), 10)
    assert [r["stimulus"].time_us for r in combined] == [0, 20000, 40000, 60000, 80000]
    assert sum(v for r in combined for c,v in r["stimulus"].channels if c>=9) == pytest.approx(10)
    assert sum(v for r in repeated for _, v in r["stimulus"].channels) == pytest.approx(5)
    assert all(r["stimulus"].intensity == 0.5 for r in combined)
    assert original == frozen
    collapsed = matched_frames(repeated, 5, collapse=True)
    assert len(collapsed) == 5
    assert all(r['stimulus'].time_us==0 for r in collapsed)
    assert sum(v for r in collapsed for _,v in r["stimulus"].channels) == pytest.approx(5)
    with pytest.raises(ValueError, match="collision"):
        paired_visual(repeated, Stimulus(0, ((1, 0.5),)), 10)


def test_brief_response_is_integrated_without_stability_gate():
    process = {"start_us": "0", "end_us": "100", "trajectory": [
        {"time_us": str(t), "nodes": [{"channel": 1, "activation": a}]} for t, a in [(0, 0), (10, 1), (20, 0), (100, 0)]]}
    before = copy.deepcopy(process)
    assert process_vector(process, (1,))[0] == pytest.approx(0.1)
    assert process_vector(process, (1,), start_us=0, end_us=20)[0] == pytest.approx(0.5)
    assert process == before


def test_calibrated_physical_library_keeps_zero_unknown_and_observation_pure():
    library = SensoryResponseLibrary((1, 2), np.eye(2))
    assert library.read([0, 0])["prediction"] is None
    assert library.read([0.02, 0])["prediction"] == 0
    assert library.read([0, 2])["prediction"] == 1
    assert library.read([1, 1])["prediction"] is None


def test_oscillator_follows_mass_and_stiffness_without_name_input():
    import math

    from lab.tools.oscillator_sensor import OscillatorSensor
    sensor=OscillatorSensor(17)
    mass=0.1
    observed=sensor.sample(mass,(2*math.pi*440)**2*mass)
    assert sensor.bands_hz[int(np.argmax(observed['spectral_fractions']))]==440
    lower=sensor.sample(mass*4,(2*math.pi*440)**2*mass)
    assert sensor.bands_hz[int(np.argmax(lower['spectral_fractions']))]==220
    assert sum(v for _,v in sensor.frame(observed).channels)==pytest.approx(1)
