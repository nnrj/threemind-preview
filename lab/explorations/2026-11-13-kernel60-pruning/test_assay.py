"""Instrument calibration only; these engineering seeds are not research origins."""
import copy
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from assay import Assay,cases
from analyze import comparison


def equal(a,b):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a: equal(a[k],b[k])
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b): equal(x,y)
    elif isinstance(a,float): assert a==pytest.approx(b,rel=3e-11,abs=3e-13)
    else: assert a==b


def test_frozen_case_pairing():
    rows=cases();assert len(rows)==640 and len({c["key"] for c in rows})==640
    assert {c["seed"] for c in rows}==set(range(261113100,261113108))
    for c in rows:
        other=next(x for x in rows if all(x[k]==c[k] for k in ("origin","course","delay","history","cue")) and x["cutoff"]!=c["cutoff"])
        assert other["profile"]==c["profile"]


@pytest.mark.parametrize("cutoff",(.008,.018))
@pytest.mark.parametrize("course",("weak","massed","spaced","strong","novelty"))
def test_native_reference_and_whole_resume(cutoff,course):
    c=copy.deepcopy(next(x for x in cases() if x["cutoff"]==cutoff and x["course"]==course and x["delay"]>1 and x["cue"]))
    c.update(seed=98765060,key="engineering")
    a,b=Assay(c,"reference"),Assay(c,"native")
    equal(a.teach(),b.teach());equal(a.state(),b.state())
    before=b.state();b.graph();b.core.observation_nodes();assert b.state()==before
    a=Assay.restore(a.state(),"reference");b=Assay.restore(b.state(),"native")
    equal(a.probe(),b.probe());equal(a.state(),b.state())
    assert Assay.restore(b.state()).state()==b.state()


def test_comparison_rejects_loss_and_reversal():
    assert comparison([.1,.2],[.1,.2])["passed"]
    assert not comparison([.1,.2],[0.,0.])["passed"]
    assert not comparison([.1,.2],[-.1,-.2])["passed"]
    assert comparison([0.,0.],[0.,0.])["passed"]
