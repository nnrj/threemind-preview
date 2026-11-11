"""Validate subtraction, opposite-history pairing and nested denominators."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from analyze_fusion import paired


def test_baseline_is_subtracted_before_history_contrast():
    rows=[]
    for h,baseline in [(0,10.),(1,-20.)]:
        for cue,value in [('none',baseline),('X',baseline+(2 if h==0 else -4))]:
            rows.append({'case':{'origin':'o0','history':h},'branch':{'cue':cue,'arm':'normalized'},'value':value})
    result=paired(rows,'value')
    assert result[('o0','X','normalized')]==3.
    assert result[('o0','none','normalized')]==0.
    with pytest.raises(ValueError,match='duplicate history'):
        paired(rows+[rows[-1]],'value')
    with pytest.raises(ValueError,match='missing opposite history'):
        paired(rows[:-1],'value')
