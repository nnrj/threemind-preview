import copy
import pytest
from assay import Assay, cases, CURVES


def test_disjoint_sources_and_frozen_cases():
    rows = cases()
    assert len(rows) == 1280 and len({r["key"] for r in rows}) == 1280
    assert {r["seed"] for r in rows} == set(range(261111810, 261111818))
    assert len({r["origin"] for r in rows}) == 8
    assert all(r["delay"] in ((1, 30) if r["course"] == "weak" else (1, 300)) for r in rows)


@pytest.mark.parametrize("rule", CURVES)
def test_local_continuity_and_all_fields(rule):
    c = copy.deepcopy(cases()[0])
    c.update(seed=98765420, curve=rule)
    x = Assay(c)
    x.teach()
    s = x.state()
    y = Assay.restore(s)
    xx = x.probe()
    yy = y.probe()
    assert xx == yy and x.state() == y.state()
    assert len(xx["response"]["frames"]) == 20
    assert set(xx["response"]["frames"][0]["out0"]) == {"activation", "inhibition", "direct", "associative"}
