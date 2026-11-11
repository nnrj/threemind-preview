import analyze_timing as a
import pytest


def test_baselines_are_observation_time_specific_and_precede_pairing():
    rows=[{'case':{'origin':'o','history':h},'branch':{'cue':'XY-1','arm':'normalized'},
           'response_second_arrival':v,'baseline_second':b} for h,v,b in [(0,10,7),(1,20,19)]]
    assert a.corrected_contrasts(rows)[('o','XY-1','normalized')]==1
    with pytest.raises(ValueError):a.corrected_contrasts(rows[:1])
    with pytest.raises(ValueError):a.corrected_contrasts(rows+rows)
