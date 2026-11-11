"""Synthetic engineering sources distinct from the scientific cases."""

import copy
import math
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from assay import Assay, CURVES, cases
from analyze import expression, tail_weight


def equivalent(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for key in a:
            equivalent(a[key], b[key])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            equivalent(x, y)
    elif isinstance(a, float):
        assert a == pytest.approx(b, rel=3e-11, abs=3e-13)
    else:
        assert a == b


def test_case_independence_and_equal_strong_drive():
    rows = cases()
    assert len(rows) == 4608 and len({r["key"] for r in rows}) == 4608
    assert {r["seed"] for r in rows}.isdisjoint(r["seed"] for r in cases(48, True))
    assert len({r["seed"] for r in cases(48, True)}) == 48
    from assay import DOSES

    assert DOSES["high-dose"] == 2 * DOSES["strong"]


@pytest.mark.parametrize("curve", CURVES)
@pytest.mark.parametrize("course", ("spaced", "strong", "novelty"))
def test_temporal_instrument_and_complete_resume(curve, course):
    case = copy.deepcopy(
        next(c for c in cases() if c["curve"] == curve and c["course"] == course and c["delay"] == 300 and c["cue"])
    )
    case.update(seed=98765031, key="engineering")
    ref, rust = Assay(case, "reference"), Assay(case, "native")
    a, b = ref.teach(), rust.teach()
    equivalent(a, b)
    left, right = ref.state(), rust.state()
    equivalent(left, right)
    ref = Assay.restore(left, "reference")
    rust = Assay.restore(right, "native")
    a, b = ref.probe(), rust.probe()
    equivalent(a, b)
    assert len(a["response"]["frames"]) == 20
    assert all(set(f["out0"]) == {"activation", "inhibition", "direct", "associative"} for f in a["response"]["frames"])
    assert ref.core.time_us == ref.teaching_end + 301_000_000
    assert Assay.restore(rust.state()).state() == rust.state()


def test_scoring_direction_absence_and_tail():
    assert expression([1.0, 0.0], [0.2, 0.0])["passed"]
    assert not expression([1.0, 0.0], [-0.2, 0.0])["passed"]
    assert not expression([0.0, 0.0], [0.2, 0.0])["passed"]
    for c in CURVES:
        v = tail_weight(dict(weight=0.5, decay_age=10.0, half_life=30.0), c)
        assert math.isfinite(v) and 0 <= v <= 0.5
