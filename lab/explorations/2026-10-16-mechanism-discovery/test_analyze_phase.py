import analyze_phase as a
import pytest


def test_same_history_control_subtracted_before_pairing_and_missing_pairs_rejected():
    rows=[{'case':{'origin':'o','history':h},'branch':{'cue':'p99-d2','arm':'normalized'},
           'response_110ms':v,'baseline_first':b} for h,v,b in [(0,10,7),(1,20,19)]]
    assert a.corrected_contrasts(rows)[('o','p99-d2','normalized')]==1
    with pytest.raises(ValueError):a.corrected_contrasts(rows[:1])
    with pytest.raises(ValueError):a.corrected_contrasts(rows+rows)
